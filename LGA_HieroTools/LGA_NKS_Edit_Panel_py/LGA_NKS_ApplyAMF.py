"""
____________________________________________________________________

  LGA_NKS_ApplyAMF v0.94 | Lega

  Pone y saca los soft effects de color de un shot, siguiendo lo que
  declara el .amf que viene con el shot.

  Con TOGGLE_CREATE_DELETE en True (el default) el boton es un TOGGLE:
  si los clips objetivo YA tienen la cadena AMF, la BORRA; si no la
  tienen, la crea. Tener soft effects colgados en el timeline todo el
  tiempo estorba, y con un solo boton se ponen y se sacan.

  De donde salen los clips objetivo (regla por CANTIDAD, no por
  presencia):

    - DOS o mas clips seleccionados -> se opera solo sobre esos.
    - UNO o ninguno -> se ignora la seleccion y se barren todos los
      tracks bajo el PLAYHEAD, tomando solo los .exr.

  El umbral esta en dos porque Hiero AUTOSELECCIONA el clip bajo el
  playhead: parado sobre un shot y sin tocar nada, selection() ya
  devuelve un item, asi que "uno seleccionado" y "ninguno seleccionado"
  son el mismo caso desde la API. Ver SELECCION_MINIMA.

  Esa regla NO depende del flag: el flag decide crear o borrar, no de
  donde salen los clips. Con el flag en False la tool solo crea, nunca
  borra.

  El boton tiene el atajo Shift+L.

  El .amf (ACES Metadata File) describe la cadena entera del plate y es la
  fuente de verdad. De ahi salen tres cosas:

    - QUE aplicar: cada <lookTransform> trae applied="true|false". Los que
      ya vienen horneados en el plate (IDT, Reference Gamut Compress) se
      saltean; solo se crean los que estan en false.
    - EN QUE ORDEN: los <lookTransform> vienen en orden de cadena. El
      primero que se crea queda en el subtrack de abajo, o sea que se
      aplica antes.
    - CON QUE PARAMETROS: la cadena corre en ACES2065-1, y el <cdlWorkingSpace>
      es la excepcion que saca al CDL a ACEScct. Ninguno de los dos es el
      scene_linear que trae el nodo por defecto. El <file> del LMT nombra el
      .clf a cargar, que entra y sale en ACES2065-1.

  Efectos que sabe crear:
    OCIOCDLTransform  <- el .cdl del shot (grade)
    OCIOFileTransform <- el LMT: el .clf o el .cube que nombra el .amf

  Si no hay .amf en la carpeta se cae a un plan fijo: el .cdl suelto (si
  hay) y UN LMT, que es el .clf y, si no hay, el .cube. Con .cdl y .cube
  se aplican los dos; nunca .clf y .cube juntos (son el mismo LMT y se
  doblaria el look). Queda avisado por consola.

  Flujo por clip:
    1. Ruta de la media del clip.
    2. Carpeta del shot, via extract_shot_code_from_path() de NamingUtils,
       que valida el vendor code contra la DB de PipeSync. Fallback: subir
       directorios hasta encontrar uno que tenga _input adentro.
    3. <shot>/_input/Look_Files/
    4. Leer el .amf y armar el plan de efectos.
    5. Crear (o reusar) cada soft effect linkeado al clip y setear sus knobs.

  Ejemplo de estructura esperada:
    T:/VFX-PROJA/101/PROJA_1013_0800_VND/_input/Look_Files/
        PROJA_1013_0800_VND_aPlate_v001.amf
        PROJA_1013_0800_VND_aPlate_v001.cdl
        algun_lmt_acesap0_linear.clf

  API relevante (Nuke 16 PythonDevGuide / Hiero / api_core):
    VideoTrack.createEffect(effectType=None, cloneFrom=None, copyFrom=None,
                            trackItem=None, timelineIn=None, timelineOut=None,
                            subTrackIndex=None) -> EffectTrackItem
    Pasando trackItem, el efecto queda LINKEADO al clip y toma su mismo
    timing. Sin trackItem hay que dar timelineIn/timelineOut, y el efecto
    queda suelto en el track (es lo que hace LGA_NKS_FrameNumber_Create).

  Con varios plates en el shot, el .amf se elige por el plate del clip
  (ver pick_amf_for_plate). El aviso de 'hay mas de uno de esa extension'
  quedo solo para el plan de respaldo, donde no hay .amf que consultar.

  v0.94: Fix: Node.hasError() deja de decidir. La v0.93 sacaba del timeline
         todo efecto cuyo nodo quedaba con hasError() en True, y en una sesion
         real de NKS eso pasaba con un .cdl y un .clf VALIDOS (el CDL hasta
         leia sus valores del archivo): la tool no aplicaba nada y avisaba
         'could not be loaded by the color node'. hasError() valida el nodo
         contra el color management de nuke.root(), que en NKS no tiene por
         que ser el del proyecto: un working space que el proyecto si tiene
         da 'Invalid input LUT selected' aunque el efecto se vea bien. Ahora
         el estado se LOGUEA por etapa (recien creado, con el archivo, con
         el working space) junto con el color management de nuke.root() y
         del proyecto, y el efecto se deja puesto. Lo que frena la creacion
         sigue siendo la validacion previa del archivo.
  v0.93: El .cube pasa a ser un look. Sin .amf, el plan de respaldo es el
         .cdl (si hay) mas UN LMT: el .clf y, si no hay, el .cube. El .cube
         va como OCIOFileTransform y su working space sale del nombre del
         archivo (sin pista, ACEScct). Con varios .cube se queda la version
         mas alta de cada LUT y, entre LUT distintos, el ultimo alfabetico,
         avisado en el log. Fix: con los configs OCIO v2 de Foundry las
         opciones del enum traen campos separados por TAB y la funcion
         devolvia la cadena entera, que deja el efecto roto sin aviso:
         ahora matchea y devuelve el nombre corto. Los archivos del plan
         se validan antes de crear el efecto (inexistente, vacio, .cube o
         XML corrupto) porque nodeHasError() NO detecta un archivo faltante;
         y un nodo que igual queda en error (Node.hasError()) se saca del
         timeline y sube al cartel, porque un nodo en error entrega negro.
         Fix (preexistente): crear un efecto en un subtrack ocupado BORRA el
         que estaba, y la cadena iba siempre al 0 y al 1, asi que se llevaba
         puestos los efectos del artista. Ahora la cadena va en un bloque
         contiguo de subtracks por ENCIMA del mas alto ocupado
         (subtracks_para_la_cadena), con el CDL antes que el LMT y sin que un
         efecto del artista la parta; sin ajenos es el 0 y el 1 de siempre.
         Un OCIOFileTransform/OCIOCDLTransform ajeno ya no hace saltear
         nuestro eslabon. El cartel dice 'could not apply everything' porque
         puede aplicar parte.
  v0.92: El .amf se resuelve por el PLATE del clip y no como 'el unico de
         esa extension'. Un shot trae un .amf por plate y cada plate tiene
         su propio grade, asi que quedarse con el primero le ponia a un
         clip de cbPlate el grade del aPlate. Ahora se toma el del plate
         del clip en su version mas alta; si el shot no trae uno para ese
         plate, o el clip no es un plate -un _comp-, se usa el del aPlate,
         y si tampoco hay, el primero. El .cdl pasa a ser el HERMANO del
         .amf elegido, y si ese .amf no tiene hermano solo se acepta un
         .cdl suelto cuando hay UNO en la carpeta: con varios no se puede
         saber cual es, y aplicar el primero es el bug de nuevo.
         Ademas la carpeta se lista una vez por corrida y
         cada plan se arma una vez por plate: el toggle hacia dos listados
         y dos parseos de XML POR CLIP, todos de los mismos archivos.
  v0.91: El working space de la cadena pasa a ser ACES2065-1 cuando el .amf
         no declara otro. El .clf del LMT no trae <cdlWorkingSpace> -solo lo
         trae el CDL, para salirse a ACEScct-, asi que su nodo quedaba en el
         default `scene_linear`, que en los configs ACES es ACEScg. El .clf
         entra y sale en AP0 y arranca con una matriz AP0 a AP1, asi que
         recibia el gamut equivocado y la LUT corria corrida. Ademas el
         matcheo contra el enum del knob deja afuera los ROLES: pidiendo
         ACES2065-1 tambien matchea 'default (ACES - ACES2065-1)', y cual
         gana dependia del orden del enum. Y si el OCIO config del proyecto
         no expone el espacio pedido, eso pasa a contar como error y sube al
         cartel: antes solo dejaba un WARN en el log y el efecto se informaba
         como creado, o sea que el look salia mal y nadie se enteraba.
  v0.90: Los clips objetivo salen del playhead salvo que haya DOS o mas
         seleccionados. Con uno solo la tool creia estar respetando una
         seleccion del usuario, pero era la autoseleccion de Hiero, y
         terminaba tocando un solo track en vez del shot entero. Del
         playhead se toman solo los .exr, para no meterle la cadena a un
         EditRef. La tool absorbe el atajo Shift+L, que deja de estar en
         Toggle AMF.
  v0.80: El boton pasa a ser un toggle de crear/borrar (flag
         TOGGLE_CREATE_DELETE) y, sin seleccion, opera sobre el
         playhead en todos los tracks. El borrado va con
         eDontRemoveLinkedItems: los efectos se crean LINKEADOS al
         clip, y removeSubTrackItem sin esa opcion se lleva puesto el
         CLIP del timeline. Solo se borra lo que apunta a Look_Files,
         asi un efecto de la misma clase puesto a mano no se pierde.
  v0.70: Avisa por cartel cuando no puede resolver un shot, en vez de
         terminar en silencio. UN solo cartel por corrida y agrupado
         por SHOT, no por clip: un shot suele tener clips en aPlate,
         bPlate y _comp_, y repetir el mismo nombre tres veces hace
         el aviso ilegible.
  v0.62: Cada corrida escribe su log a logs/DebugPy_LGA_NKS_ApplyAMF.log,
         prendido o no el debug por consola. Sin eso la tool era
         una caja negra cuando no hacia nada.
  v0.61: El debug por consola queda apagado por default.
  v0.60: Los efectos van a un subtrack FIJO (el indice de la cadena)
         y no a uno nuevo por llamada. Sin pasar subTrackIndex, cada
         createEffect abria un subtrack propio: el segundo clip del
         track quedaba con sus efectos en s1/s2 y un s0 vacio debajo,
         que se veia como una franja muerta entre el clip y su cadena.
  v0.50: No vuelve a crear un efecto que el clip ya tiene: se saltea y se
         crea solo el que falta. La deteccion no se queda con linkedItems():
         tambien barre los subtracks del track, porque un efecto creado a
         mano queda suelto y ahi no figura.
  v0.40: El .amf pasa a ser la fuente de verdad: de ahi salen el orden, el
         applied de cada transform, el working space del CDL y el nombre
         del .clf. El working space se matchea contra las opciones reales
         del knob, para no depender del nombre que use el OCIO config.
  v0.30: Suma el OCIOFileTransform con el .clf, despues del CDL. La eleccion
         de archivo pasa a ser "el unico de esa extension".
  v0.20: Resuelve el .cdl de <shot>/_input/Look_Files y lo carga en el
         efecto (file + cccid + read_from_file). Reusa el efecto si el clip
         ya tiene uno. No crea nada si no encuentra el .cdl.
  v0.10: Version inicial exploratoria.
____________________________________________________________________

"""

import os
import re
import sys
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path

import hiero.core
import hiero.ui

# ============================
# Configuracion
# ============================

DEBUG = False

# Nombres de carpeta donde viven los archivos de look, colgando del shot.
INPUT_DIR_NAME = "_input"
LOOK_DIR_NAME = "Look_Files"

# De que plate es una media, y con que version.
#
# 'SHOT_cbPlate_v004.1001.exr' -> ('cbplate', 4). El patron es el mismo que
# usa LGA_NKS_CreateNKScript para leer los plates de un shot; se copia en vez
# de importarse porque los dos modulos son hermanos y ninguno depende del
# otro. La version sale del MISMO match que el plate: un prerender como
# 'SHOT_aPlate_v001_Denoised_v02' tiene dos '_v###' y el que vale es el que
# viene pegado al plate.
PLATE_VER_RE = re.compile(r"_([A-Za-z][A-Za-z0-9]*?Plate[0-9]*)_v(\d+)", re.IGNORECASE)

