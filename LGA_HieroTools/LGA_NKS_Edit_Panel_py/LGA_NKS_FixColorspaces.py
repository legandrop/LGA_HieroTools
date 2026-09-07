"""
____________________________________________________________________

  LGA_NKS_FixColorspaces v1.22 | Lega

  Corrige el color transform de los clips del timeline activo.

  Si el proyecto tiene color management configurado en PipeSync (Project
  Settings tab, clave `color_management` del envelope - ver
  LGA_NKS_ColorManagement_Config) Y esta habilitado, resuelve el token que le
  corresponde a cada track de plate/publish contra el config OCIO activo del
  clip y le aplica el resultado. Si el proyecto NO esta managed, o no hay
  secuencia activa, o no se puede resolver el proyecto, corre el camino
  VIEJO: recorre TODOS los clips del bin (project.clips()) y a los que
  tengan colorspace 'rec709' o 'gamma2.2' en el knob del Read les pone
  'Output - Rec.709'.

  Camino MANAGED (proyecto con color_management.enabled=true):
    1. Proyecto del timeline activo: primer clip con media de la secuencia
       activa, extract_project_name_from_path() y fallback a
       extract_project_name() (ver LGA_NKS_Flow_NamingUtils, mismo patron
       de llamada que LGA_NKS_Flow_CheckTimelineShots).
    2. Por cada VideoTrack de hiero.ui.activeSequence().videoTracks():
         - nombre termina en "plate" (case-insensitive)     -> token 'plates'
         - nombre esta en TASK_EXR_TRACKS (LGA_NKS_GetClip, hoy ["_comp_",
           "_roto_", "_cleanup_", "_cg_"], case-insensitive) -> token
           'exr_publish'
         - cualquier otro track (EditRef, EditRefClean, ...)  -> NO SE TOCA
    3. El colorspace vive en el CLIP del bin (trackItem.source()), no en el
       TrackItem. Un mismo clip visto bajo dos reglas distintas (por ejemplo
       aparece en un track de plate Y en uno de publish) queda en
       CONFLICTO y no se toca: primero se agrupan TODOS los clips por regla,
       recien despues se aplica, asi un clip con dos reglas distintas se
       detecta antes de tocar nada.
    4. El token se resuelve a un nombre real de colorspace con
       resolve_ocio_name(token, clip.getAvailableOcioColourTransforms()). Si
       no resuelve, el clip se reporta como 'sin transform disponible' y no
       se toca.
    5. Si clip.sourceMediaColourTransform() ya es ese nombre, se saltea (no
       se reescribe). Si no, se aplica con setSourceMediaColourTransform().
    6. Al final se imprime un resumen: corregidos, ya-estaban-bien,
       en-conflicto, sin-transform-disponible, con el nombre del clip y el
       track en cada caso.

  CONTRATO DE EJECUCION: el modulo NO ejecuta nada al importarse (sin
  side-effect de nivel de modulo) y expone main(). LGA_NKS_Edit_Panel.py
  carga el script con exec_module() y despues llama a module.main() si
  existe: si ademas quedara una llamada suelta a nivel de modulo, el
  trabajo correria DOS VECES. Por eso los imports de hiero.core/hiero.ui, y
  el de TASK_EXR_TRACKS (que a su vez importa hiero.core), estan DIFERIDOS
  adentro de las funciones que los usan: este archivo se puede importar en
  un proceso sin Nuke/Hiero sin que explote y sin que haga nada.

  v1.22: El camino managed se extrae a `run_if_color_managed()`, que ahora
         comparten el boton del Edit Panel y el Flow Pull -que lo dispara al
         terminar, porque cada bump de version cambia el clip a otra Version,
         que es otro Clip con su propio color transform-. NO abre grupo de undo:
         lo abre el llamador, que es la convencion del repo, y los dos llamadores
         ya vienen dentro de uno. `main()` pasa a delegar en ella y solo decide el
         fallback al camino viejo. `_volcar_log()` pasa a `volcar_log()`, publica,
         porque ahora la llama otro modulo. Sin cambios para el boton.
  v1.21: Dos huecos de robustez que salieron en la auditoria. El camino
         VIEJO ya no toca clips que pertenecen a un proyecto color managed:
         `hiero.core.projects()` devuelve todos los proyectos abiertos, asi
         que apretar el boton con un proyecto no managed activo le pisaba el
         colorspace al managed que estuviera abierto al lado. Y el camino
         MANAGED pasa a atrapar sus propias excepciones e informarlas por
         consola: antes cualquier fallo no contemplado se lo tragaba
         execute_external_script() del panel y el boton no hacia nada, sin
         aviso. No cae al camino viejo ante el error, a proposito.
  v1.20: Reescritura completa. Agrega el camino MANAGED (color management
         por proyecto via LGA_NKS_ColorManagement_Config + resolve_ocio_name)
         para proyectos con `color_management.enabled=true`; el camino viejo
         (rec709/gamma2.2 -> Output - Rec.709 sobre todos los clips del bin)
         se conserva intacto para el resto de los proyectos. Pasa a exponer
         main() y saca la llamada de nivel de modulo (antes corria por
         side-effect al importarse).
  v1.10: Detecta clips con colorspace "rec709" o "gamma2.2" y cambia su
         color transform a "Output - Rec.709" (busca en todos los clips del
         proyecto).
____________________________________________________________________

"""

