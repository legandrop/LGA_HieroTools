"""
____________________________________________________________________

  LGA_NKS_ShotNavigation v1.00 | Lega

  Lleva el timeline de Hiero/NKS hasta un shot pedido por nombre: busca el
  clip en los proyectos abiertos, cambia de secuencia con el switch del
  Projects Panel, selecciona el clip, marca In/Out (con el clip de EditRef
  si lo hay), mueve el playhead y hace Zoom to Fit.

  Existe para que una app de afuera (PipeSync, via LGA_NKS_RemoteNav) pueda
  decir "llevame a este shot" sin saber nada del timeline. La navegacion del
  Flow Pull (navigate_to_pull_result) exige la task y un objeto Sequence ya
  resuelto; esta arranca solo con proyecto y shot.

  Si el proyecto no esta abierto, busca su .hrox en el root del contexto y
  lo abre con la misma apertura del Projects Panel (congelado de repintado,
  post-apertura y switch), y recien despues navega.

  Nunca muestra carteles en NKS: devuelve un resultado explicito (dict con
  "status" y "detail") y el que llamo decide como avisar.

  v1.00: Primera version.
____________________________________________________________________
"""

import os
import re
import sys
import time
import importlib
import traceback

import hiero.core
import hiero.ui

from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtCore
from LGA_NKS_Shared.LGA_NKS_Flow_NamingUtils import (
    clean_base_name,
    extract_project_name_from_path,
    extract_shot_code,
    extract_task_name,
    normalize_task_name,
)
from LGA_NKS_Shared.LGA_NKS_GetClip import TASK_EXR_TRACKS, TRACK_comp_EXR

DEBUG = False

EDITREF_TRACK = "EditRef"

# Estados del resultado. "opening" es el unico intermedio: se informa antes de
# abrir un proyecto, porque eso tarda segundos y el que pidio tiene que saberlo.
STATUS_OK = "ok"
STATUS_OPENING = "opening"
STATUS_NOT_FOUND = "not_found"
STATUS_NO_PROJECT = "no_project"
STATUS_ERROR = "error"

_TOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROJECTS_PANEL_PY = os.path.join(_TOOLS_DIR, "LGA_NKS_Projects_Panel_py")
LOG_PATH = os.path.join(_TOOLS_DIR, "logs", "DebugPy_ShotNavigation.log")

_LOG_LINES = []
_LOG_START = [time.time()]


# ----------------------------------------------------------------------
# Log: una corrida = un pedido de navegacion, el .log se pisa en cada una
# ----------------------------------------------------------------------
def _reset_log():
    del _LOG_LINES[:]
    _LOG_START[0] = time.time()


def debug_print(*message):
    linea = " ".join(str(m) for m in message)
    _LOG_LINES.append("[{0:.3f}s] {1}".format(time.time() - _LOG_START[0], linea))
    if DEBUG:
        print(linea)


def _flush_log():
    """Escribe el log de la corrida, pisando el anterior. Nunca rompe la tool."""
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("Fecha: {0}\n".format(time.strftime("%Y-%m-%d %H:%M:%S")))
            handle.write("\n".join(_LOG_LINES) + "\n")
    except Exception:
        pass


def _result(status, detail, **extra):
    result = {"status": status, "detail": detail}
    result.update(extra)
    debug_print("Resultado: {0} | {1}".format(status, detail))
    return result


# ----------------------------------------------------------------------
# Modulos del Projects Panel (import diferido, con el MISMO nombre que usa el
# panel para compartir su estado: memoria de timelines, reload, etc.)
# ----------------------------------------------------------------------
def _projects_panel_module(name):
    if _PROJECTS_PANEL_PY not in sys.path:
        sys.path.insert(0, _PROJECTS_PANEL_PY)
    module = sys.modules.get(name)
    if module is None:
        module = importlib.import_module(name)
    return module