# El plate que se usa cuando el clip NO es un plate.
#
# Un _comp, un precomp o un render de review no nombran ningun plate, y el
# look que les corresponde es el del plate principal. Tambien es el respaldo
# cuando el clip SI es un plate pero el shot no trae .amf para ese: mejor el
# del aPlate que ninguno.
PLATE_POR_DEFECTO = "aplate"

# El espacio en el que corre la cadena de un .amf.
#
# La pipeline ACES que describe un .amf opera en ACES2065-1, y por eso el CDL
# necesita declarar su <cdlWorkingSpace>: salirse a ACEScct es la EXCEPCION,
# no la regla. Un lookTransform que no declara nada corre en ACES2065-1.
#
# Sin esto, el nodo se queda con su default `scene_linear`, que es un ROL del
# config OCIO y no un espacio: en los configs ACES apunta a ACEScg (AP1). Un
# .clf de LMT entra y sale en AP0 -lo declara en su propio InputDescriptor y
# arranca con una matriz AP0 a AP1-, asi que alimentarlo con AP1 le mete una
# conversion de gamut de mas y corre la LUT sobre datos que no le corresponden.
#
# El knob no dice "la entrada esta en", dice "aplicalo en": el nodo convierte
# de scene_linear a este espacio, aplica el archivo y vuelve. Por eso pedir
# ACES2065-1 es correcto sea cual sea el working space del proyecto, y por eso
# la tool NO tiene que consultar el espacio del proyecto ni el del clip.
AMF_WORKING_SPACE = "ACES2065-1"

# Extensiones de los archivos de look que entiende el plan de respaldo.
CDL_EXTENSION = ".cdl"
CLF_EXTENSION = ".clf"
CUBE_EXTENSION = ".cube"

# Un .cube es un LUT 1D/3D pelado: no trae metadata, ni siquiera dice en que
# espacio espera su entrada. Se deduce del nombre del archivo y, sin pista, se
# asume ACEScct, que es la convencion de los LMT de ACES (un LMT en un
# OCIOFileTransform con working space ACEScct es la forma en que el estudio
# arma el look del shot). El nombre que se pide es el LOGICO ('ACEScct'): el
# nombre real del colorspace lo resuelve match_colorspace_option contra el
# config OCIO activo, porque cambia de config en config ('ACEScct' a secas o
# 'ACES - ACEScct').
CUBE_DEFAULT_SPACE = "ACEScct"

# Pista del nombre -> espacio logico. 'linear' se lee como lineal ACES (AP0),
# no como cualquier lineal: el .cube de un LMT de ACES que dice 'Linear' habla
# de ACES2065-1. Los lookaround evitan que 'acescc' matchee adentro de
# 'acescct' y que 'linear' matchee adentro de 'nonlinear'.
_CUBE_SPACE_HINTS = {
    "acescct": "ACEScct",
    "acescc": "ACEScc",
    "acescg": "ACEScg",
    "ap1": "ACEScg",
    "aces2065": "ACES2065-1",
    "ap0": "ACES2065-1",
    "linear": "ACES2065-1",
}
_CUBE_SPACE_RE = re.compile(
    r"(?<![a-z0-9])(%s)(?![a-z])"
    % "|".join(sorted(_CUBE_SPACE_HINTS, key=len, reverse=True))
)

# '<nombre>_v003' al final del nombre (sin extension). Sin distinguir mayusculas:
# hay carpetas con '_V003'.
_LUT_VERSION_RE = re.compile(r"^(?P<base>.+)_v(?P<version>\d+)$", re.IGNORECASE)

# Si el clip ya tiene un efecto de ese tipo, se lo deja como esta y se crea solo
# el que falta. Asi el boton es idempotente y no apila efectos al reintentar, ni
# pisa un archivo que alguien haya cambiado a mano.
SKIP_IF_EXISTS = True

# El boton como TOGGLE: si los clips objetivo ya tienen la cadena AMF, la borra;
# si no la tienen, la crea. Ademas, sin seleccion opera sobre el playhead.
#
# En False queda el comportamiento viejo -crear sobre la seleccion, nunca
# borrar-. El codigo de creacion es el mismo en los dos casos: el flag no
# bifurca la logica de creacion, solo decide si ademas se puede borrar y de
# donde salen los clips.
TOGGLE_CREATE_DELETE = True

# Los tipos que pone esta tool. Es la lista que mira el toggle para saber si un
# clip "ya tiene AMF", y la unica que se borra. Tiene que coincidir con la de
# LGA_NKS_ToggleAMF: son las dos puntas de la misma herramienta.
AMF_EFFECT_TYPES = ("OCIOCDLTransform", "OCIOFileTransform")

# Cuantos clips seleccionados hacen falta para creerle a la seleccion.
#
# Hiero AUTOSELECCIONA el clip que esta bajo el playhead: parado sobre un shot
# y sin haber hecho click en nada, selection() ya devuelve UN item. O sea que
# "un clip seleccionado" y "ningun clip seleccionado" son indistinguibles desde
# la API, y por eso la tool tomaba la autoseleccion como si fuera una eleccion
# del usuario y nunca llegaba a mirar los demas tracks.
#
# Con DOS o mas, en cambio, la seleccion es deliberada: eso no lo hace solo.
SELECCION_MINIMA = 2

# Extensiones que se aceptan al barrer por playhead. El barrido mira TODOS los
# tracks, asi que sin filtro se lleva puesto lo que no es un plate -un EditRef
# .mov, un audio-, y la cadena del .amf no tiene sentido ahi.
#
# NO se aplica a la seleccion explicita: si el usuario eligio esos clips a
# mano, manda el. El filtro esta para el barrido a ciegas, no para
# contradecirlo.
PLAYHEAD_EXTENSIONS = (".exr",)

# La corrida SIEMPRE deja su log, este o no prendido el debug por consola. Sin
# esto la tool era una caja negra: si no hacia nada, no habia donde mirar por
# que -y justamente el caso mas comun, "el clip ya tenia los efectos y se
# saltearon", es silencioso-.
LOG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "logs", "DebugPy_LGA_NKS_ApplyAMF.log"
)

_LOG_LINES = []


def debug_print(*message):
    """Acumula para el .log y, si DEBUG, ademas escribe en la consola."""
    linea = " ".join(str(m) for m in message)
    _LOG_LINES.append(linea)
    if DEBUG:
        print(linea)


def _volcar_log():
    """Escribe el log de la corrida, pisando el anterior. Nunca rompe la tool."""
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(_LOG_LINES) + "\n")
    except Exception:
        pass
    del _LOG_LINES[:]


# ============================
# Naming centralizado
# ============================

# La carpeta del shot se detecta por NOMBRE y no por profundidad de ruta. El
# helper central valida ademas el vendor code contra la DB de PipeSync, que es
# lo que un conteo de segmentos no puede saber (naming PROYECTO_SEQ_SHOT_VENDOR).
_shared_dir = Path(__file__).parent.parent / "LGA_NKS_Shared"
if _shared_dir.exists():
    sys.path.insert(0, str(_shared_dir))
try:
    from LGA_NKS_Flow_NamingUtils import (
        extract_shot_code_from_path,
        extract_project_name_from_path,
    )
except ImportError:
    extract_shot_code_from_path = None
    extract_project_name_from_path = None
    debug_print("[WARN] No se pudo importar LGA_NKS_Flow_NamingUtils")


# ============================
# Helpers genericos
# ============================


def _safe_name(obj):
    """name() sin romper si el objeto no lo tiene o esta invalidado."""
    try:
        return obj.name()
    except Exception:
        return repr(obj)


def _safe_call(obj, method_name, default="<n/a>"):
    """Llama a un metodo sin argumentos y devuelve default si falla."""
    try:
        method = getattr(obj, method_name, None)
        if method is None:
            return default
        return method()
    except Exception as e:
        return f"<error: {e}>"


def _find_subdir(parent_dir, wanted_name):
    """Busca una subcarpeta por nombre sin distinguir mayusculas.

    En Windows daria igual, pero este repo tambien corre en macOS, donde el
    filesystem si distingue.
    """
    if not parent_dir or not os.path.isdir(parent_dir):
        return None
    wanted = wanted_name.lower()
    try:
        for entry in os.scandir(parent_dir):
            if entry.is_dir() and entry.name.lower() == wanted:
                return entry.path
    except OSError as e:
        debug_print(f"  [WARN] No se pudo listar '{parent_dir}': {e}")
    return None


def _local_tag(element):
    """Nombre del tag sin el namespace.

    Los XML de ACES declaran namespace (urn:ampas:aces:amf:v2.0,
    urn:ASC:CDL:v1.01), asi que los tags vienen como '{urn:...}lookTransform'.
    """
    return element.tag.split("}")[-1]


def _normalize(text):
    """Deja solo letras y numeros en minuscula, para comparar nombres de espacios."""
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


# ============================
# Resolucion de rutas
# ============================


def get_media_path(track_item):
    """Ruta en disco de la media del clip."""
    try:
        return track_item.source().mediaSource().firstpath()
    except Exception as e:
        debug_print(f"  [WARN] No se pudo leer la media del clip: {e}")
        return None


def resolve_shot_dir(media_path):
    """Carpeta del shot a partir de la ruta de la media.

    Sirve tanto para una media de _input como para un publish de Comp: en los
    dos casos la carpeta del shot esta mas arriba en la misma ruta.
    """
    if not media_path:
        return None

    normalized = re.sub(r"[\\/]+", "/", str(media_path))

    # Camino 1: el helper central, que reconoce el vendor code.
    if extract_shot_code_from_path:
        project_name = (
            extract_project_name_from_path(normalized)
            if extract_project_name_from_path
            else None
        )
        shot_code = extract_shot_code_from_path(normalized, project_name)
        debug_print(f"  project (de la ruta) : {project_name}")
        debug_print(f"  shot code            : {shot_code or '<no reconocido>'}")
        if shot_code:
            segments = normalized.split("/")
            for index in range(len(segments) - 1, -1, -1):
                if segments[index] == shot_code:
                    return "/".join(segments[: index + 1])

    # Camino 2: fallback estructural. Subir hasta el directorio que tenga _input
    # adentro. Cubre los shots con bloques de descripcion, que es el limite
    # conocido de is_shot_folder_name().
    debug_print("  [INFO] Fallback: buscando el directorio que contenga _input")
    current = os.path.dirname(normalized)
    while current and current != os.path.dirname(current):
        if _find_subdir(current, INPUT_DIR_NAME):
            return re.sub(r"[\\/]+", "/", current)
        current = os.path.dirname(current)

    return None


def resolve_look_dir(shot_dir):
    """<shot>/_input/Look_Files"""
    if not shot_dir:
        return None
    input_dir = _find_subdir(shot_dir, INPUT_DIR_NAME)
    if not input_dir:
        debug_print(f"  [ERROR] No existe '{INPUT_DIR_NAME}' en {shot_dir}")
        return None
    look_dir = _find_subdir(input_dir, LOOK_DIR_NAME)
    if not look_dir:
        debug_print(f"  [ERROR] No existe '{LOOK_DIR_NAME}' en {input_dir}")
        return None
    return re.sub(r"[\\/]+", "/", look_dir)


# Cache de UNA corrida. El toggle arma el plan por CLIP, y todos los clips de
# un shot miran la misma carpeta: sin esto, veinte clips son cuarenta listados
# y cuarenta parseos de XML de los mismos archivos. Con esto la carpeta se
# lista una vez y cada plan se arma una vez por plate distinto. Importa mas de
# lo que parece porque Look_Files vive en el disco del estudio, no en local.
#
# NO se persiste entre corridas: entre un toggle y el siguiente el usuario pudo
# bajar un .amf que faltaba. Hoy eso ya lo garantiza el cargador -el panel corre
# la tool con execute_external_script, que arma un modulo NUEVO por click y no lo
# registra en sys.modules, asi que los dos dicts nacen vacios solos-, pero
# reset_caches() se llama igual al arrancar: el dia que alguien importe este
# modulo de la forma normal, el cargador deja de salvarnos.
_ARCHIVOS_CACHE = {}
_PLAN_CACHE = {}
_CUBE_CACHE = {}
_VALIDACION_CACHE = {}

