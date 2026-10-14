"""
____________________________________________________________________

  LGA_NKS_Flow_NamingUtils v1.22 | Lega

  Utilidades para detectar y extraer información de nombres de archivos/shots
  Compatible con estos sistemas de nomenclatura:
  - PROYECTO_SEQ_SHOT_DESC1_DESC2 (5 bloques con descripción)
  - PROYECTO_SEQ_SHOT (3 bloques simplificado)
  - Cualquiera de esas variantes + VENDOR al final del bloque base
    (PROYECTO_SEQ_SHOT_VENDOR), donde VENDOR sale de la DB de PipeSync.
  Si el ultimo bloque antes de la version es una task registrada o un plate
  (aPlate, bPlate...), el shot es todo lo anterior y no se cuentan bloques.

  Usado por runtime activo:
  - LGA_NKS_Flow_Panel.py
  - LGA_NKS_Assignee_Panel.py
  - LGA_NKS_Flow_S3_Panel.py
  - LGA_NKS_Shared/LGA_NKS_GetClip.py
  - LGA_NKS_Flow_Rev_Panel_py/LGA_NKS_Flow_Pull.py
  - LGA_NKS_Flow_Rev_Panel_py/LGA_NKS_Flow_Push.py
  - LGA_NKS_Flow_Rev_Panel_py/LGA_NKS_Flow_Push_connector.py
  - LGA_NKS_Flow_Rev_Panel_py/LGA_NKS_Flow_Shot_info.py
  - LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Assignee.py
  - LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Assign_Assignee.py
  - LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Clear_Assignees.py
  - LGA_NKS_Flow_S3_Panel_py/LGA_NKS_Flow_ShowInFlow.py
  - LGA_NKS_Flow_S3_Panel_py/LGA_NKS_Flow_Thumbs.py
  - LGA_NKS_Flow_S3_Panel_py/LGA_NKS_Flow_CreateShot.py
  - LGA_NKS_Flow_S3_Panel_py/LGA_NKS_Flow_CheckTimelineShots.py
  - LGA_NKS_Flow_S3_Panel_py/LGA_NKS_Flow_ShotPriority.py
  - LGA_NKS_Flow_S3_Panel_py/LGA_NKS_FileManagerS3_Upload.py
  - LGA_NKS_Flow_S3_Panel_py/LGA_NKS_FileManagerS3_Download.py
  - LGA_NKS_Flow_S3_Panel_py/LGA_NKS_FileManagerS3_OpenPath.py
  - LGA_NKS_Flow_S3_Panel_py/LGA_NKS_PipeSync_CreatePsync.py
  - LGA_NKS_Flow_S3_Panel_py/LGA_NKS_PipeSync_OpenPath.py
  - LGA_NKS_Review_Panel_py/LGA_NKS_MatchVerToEXR.py
  - LGA_NKS_Edit_Panel_py/LGA_NKS_SetShotName.py
  - LGA_NKS_Review_Panel_py/LGA_NKS_CompareVerToEditref.py
  - LGA_NKS_Review_Panel_py/LGA_NKS_CompareEXR_to_aPlate.py
  - LGA_NKS_Edit_Panel_py/LGA_NKS_CreateV000.py

  v1.22: El shot code se ancla en el ultimo bloque cuando es una task
         registrada (comp, roto, cleanup, cg y sus aliases) o un plate: el shot
         es todo lo anterior, tenga la descripcion uno o dos bloques. Se saca
         la deteccion de series (tres bloques numericos tras el proyecto): ya
         no se usan, y confundia PROYECTO_SEQ_SHOT_DESC1_DESC2 cuando DESC1 es
         numerico, con lo que el shot code terminaba incluyendo la task.
  v1.21: SUP se conserva en el shot code de Flow y Hiero, igual que los
         vendors externos. Sigue siendo un token interno solo para resolver
         acceso y task, sin pasar a ser un vendor externo de PipeSync.
  v1.20: Actualiza la lista de consumidores tras mover las comparaciones al
         Review Panel; no cambia la logica de nombres.
  v1.19: SUP sigue resolviendo la task pero se omite del shot_code de Flow.
  v1.18: SUP es un token interno de naming, separado del catálogo de vendors.
         Se normaliza sin distinguir mayúsculas y nunca depende de PipeSync.
  v1.17: la familia CG lee las tasks registradas de LGA_NKS_TaskScope en vez
         de LGA_NKS_GetClip. GetClip importa hiero, asi que fuera de NKS el
         import fallaba, el except lo tapaba y la regla no se aplicaba nunca
         (ni se podia testear). Sin cambio de comportamiento dentro de NKS.
  v1.16: normalize_task_name() aplica la familia CG en contexto client: toda
         task que no sea un track registrado (layout, lighting, anim, ...)
         se mapea por exclusion a la task CG. En studio no cambia nada.
  v1.15: extract_shot_code_from_path() devuelve el nombre de la carpeta de
         shot validada contra los vendor codes de PipeSync. Pull la usa para
         no confundir sufijos de publish con descripciones del shot.
  v1.14: soporte de vendor code al final del bloque base
         (PROYECTO_SEQ_SHOT_VENDOR). Los vendor codes validos se leen de la DB
         de PipeSync via LGA_NKS_Vendors_Config; NO se adivinan por estructura,
         porque un bloque alfabetico despues de dos numeros puede ser tanto un
         vendor ("PROJA_1013_0800_VEN") como una task ("PROJA_1048_060_Compo").
         Antes, el vendor se comia como DESC1 y el shot_code terminaba
         incluyendo la task, con lo que no matcheaba ningun shot de Flow.
  v1.13: extract_sequence_name_from_path(): extrae el nombre de secuencia desde
         el segmento de ruta que sigue a "VFX-NOMBRE" (estructura
         VFX-PROYECTO/SECUENCIA/SHOT) en lugar del nombre del timeline de Hiero.
         Fallback: nombre del timeline (comportamiento anterior).
         Ver docs/Docu_ProjectName_Extraction.md para el patrón completo.
  v1.12: extract_project_name_from_path(): extrae el nombre de proyecto desde
         el segmento de ruta "VFX-NOMBRE" en lugar del prefijo del filename.
         Fallback: extract_project_name() (comportamiento anterior).
         Ver docs/Docu_ProjectName_Extraction.md para el patrón completo.
  v1.11: Aliases de task: TASK_NAME_ALIASES y normalize_task_name().
         extract_task_name() normaliza el resultado para que "compo" → "comp"
         en toda la pipeline que use este módulo.
____________________________________________________________________________________
"""