import os
import sys
import traceback
from pathlib import Path

DEBUG = False

LOG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "logs",
    "DebugPy_LGA_NKS_FixColorspaces.log",
)

_LOG_LINES = []


def debug_print(*message):
    """Acumula para el .log y, si DEBUG, ademas escribe en la consola."""
    linea = " ".join(str(m) for m in message)
    _LOG_LINES.append(linea)
    if DEBUG:
        print(linea)


def volcar_log():
    """Escribe el log de la corrida, pisando el anterior. Nunca rompe la tool."""
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(_LOG_LINES) + "\n")
    except Exception:
        pass
    del _LOG_LINES[:]


# ============================
# Imports de modulos hermanos (Shared)
# ============================
#
# LGA_NKS_ColorManagement_Config y LGA_NKS_Flow_NamingUtils son PYTHON PURO
# (sin import de hiero/nuke a nivel de modulo), asi que se importan aca
# arriba sin romper la carga de este archivo fuera de Nuke.
#
# LGA_NKS_GetClip, en cambio, hace `import hiero.core` a nivel de modulo: si
# se importara aca arriba, cargar ESTE archivo fuera de Nuke fallaria por
# transitividad aunque este archivo no toque hiero directo. Por eso
# TASK_EXR_TRACKS se importa RECIEN adentro de _get_task_exr_tracks(), que
# solo se llama desde el camino managed (dentro de Hiero).

_SHARED_DIR = Path(__file__).resolve().parent.parent / "LGA_NKS_Shared"
if _SHARED_DIR.exists() and str(_SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(_SHARED_DIR))

from LGA_NKS_ColorManagement_Config import (  # noqa: E402
    get_color_management,
    is_color_managed,
    resolve_ocio_name,
)
from LGA_NKS_Flow_NamingUtils import (  # noqa: E402
    clean_base_name,
    extract_project_name,
    extract_project_name_from_path,
)


def _get_task_exr_tracks():
    """
    Import DIFERIDO de TASK_EXR_TRACKS.

    LGA_NKS_GetClip hace `import hiero.core` a nivel de modulo, asi que
    importarlo fuera de Nuke/Hiero explota. Se posterga hasta el momento en
    que hace falta de verdad: adentro del camino managed, que solo corre
    llamado desde el panel, adentro de Hiero.
    """
    from LGA_NKS_GetClip import TASK_EXR_TRACKS

    return TASK_EXR_TRACKS


# ============================
# Camino VIEJO (proyectos sin color management)
# ============================

COLORSPACE_INVALIDO = ("rec709", "gamma2.2")
COLORSPACE_CORRECTO = "Output - Rec.709"