def _projects_panel_instance():
    """El ProjectsPanel vivo, o None si el modulo no se cargo o el widget murio."""
    module = sys.modules.get("LGA_NKS_Projects_Panel")
    panel = getattr(module, "projectsPanel", None) if module else None
    if panel is None:
        return None
    try:
        from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import is_widget_alive

        return panel if is_widget_alive(panel) else None
    except Exception:
        return panel


# ----------------------------------------------------------------------
# Identificacion de proyecto y shot
# ----------------------------------------------------------------------
def _fold(value):
    return str(value or "").strip().casefold()


def _project_key_of(project):
    """Proyecto de trabajo (carpeta VFX-<nombre>) de un proyecto abierto de Hiero."""
    try:
        path = project.path()
    except Exception:
        path = ""
    try:
        name = project.name()
    except Exception:
        name = ""
    scan = _projects_panel_module("LGA_Projects_Panel_ScanProjects")
    return scan.obtener_clave_proyecto(path, name)


def open_projects_for(project_name):
    """Proyectos abiertos en Hiero cuyo .hrox cuelga de VFX-<project_name>."""
    target = _fold(project_name)
    found = []
    for project in hiero.core.projects():
        try:
            if _fold(_project_key_of(project)) == target:
                found.append(project)
        except Exception as e:
            debug_print("No se pudo leer la clave de un proyecto abierto: {0}".format(e))
    return found


def _clip_file_path(item):
    try:
        fileinfos = item.source().mediaSource().fileinfos()
        if fileinfos:
            return fileinfos[0].filename()
    except Exception:
        pass
    return ""


def _clip_matches_shot(item, project_fold, shot_fold):
    """
    True si el clip es del shot pedido. Mismo criterio que el Flow Pull:
    la carpeta del shot en la ruta de la media, o el shot_code del filename.
    La ruta se compara por segmento entero, asi un shot no matchea un prefijo
    de otro (PROJA_010_0100 contra PROJA_010_01000).
    """
    path = _clip_file_path(item)
    if path:
        path_project = extract_project_name_from_path(path)
        if path_project and _fold(path_project) != project_fold:
            return False
        segments = [s for s in re.split(r"[\\/]+", path) if s]
        if any(_fold(s) == shot_fold for s in segments[:-1]):
            return True
        base = clean_base_name(os.path.basename(path))
    else:
        try:
            base = clean_base_name(item.name())
        except Exception:
            return False
    return _fold(extract_shot_code(base)) == shot_fold


def _task_track_for(task_name):
    """Track EXR registrado para una task, o None."""
    if not task_name:
        return None
    wanted = normalize_task_name(str(task_name).strip().strip("_").lower())
    for track_name in TASK_EXR_TRACKS:
        if normalize_task_name(track_name.strip("_").lower()) == wanted:
            return track_name
    return None


def _clip_rank(item, track_name, task_track, task_fold):
    """
    Menor es mejor. Orden: la task pedida (por track o por filename), despues
    comp, despues el resto de los tracks de task, EditRef y cualquier otro.
    Un empate lo desempata el timelineIn mas chico.
    """
    if task_track and track_name == task_track:
        return 0
    if task_fold:
        base = clean_base_name(os.path.basename(_clip_file_path(item) or ""))
        clip_task = extract_task_name(base) if base else None
        if clip_task and _fold(normalize_task_name(clip_task)) == task_fold:
            return 1
    if track_name == TRACK_comp_EXR:
        return 2
    if track_name in TASK_EXR_TRACKS:
        return 3 + TASK_EXR_TRACKS.index(track_name)
    if track_name == EDITREF_TRACK:
        return 20
    return 30


def _find_shot_in_sequence(seq, project_fold, shot_fold, task_track, task_fold):
    """(clip, track_name, cantidad de clips del shot) del mejor clip, o (None, None, 0)."""
    best = None
    count = 0
    for track in seq.videoTracks():
        try:
            track_name = track.name()
        except Exception:
            continue
        for item in track.items():
            if isinstance(item, hiero.core.EffectTrackItem):
                continue
            if not _clip_matches_shot(item, project_fold, shot_fold):
                continue
            count += 1
            key = (_clip_rank(item, track_name, task_track, task_fold), item.timelineIn())
            if best is None or key < best[0]:
                best = (key, item, track_name)
    if best is None:
        return None, None, 0
    return best[1], best[2], count