import re
import os

_VERSION_RE = re.compile(r"^v\d+$", re.IGNORECASE)

# Aliases de task: nombres alternativos que deben tratarse como su canonical.
# Ej: archivos llamados "Compo" pertenecen a la task "comp".
TASK_NAME_ALIASES = {
    "compo": "comp",
}

# Token reservado para planos internos del supervisor. No representa un vendor
# externo y por eso nunca debe recibir grupos ni usuarios de vendor.
INTERNAL_VENDOR_TOKEN = "SUP"


def normalize_vendor_token(value):
    """Normaliza un token de vendor o naming para comparaciones seguras."""
    return str(value or "").strip().upper()


def is_internal_vendor_token(value):
    """True únicamente para el token interno SUP, sin distinguir el caso."""
    return normalize_vendor_token(value) == INTERNAL_VENDOR_TOKEN


def _apply_cg_family(name):
    """En contexto client, mapea cualquier task no registrada a la task CG.

    En client solo existen dos tasks de Flow: comp y CG. Los archivos de la
    task CG llevan la DISCIPLINA en el filename (layout, lighting, anim, ...),
    asi que todo token de task que no corresponda a un track registrado
    pertenece por exclusion a la familia CG. No se mantiene una lista de
    disciplinas: es una regla por exclusion, deliberadamente.

    En studio no cambia nada: la resolucion de task de Push/Pull se gobierna
    por la PRESENCIA del track en el timeline (TASK_EXR_TRACKS), y en studio
    no existe el track CG; este mapeo ademas solo se activa en client.

    Los imports son lazy y tolerantes a fallas, igual que _get_vendor_lookup:
    este modulo tiene que seguir funcionando sin la cadena de imports de
    contexto (scripts sueltos, tests).

    La lista de tasks registradas sale de LGA_NKS_TaskScope y NO de
    LGA_NKS_GetClip: GetClip importa hiero, asi que fuera de NKS ese import
    fallaba, el `except Exception` se lo tragaba y la regla de familia CG no
    se aplicaba ni se podia testear. TaskScope no importa hiero.
    """
    try:
        try:
            from LGA_NKS_ContextProfile import is_client_context
        except ImportError:
            from LGA_NKS_Shared.LGA_NKS_ContextProfile import is_client_context
        if not is_client_context():
            return name
        try:
            from LGA_NKS_TaskScope import all_track_task_names, CG_TASK_NAME
        except ImportError:
            from LGA_NKS_Shared.LGA_NKS_TaskScope import (
                all_track_task_names,
                CG_TASK_NAME,
            )
        if name in all_track_task_names():
            return name
        return CG_TASK_NAME
    except Exception:
        return name