# Avisos de la corrida que NO son un fallo (por ejemplo, "habia varios .cube y se
# eligio uno"). Van al log y al RESUMEN; no abren un cartel: son decisiones
# deterministas de la tool, no algo que el usuario tenga que resolver ahora.
_AVISOS_CORRIDA = []


def _anotar_aviso_corrida(aviso):
    """Suma un aviso a la corrida, sin repetirlo (el plan se arma por plate)."""
    if aviso not in _AVISOS_CORRIDA:
        _AVISOS_CORRIDA.append(aviso)


def reset_caches():
    """Vacia los caches. Se llama al arrancar cada corrida."""
    _ARCHIVOS_CACHE.clear()
    _PLAN_CACHE.clear()
    _CUBE_CACHE.clear()
    _VALIDACION_CACHE.clear()
    del _AVISOS_CORRIDA[:]


def _archivos_de(look_dir):
    """Los archivos de la carpeta de look. Un solo listado por corrida."""
    if not look_dir:
        return []
    if look_dir in _ARCHIVOS_CACHE:
        return _ARCHIVOS_CACHE[look_dir]
    try:
        archivos = sorted(
            re.sub(r"[\\/]+", "/", entry.path)
            for entry in os.scandir(look_dir)
            if entry.is_file()
        )
    except OSError as e:
        debug_print(f"  [ERROR] No se pudo listar '{look_dir}': {e}")
        archivos = []
    _ARCHIVOS_CACHE[look_dir] = archivos
    return archivos


def plate_and_version(nombre):
    """('cbplate', 4) para 'SHOT_cbPlate_v004.exr'. (None, -1) si no hay."""
    if not nombre:
        return None, -1
    match = PLATE_VER_RE.search(str(nombre))
    if not match:
        return None, -1
    return match.group(1).lower(), int(match.group(2))


def plate_from_path(path):
    """El plate de esa media, en minuscula, o None si no nombra ninguno.

    Se mira el nombre del ARCHIVO y no la ruta entera: la carpeta del shot
    puede nombrar un plate que no es el del clip.
    """
    if not path:
        return None
    normalizada = re.sub(r"[\\/]+", "/", str(path))
    return plate_and_version(os.path.basename(normalizada))[0]


def pick_amf_for_plate(look_dir, plate):
    """El .amf que le corresponde a ese plate, o None si no hay ninguno.

    El .amf del plate del clip, en su version mas alta. Si el shot no trae uno
    para ese plate -o el clip no es un plate, como un _comp-, se cae al
    PLATE_POR_DEFECTO. Si tampoco esta, el primero de la carpeta, que es el
    comportamiento que habia antes de resolver por plate.

    Hace falta porque un shot trae un .amf por plate y cada plate tiene su
    propio grade: quedarse con el primero le pone a un clip de cbPlate el
    grade del aPlate.
    """
    amfs = [p for p in _archivos_de(look_dir) if p.lower().endswith(".amf")]
    if not amfs:
        return None

    por_plate = {}
    for path in amfs:
        nombre_plate, version = plate_and_version(os.path.basename(path))
        if nombre_plate is None:
            continue
        anterior = por_plate.get(nombre_plate)
        if anterior is None or version > anterior[0]:
            por_plate[nombre_plate] = (version, path)

    for buscado in (plate, PLATE_POR_DEFECTO):
        if buscado and buscado in por_plate:
            return por_plate[buscado][1]
    return amfs[0]


def sibling_look_file(amf_path, extension):
    """El hermano del .amf: mismo nombre base, otra extension.

    Es la unica forma precisa de resolver el .cdl cuando el shot trae varios
    plates: elegido el .amf del cbPlate, su grade es el .cdl del cbPlate y no
    'el primer .cdl de la carpeta'. La comparacion ignora mayusculas porque hay
    carpetas donde el .amf dice 'cbPLATE' y el .cdl 'cbPlate'.
    """
    if not amf_path:
        return None
    buscado = os.path.basename(os.path.splitext(amf_path)[0] + extension).lower()
    for path in _archivos_de(os.path.dirname(amf_path)):
        if os.path.basename(path).lower() == buscado:
            return path
    return None


def find_look_file(look_dir, extension, quiet=False):
    """El unico archivo de esa extension en la carpeta de look.

    Los nombres no siempre vienen bien armados, asi que no se filtra por
    nombre: se busca por extension y se espera que haya uno solo.

    PENDIENTE: si hay mas de uno hay que mostrar un cartel. Por ahora avisa
    por consola y devuelve el primero, para no frenar el resto del flujo.
    """
    if not look_dir:
        return None

    candidates = [
        path for path in _archivos_de(look_dir)
        if path.lower().endswith(extension)
    ]

    if not candidates:
        if not quiet:
            debug_print(f"  [ERROR] No hay ningun '*{extension}' en {look_dir}")
        return None

    if len(candidates) > 1:
        debug_print(f"  [AVISO] Hay {len(candidates)} archivos '{extension}', deberia haber uno solo:")
        for path in candidates:
            debug_print(f"      - {os.path.basename(path)}")
        debug_print(f"  [AVISO] Por ahora se usa: {os.path.basename(candidates[0])}")

    return candidates[0]


def read_cccid(cdl_path):
    """Atributo id del primer <ColorCorrection> del .cdl.

    Es lo que el OCIOCDLTransform espera en el knob cccid para elegir que
    correccion aplicar dentro del archivo. No se arma con el nombre del clip:
    el archivo puede tener otra version que la media (v001 contra V002).
    """
    try:
        root = ET.parse(cdl_path).getroot()
    except Exception as e:
        debug_print(f"  [WARN] No se pudo parsear el .cdl: {e}")
        return None

    ids = [
        element.get("id")
        for element in root.iter()
        if _local_tag(element) == "ColorCorrection" and element.get("id")
    ]

    if not ids:
        debug_print("  [WARN] El .cdl no declara ningun ColorCorrection id")
        return None

    if len(ids) > 1:
        debug_print(f"  [INFO] El .cdl tiene {len(ids)} ids, se usa el primero: {ids}")
    return ids[0]


# ============================
# .cube como look del shot
# ============================


def parse_lut_name(basename):
    """(nombre sin version, version) de un .cube, o (None, None) si no trae.

    A diferencia de un .amf, el token que precede a '_vNNN' NO identifica un
    plate: en 'PROJA_Preview_LMT_v001.cube' y 'PROJA_Final_LMT_v001.cube' los
    dos terminan en 'LMT' y son LUT distintos. Por eso la clave de agrupado es el
    nombre ENTERO sin el '_vNNN' final: las versiones de un mismo LUT colapsan
    en una entrada y dos LUT distintos quedan separados.
    """
    stem = os.path.splitext(basename)[0]
    match = _LUT_VERSION_RE.match(stem)
    if not match:
        return None, None
    return match.group("base"), int(match.group("version"))


def pick_cube(look_dir):
    """El .cube del shot, o None si no hay. SIN cartel de eleccion.

    Se agrupa por nombre sin el '_vNNN' final y de cada LUT se queda la version
    mas alta. Si quedan varios LUT distintos no se pregunta -la tool procesa
    muchos clips de una vez, un cartel por clip es inviable-: se elige de forma
    determinista el ULTIMO por orden alfabetico y queda avisado en el log y en
    el RESUMEN. Los .cube sin '_vNNN' son cada uno su propio LUT.

    Es el LMT del shot, no de un plate: no se filtra por plate (igual que el
    .clf). Cacheado por carpeta, asi el aviso sale una sola vez por corrida.
    """
    if not look_dir:
        return None
    if look_dir in _CUBE_CACHE:
        return _CUBE_CACHE[look_dir]

    cubes = [
        p for p in _archivos_de(look_dir) if p.lower().endswith(CUBE_EXTENSION)
    ]
    elegido = None
    if cubes:
        por_lut = {}
        for path in cubes:
            nombre = os.path.basename(path)
            base, version = parse_lut_name(nombre)
            if base is None:
                clave, version = os.path.splitext(nombre)[0].lower(), -1
            else:
                clave = base.lower()
            anterior = por_lut.get(clave)
            if anterior is None or version > anterior[0]:
                por_lut[clave] = (version, path)

        ordenados = sorted(por_lut)
        elegido = por_lut[ordenados[-1]][1]
        debug_print(
            "  .cube encontrados    : %d (%d LUT distinto%s)"
            % (len(cubes), len(ordenados), "" if len(ordenados) == 1 else "s")
        )
        if len(ordenados) > 1:
            aviso = (
                "%d distintos .cube en %s: se usa '%s' (el ultimo por orden "
                "alfabetico, en su version mas alta); no se uso: %s"
                % (
                    len(ordenados),
                    LOOK_DIR_NAME,
                    os.path.basename(elegido),
                    ", ".join(os.path.basename(por_lut[c][1]) for c in ordenados[:-1]),
                )
            )
            debug_print("  [AVISO] " + aviso)
            _anotar_aviso_corrida(aviso)

    _CUBE_CACHE[look_dir] = elegido
    return elegido


def cube_working_space(cube_path):
    """Espacio de color en el que corre el .cube. Devuelve (espacio, origen).

    Un .cube no declara su espacio de entrada, asi que se lee del nombre
    (ACEScct, ACEScc, ACEScg, AP1, ACES2065, AP0, Linear; sin distinguir
    mayusculas ni exigir un separador concreto) y, sin pista, se asume
    CUBE_DEFAULT_SPACE. Si el nombre trae mas de un espacio ('ACEScg_to_ACEScct')
    gana el PRIMERO, que por convencion es el de entrada, y queda avisado en el
    log. El espacio devuelto es el nombre logico: configure_effect_node lo
    resuelve contra el config OCIO real.

    `origen` es 'nombre' o 'default', para el log.
    """
    stem = os.path.splitext(os.path.basename(cube_path))[0].lower()
    hallados = [m.group(1) for m in _CUBE_SPACE_RE.finditer(stem)]
    if not hallados:
        return CUBE_DEFAULT_SPACE, "default"

    espacios = []
    for pista in hallados:
        espacio = _CUBE_SPACE_HINTS[pista]
        if espacio not in espacios:
            espacios.append(espacio)
    if len(espacios) > 1:
        debug_print(
            "  [AVISO] El nombre del .cube menciona varios espacios (%s): "
            "se usa el primero." % ", ".join(espacios)
        )
    return espacios[0], "nombre"


def cube_spec(cube_path):
    """El .cube como eslabon LMT: un OCIOFileTransform con su working space."""
    espacio, origen = cube_working_space(cube_path)
    debug_print(
        "    [APLICAR] LUT -> %s (working space: %s, segun %s)"
        % (os.path.basename(cube_path), espacio, origen)
    )
    return {
        "type": "OCIOFileTransform",
        "file": re.sub(r"[\\/]+", "/", cube_path),
        "cccid": None,
        "working_space": espacio,
    }


# ============================
# Validacion del archivo de look
# ============================
#
# POR QUE existe: en NKS, EffectTrackItem.nodeHasError() devuelve False aunque el
# knob `file` apunte a un archivo que no existe (medido), asi que el
# "[WARN] El nodo quedo en error" no avisa nunca de lo mas comun. Y el knob
# ACEPTA cualquier ruta en setValue. Entonces el unico control confiable es mirar
# el archivo ANTES de crear el efecto: un efecto que no puede cargar su archivo
# no se crea, y el motivo sube al cartel final.