def _ordered_sequences(projects, sequence_hint):
    """
    Secuencias donde buscar, en orden: la activa (si es de estos proyectos),
    las que se llaman como la secuencia del shot, y el resto.
    """
    ordered = []

    def _add(seq):
        # Por igualdad de Hiero y no por nombre: dos secuencias pueden llamarse
        # igual, y los wrappers de Python cambian entre llamadas (id no sirve).
        if not any(seq == already for already in ordered):
            ordered.append(seq)

    all_seqs = []
    for project in projects:
        try:
            all_seqs.extend(project.sequences())
        except Exception as e:
            debug_print("No se pudieron listar secuencias de un proyecto: {0}".format(e))

    try:
        active = hiero.ui.activeSequence()
    except Exception:
        active = None
    if active is not None:
        for seq in all_seqs:
            if seq == active:
                _add(seq)
                break

    hint = _fold(sequence_hint)
    if hint:
        for seq in all_seqs:
            if _fold(seq.name()) == hint:
                _add(seq)

    for seq in all_seqs:
        _add(seq)
    return ordered


def find_shot(projects, shot, sequence_hint=None, task=None, project_name=""):
    """
    Busca el shot en las secuencias de los proyectos dados.
    Devuelve (seq, clip, track_name, clips_del_shot, secuencias_revisadas).
    """
    project_fold = _fold(project_name)
    shot_fold = _fold(shot)
    task_track = _task_track_for(task)
    task_fold = _fold(normalize_task_name(task)) if task else ""
    sequences = _ordered_sequences(projects, sequence_hint)
    revisadas = 0
    for seq in sequences:
        revisadas += 1
        clip, track_name, count = _find_shot_in_sequence(
            seq, project_fold, shot_fold, task_track, task_fold
        )
        if clip is not None:
            debug_print(
                "Shot encontrado en secuencia '{0}' track '{1}' ({2} clip(s) del shot)".format(
                    seq.name(), track_name, count
                )
            )
            return seq, clip, track_name, count, revisadas
    return None, None, None, 0, revisadas


# ----------------------------------------------------------------------
# Timeline: switch + seleccion + In/Out + playhead
# ----------------------------------------------------------------------
def _editref_clip_at(seq, position):
    for track in seq.videoTracks():
        if track.name() != EDITREF_TRACK:
            continue
        for item in track.items():
            if isinstance(item, hiero.core.EffectTrackItem):
                continue
            if item.timelineIn() <= position <= item.timelineOut():
                return item
    return None


def _bring_main_window_to_front():
    """
    Trae NKS adelante. En Windows un proceso de fondo no puede tomar el foco
    por su cuenta: funciona porque el que pide (PipeSync) llama antes a
    AllowSetForegroundWindow. Sin ese permiso Windows solo hace titilar el
    boton de la barra de tareas, que tampoco molesta.
    """
    try:
        window = hiero.ui.mainWindow()
    except Exception:
        return
    if window is None:
        return
    try:
        if window.isMinimized():
            window.showNormal()
        window.raise_()
        window.activateWindow()
    except Exception as e:
        debug_print("No se pudo activar la ventana principal: {0}".format(e))
    if sys.platform == "win32":
        try:
            import ctypes

            user32 = ctypes.windll.user32
            user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
            user32.SetForegroundWindow(ctypes.c_void_p(int(window.winId())))
        except Exception as e:
            debug_print("SetForegroundWindow fallo: {0}".format(e))