def normalize_task_name(name):
    """Devuelve el nombre canonical de una task, resolviendo aliases conocidos.

    En contexto client aplica ademas la regla de familia CG: toda task que no
    sea un track registrado se considera CG (ver _apply_cg_family).
    """
    if not name:
        return name
    normalized = TASK_NAME_ALIASES.get(name.lower(), name.lower())
    return _apply_cg_family(normalized)


def _strip_version_suffix(parts):
    """Remueve un sufijo de versión tipo v### si está presente."""
    if parts and _VERSION_RE.match(parts[-1]):
        return parts[:-1]
    return parts


def _is_numeric_block(value):
    """True si el bloque comienza con un dígito."""
    return bool(value) and value[0].isdigit()


def _is_vendor_format(parts):
    """
    Detecta formato con vendor delante:
    PROYECTO_VENDOR_SEQ_SHOT, donde VENDOR es solo letras.
    """
    return (
        len(parts) >= 4
        and parts[1].isalpha()
        and _is_numeric_block(parts[2])
        and _is_numeric_block(parts[3])
    )


def _base_block_count(parts):
    """Bloques del shot sin descripcion ni vendor final: PROYECTO_SEQ_SHOT.

    Son 4 solo en el formato historico con el vendor adelante. Ya no existe la
    base de serie (PROYECTO_TEMP_EP_SEQ_SHOT): no se usa mas, y detectarla por
    "tres bloques numericos tras el proyecto" confundia un shot con descripcion
    cuyo primer bloque es numerico (PROYECTO_SEQ_SHOT_010_Desc).
    """
    return 4 if _is_vendor_format(parts) else 3


# Ancla del parser: los plates de _input se llaman <shot>_aPlate_v01, <shot>_bPlate...
_PLATE_TOKEN_RE = re.compile(r"^[a-z]plate$", re.IGNORECASE)

# Bloques minimos de un shot (PROYECTO_SEQ_SHOT). El ancla nunca deja menos.
_MIN_SHOT_BLOCKS = 3

# Tasks reconocibles por nombre, cacheadas tras el primer intento.
_anchor_tasks = None


def _get_anchor_tasks():
    """Tasks con track registrado + aliases, en minuscula.

    Sale de LGA_NKS_TaskScope (no importa hiero) con el mismo import tolerante
    que _apply_cg_family. Si no carga, usa la lista conocida para que el ancla
    funcione igual en scripts sueltos y tests.
    """
    global _anchor_tasks
    if _anchor_tasks is not None:
        return _anchor_tasks
    try:
        try:
            from LGA_NKS_TaskScope import all_track_task_names
        except ImportError:
            from LGA_NKS_Shared.LGA_NKS_TaskScope import all_track_task_names
        tasks = set(all_track_task_names())
    except Exception:
        tasks = {"comp", "roto", "cleanup", "cg"}
    _anchor_tasks = frozenset(tasks | set(TASK_NAME_ALIASES))
    return _anchor_tasks


def _is_anchor_token(block):
    """True si el bloque es una task registrada (o alias) o un plate."""
    if not block:
        return False
    return block.lower() in _get_anchor_tasks() or bool(_PLATE_TOKEN_RE.match(block))


# Resolver de vendor codes, cacheado tras el primer intento. _analyze_shotname
# corre dos veces por clip (shot code + task), asi que el import no puede
# repetirse en cada llamada. False = ya se intento y no esta disponible.
_vendor_lookup = None