def _motivo_cube_invalido(path):
    """None si el .cube parece valido; si no, el motivo corto (en ingles).

    Chequeo estructural, no una validacion completa del formato: el header tiene
    que declarar LUT_1D_SIZE y/o LUT_3D_SIZE y tienen que estar todas las filas
    de datos (N para 1D, N^3 para 3D). OCIO rechaza un .cube sin tamano, con
    filas de menos Y con filas de mas (medido en NKS: 4^3 + 10 filas sobrantes
    dejan el nodo en error), y un nodo en error entrega negro. Las palabras
    clave desconocidas se ignoran: rechazarlas dejaria sin look a un archivo
    valido con una extension rara.
    """
    tam_1d = tam_3d = 0
    filas = 0
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            for linea in handle:
                texto = linea.strip()
                if not texto or texto.startswith("#"):
                    continue
                partes = texto.split()
                clave = partes[0].upper()
                if clave == "LUT_1D_SIZE" and len(partes) > 1:
                    tam_1d = int(partes[1])
                elif clave == "LUT_3D_SIZE" and len(partes) > 1:
                    tam_3d = int(partes[1])
                elif clave in (
                    "TITLE", "DOMAIN_MIN", "DOMAIN_MAX",
                    "LUT_1D_INPUT_RANGE", "LUT_3D_INPUT_RANGE",
                ):
                    continue
                elif len(partes) == 3:
                    # Una fila de datos son tres numeros. Cualquier otra linea
                    # (una palabra clave que no conocemos) se ignora: rechazarla
                    # dejaria sin look a un .cube valido con una extension rara.
                    try:
                        float(partes[0]), float(partes[1]), float(partes[2])
                    except ValueError:
                        continue
                    filas += 1
    except (ValueError, OSError):
        return "is not a valid .cube LUT"
    if tam_1d <= 0 and tam_3d <= 0:
        return "is not a valid .cube LUT (no LUT_1D_SIZE / LUT_3D_SIZE)"
    esperadas = (tam_1d if tam_1d > 0 else 0) + (tam_3d ** 3 if tam_3d > 0 else 0)
    if filas < esperadas:
        return "is truncated (%d of %d LUT rows)" % (filas, esperadas)
    if filas > esperadas:
        return "has extra data (%d LUT rows, expected %d)" % (filas, esperadas)
    return None


def motivo_archivo_inutil(path):
    """None si el archivo de look se puede cargar; si no, el motivo (en ingles).

    Mira, en orden: que exista, que se pueda leer, que no este vacio, y que su
    contenido tenga forma (.cube estructurado; .cdl y .clf como XML bien
    formado). Cacheado por ruta: veinte clips del mismo shot leen el archivo una
    sola vez, y los .cube grandes (65^3 son ~270k filas) no se releen.
    """
    if path in _VALIDACION_CACHE:
        return _VALIDACION_CACHE[path]

    nombre = os.path.basename(path)
    motivo = None
    if not os.path.isfile(path):
        motivo = "'%s' does not exist" % nombre
    else:
        vacio = False
        try:
            with open(path, "rb") as handle:
                handle.read(1)
            vacio = os.path.getsize(path) == 0
        except OSError:
            motivo = "'%s' cannot be read" % nombre
        if motivo is None and vacio:
            motivo = "'%s' is empty" % nombre
        if motivo is None:
            extension = os.path.splitext(path)[1].lower()
            if extension == CUBE_EXTENSION:
                detalle = _motivo_cube_invalido(path)
                if detalle:
                    motivo = "'%s' %s" % (nombre, detalle)
            elif extension in (CDL_EXTENSION, CLF_EXTENSION):
                try:
                    ET.parse(path)
                except Exception:
                    motivo = "'%s' is not valid XML" % nombre

    if motivo:
        debug_print("  [ERROR] Archivo de look inutilizable: %s" % motivo)
    _VALIDACION_CACHE[path] = motivo
    return motivo


# ============================
# Lectura del .amf
# ============================


def _target_space_from_transform_id(transform_id):
    """Espacio destino de un ACEScsc.

    'urn:ampas:aces:transformId:v1.5:ACEScsc.Academy.ACES_to_ACEScct.a1.0.3'
    devuelve 'ACEScct'.
    """
    if not transform_id:
        return None
    match = re.search(r"ACES_to_([A-Za-z0-9]+)", transform_id)
    return match.group(1) if match else None


def _target_space_from_description(description):
    """Espacio destino de una descripcion tipo 'ACES2065-1 to ACEScct'."""
    if not description or " to " not in description:
        return None
    return description.split(" to ")[-1].strip() or None


def _read_look_transform(element):
    """Interpreta un <lookTransform> del .amf.

    Devuelve un dict con lo que se pudo reconocer: si es el CDL (trae
    cdlWorkingSpace), si es un LMT de archivo (trae file), y si ya viene
    aplicado en el plate.
    """
    info = {
        "applied": (element.get("applied") or "").strip().lower() == "true",
        "description": None,
        "working_space": None,
        "file": None,
        "has_cdl": False,
    }

    for child in element.iter():
        tag = _local_tag(child)
        text = (child.text or "").strip() if child.text else ""

        if tag == "description" and not info["description"]:
            info["description"] = text
        elif tag == "file" and text:
            info["file"] = text
        elif tag in ("SOPNode", "SatNode", "SATNode", "cdlWorkingSpace"):
            info["has_cdl"] = True

    # El working space del CDL: se prefiere el transformId, que es estructurado.
    for child in element.iter():
        if _local_tag(child) != "toCdlWorkingSpace":
            continue
        for sub in child.iter():
            sub_tag = _local_tag(sub)
            sub_text = (sub.text or "").strip() if sub.text else ""
            if sub_tag == "transformId":
                info["working_space"] = _target_space_from_transform_id(sub_text)
            elif sub_tag == "description" and not info["working_space"]:
                info["working_space"] = _target_space_from_description(sub_text)

    return info


def read_amf(amf_path):
    """Lee el .amf y devuelve la lista de <lookTransform> en orden de cadena."""
    try:
        root = ET.parse(amf_path).getroot()
    except Exception as e:
        debug_print(f"  [WARN] No se pudo parsear el .amf: {e}")
        return []

    return [
        _read_look_transform(element)
        for element in root.iter()
        if _local_tag(element) == "lookTransform"
    ]


def build_effect_plan(look_dir, plate=None):
    """Arma la lista de efectos a crear, en orden.

    Con .amf: se respeta el orden y el applied de cada lookTransform, y se
    toman working space y nombre de archivo de ahi. Sin .amf: plan fijo por
    extension.

    `plate` es el plate del clip -'cbplate', 'aplate', None para un _comp- y
    decide CUAL .amf se lee. El resultado se cachea por (carpeta, plate):
    todos los clips de un mismo plate comparten plan, asi que el .amf se
    parsea una vez y no una por clip.
    """
    clave = (look_dir, plate)
    if clave in _PLAN_CACHE:
        return _PLAN_CACHE[clave]
    plan = _build_effect_plan_sin_cache(look_dir, plate)
    _PLAN_CACHE[clave] = plan
    return plan


def _build_effect_plan_sin_cache(look_dir, plate):
    """El trabajo real de build_effect_plan. Ver el cache alla."""
    amf_path = pick_amf_for_plate(look_dir, plate)
    if not amf_path:
        debug_print("  [AVISO] El shot no trae .amf: se usa el plan fijo por extension.")
        return _fallback_plan(look_dir)

    elegido = plate_from_path(amf_path)
    if plate and elegido and elegido != plate:
        debug_print(
            f"  [AVISO] El shot no trae .amf para '{plate}': se usa el de "
            f"'{elegido}'"
        )
    debug_print(f"  plate del clip       : {plate or '<no es un plate>'}")
    debug_print(f"  amf                  : {amf_path}")
    look_transforms = read_amf(amf_path)
    if not look_transforms:
        debug_print("  [AVISO] El .amf no declara lookTransform: se usa el plan fijo.")
        return _fallback_plan(look_dir)

    plan = []
    for index, info in enumerate(look_transforms, start=1):
        etiqueta = info["description"] or "<sin descripcion>"

        if info["applied"]:
            debug_print(f"    {index}. [YA APLICADO] {etiqueta}")
            continue

        if info["has_cdl"]:
            # El grade es el del .amf elegido, no 'el primer .cdl'. Con varios
            # plates en la carpeta esa diferencia es el grade de otra toma.
            cdl_path = sibling_look_file(amf_path, ".cdl")
            if not cdl_path:
                # Sin hermano se acepta un .cdl suelto SOLO si hay uno solo en
                # la carpeta: ahi el nombre no sigue la convencion pero no hay
                # ambiguedad. Con varios y ninguno hermano, elegir "el primero"
                # es volver a mezclar el grade de otra toma, que es justo lo que
                # este cambio arregla. Se prefiere avisar y no crear el CDL.
                sueltos = [
                    p for p in _archivos_de(look_dir) if p.lower().endswith(".cdl")
                ]
                if len(sueltos) == 1:
                    cdl_path = sueltos[0]
                    debug_print(
                        f"    {index}. [AVISO] El .amf no tiene un .cdl hermano; "
                        f"se usa el unico de la carpeta: {os.path.basename(cdl_path)}"
                    )
                elif sueltos:
                    debug_print(
                        f"    {index}. [ERROR] El .amf no tiene un .cdl hermano y hay "
                        f"{len(sueltos)} .cdl en la carpeta: no se puede saber cual es "
                        f"el de este plate"
                    )
                    # Sin continue, abajo se avisaria "no hay .cdl en la
                    # carpeta", que es mentira: hay, y ese es el problema.
                    continue
            if not cdl_path:
                debug_print(f"    {index}. [ERROR] El .amf pide un CDL y no hay .cdl en la carpeta")
                continue
            debug_print(
                f"    {index}. [APLICAR] CDL -> {os.path.basename(cdl_path)} "
                f"(working space: {info['working_space'] or 'sin declarar'})"
            )
            plan.append(
                {
                    "type": "OCIOCDLTransform",
                    "file": cdl_path,
                    "cccid": read_cccid(cdl_path),
                    "working_space": info["working_space"] or AMF_WORKING_SPACE,
                }
            )
            continue

        if info["file"]:
            # El .amf nombra el archivo; se resuelve contra la carpeta de look.
            lmt_path = os.path.join(look_dir, info["file"])
            if not os.path.isfile(lmt_path):
                debug_print(
                    f"    {index}. [AVISO] El .amf nombra '{info['file']}' y no esta en la carpeta"
                )
                extension_lmt = os.path.splitext(info["file"])[1].lower()
                if extension_lmt == CUBE_EXTENSION:
                    # Para un .cube la eleccion es la determinista de pick_cube
                    # (version mas alta, ultimo alfabetico) y no "el primero".
                    lmt_path = pick_cube(look_dir)
                else:
                    lmt_path = find_look_file(look_dir, extension_lmt)
                if not lmt_path:
                    debug_print(f"    {index}. [ERROR] Tampoco hay otro archivo de esa extension")
                    continue
            lmt_path = re.sub(r"[\\/]+", "/", lmt_path)
            espacio_lmt = info["working_space"] or AMF_WORKING_SPACE
            debug_print(
                f"    {index}. [APLICAR] LMT -> {os.path.basename(lmt_path)} "
                f"(working space: {espacio_lmt})"
            )
            plan.append(
                {
                    "type": "OCIOFileTransform",
                    "file": lmt_path,
                    "cccid": None,
                    "working_space": info["working_space"] or AMF_WORKING_SPACE,
                }
            )
            continue

        # Transforms que el .amf declara solo por transformId (built-in del
        # config OCIO, sin archivo). No se pueden cargar en un nodo de archivo.
        debug_print(f"    {index}. [SALTEADO] Sin archivo asociado: {etiqueta}")

    return plan