# El switch del Projects Panel restaura la vista guardada de la secuencia y
# deja programado un reintento a MEMORY_RESTORE_RETRY_MS que vuelve a aplicar
# zoom, scroll y PLAYHEAD viejos. Si el foco al clip corre antes, ese reintento
# lo pisa. Por eso el foco espera ese tiempo mas este margen. La post-apertura
# de un proyecto usa el mismo switch, asi que vale tambien para ese camino.
FOCUS_AFTER_MEMORY_MARGIN_MS = 100


def _focus_delay_ms():
    try:
        switch = _projects_panel_module("LGA_Projects_Panel_SwitchSequence")
        retry = int(getattr(switch, "MEMORY_RESTORE_RETRY_MS", 150))
    except Exception:
        retry = 150
    return retry + FOCUS_AFTER_MEMORY_MARGIN_MS


def _focus_clip(seq, clip):
    """Selecciona, marca In/Out y mueve el playhead. Mismo patron que el Flow Pull."""
    timeline_editor = hiero.ui.getTimelineEditor(seq)
    reference = clip
    editref = _editref_clip_at(seq, clip.timelineIn())
    if editref is not None:
        reference = editref
        debug_print("In/Out tomado de EditRef: '{0}'".format(editref.name()))
    else:
        debug_print("Sin clip de EditRef en esa posicion: In/Out del propio clip")

    if timeline_editor:
        timeline_editor.setSelection([reference])

    in_point = reference.timelineIn()
    out_point = reference.timelineOut()
    try:
        seq.setInTime(in_point)
        seq.setOutTime(out_point)
    except Exception as e:
        debug_print("No se pudieron establecer In/Out: {0}".format(e))

    viewer = hiero.ui.currentViewer()
    if viewer:
        viewer.setTime(in_point)

    _bring_main_window_to_front()

    # Zoom to Fit actua sobre el timeline con foco: sin esto, si el foco quedo
    # en otro panel, la accion no hace nada. Mismo par de llamadas que el Pull.
    if timeline_editor:
        try:
            window = timeline_editor.window()
            if window:
                window.activateWindow()
                window.setFocus()
        except Exception as e:
            debug_print("No se pudo dar foco al timeline: {0}".format(e))

    def _zoom_to_fit():
        try:
            action = hiero.ui.findMenuAction("Zoom to Fit")
            if action:
                action.trigger()
        except Exception as e:
            debug_print("Zoom to Fit fallo: {0}".format(e))

    QtCore.QTimer.singleShot(0, _zoom_to_fit)
    return reference, in_point, out_point


def _navigate(project_name, shot, sequence_hint, task, opened_project, finish, is_current):
    """Busca y navega en lo que ya esta abierto. Llama finish(resultado) una vez."""
    projects = open_projects_for(project_name)
    if not projects:
        finish(_result(
            STATUS_NO_PROJECT,
            "No hay ningun proyecto abierto de VFX-{0}.".format(project_name),
        ))
        return
    debug_print(
        "Proyectos abiertos del shot: {0}".format([p.name() for p in projects])
    )

    seq, clip, track_name, count, revisadas = find_shot(
        projects, shot, sequence_hint, task, project_name
    )
    if seq is None:
        finish(_result(
            STATUS_NOT_FOUND,
            "El shot {0} no tiene clip en ninguna de las {1} secuencias de {2}.".format(
                shot, revisadas, ", ".join(p.name() for p in projects)
            ),
            opened_project=opened_project,
        ))
        return

    switch = _projects_panel_module("LGA_Projects_Panel_SwitchSequence")
    seq_name = seq.name()
    try:
        switched = bool(
            switch.switch_to_sequence_hybrid(seq_name, target_project=seq.project())
        )
    except Exception:
        finish(_result(
            STATUS_ERROR,
            "Fallo el cambio a la secuencia {0}:\n{1}".format(seq_name, traceback.format_exc()),
        ))
        return
    if not switched:
        finish(_result(
            STATUS_ERROR,
            "El switch del Projects Panel no pudo abrir la secuencia {0} "
            "(ver logs/DebugPy_ProjectsPanel.log).".format(seq_name),
        ))
        return

    def _focus_later():
        if not is_current():
            debug_print("El pedido ya no es el vigente: no se mueve el timeline")
            finish(_result(STATUS_ERROR, "Pedido vencido antes de navegar."))
            return
        try:
            # El switch reabre el timeline: se vuelve a buscar el clip en la
            # secuencia ya activa en vez de confiar en el objeto de antes.
            active = hiero.ui.activeSequence() or seq
            found, found_track, _count = _find_shot_in_sequence(
                active,
                _fold(project_name),
                _fold(shot),
                _task_track_for(task),
                _fold(normalize_task_name(task)) if task else "",
            )
            if found is not None:
                target, target_track = found, found_track
            else:
                target, target_track = clip, track_name
            _reference, in_point, out_point = _focus_clip(active, target)
            finish(_result(
                STATUS_OK,
                "Secuencia {0}, track {1}, clip {2} [{3}-{4}]".format(
                    seq_name, target_track, target.name(), in_point, out_point
                ),
                sequence=seq_name,
                track=target_track,
                clip=target.name(),
                in_frame=in_point,
                out_frame=out_point,
                clips_of_shot=count,
                opened_project=opened_project,
            ))
        except Exception:
            finish(_result(STATUS_ERROR, traceback.format_exc()))

    delay = _focus_delay_ms()
    debug_print("Foco al clip diferido {0} ms (despues del reintento de memoria)".format(delay))
    QtCore.QTimer.singleShot(delay, _focus_later)