def extraer_colorspace_desde_read(clip):
    """Intenta obtener el valor del knob 'colorspace' del nodo Read."""
    try:
        read_node = clip.readNode()
        if read_node and "colorspace" in read_node.knobs():
            return read_node["colorspace"].value()
    except Exception:
        pass
    return None


def _project_name_de_clip(clip):
    """
    Nombre canonico del proyecto al que pertenece un clip, sacado de la RUTA
    de su media (VFX-<PROYECTO>), no del nombre del .hrox.

    Devuelve "" si no se puede resolver.
    """
    try:
        media = clip.mediaSource()
        fileinfos = media.fileinfos() if media else None
        file_path = fileinfos[0].filename() if fileinfos else ""
    except Exception:
        return ""
    if not file_path:
        return ""
    return extract_project_name_from_path(file_path) or ""


def buscar_y_cambiar_clips_rec709_en_todos(proyecto, corregidos, saltados_managed):
    """Recorre todos los clips del proyecto y corrige los que tengan colorspace 'rec709' o 'gamma2.2'."""
    for clip in proyecto.clips():
        # 🔴 Un clip que pertenece a un proyecto CON color management NO se toca por este
        # camino, aunque el proyecto activo no sea el suyo.
        #
        # `hiero.core.projects()` devuelve TODOS los proyectos abiertos, y en Nuke Studio es
        # normal tener dos. Antes eso era inofensivo: todos recibian el mismo tratamiento.
        # Ahora no: apretar el boton con un proyecto NO managed activo barria tambien el bin
        # del managed que estuviera abierto al lado y le pisaria el colorspace de sus plates
        # con Output - Rec.709, sin aviso y sin pasar por la deteccion de conflictos, que
        # solo corre del lado managed. El filtro va por CLIP y no por proyecto porque el
        # nombre canonico sale de la ruta del media, no del nombre del .hrox.
        clip_project = _project_name_de_clip(clip)
        if clip_project and is_color_managed(clip_project):
            saltados_managed.add(clip_project)
            debug_print(
                "[legacy] {0} pertenece a {1}, que esta color managed: no se toca.".format(
                    clip.name(), clip_project
                )
            )
            continue

        colorspace = extraer_colorspace_desde_read(clip)
        if colorspace and colorspace.lower() in COLORSPACE_INVALIDO:
            try:
                clip.setSourceMediaColourTransform(COLORSPACE_CORRECTO)
                path = clip.mediaSource().firstpath()
                corregidos.append((clip.name(), path, colorspace))
                debug_print(
                    "[legacy] {0}: {1} -> {2}".format(
                        clip.name(), colorspace, COLORSPACE_CORRECTO
                    )
                )
            except Exception as e:
                print("Error al cambiar el colorspace de {0}: {1}".format(clip.name(), e))
                debug_print("[legacy][ERROR] {0}: {1}".format(clip.name(), e))


def corregir_clips_con_colorspace_rec709():
    """Camino viejo: recorre TODOS los clips del bin de cada proyecto abierto."""
    import hiero.core

    proyectos = hiero.core.projects()
    if not proyectos:
        print("No hay proyectos abiertos.")
        debug_print("[legacy] No hay proyectos abiertos.")
        return

    corregidos = []
    saltados_managed = set()

    for proyecto in proyectos:
        debug_print("[legacy] Explorando proyecto: {0}".format(proyecto.name()))
        buscar_y_cambiar_clips_rec709_en_todos(proyecto, corregidos, saltados_managed)

    if corregidos:
        print("Clips corregidos con nuevo colorspace:")
        for nombre, ruta, cs in corregidos:
            print(" - {0}: {1} -> {2} ({3})".format(nombre, cs, COLORSPACE_CORRECTO, ruta))
    else:
        print("No se encontraron clips con colorspace 'rec709' o 'gamma2.2'.")

    if saltados_managed:
        print(
            "Se saltearon los clips de estos proyectos, que tienen color management: {0}".format(
                ", ".join(sorted(saltados_managed))
            )
        )