def _fallback_plan(look_dir):
    """Plan fijo por extension, para shots sin .amf.

    El plan es el .cdl suelto (si hay) y despues UN LMT: el .clf si existe y,
    si no, el .cube. Con .cdl y .cube se aplican los dos (decision de Lega).
    Nunca .clf y .cube juntos: son ambos el LMT del shot, y aplicar los dos
    dobla el look. Si estan los dos gana el .clf y el .cube queda avisado.

    Sin .amf el unico working space que se puede afirmar es el del .clf: un LMT
    de ACES entra y sale en ACES2065-1 por convencion, y el archivo mismo lo
    declara. El del .cube sale del nombre (ver cube_working_space). El del .cdl
    queda sin tocar a proposito: un .cdl suelto puede estar hecho para ACEScct,
    ACEScc o lineal, y no hay de donde saberlo. Adivinarlo seria peor que dejar
    el default y que el log lo diga.
    """
    plan = []

    cdl_path = find_look_file(look_dir, CDL_EXTENSION, quiet=True)
    if cdl_path:
        plan.append(
            {
                "type": "OCIOCDLTransform",
                "file": cdl_path,
                "cccid": read_cccid(cdl_path),
                "working_space": None,
            }
        )

    clf_path = find_look_file(look_dir, CLF_EXTENSION, quiet=True)
    cube_path = pick_cube(look_dir)
    if clf_path:
        plan.append(
            {
                "type": "OCIOFileTransform",
                "file": clf_path,
                "cccid": None,
                "working_space": AMF_WORKING_SPACE,
            }
        )
        if cube_path:
            aviso = (
                "Look_Files trae .clf y .cube, los dos son el LMT: se usa el "
                ".clf y el .cube queda sin aplicar (%s)" % os.path.basename(cube_path)
            )
            debug_print("  [AVISO] " + aviso)
            _anotar_aviso_corrida(aviso)
    elif cube_path:
        plan.append(cube_spec(cube_path))

    if not plan:
        debug_print(
            "  [ERROR] No hay ningun '*.cdl', '*.clf' ni '*.cube' en %s" % look_dir
        )
    return plan


# ============================
# Soft effects
# ============================


def _guid(obj):
    """guid() del objeto, para comparar identidad entre dos barridos distintos."""
    try:
        return obj.guid()
    except Exception:
        return None


def _node_class(effect):
    """Clase del nodo de un EffectTrackItem ('OCIOCDLTransform', ...)."""
    node = _safe_call(effect, "node", None)
    try:
        return node.Class() if node else None
    except Exception:
        return None


def _node_file(effect):
    """Valor del knob file, para poder mostrar a que archivo apunta el efecto."""
    node = _safe_call(effect, "node", None)
    if not node:
        return None
    try:
        return node["file"].value()
    except Exception:
        return None


def _sub_track_index(effect):
    """subTrackIndex() del efecto, o None si no se puede leer."""
    try:
        indice = effect.subTrackIndex()
    except Exception:
        return None
    return indice if isinstance(indice, int) and indice >= 0 else None


def scan_clip_effects(track_item):
    """Todos los soft effects que afectan al clip, con como fueron encontrados.

    Hay dos formas de que un efecto quede sobre un clip y solo una figura en
    linkedItems():

      - LINKEADO: creado con createEffect(trackItem=...). Se mueve con el clip.
      - SUELTO: creado con timelineIn/timelineOut, o arrastrado a mano en la
        UI. Vive en un subtrack del track y afecta al clip por solaparse en
        tiempo, pero el clip no sabe nada de el.

    Si solo miraramos linkedItems(), un efecto hecho a mano no se veria y el
    boton crearia un duplicado encima.

    Devuelve una lista de dicts con effect, class, linked, same_range, in, out
    y file.
    """
    resultado = []
    vistos = set()

    try:
        clip_in = track_item.timelineIn()
        clip_out = track_item.timelineOut()
    except Exception as e:
        debug_print(f"  [WARN] No se pudo leer el rango del clip: {e}")
        clip_in = clip_out = None

    def _agregar(effect, linked):
        guid = _guid(effect)
        if guid is not None and guid in vistos:
            return
        if guid is not None:
            vistos.add(guid)
        try:
            efecto_in = effect.timelineIn()
            efecto_out = effect.timelineOut()
        except Exception:
            efecto_in = efecto_out = None
        resultado.append(
            {
                "effect": effect,
                "class": _node_class(effect),
                "linked": linked,
                "same_range": (
                    clip_in is not None
                    and efecto_in == clip_in
                    and efecto_out == clip_out
                ),
                "in": efecto_in,
                "out": efecto_out,
                "file": _node_file(effect),
                "sub": _sub_track_index(effect),
            }
        )

    # 1. Los linkeados al clip.
    try:
        for item in track_item.linkedItems():
            if isinstance(item, hiero.core.EffectTrackItem):
                _agregar(item, linked=True)
    except Exception as e:
        debug_print(f"  [WARN] No se pudo leer linkedItems(): {e}")

    # 2. Los sueltos del track que se solapan en tiempo con el clip.
    track = track_item.parent()
    if track and clip_in is not None:
        try:
            sub_tracks = track.subTrackItems()
        except Exception as e:
            debug_print(f"  [WARN] No se pudo leer subTrackItems(): {e}")
            sub_tracks = ()

        for sub_track in sub_tracks:
            items = sub_track if isinstance(sub_track, (list, tuple)) else [sub_track]
            for item in items:
                if not isinstance(item, hiero.core.EffectTrackItem):
                    continue
                try:
                    if item.timelineIn() <= clip_out and item.timelineOut() >= clip_in:
                        _agregar(item, linked=False)
                except Exception:
                    continue

    return resultado


def report_clip_effects(efectos):
    """Vuelca lo que hay sobre el clip antes de tocar nada."""
    if not efectos:
        debug_print("  [EFECTOS EN EL CLIP] ninguno")
        return

    debug_print(f"  [EFECTOS EN EL CLIP] {len(efectos)}")
    for info in efectos:
        origen = "linkeado" if info["linked"] else "suelto en el track"
        rango = f"{info['in']}-{info['out']}"
        exacto = "" if info["same_range"] else " (otro rango que el clip)"
        debug_print(
            f"      {info['class'] or '<sin nodo>':<20} {origen:<18} {rango}{exacto}"
        )
        if info["file"]:
            debug_print(f"      {'':<20} file: {info['file']}")


def find_existing_effect(efectos, effect_type):
    """El efecto de ese tipo que ya esta sobre el clip, o None.

    Cuenta como propio del clip el que esta linkeado y el que cubre exactamente
    su rango. Uno que solapa parcial se reporta pero no bloquea: puede ser un
    grade que abarca varios clips del track y no tiene por que ser este.

    Y ademas tiene que ser NUESTRO, o sea cargar un archivo de Look_Files (ver
    _apunta_al_look). Un OCIOFileTransform o un OCIOCDLTransform que el artista
    puso a mano, con un archivo de otra carpeta, ya NO hace saltear la creacion:
    antes el LMT del shot no entraba si el clip tenia cualquier otro
    OCIOFileTransform. Lo ajeno no se toca (ni se borra, ni se pisa, ver
    subtracks_para_la_cadena) pero tampoco bloquea el look del shot.
    """
    for info in efectos:
        if info["class"] != effect_type:
            continue
        if not (info["linked"] or info["same_range"]):
            continue
        if _apunta_al_look(info):
            return info
    return None


def subtracks_para_la_cadena(efectos, cantidad):
    """Los `cantidad` subtracks CONTIGUOS donde va la cadena de look del clip.

    POR QUE: createEffect(subTrackIndex=N) sobre un subtrack ocupado en el mismo
    rango BORRA el efecto que estaba (medido: Blur en sub 0 + crear el CDL en
    sub 0 deja el Blur invalido, y no avisa). Con la cadena en posiciones
    fijas (0, 1) la tool se llevaba puesto el trabajo del artista.

    CRITERIO: la cadena (CDL + LMT) es un BLOQUE, y un efecto del artista no
    puede quedar partiendola por el medio. Va en subtracks consecutivos que
    empiezan en el primero POR ENCIMA del mas alto ocupado por cualquier efecto
    que solape el clip (nuestro o ajeno), o en 0 si no hay ninguno. Medido en
    NKS: el subtrack mas BAJO se aplica primero y los huecos no cambian nada,
    asi que la cadena queda aplicada DESPUES de todo lo que ya habia, el CDL
    antes que el LMT:

        sin ajenos        -> 0, 1      (igual que siempre)
        ajeno en 0        -> 1, 2
        Blur 0 + Text 1   -> 2, 3
        ajeno solo en 1   -> 2, 3      (no 0 y 2: partiria la cadena)

    Los huecos que dejen los ajenos por debajo no se usan: llenarlos es lo que
    intercalaba el efecto del artista entre el CDL y el LMT.

    Devuelve None si algun efecto no dice en que subtrack esta: no se puede
    saber que esta libre y es mejor no crear que pisar.
    """
    ocupados = []
    for info in efectos:
        if info.get("sub") is None:
            return None
        ocupados.append(info["sub"])
    inicio = max(ocupados) + 1 if ocupados else 0
    return list(range(inicio, inicio + cantidad))


def create_effect_on_track_item(track_item, effect_type, sub_track_index):
    """Crea un soft effect linkeado al TrackItem. Devuelve el EffectTrackItem o None.

    `sub_track_index` NO es opcional a proposito. La doc de createEffect dice:
    "subTrackIndex - if specified, will be placed on the appropriate sub-track,
    otherwise will be placed on a NEW sub-track". O sea que sin pasarlo, CADA
    llamada abre un subtrack nuevo en vez de reusar el que ya esta.

    Eso dejaba un hueco VERTICAL en el track: el primer clip con AMF ocupaba
    los subtracks 0 y 1, y el segundo clip -que en s0 y s1 tiene lugar libre,
    porque los del primero estan en otro rango de tiempo- se iba igual a s1 y
    s2, dejando s0 vacio debajo de sus efectos. Se veia como una franja muerta
    entre el clip y sus propios efectos, y crecia con cada clip.

    Pasando el indice, la cadena queda pegada al clip. El indice no es fijo: es
    un subtrack LIBRE del clip (subtracks_para_la_cadena), porque crear sobre uno
    ocupado borra el efecto que estaba. Sin efectos ajenos son el 0 y el 1.
    """
    track = track_item.parent()
    if not track:
        debug_print("    [ERROR] El clip no tiene track padre.")
        return None

    if not hasattr(track, "createEffect"):
        debug_print("    [ERROR] El track no expone createEffect(). Version de Hiero muy vieja.")
        return None

    # Intento 1: linkeado al trackItem (hereda el timing del clip).
    try:
        effect = track.createEffect(
            effectType=effect_type,
            trackItem=track_item,
            subTrackIndex=sub_track_index,
        )
        if effect:
            debug_print(
                f"    [OK] Creado y linkeado: {_safe_name(effect)} (subtrack {sub_track_index})"
            )
            return effect
        debug_print("    [WARN] createEffect() devolvio None con trackItem.")
    except Exception as e:
        debug_print(f"    [ERROR] Fallo createEffect() con trackItem: {e}")
        debug_print(traceback.format_exc())

    # Intento 2: por timing explicito, como hace LGA_NKS_FrameNumber_Create.
    timeline_in = _safe_call(track_item, "timelineIn", None)
    timeline_out = _safe_call(track_item, "timelineOut", None)
    try:
        effect = track.createEffect(
            effectType=effect_type,
            timelineIn=timeline_in,
            timelineOut=timeline_out,
            subTrackIndex=sub_track_index,
        )
        if effect:
            debug_print(f"    [OK] Creado (sin linkear): {_safe_name(effect)}")
            return effect
        debug_print("    [WARN] createEffect() devolvio None tambien con timing explicito.")
    except Exception as e:
        debug_print(f"    [ERROR] Fallo createEffect() con timing explicito: {e}")
        debug_print(traceback.format_exc())

    return None


def _set_knob(node, knob_name, value):
    """setValue con log. True si se pudo."""
    try:
        node[knob_name].setValue(value)
        debug_print(f"    [OK] {knob_name} = {value!r}")
        return True
    except Exception as e:
        debug_print(f"    [ERROR] No se pudo setear {knob_name}: {e}")
        return False