# ----------------------------------------------------------------------
# Proyecto cerrado: buscar su .hrox y abrirlo con el Projects Panel
# ----------------------------------------------------------------------
def find_project_hrox(project_name):
    """
    Ruta del .hrox (version mas alta) de VFX-<project_name> en el root del
    contexto, o (None, motivo). Con varios proyectos en la carpeta SUP (por
    ejemplo PROJA_SUP y PROJA_Breakdown) se prefiere el que se muestra igual
    que el nombre del proyecto, que es el principal.

    Corre en el hilo principal a proposito: son dos listados de carpeta (la
    VFX- del proyecto y sus *_SUP), no el escaneo del root entero que el panel
    hace en un worker, y la apertura que sigue bloquea mucho mas.
    """
    scan = _projects_panel_module("LGA_Projects_Panel_ScanProjects")
    base = scan.get_base_scan_path()
    if not base or not os.path.isdir(base):
        return None, "El root de proyectos no existe: {0}".format(base)

    wanted_vfx = _fold("VFX-" + project_name)
    try:
        vfx_folder = next(
            (n for n in os.listdir(base) if _fold(n) == wanted_vfx
             and os.path.isdir(os.path.join(base, n))),
            None,
        )
    except OSError as e:
        return None, "No se pudo listar {0}: {1}".format(base, e)
    if not vfx_folder:
        return None, "No existe la carpeta VFX-{0} en {1}".format(project_name, base)

    vfx_path = os.path.join(base, vfx_folder)
    candidatos = []
    try:
        sups = sorted(os.listdir(vfx_path), key=lambda v: v.casefold())
    except OSError as e:
        return None, "No se pudo listar {0}: {1}".format(vfx_path, e)
    for sup in sups:
        sup_path = os.path.join(vfx_path, sup)
        if not (os.path.isdir(sup_path) and scan._is_sup_folder_name(sup)):
            continue
        grupos = scan._agrupar_hrox_por_proyecto(scan._list_hrox_files(sup_path))
        for clave in sorted(grupos):
            ruta, _version = scan._elegir_version_mas_alta(grupos[clave])
            if ruta:
                candidatos.append((clave, ruta))

    if not candidatos:
        return None, "No hay ningun .hrox en las carpetas *_SUP de {0}".format(vfx_path)

    debug_print("Candidatos .hrox: {0}".format([os.path.basename(r) for _n, r in candidatos]))
    # Se compara la clave del grupo (sin version ni sufijos como "_Mac"), no el
    # nombre del archivo: "PROJA_SUP_v041_Mac" tiene que ser el principal.
    principal = [
        ruta for clave, ruta in candidatos
        if _fold(scan.obtener_nombre_display_proyecto(clave)) == _fold(project_name)
    ]
    return (principal[0] if principal else candidatos[0][1]), ""