# ============================
# Camino MANAGED (color management por proyecto)
# ============================


def _resolve_active_project_name(seq):
    """
    Nombre del proyecto del timeline activo: primer clip con media de la
    secuencia, resuelto con NamingUtils (ruta primero, filename despues).
    Mismo patron de llamada que LGA_NKS_Flow_CheckTimelineShots.

    Devuelve "" si no se pudo resolver (secuencia vacia, o ningun clip con
    media localizable).
    """
    import hiero.core

    for track in seq.videoTracks():
        for item in track:
            if isinstance(item, hiero.core.EffectTrackItem):
                continue
            try:
                source = item.source()
                media = source.mediaSource() if source else None
                fileinfos = media.fileinfos() if media else None
                file_path = fileinfos[0].filename() if fileinfos else ""
            except Exception:
                file_path = ""

            if not file_path:
                continue

            project_name = extract_project_name_from_path(file_path)
            if project_name:
                debug_print("[managed] Proyecto (desde ruta): {0}".format(project_name))
                return project_name

            base_name = clean_base_name(os.path.basename(file_path))
            project_name = extract_project_name(base_name)
            if project_name:
                debug_print(
                    "[managed] Proyecto (fallback filename): {0}".format(project_name)
                )
                return project_name

    return ""


def _clasificar_track(track_name, exr_tracks):
    """
    Devuelve el token ('plates' | 'exr_publish') que le corresponde a un
    track por su nombre, o None si el track no se toca (EditRef y similares).
    """
    nombre = (track_name or "").strip()
    if not nombre:
        return None
    if nombre.lower().endswith("plate"):
        return "plates"
    if nombre.lower() in [t.lower() for t in exr_tracks]:
        return "exr_publish"
    return None


def _clip_key(clip):
    """
    Clave estable para agrupar el MISMO clip visto desde distintos
    TrackItems.

    `id(clip)` no sirve: cada trackItem.source() puede devolver un wrapper de
    Python nuevo para el mismo Clip nativo (ver el helper _guid() de
    LGA_NKS_ApplyAMF.py, que existe por el mismo motivo: "comparar identidad
    entre dos barridos distintos"). guid() es estable entre llamadas; si no
    esta disponible, se cae a id() como ultimo recurso (en el peor caso, dos
    referencias al mismo clip nativo se tratan como clips distintos y no
    detectan un conflicto real, pero no rompe).
    """
    try:
        return clip.guid()
    except Exception:
        return id(clip)


def _nombre_clip_seguro(clip):
    try:
        return clip.name()
    except Exception:
        return "<clip>"


def _clips_por_regla(seq, exr_tracks):
    """
    Agrupa, por token, los clips que le corresponden a cada regla.

    Devuelve (asignaciones, conflictos):
      - asignaciones: {clip_key: (token, clip, track_name)} para clips con
        UNA sola regla.
      - conflictos: [(clip, [(token, track_name), ...])] para clips que
        matchean mas de una regla.

    Se agrupa TODO antes de aplicar nada, porque el colorspace vive en el
    Clip del bin y no en el TrackItem: si un mismo clip aparece bajo dos
    tracks con reglas distintas, aplicar la primera que se encuentre lo
    dejaria con el token equivocado segun el orden de iteracion.
    """
    import hiero.core

    por_clip = {}  # clip_key -> {"clip": clip, "reglas": {(token, track_name), ...}}

    for track in seq.videoTracks():
        token = _clasificar_track(track.name(), exr_tracks)
        if not token:
            continue

        for item in track:
            if isinstance(item, hiero.core.EffectTrackItem):
                continue
            try:
                clip = item.source()
            except Exception:
                clip = None
            if clip is None:
                continue

            key = _clip_key(clip)
            entry = por_clip.setdefault(key, {"clip": clip, "reglas": set()})
            entry["reglas"].add((token, track.name()))

    asignaciones = {}
    conflictos = []
    for key, entry in por_clip.items():
        tokens = set(token for token, _track_name in entry["reglas"])
        if len(tokens) > 1:
            conflictos.append((entry["clip"], sorted(entry["reglas"])))
            continue
        token, track_name = next(iter(entry["reglas"]))
        asignaciones[key] = (token, entry["clip"], track_name)

    return asignaciones, conflictos