def match_colorspace_option(node, knob_name, wanted):
    """Encuentra en el enum del knob la opcion que corresponde a `wanted`.

    El nombre exacto del espacio depende del OCIO config del proyecto: el
    mismo ACEScct puede figurar como 'ACEScct' o 'ACES - ACEScct'. Por eso no
    se hardcodea el string, se busca contra las opciones reales del knob.

    Cada opcion del enum de Nuke 17 trae el nombre del colorspace seguido de
    campos separados por TAB: en aces_1.2 'ACES - ACEScct<TAB>Colorspaces/ACES/
    ACES - ACEScct', y en los configs v2 de Foundry (fn-nuke_cg-config-v2.2.0_
    aces-v1.3, studio v2.2.0, los v3.0.0 de ACES 2.0) 'ACEScct<TAB>Colorspaces/
    ACES/ACEScct<TAB><TAB>ACES - ACEScct,acescct_ap1'. El knob ACEPTA la cadena
    entera, pero con los configs v2 el nodo queda con error y el look no se
    aplica, sin ningun aviso. Lo valido es SOLO el primer campo, asi que se
    matchea contra el y se devuelve ese.
    """
    if not wanted:
        return None

    try:
        options = list(node[knob_name].values())
    except Exception as e:
        debug_print(f"    [WARN] No se pudieron leer las opciones de {knob_name}: {e}")
        return None

    target = _normalize(wanted)

    # Cada opcion es (cadena entera, nombre corto). El nombre corto es lo que va
    # antes del primer TAB; sin TAB (otras versiones de Nuke) es la cadena entera
    # y todo sigue como antes. Se matchea contra el nombre corto y no contra la
    # cadena larga: esa trae la ruta y los alias del colorspace, y 'acescc'
    # aparece adentro de los de 'ACEScct'. Se DEVUELVE el corto.
    pares = [(str(o), str(o).split("\t")[0]) for o in options]

    # Los alias van al final. aces_1.2 trae una familia 'Utility/Aliases' con
    # nombres en minuscula ('acescct', 'acescg'...) que son colorspaces validos
    # pero no son el nombre del espacio: con el matcheo por nombre corto ganarian
    # por igualdad exacta y el nodo quedaria con 'acescct' en vez de
    # 'ACES - ACEScct'. Solo se usan si nada mas sirve.
    sin_alias = [par for par in pares if "/aliases/" not in par[0].lower()]

    # Tres pasadas: primero los espacios nombrados DIRECTO (sin alias), despues
    # los demas sin alias, y recien al final todo. Los ROLES del config aparecen
    # como 'scene_linear (ACES - ACEScg)' y son una INDIRECCION: pidiendo
    # ACES2065-1 matchean 'ACES - ACES2065-1' y 'default (ACES - ACES2065-1)', y
    # cual gana depende del orden del enum. La segunda pasada no es un adorno:
    # hay colorspaces directos con parentesis en su propio nombre -en aces_1.2
    # hay 34, del tipo 'Input - ARRI - V3 LogC (EI160) - Wide Gamut'-, y
    # descartarlos de una dejaria sin resolver a quien pida uno de esos. Un rol
    # o un alias solo gana si NADA directo sirve.
    directas = [par for par in sin_alias if "(" not in par[1]]

    for candidatas in (directas, sin_alias, pares):
        # De mas estricto a mas laxo. El orden importa: buscando 'ACEScc'
        # primero por igualdad y sufijo se evita que matchee 'ACEScct' por
        # contencion.
        for _entera, corto in candidatas:
            if _normalize(corto) == target:
                return corto
        for _entera, corto in candidatas:
            if _normalize(corto).endswith(target):
                return corto
        for _entera, corto in candidatas:
            if target in _normalize(corto):
                return corto

    debug_print(f"    [WARN] '{wanted}' no figura entre las opciones de {knob_name}")
    return None


def configure_effect_node(node, spec):
    """Carga el archivo de look y los parametros del .amf en el nodo.

    Devuelve (ok, motivo), donde `motivo` es el texto para el cartel del
    usuario cuando algo quedo mal, o None si salio todo bien.
    """
    if not node:
        debug_print("    [ERROR] El efecto no tiene nodo.")
        return False, "the effect has no node"

    effect_type = spec["type"]
    ok = True
    motivo = None

    if effect_type == "OCIOCDLTransform":
        # read_from_file va PRIMERO: con el knob en False, file y cccid quedan
        # deshabilitados y el nodo ignora el archivo.
        ok &= _set_knob(node, "read_from_file", True)
        ok &= _set_knob(node, "file", spec["file"])
        if spec.get("cccid"):
            ok &= _set_knob(node, "cccid", spec["cccid"])
        else:
            debug_print("    [WARN] Sin cccid: el nodo toma la primera correccion del archivo.")
    else:
        ok &= _set_knob(node, "file", spec["file"])
    debug_print("    [ESTADO] con el archivo cargado : %s" % _estado_error(node))

    # El working space sale del .amf, o de AMF_WORKING_SPACE si el .amf no lo
    # declara. El default del nodo, `scene_linear`, es un rol que en los configs
    # ACES cae en ACEScg: no es el espacio en el que corre la cadena.
    wanted = spec.get("working_space")
    if wanted:
        opcion = match_colorspace_option(node, "working_space", wanted)
        if opcion:
            ok &= _set_knob(node, "working_space", opcion)
            debug_print("    [ESTADO] con el working space   : %s" % _estado_error(node))
        else:
            # NO es cosmetico y no puede pasar en silencio: el nodo se queda en
            # `scene_linear`, que en los configs ACES es ACEScg, y el archivo de
            # look termina corriendo sobre el gamut equivocado. El efecto queda
            # creado pero MAL, asi que cuenta como error y sube al cartel. Un
            # resultado incorrecto informado como "creado" es el peor final.
            debug_print(
                f"    [ERROR] El OCIO config del proyecto no expone '{wanted}': "
                f"el working_space queda en el default del nodo y el look sale mal."
            )
            motivo = f"the project OCIO config has no '{wanted}' colorspace"
            ok = False

    return ok, motivo


def print_node_knobs(node, titulo):
    """Vuelca los knobs del nodo. Sirve para ver que queda por configurar."""
    if not node:
        return
    try:
        knobs = node.knobs()
    except Exception as e:
        debug_print(f"    [WARN] No se pudieron leer los knobs: {e}")
        return

    debug_print(f"    [KNOBS DE {titulo}] ({len(knobs)} en total)")
    for knob_name in sorted(knobs.keys()):
        try:
            value = knobs[knob_name].value()
        except Exception as e:
            value = f"<no legible: {e}>"
        try:
            knob_class = knobs[knob_name].Class()
        except Exception:
            knob_class = "?"
        debug_print(f"      {knob_name:<26} [{knob_class}] = {value!r}")


def verify_node(node, effect_type):
    """Relee los knobs que nos importan para confirmar que quedo lo que queriamos."""
    if not node:
        return
    if effect_type == "OCIOCDLTransform":
        knob_names = ("read_from_file", "file", "cccid", "working_space", "slope", "offset", "power", "saturation")
    else:
        knob_names = ("file", "working_space", "direction", "interpolation")

    debug_print("    [VERIFICACION]")
    for knob_name in knob_names:
        try:
            debug_print(f"      {knob_name:<16} = {node[knob_name].value()!r}")
        except Exception as e:
            debug_print(f"      {knob_name:<16} = <no legible: {e}>")


def _node_has_error(node, effect):
    """True si Node.hasError() marca el nodo del efecto. Es un DATO, no un veredicto.

    Sirve para el log y nada mas: NO alcanza para decir que el efecto esta roto.
    hasError() valida el nodo contra el color management de nuke.root(), y en NKS
    ese no tiene por que ser el del proyecto. Con un working space que el config
    de nuke.root() no tiene, hasError() da True ('Invalid input LUT selected')
    con el archivo bien cargado: medido en Nuke 16 y 17, y visto en una sesion
    real de NKS 16 con un .cdl y un .clf validos. Ver Docu_ApplyAMF_NKS.md.

    EffectTrackItem.nodeHasError() queda de respaldo solo si el nodo no se puede
    consultar: en NKS devuelve False hasta con un archivo inexistente.
    """
    if node is not None:
        try:
            return bool(node.hasError())
        except Exception as e:
            debug_print("    [WARN] No se pudo leer Node.hasError(): %s" % e)
    return _safe_call(effect, "nodeHasError", False) is True


def _estado_error(node, effect=None):
    """Los indicadores de error del nodo en una linea, para el log.

    Se loguean por ETAPA (recien creado, con el archivo, con el working space):
    es lo que deja ver QUE knob dispara el error sin tener que armar otra sonda.
    """
    partes = []
    for nombre in ("hasError", "error"):
        try:
            partes.append("%s=%s" % (nombre, getattr(node, nombre)()))
        except Exception as e:
            partes.append("%s=<%s>" % (nombre, e))
    if effect is not None:
        partes.append("nodeHasError=%s" % _safe_call(effect, "nodeHasError"))
    return " ".join(partes)


def _log_contexto_color(project):
    """Vuelca al log el color management de nuke.root() y el del proyecto.

    Son DOS cosas distintas en NKS y Node.hasError() mira la primera: cuando no
    coinciden, un efecto sano figura con error. Va una vez por corrida.
    """
    debug_print("  [COLOR] de nuke.root() y del proyecto:")
    try:
        import nuke

        debug_print("    nuke                 : %s" % nuke.NUKE_VERSION_STRING)
        root = nuke.root()
        for knob_name in (
            "colorManagement", "OCIO_config", "customOCIOConfigPath", "workingSpaceLUT",
        ):
            try:
                debug_print("    root.%-15s : %r" % (knob_name, root[knob_name].value()))
            except Exception as e:
                debug_print("    root.%-15s : <no legible: %s>" % (knob_name, e))
    except Exception as e:
        debug_print("    [WARN] No se pudo leer nuke.root(): %s" % e)
    for metodo in (
        "ocioConfigName", "ocioConfigPath", "useOCIOEnvironmentOverride",
        "lutSettingWorkingSpace",
    ):
        debug_print("    proyecto.%-28s : %r" % (metodo + "()", _safe_call(project, metodo)))
    debug_print("    env OCIO             : %r" % os.environ.get("OCIO"))


def apply_effect(track_item, spec, efectos_existentes, sub_track_index, fallos=None, shot=None):
    """Crea el soft effect si falta. Devuelve 'creado', 'salteado' o 'error'.

    `sub_track_index` es un subtrack LIBRE del clip (ver subtracks_para_la_cadena) y se
    usa tal cual. Es None cuando el efecto ya existe y se va a saltear.
    """
    effect_type = spec["type"]
    debug_print(f"\n  --- {effect_type} ---")

    if SKIP_IF_EXISTS:
        existente = find_existing_effect(efectos_existentes, effect_type)
        if existente:
            origen = "linkeado" if existente["linked"] else "suelto en el track"
            debug_print(
                f"    [SALTEADO] El clip ya tiene un {effect_type} ({origen}): "
                f"'{_safe_name(existente['effect'])}'"
            )
            if existente["file"]:
                debug_print(f"               apunta a: {existente['file']}")
            return "salteado"

    debug_print(f"    archivo   : {spec['file']}")
    if spec.get("cccid"):
        debug_print(f"    cccid     : {spec['cccid']}")

    effect = create_effect_on_track_item(track_item, effect_type, sub_track_index)
    if not effect:
        return "error"

    debug_print(f"    subTrackIndex : {_safe_call(effect, 'subTrackIndex')}")
    debug_print(f"    timelineIn/Out: {_safe_call(effect, 'timelineIn')} / {_safe_call(effect, 'timelineOut')}")

    node = _safe_call(effect, "node", None)
    debug_print("    [ESTADO] recien creado          : %s" % _estado_error(node, effect))
    ok, motivo = configure_effect_node(node, spec)
    if motivo and fallos is not None and shot:
        _anotar_fallo(fallos, shot, motivo)

    # El OCIOFileTransform todavia no esta afinado: mostramos todos sus knobs
    # para decidir que mas hay que setear (direction, interpolation...).
    if effect_type == "OCIOFileTransform":
        print_node_knobs(node, effect_type)
    else:
        verify_node(node, effect_type)

    # Node.hasError() se LOGUEA y no decide nada: el efecto queda puesto. Sacarlo
    # por este dato fue el bug de la v0.93 -hasError() da True con un archivo
    # sano cuando el working space no figura en el config de nuke.root(), ver
    # _node_has_error-, y dejaba la tool sin aplicar nada. El archivo ya paso
    # motivo_archivo_inutil antes de crear el efecto, que es el control que vale.
    if _node_has_error(node, effect):
        debug_print(
            "    [WARN] Node.hasError() marca el nodo con '%s' cargado (%s). El efecto "
            "se deja: mirar los [ESTADO] de arriba y el [COLOR] de la corrida; si "
            "el clip sale negro en el viewer, el error es real."
            % (os.path.basename(str(spec["file"])), _estado_error(node, effect))
        )

    return "creado" if ok else "error"