def _get_vendor_lookup():
    """Devuelve is_vendor_code() de Vendors_Config, o None si no esta disponible.

    El import es lazy y tolerante a fallas a proposito: este modulo tiene que
    seguir funcionando en contextos donde no esten la DB ni la cadena de imports
    de PipeSync (scripts sueltos, tests).
    """
    global _vendor_lookup
    if _vendor_lookup is not None:
        return _vendor_lookup or None

    try:
        try:
            from LGA_NKS_Vendors_Config import is_vendor_code
        except ImportError:
            from LGA_NKS_Shared.LGA_NKS_Vendors_Config import is_vendor_code
        _vendor_lookup = is_vendor_code
    except Exception:
        _vendor_lookup = False
    return _vendor_lookup or None


def _is_known_vendor_code(block, project_name):
    """
    True si `block` es un vendor code configurado en Flow para ese proyecto.

    La lista sale de la DB de PipeSync. Si no se puede resolver, devuelve False
    y el naming se comporta como antes de v1.14.
    """
    if is_internal_vendor_token(block):
        return True
    if not block or not block.isalpha():
        return False

    lookup = _get_vendor_lookup()
    if lookup is None:
        return False

    try:
        return lookup(block, project_name)
    except Exception:
        return False


def _analyze_shotname(base_name):
    """
    Separa el nombre base en shot y task. Retorna:
    (shot_parts, task_block | None, base_count)

    base_count son los bloques del shot sin descripcion (3, o 4 con vendor).

    1. Ancla: si el ultimo bloque es una task registrada o un plate, el shot es
       todo lo anterior. No depende de contar, asi que no importa si la
       descripcion tiene uno o dos bloques ni si el vendor esta en la DB.
    2. Conteo, cuando el ultimo bloque no se reconoce (en client, las
       disciplinas de la familia CG): base de 3 bloques, +1 si sigue un vendor
       conocido, +2 de descripcion si sobran al menos dos bloques.
    """
    if not base_name:
        return [], None, 0

    core_parts = _strip_version_suffix(base_name.split("_"))
    if not core_parts:
        return [], None, 0

    base_count = _base_block_count(core_parts)

    # Vendor al final del bloque base: PROYECTO_SEQ_SHOT_VENDOR.
    if len(core_parts) > base_count and _is_known_vendor_code(
        core_parts[base_count], core_parts[0]
    ):
        base_count += 1

    if len(core_parts) > _MIN_SHOT_BLOCKS and _is_anchor_token(core_parts[-1]):
        return core_parts[:-1], core_parts[-1], base_count

    shot_count = base_count + (2 if len(core_parts) >= base_count + 2 else 0)
    task = core_parts[shot_count] if len(core_parts) > shot_count else None
    return core_parts[:shot_count], task, base_count


def detect_shotname_format(base_name):
    """
    Detecta si el shotname lleva bloques de descripción.

    Es descripción todo bloque del shot que sobra después del bloque base
    (PROYECTO_SEQ_SHOT, más el vendor si lo hay). Ver _analyze_shotname.

    Args:
        base_name (str): Nombre base del archivo sin extensión ni versión

    Returns:
        bool: True si el shot tiene descripción, False si es simplificado
    """
    shot_parts, _, base_count = _analyze_shotname(base_name)
    return len(shot_parts) > base_count


def extract_shot_code(base_name):
    """
    Extrae el shot_code de un nombre base de archivo.
    Detecta automáticamente el formato y extrae el shot_code correcto.

    Args:
        base_name (str): Nombre base del archivo sin extensión ni versión

    Returns:
        str: Shot code extraído con o sin descripción
    """
    shot_parts, _, _ = _analyze_shotname(base_name)
    return "_".join(shot_parts)


def extract_vendor_token(base_name, project_name=None):
    """Devuelve SUP o el vendor externo reconocido al final del bloque base."""
    parts = _strip_version_suffix((base_name or "").split("_"))
    if not parts:
        return ""
    original_base = _base_block_count(parts)
    if len(parts) <= original_base:
        return ""
    candidate = parts[original_base]
    if is_internal_vendor_token(candidate) or _is_known_vendor_code(candidate, project_name or parts[0]):
        return normalize_vendor_token(candidate)
    return ""