def corregir_clips_con_color_management(project_name, cm_config, seq):
    """
    Camino managed: aplica el token que le corresponde a cada track de
    plate/publish, resolviendolo contra el config OCIO activo del clip.
    """
    exr_tracks = _get_task_exr_tracks()
    asignaciones, conflictos = _clips_por_regla(seq, exr_tracks)

    corregidos = []
    ya_bien = []
    sin_transform = []

    for token, clip, track_name in asignaciones.values():
        wanted_token = cm_config.get(token)
        if not wanted_token:
            # El proyecto es managed pero no declaro token para esta regla
            # (ej. exr_publish vacio): no hay nada que resolver para este clip.
            debug_print(
                "[managed] {0} ({1}): sin token configurado para '{2}', se ignora".format(
                    _nombre_clip_seguro(clip), track_name, token
                )
            )
            continue

        try:
            disponibles = clip.getAvailableOcioColourTransforms()
        except Exception as e:
            sin_transform.append((_nombre_clip_seguro(clip), track_name, wanted_token))
            debug_print(
                "[managed][ERROR] {0}: no se pudieron leer los transforms disponibles ({1})".format(
                    _nombre_clip_seguro(clip), e
                )
            )
            continue

        nombre_real = resolve_ocio_name(wanted_token, disponibles)
        if not nombre_real:
            sin_transform.append((_nombre_clip_seguro(clip), track_name, wanted_token))
            debug_print(
                "[managed] {0} ({1}): '{2}' no resolvio contra el config OCIO activo".format(
                    _nombre_clip_seguro(clip), track_name, wanted_token
                )
            )
            continue

        try:
            actual = clip.sourceMediaColourTransform()
        except Exception:
            actual = None

        if actual == nombre_real:
            ya_bien.append((_nombre_clip_seguro(clip), track_name, nombre_real))
            continue

        try:
            clip.setSourceMediaColourTransform(nombre_real)
            corregidos.append((_nombre_clip_seguro(clip), track_name, actual, nombre_real))
            debug_print(
                "[managed] {0} ({1}): {2} -> {3}".format(
                    _nombre_clip_seguro(clip), track_name, actual, nombre_real
                )
            )
        except Exception as e:
            sin_transform.append((_nombre_clip_seguro(clip), track_name, wanted_token))
            debug_print(
                "[managed][ERROR] No se pudo setear {0}: {1}".format(
                    _nombre_clip_seguro(clip), e
                )
            )

    _imprimir_resumen_managed(project_name, corregidos, ya_bien, conflictos, sin_transform)


def _imprimir_resumen_managed(project_name, corregidos, ya_bien, conflictos, sin_transform):
    print(
        "Color management ({0}): {1} corregidos, {2} ya estaban bien, {3} en conflicto, "
        "{4} sin transform disponible.".format(
            project_name, len(corregidos), len(ya_bien), len(conflictos), len(sin_transform)
        )
    )

    if corregidos:
        print("Corregidos:")
        for nombre, track_name, antes, despues in corregidos:
            print(" - {0} [{1}]: {2} -> {3}".format(nombre, track_name, antes, despues))

    if conflictos:
        print("En conflicto (no tocados):")
        for clip, reglas in conflictos:
            nombre = _nombre_clip_seguro(clip)
            tracks = ", ".join("{0}:{1}".format(token, track_name) for token, track_name in reglas)
            print(" - {0}: aparece bajo reglas distintas ({1})".format(nombre, tracks))

    if sin_transform:
        print("Sin transform disponible (no tocados):")
        for nombre, track_name, token in sin_transform:
            print(" - {0} [{1}]: token '{2}' no resolvio".format(nombre, track_name, token))


# ============================
# Entry point
# ============================