# ============================
# Borrado (la otra mitad del toggle)
# ============================


def _remove_options():
    """La opcion que impide que borrar el efecto se lleve puesto el CLIP.

    Esto NO es defensivo de mas: los efectos de esta tool se crean con
    createEffect(trackItem=...), o sea LINKEADOS al clip, y
    removeSubTrackItem por defecto borra tambien lo linkeado. Sin esta
    opcion, apretar el boton para sacar los efectos borraria el clip del
    timeline.

    Medido en +Building_Blocks/Hiero/Timeline/LGA_H-DeleteAll_TransformSoftEffects.py.

    Si la enum no esta (otra version de Hiero), se devuelve None y el
    borrado se CANCELA. No hay fallback a removeSubTrackItem(effect) a
    secas: ese "fallback" es justamente el accidente.
    """
    try:
        return hiero.core.TrackBase.RemoveItemOptions.eDontRemoveLinkedItems
    except Exception as e:
        debug_print("  [ERROR] No se pudo obtener eDontRemoveLinkedItems: %s" % e)
        return None


def _apunta_al_look(info):
    """True si el efecto carga un archivo de la carpeta de look del shot.

    Es lo que distingue un efecto NUESTRO de uno que el usuario puso a
    mano: los que crea esta tool siempre quedan con el knob file apuntando
    a <shot>/_input/Look_Files/. Un OCIOCDLTransform que alguien agrego
    por su cuenta -para probar un grade, con el archivo vacio o con un
    .cdl de otro lado- no cae ahi.

    Sin esto alcanzaba con que la clase del nodo coincidiera, y el toggle
    borraba trabajo ajeno.

    Se prefirio esto antes que marcar los efectos propios con un tag: los
    timelines que ya existen tienen efectos creados por las versiones
    anteriores, sin tag, y una marca nueva los dejaria fuera del alcance
    del boton. La ruta, en cambio, ya esta puesta desde la v0.20.
    """
    ruta = info.get("file") or ""
    if not ruta:
        return False
    normalizada = re.sub(r"[\\/]+", "/", str(ruta)).lower()
    return ("/%s/" % LOOK_DIR_NAME.lower()) in normalizada


def collect_amf_effects(track_item):
    """Los efectos de ESTA tool que hay sobre el clip.

    Tres condiciones, y las tres tienen que darse:

      1. La clase del nodo es una de las que crea la tool.
      2. Esta linkeado al clip, o cubre exactamente su rango. Un efecto
         que solapa PARCIAL queda afuera a proposito: puede ser un grade
         que abarca varios clips del track.
      3. Apunta a la carpeta de look del shot (ver _apunta_al_look).

    La condicion 3 NO esta del lado de la creacion, y la asimetria es
    deliberada: para CREAR, un efecto ajeno de la misma clase igual
    cuenta y frena la creacion, porque apilar dos grades encima del
    mismo clip es peor que no hacer nada. Los dos lados erran hacia no
    tocar lo que el usuario puso a mano.
    """
    return [
        info
        for info in scan_clip_effects(track_item)
        if info["class"] in AMF_EFFECT_TYPES
        and (info["linked"] or info["same_range"])
        and _apunta_al_look(info)
    ]


def clip_has_amf(track_item):
    """True si el clip ya tiene al menos un efecto de la cadena AMF."""
    try:
        return bool(collect_amf_effects(track_item))
    except Exception as e:
        debug_print("  [WARN] No se pudo mirar '%s': %s" % (_safe_name(track_item), e))
        return False


def remove_amf_effects(track_items):
    """Saca la cadena AMF de todos los clips. Devuelve (borrados, errores).

    Los efectos se juntan primero y se borran despues, deduplicados por
    guid: un mismo efecto puede aparecer al mirar dos clips distintos, y
    borrarlo dos veces es un error garantizado.
    """
    opciones = _remove_options()
    if opciones is None:
        debug_print("[ERROR] Borrado cancelado: sin eDontRemoveLinkedItems se borraria el clip.")
        return 0, 1

    # guid -> (track, effect). El guid es lo unico que identifica al mismo
    # efecto encontrado desde dos clips.
    objetivo = {}
    for track_item in track_items:
        track = track_item.parent()
        if not track:
            continue
        for info in collect_amf_effects(track_item):
            effect = info["effect"]
            clave = _guid(effect)
            if clave is None:
                clave = id(effect)
            if clave not in objetivo:
                objetivo[clave] = (track, effect, info["class"])

    debug_print("\n  [A BORRAR] %d efecto(s)" % len(objetivo))

    borrados = 0
    errores = 0
    for track, effect, clase in objetivo.values():
        nombre = _safe_name(effect)
        try:
            track.removeSubTrackItem(effect, opciones)
            borrados += 1
            debug_print("    [OK] borrado %-20s %s" % (clase or "<sin nodo>", nombre))
        except Exception as e:
            errores += 1
            debug_print("    [ERROR] no se pudo borrar '%s': %s" % (nombre, e))
            debug_print(traceback.format_exc())

    return borrados, errores


# ============================
# Proceso por clip
# ============================


def _anotar_fallo(fallos, shot, motivo):
    """Registra el motivo por el que un shot no se pudo resolver.

    Un motivo que el shot YA tiene no se repite: si no hay Look_Files, todos
    sus clips van a fallar por lo mismo y verlo veinte veces no aporta nada.

    Los motivos DISTINTOS si se acumulan. Un mismo clip puede fallar por dos
    cosas a la vez -el config del proyecto sin ACEScct para el CDL y sin
    ACES2065-1 para el LMT- y quedarse solo con el primero esconde la mitad
    del problema. Los motivos posibles son un puñado fijo, asi que el cartel
    no crece sin control.
    """
    if not motivo:
        return
    anteriores = fallos.get(shot)
    if anteriores is None:
        fallos[shot] = motivo
    elif motivo not in anteriores.split("; "):
        # Se compara contra los motivos YA guardados, no como substring del
        # texto entero: un motivo que fuera pedazo de otro se perderia.
        fallos[shot] = "%s; %s" % (anteriores, motivo)


def _avisar_fallos(fallos, total_clips):
    """UN cartel al final con los shots que no se pudieron resolver.

    Uno solo y por shot, no por clip: con una seleccion de veinte clips de
    cinco shots, veinte carteles -o veinte lineas repetidas- no se leen.
    """
    if not fallos:
        return

    # El texto va en ingles, como todo lo visible del pack.
    plural = "s" if len(fallos) > 1 else ""
    lineas = [
        "Apply AMF could not apply everything on %d shot%s:" % (len(fallos), plural),
        "",
    ]
    MAX = 12
    for shot in sorted(fallos)[:MAX]:
        lineas.append("    %s  -  %s" % (shot, fallos[shot]))
    if len(fallos) > MAX:
        lineas.append("    ... and %d more" % (len(fallos) - MAX))
    lineas.append("")
    lineas.append(
        "The look files live in <shot>/%s/%s (.amf, .cdl, .clf and .cube)."
        % (INPUT_DIR_NAME, LOOK_DIR_NAME)
    )

    mensaje = "\n".join(lineas)
    debug_print("\n[AVISO AL USUARIO]\n" + mensaje)
    try:
        from LGA_NKS_Shared.LGA_NKS_MessageBox import show_warning

        show_warning(hiero.ui.mainWindow(), "Apply AMF", mensaje)
    except Exception as e:
        debug_print("[WARN] No se pudo mostrar el cartel: %s" % e)


def process_track_item(track_item, fallos):
    """Resuelve el look del clip y le crea los efectos que le falten.

    Devuelve un dict con cuantos quedaron creados, salteados y con error.

    Los motivos por los que un clip no se pudo resolver se anotan en
    `fallos`, indexados por SHOT y no por clip: un mismo shot suele tener
    clips en aPlate, bPlate y _comp_, y al usuario le sirve saber que le
    falta el look a ESE shot, no verlo repetido tres veces.
    """
    debug_print("\n" + "-" * 70)
    debug_print(f"[CLIP] {_safe_name(track_item)}")
    debug_print("-" * 70)

    resumen = {"creado": 0, "salteado": 0, "error": 0}

    track = track_item.parent()
    debug_print(f"  track                : {_safe_name(track) if track else '<sin track>'}")

    # Se mira que hay sobre el clip ANTES de tocar nada, asi el barrido no ve
    # los efectos que estamos por crear en esta misma pasada.
    efectos_existentes = scan_clip_effects(track_item)
    report_clip_effects(efectos_existentes)

    media_path = get_media_path(track_item)
    debug_print(f"  media                : {media_path}")
    if not media_path:
        _anotar_fallo(fallos, _safe_name(track_item), "the clip has no media on disk")
        resumen["error"] += 1
        return resumen

    shot_dir = resolve_shot_dir(media_path)
    debug_print(f"  shot dir             : {shot_dir}")
    if not shot_dir:
        debug_print("  [ERROR] No se pudo resolver la carpeta del shot.")
        _anotar_fallo(fallos, _safe_name(track_item), "could not resolve the shot folder")
        resumen["error"] += 1
        return resumen

    # De aca en adelante el fallo es DEL SHOT, no del clip.
    shot = os.path.basename(shot_dir.rstrip("/"))

    look_dir = resolve_look_dir(shot_dir)
    debug_print(f"  look dir             : {look_dir}")
    if not look_dir:
        _anotar_fallo(fallos, shot, f"no {LOOK_DIR_NAME} folder in {INPUT_DIR_NAME}")
        resumen["error"] += 1
        return resumen

    debug_print("  [PLAN SEGUN EL AMF]")
    plan = build_effect_plan(look_dir, plate_from_path(media_path))
    if not plan:
        debug_print("  [ERROR] No quedo ningun efecto por aplicar en este clip.")
        # Un plan vacio tiene dos causas -el .amf no deja nada pendiente, o no hay
        # ningun .cdl/.clf/.cube-, y ninguna es "falta un .cdl": el texto viejo
        # mandaba a buscar un archivo que a veces ni hacia falta.
        _anotar_fallo(
            fallos,
            shot,
            f"nothing to apply (no pending .amf look and no .cdl, .clf or .cube in {LOOK_DIR_NAME})",
        )
        resumen["error"] += 1
        return resumen

    # Los archivos del plan se miran ANTES de crear nada: nodeHasError() no
    # detecta un archivo faltante en NKS (ver motivo_archivo_inutil). Un efecto
    # que no puede cargar su archivo no se crea, y el motivo sube al cartel.
    plan_valido = []
    for spec in plan:
        motivo_archivo = motivo_archivo_inutil(spec["file"])
        if motivo_archivo:
            _anotar_fallo(fallos, shot, motivo_archivo)
            resumen["error"] += 1
            debug_print(
                f"  [ERROR] No se crea el {spec['type']}: {motivo_archivo}"
            )
        else:
            plan_valido.append(spec)

    # Los efectos se crean en el orden del plan: el primero queda en el
    # subtrack de abajo, o sea que se aplica antes. El subtrack va explicito
    # (sin eso cada llamada abre uno nuevo y los clips terminan con sus efectos
    # a distinta altura) y sale de subtracks_para_la_cadena: NUNCA se crea en un
    # subtrack que ocupa otro efecto, porque eso lo borra. La cadena es un bloque
    # contiguo por encima del mas alto ocupado, asi la cadena queda compacta
    # aunque se haya descartado un eslabon por su archivo, y sin ajenos es el
    # 0 y el 1 de siempre.
    pendientes = [
        spec
        for spec in plan_valido
        if not (SKIP_IF_EXISTS and find_existing_effect(efectos_existentes, spec["type"]))
    ]
    libres = subtracks_para_la_cadena(efectos_existentes, len(pendientes))
    if libres is None:
        debug_print(
            "  [ERROR] Un efecto del clip no dice su subtrack: no se puede elegir "
            "uno libre y no se crea nada para no pisar trabajo ajeno."
        )
        _anotar_fallo(
            fallos,
            shot,
            "no free sub-track found for the color effects (nothing was created on this clip)",
        )
        resumen["error"] += len(pendientes)
        pendientes = []
        plan_valido = [s for s in plan_valido if find_existing_effect(efectos_existentes, s["type"])]
    debug_print(
        "  subtracks de la cadena : %s (ocupados: %s)"
        % (libres, sorted(i["sub"] for i in efectos_existentes if i.get("sub") is not None))
    )
    ids_pendientes = set(id(sp) for sp in pendientes)
    for spec in plan_valido:
        sub = libres.pop(0) if id(spec) in ids_pendientes else None
        resumen[apply_effect(track_item, spec, efectos_existentes, sub, fallos, shot)] += 1

    debug_print("")
    debug_print(
        f"  [CLIP LISTO] creados: {resumen['creado']} | "
        f"ya estaban: {resumen['salteado']} | errores: {resumen['error']}"
    )
    return resumen