def find_unknown_vendor_slot(
    base_name, known_tasks, project_name=None, client_cg_by_exclusion=False
):
    """Detecta `..._X_task` cuando X no es vendor ni SUP.

    En Client el último token puede ser cualquier disciplina de la familia CG,
    que se resuelve por exclusión y por eso no depende de una lista finita.
    """
    parts = _strip_version_suffix((base_name or "").split("_"))
    if not parts:
        return ""
    base_count = _base_block_count(parts)
    if len(parts) != base_count + 2:
        return ""
    candidate, task = parts[base_count], parts[base_count + 1]
    known = {str(item or "").strip().lower() for item in (known_tasks or [])}
    if not client_cg_by_exclusion and str(task).strip().lower() not in known:
        return ""
    if is_internal_vendor_token(candidate) or _is_known_vendor_code(candidate, project_name or parts[0]):
        return ""
    return candidate


def extract_shot_code_with_vendor_candidate(base_name, candidate):
    """Forma el shot code con un candidato que todavía debe validar Flow."""
    parts = _strip_version_suffix((base_name or "").split("_"))
    if not parts or not candidate:
        return extract_shot_code(base_name)
    base_count = _base_block_count(parts)
    if len(parts) > base_count and normalize_vendor_token(parts[base_count]) == normalize_vendor_token(candidate):
        return "_".join(parts[:base_count + 1])
    return extract_shot_code(base_name)


_SHOT_FOLDER_RE = re.compile(
    r"^[A-Za-z0-9]+(?:_[A-Za-z]+|_[0-9]{3,5}[A-Za-z]?)?_[0-9]{3,5}[A-Za-z]?_[0-9]{3,4}$"
)


def is_shot_folder_name(segment, project_name=None):
    """
    True si un segmento de ruta es el nombre de carpeta de un shot.

    Sirve para encontrar la carpeta del shot recorriendo una ruta de disco, que
    es un problema distinto al de parsear un filename: aca no hay task ni
    version, solo el nombre del directorio.

    Acepta el patron historico (PROYECTO[_VENDOR|_EP]_SEQ_SHOT) y, ademas, ese
    mismo patron con un vendor code al final (PROYECTO_SEQ_SHOT_VENDOR). El
    vendor se valida contra la DB de PipeSync, igual que en _analyze_shotname.

    LIMITE CONOCIDO: no cubre los shots con bloques de descripcion
    (PROYECTO_SEQ_SHOT_DESC1_DESC2, con o sin vendor). Nunca los cubrio: el
    patron historico solo contempla el bloque base. Esos shots se resuelven por
    la deteccion de estructura de ruta que los callers usan como paso 2. Ampliar
    el patron a descripciones cambiaria el comportamiento de shots sin vendor,
    asi que es una decision aparte.

    Args:
        segment (str): Un unico segmento de ruta (sin barras).
        project_name (str | None): Proyecto al que pertenece, para acotar la
            lista de vendors validos.

    Returns:
        bool
    """
    if not segment:
        return False

    if _SHOT_FOLDER_RE.match(segment):
        return True

    # Variante con vendor al final: se le saca el ultimo bloque y se revalida el
    # resto con el patron historico.
    if "_" in segment:
        cuerpo, _, ultimo = segment.rpartition("_")
        if _is_known_vendor_code(ultimo, project_name or cuerpo.split("_")[0]):
            return bool(_SHOT_FOLDER_RE.match(cuerpo))

    return False


def extract_project_name(base_name):
    """
    Extrae el nombre del proyecto del nombre base del archivo (primer bloque antes de _).
    Ej: "PROJA_1048_060_Compo" → "PROJA".

    NOTA: Este método es el fallback. Prefiere extract_project_name_from_path()
    cuando tenés la ruta completa del archivo disponible.

    Args:
        base_name (str): Nombre base del archivo

    Returns:
        str: Nombre del proyecto (primer campo)
    """
    if not base_name:
        return ""

    parts = base_name.split("_")
    return parts[0] if parts else ""