def run_if_color_managed(seq=None):
    """
    Corre SOLO el camino managed sobre la secuencia dada (por defecto, la activa).

    Es el punto de entrada que comparten el boton del Edit Panel y el Flow Pull,
    que lo dispara al terminar: un bump de version cambia el clip a otra `Version`,
    que en Hiero es OTRO Clip con su propio color transform, asi que despues de un
    pull los clips recien versionados vuelven al espacio que traiga el archivo.

    Si el proyecto NO esta color managed no hace NADA: no cae al camino viejo. Esa
    decision es del llamador -`main()` la toma, el pull no-, porque correr el
    barrido de rec709 sobre todos los clips del bin como efecto secundario de un
    pull seria una sorpresa desagradable.

    🔴 NO abre grupo de undo: lo abre el LLAMADOR, que es la convencion del repo
    ("El undo lo maneja el propio script, para no anidar bloques",
    LGA_NKS_Edit_Panel.py). Los dos llamadores ya vienen dentro de uno: el boton por
    `fix_colorspaces()` del Edit Panel, y el pull por `run_FPT_pull()` /
    `run_FPT_pull_with_deselect()` del Flow Panel, que envuelven `FPT_Hiero()` en
    `project.beginUndo("Run External Script")`. Una version anterior de esto abria su
    propio `beginUndo` para el pull, creyendo que el pull no tenia: lo tiene, pero lo
    abre el panel, no el archivo del pull. Anidarlos fusiona los macros y el Ctrl+Z
    deja de comportarse como uno espera.

    Devuelve True si el proyecto estaba managed (haya corrido bien o haya fallado)
    y False si no lo estaba, para que el llamador decida que sigue.
    """
    import hiero.ui

    if seq is None:
        seq = hiero.ui.activeSequence()
    if seq is None:
        debug_print("[managed] No hay secuencia activa.")
        return False

    project_name = _resolve_active_project_name(seq)
    if not project_name or not is_color_managed(project_name):
        return False

    cm_config = get_color_management(project_name)
    debug_print(
        "[managed] project_name={0!r} managed=True cm_config={1!r}".format(
            project_name, cm_config
        )
    )

    # 🔴 El camino managed atrapa sus propias excepciones y NO cae al camino viejo.
    # El porque esta en el header: el panel se traga las excepciones y devuelve True
    # igual, asi que sin esto el boton no hace nada y nadie se entera; y correr el
    # barrido de rec709 sobre un proyecto managed es justo lo que hay que evitar.
    try:
        corregir_clips_con_color_management(project_name, cm_config, seq)
    except Exception as e:
        print(
            "Fix Colorspaces fallo en el proyecto color managed {0}: {1}".format(
                project_name, e
            )
        )
        print(
            "No se aplico ningun cambio. El detalle esta en "
            "logs/DebugPy_LGA_NKS_FixColorspaces.log"
        )
        debug_print("[managed][ERROR] {0}".format(traceback.format_exc()))
    return True


def main():
    """
    Punto de entrada que llama LGA_NKS_Edit_Panel.py via exec_module() +
    module.main(). Ver el CONTRATO DE EJECUCION en el header del modulo.

    Delega el camino managed en run_if_color_managed() -la misma funcion que
    dispara el Flow Pull al terminar- y decide el fallback: si el proyecto no
    esta color managed, corre el barrido viejo. Sin `undo_label` porque el panel
    ya envuelve la llamada en su propio `project.beginUndo("Fix Colorspaces")`.
    """
    try:
        if not run_if_color_managed():
            debug_print("[main] proyecto no managed, camino viejo")
            corregir_clips_con_colorspace_rec709()
    finally:
        volcar_log()


# Ejecucion desde el panel: LGA_NKS_Edit_Panel.py carga este script con
# exec_module() y llama a main() si existe (ver CONTRATO DE EJECUCION mas
# arriba). NO descomentar la siguiente linea: dejarla activa hace que el
# trabajo corra DOS VECES (una por el exec_module, otra por esta llamada).
# main()