# ============================
# Entrada
# ============================


def get_selected_track_items():
    """Devuelve los TrackItem seleccionados en el timeline, sin soft effects."""
    seq = hiero.ui.activeSequence()
    if not seq:
        debug_print("[ERROR] No hay secuencia activa.")
        return None, []

    te = hiero.ui.getTimelineEditor(seq)
    if not te:
        debug_print("[ERROR] No se pudo obtener el timeline editor.")
        return seq, []

    selection = te.selection() or []
    track_items = [
        item
        for item in selection
        if isinstance(item, hiero.core.TrackItem)
        and not isinstance(item, hiero.core.EffectTrackItem)
    ]
    debug_print(f"[INFO] Clips seleccionados: {len(track_items)} (de {len(selection)} items)")
    return seq, track_items


def get_playhead_time():
    """Frame del playhead, o None si no hay viewer activo."""
    try:
        viewer = hiero.ui.currentViewer()
        if not viewer:
            return None
        return viewer.time()
    except Exception as e:
        debug_print("[WARN] No se pudo leer el playhead: %s" % e)
        return None


def _extension_aceptada(track_item):
    """True si la media del clip es de un tipo al que aplicarle la cadena."""
    media_path = get_media_path(track_item)
    if not media_path:
        return False
    return str(media_path).lower().endswith(PLAYHEAD_EXTENSIONS)


def get_track_items_at_playhead(seq, tiempo):
    """Los clips bajo el playhead, en TODOS los tracks, filtrados por extension.

    Los descartados por extension se loguean uno por uno: cuando el usuario
    espera que el boton toque un clip y no lo toca, tiene que poder ver por
    que en el .log en vez de quedarse con un silencio.
    """
    encontrados = []
    descartados = []
    for track in seq.videoTracks():
        try:
            items = track.items()
        except Exception:
            continue
        for item in items:
            # track.items() da clips, no efectos, pero el guard no cuesta nada
            # y esta tool no tiene por que aplicarse sobre otro soft effect.
            if isinstance(item, hiero.core.EffectTrackItem):
                continue
            if not isinstance(item, hiero.core.TrackItem):
                continue
            try:
                if not (item.timelineIn() <= tiempo <= item.timelineOut()):
                    continue
            except Exception:
                continue
            if _extension_aceptada(item):
                encontrados.append(item)
            else:
                descartados.append(item)

    for item in descartados:
        debug_print(
            "  [SALTEADO] '%s' no es %s"
            % (_safe_name(item), "/".join(PLAYHEAD_EXTENSIONS))
        )

    return encontrados


def get_target_track_items():
    """Los clips sobre los que hay que trabajar, y de donde salieron.

    La regla es por CANTIDAD, no por presencia, y el motivo es que Hiero
    autoselecciona el clip bajo el playhead (ver SELECCION_MINIMA):

      - DOS o mas clips seleccionados -> se usan esos y nada mas. Eso solo
        pasa si el usuario los eligio.
      - UNO o ninguno -> se ignora la seleccion y se barren todos los
        tracks bajo el playhead. Con un solo clip no hay forma de saber si
        lo eligio el usuario o lo puso ahi la autoseleccion, y suponer lo
        primero dejaba la tool operando sobre un track cuando el gesto
        natural -parado sobre un shot, sin seleccionar nada- es que opere
        sobre el shot entero.

    Esta regla NO depende de TOGGLE_CREATE_DELETE: ese flag decide si se
    crea o se borra, no de donde salen los clips.

    Devuelve (seq, track_items, origen), con origen en {'seleccion',
    'playhead'} para que el cartel y el log digan de donde salio la lista.
    """
    seq, seleccionados = get_selected_track_items()
    if not seq:
        return None, [], None

    if len(seleccionados) >= SELECCION_MINIMA:
        debug_print("[INFO] Seleccion deliberada: %d clips." % len(seleccionados))
        return seq, seleccionados, "seleccion"

    if len(seleccionados) == 1:
        debug_print(
            "[INFO] Un solo clip seleccionado ('%s'): puede ser la autoseleccion "
            "de Hiero, asi que se barre el playhead." % _safe_name(seleccionados[0])
        )

    tiempo = get_playhead_time()
    if tiempo is None:
        debug_print("[ERROR] No hay viewer activo: no se puede saber donde esta el playhead.")
        return seq, [], None

    track_items = get_track_items_at_playhead(seq, tiempo)
    debug_print(
        "[INFO] %d clip(s) bajo el playhead (frame %s)" % (len(track_items), tiempo)
    )
    return seq, track_items, "playhead"


def _avisar_sin_clips():
    """Cartel para cuando no hay nada sobre lo que trabajar."""
    mensaje = (
        "Nothing to work on.\n\n"
        "Place the playhead over a shot, or select two or more clips.\n"
        "Only %s clips are picked up from the playhead."
        % "/".join(ext.lstrip(".").upper() for ext in PLAYHEAD_EXTENSIONS)
    )
    debug_print("[ERROR] No hay clips ni en la seleccion ni bajo el playhead.")
    try:
        from LGA_NKS_Shared.LGA_NKS_MessageBox import show_warning

        show_warning(hiero.ui.mainWindow(), "Apply AMF", mensaje)
    except Exception as e:
        debug_print("[WARN] No se pudo mostrar el cartel: %s" % e)


def decidir_modo(track_items):
    """'borrar' si ALGUN clip objetivo ya tiene la cadena AMF; si no, 'crear'.

    La decision se toma UNA vez para toda la tanda, no clip por clip. Con
    una seleccion mezclada -tres clips con efectos y dos sin- decidir por
    clip crearia en unos y borraria en otros en la misma pasada, que es
    justo el resultado que nadie quiere ver.

    Y unifica hacia abajo (alguno prendido -> apagar todos), igual que
    LGA_NKS_ToggleAMF, para que los dos botones se comporten igual.
    """
    for track_item in track_items:
        if clip_has_amf(track_item):
            debug_print(
                "[MODO] BORRAR: '%s' ya tiene la cadena AMF." % _safe_name(track_item)
            )
            return "borrar"
    debug_print("[MODO] CREAR: ningun clip objetivo tiene la cadena AMF.")
    return "crear"


def _main_interno():
    # Los caches valen para ESTA corrida y nada mas. Ver por que no alcanza con
    # el cargador en el comentario de _ARCHIVOS_CACHE.
    reset_caches()

    debug_print("\n" + "=" * 70)
    debug_print("  LGA_NKS_ApplyAMF - soft effects de color segun el .amf del shot")
    debug_print(f"  desde {INPUT_DIR_NAME}/{LOOK_DIR_NAME}")
    debug_print("=" * 70)

    seq, track_items, origen = get_target_track_items()
    if not seq:
        return

    if not track_items:
        _avisar_sin_clips()
        return

    debug_print("  clips objetivo : %d (por %s)" % (len(track_items), origen))

    # --- Rama de BORRADO -------------------------------------------------
    # Sacar los efectos no necesita ni el shot ni el disco: se trabaja solo
    # con lo que ya esta en el timeline. Por eso sale por aca antes de todo
    # el camino de resolucion de rutas.
    if TOGGLE_CREATE_DELETE and decidir_modo(track_items) == "borrar":
        project = seq.project()
        if project:
            project.beginUndo("Apply AMF - remove")
        try:
            borrados, errores = remove_amf_effects(track_items)
        finally:
            if project:
                project.endUndo()

        debug_print("\n" + "=" * 70)
        debug_print("  RESUMEN (borrado) sobre %d clip(s):" % len(track_items))
        debug_print("    efectos borrados : %d" % borrados)
        debug_print("    con error        : %d" % errores)
        debug_print("=" * 70 + "\n")
        return

    # --- Rama de CREACION ------------------------------------------------
    project = seq.project()
    total = {"creado": 0, "salteado": 0, "error": 0}
    # shot -> motivo. Se llena en process_track_item y se avisa UNA vez al final.
    fallos = {}
    _log_contexto_color(project)

    if project:
        project.beginUndo("Apply AMF")
    try:
        for track_item in track_items:
            try:
                for clave, cantidad in process_track_item(track_item, fallos).items():
                    total[clave] += cantidad
            except Exception as e:
                debug_print(f"[ERROR] Fallo procesando '{_safe_name(track_item)}': {e}")
                debug_print(traceback.format_exc())
                _anotar_fallo(fallos, _safe_name(track_item), "unexpected error (see the log)")
                total["error"] += 1
    finally:
        if project:
            project.endUndo()

    debug_print("\n" + "=" * 70)
    debug_print(f"  RESUMEN sobre {len(track_items)} clip(s):")
    debug_print(f"    efectos creados : {total['creado']}")
    debug_print(f"    ya estaban      : {total['salteado']}")
    debug_print(f"    con error       : {total['error']}")
    for aviso in _AVISOS_CORRIDA:
        debug_print(f"    [AVISO] {aviso}")
    debug_print("=" * 70 + "\n")

    # El cartel va DESPUES del endUndo y del resumen: primero se termina el
    # trabajo sobre el timeline, despues se le habla al usuario.
    _avisar_fallos(fallos, len(track_items))

    # Salir sin haber hecho NADA y sin nada que avisar es el peor final: el
    # boton parece roto. Pasa cuando todos los clips ya tenian su cadena, o
    # cuando tienen un efecto de la misma clase puesto a mano -que frena la
    # creacion pero no cuenta como nuestro para borrarlo-.
    if not fallos and total["creado"] == 0 and total["error"] == 0:
        mensaje = (
            "Nothing to do: the %d selected clip%s already had their color effects.\n\n"
            "If you expected them to be removed, they were not created by Apply AMF: "
            "only effects loading a file from %s are removed."
            % (
                len(track_items),
                "s" if len(track_items) > 1 else "",
                LOOK_DIR_NAME,
            )
        )
        debug_print("\n[AVISO AL USUARIO] No se creo ni se borro nada.")
        try:
            from LGA_NKS_Shared.LGA_NKS_MessageBox import show_info

            show_info(hiero.ui.mainWindow(), "Apply AMF", mensaje)
        except Exception as e:
            debug_print("[WARN] No se pudo mostrar el cartel: %s" % e)


def main():
    """Envoltorio: corra bien o falle, la corrida SIEMPRE deja su log.

    El try/finally cubre tambien los return tempranos de _main_interno
    (sin secuencia activa, sin clips seleccionados, sin .cdl), que son
    justo los casos en los que la tool "no hace nada" y hay que poder
    ver por que.
    """
    try:
        _main_interno()
    except Exception:
        debug_print("[ERROR] Excepcion no atrapada:")
        debug_print(traceback.format_exc())
        raise
    finally:
        _volcar_log()


if __name__ == "__main__":
    main()