def extract_project_name_from_path(file_path):
    """
    Extrae el nombre del proyecto desde el segmento de ruta "VFX-NOMBRE".

    Los proyectos VFX siempre viven bajo una carpeta raíz con el patrón "VFX-NOMBRE"
    (ej: T:/VFX-PROJALT/...). El nombre del proyecto en la DB es "NOMBRE"
    (sin el prefijo "VFX-").

    Si no se encuentra ningún segmento con ese patrón, retorna None para que
    el caller pueda hacer fallback a extract_project_name().

    Ej:
        "T:/VFX-PROJALT/101/PROJA_1048_060/..." → "PROJALT"
        "T:/VFX-PROJF/102/..."                 → "PROJF"
        "/path/sin/prefijo/vfx/..."           → None

    Args:
        file_path (str): Ruta completa del archivo.

    Returns:
        str | None: Nombre del proyecto, o None si no se encuentra el patrón.
    """
    if not file_path:
        return None
    import os as _os
    normalized = _os.path.normpath(file_path)
    for part in normalized.split(_os.sep):
        if part.upper().startswith("VFX-") and len(part) > 4:
            return part[4:]  # strip "VFX-"
    return None


def extract_shot_code_from_path(file_path, project_name=None):
    """Devuelve el nombre de la carpeta de shot presente en una ruta de media.

    Recorre la ruta desde el archivo hacia la raíz y acepta solamente segmentos
    que ``is_shot_folder_name()`` valida. Esa validación consulta los vendor
    codes de PipeSync cuando el último bloque puede ser un vendor; por eso no
    confunde un sufijo de publish con parte del nombre del shot.

    Devuelve ``""`` cuando la ruta no contiene una carpeta de shot reconocible,
    para que el caller conserve su parser de filename como fallback.
    """
    if not file_path:
        return ""

    normalized = re.sub(r"[\\/]+", "/", str(file_path))
    for segment in reversed(normalized.split("/")):
        if is_shot_folder_name(segment, project_name):
            return segment
    return ""


def extract_sequence_name_from_path(file_path):
    """
    Extrae el nombre de la secuencia desde el segmento de ruta que sigue
    inmediatamente a la carpeta "VFX-NOMBRE".

    La estructura en disco siempre es:
        .../VFX-PROYECTO/SECUENCIA/SHOT/...

    El segmento siguiente al "VFX-NOMBRE" es la secuencia (en Flow, el code de
    la entidad Sequence).

    Si no se encuentra el patrón (no hay segmento "VFX-*" o no hay segmento
    siguiente), retorna None para que el caller pueda hacer fallback al nombre
    del timeline de Hiero (comportamiento anterior).

    Ej:
        "T:/VFX-PROJALT/101/PROJA_1048_060/..." → "101"
        "T:/VFX-PROJF/080/PROJF_080_010/..."    → "080"
        "/path/sin/prefijo/vfx/..."           → None

    Args:
        file_path (str): Ruta completa del archivo.

    Returns:
        str | None: Nombre de la secuencia, o None si no se encuentra el patrón.
    """
    if not file_path:
        return None
    import os as _os
    normalized = _os.path.normpath(file_path)
    parts = normalized.split(_os.sep)
    for idx, part in enumerate(parts):
        if part.upper().startswith("VFX-") and len(part) > 4:
            if idx + 1 < len(parts):
                return parts[idx + 1]
            return None
    return None


def clean_base_name(file_name):
    """
    Limpia el nombre de archivo removiendo extensiones y versiones.
    
    Args:
        file_name (str): Nombre completo del archivo
        
    Returns:
        str: Nombre base limpio sin extensión ni versión
    """
    if not file_name:
        return ""
    
    # Remover extensión de secuencia EXR/DPX y frames
    base_name = re.sub(r"_%04d\.(exr|dpx)$", "", file_name, flags=re.IGNORECASE)
    base_name = re.sub(r"_\d{4}\.(exr|dpx)$", "", base_name, flags=re.IGNORECASE)  # También formato sin %04d
    base_name = re.sub(r"\.%04d\.(exr|dpx)$", "", base_name, flags=re.IGNORECASE)  # Para archivos DPX con .%04d

    # Remover extensión común
    base_name = os.path.splitext(base_name)[0]

    # Remover versión al final (_v19, _v001, etc.)
    base_name = re.sub(r"_v\d+$", "", base_name)
    
    return base_name


def extract_task_name(base_name):
    """
    Extrae el nombre de la tarea del nombre base del archivo.
    
    Args:
        base_name (str): Nombre base del archivo sin extensión ni versión
        
    Returns:
        str: Nombre de la tarea o None si no se encuentra
    """
    # Devuelve el bloque tal cual ("Compo", "aPlate"): normalizarlo es cosa
    # del caller, con normalize_task_name().
    _, task, _ = _analyze_shotname(base_name)
    return task