def goto_shot(project, shot, sequence=None, task=None, on_result=None, on_progress=None,
              is_current=None):
    """
    Navega al shot. Llama on_result(dict) UNA vez con el resultado final. Si
    hay que abrir el proyecto, antes llama on_progress(dict) con "opening".

    is_current: callable opcional. Si devuelve False antes de mover el
    timeline (por ejemplo, el server ya libero el pedido por timeout y entro
    otro), no se navega: un salto tardio pisaria al pedido nuevo.

    Tiene que correr en el hilo principal y fuera de un slot de socket: el
    switch de secuencia procesa eventos (el server lo difiere con un timer).
    """
    if is_current is None:
        def is_current():
            return True

    _reset_log()
    debug_print(
        "Pedido: project='{0}' sequence='{1}' shot='{2}' task='{3}'".format(
            project, sequence, shot, task
        )
    )

    def _finish(result):
        _flush_log()
        if on_result:
            on_result(result)

    try:
        if open_projects_for(project):
            _navigate(project, shot, sequence, task, False, _finish, is_current)
            return
        _open_then_navigate(project, shot, sequence, task, _finish, on_progress, is_current)
    except Exception:
        _finish(_result(STATUS_ERROR, traceback.format_exc()))


def _open_then_navigate(project, shot, sequence, task, finish, on_progress, is_current):
    hrox, motivo = find_project_hrox(project)
    if not hrox:
        finish(_result(STATUS_NO_PROJECT, motivo))
        return

    panel = _projects_panel_instance()
    if panel is None or not hasattr(panel, "after_project_open"):
        finish(
            _result(
                STATUS_ERROR,
                "El proyecto no esta abierto y el Projects Panel no esta cargado "
                "para abrirlo: {0}".format(hrox),
            )
        )
        return

    debug_print("Proyecto cerrado, se abre: {0}".format(hrox))
    if on_progress:
        on_progress({"status": STATUS_OPENING, "detail": os.path.basename(hrox)})

    def _after_open():
        # La post-apertura ya dejo el proyecto en su ultimo timeline; desde
        # ahi se navega al shot como si hubiera estado abierto.
        debug_print("Post-apertura terminada")
        if not is_current():
            debug_print("El pedido ya no es el vigente: no se navega")
            finish(_result(STATUS_ERROR, "Pedido vencido durante la apertura."))
            return
        try:
            _navigate(project, shot, sequence, task, True, finish, is_current)
        except Exception:
            finish(_result(STATUS_ERROR, traceback.format_exc()))

    def _open():
        # Mismos pasos que ProjectHandler.on_project_click, con on_done.
        panel.begin_project_open()
        try:
            opened = hiero.core.openProject(hrox)
        except Exception:
            panel.end_project_open()
            finish(_result(STATUS_ERROR, "openProject fallo:\n" + traceback.format_exc()))
            return
        if opened is None:
            panel.end_project_open()
            finish(_result(STATUS_ERROR, "openProject devolvio None: {0}".format(hrox)))
            return
        try:
            panel.start_scan()
        except Exception as e:
            debug_print("No se pudo refrescar el Projects Panel: {0}".format(e))
        try:
            panel.after_project_open(opened, on_done=_after_open)
        except Exception:
            # Sin esto el repintado quedaria congelado desde begin_project_open.
            panel.end_project_open()
            finish(_result(STATUS_ERROR, "after_project_open fallo:\n" + traceback.format_exc()))

    # Diferido para no abrir el proyecto adentro del mismo tick del pedido; el
    # "opening" ya salio (el server hace flush al escribirlo).
    QtCore.QTimer.singleShot(50, _open)
