# -*- coding: utf-8 -*-
"""
____________________________________________________________________

  LGA_NKS_TaskScope v1.00 | Lega

  Scope de tasks por contexto Studio/Client, en un solo lugar.

  Responde la pregunta que hasta ahora cada herramienta contestaba por su
  cuenta: "que tasks existen en el contexto activo". Antes ese saber vivia
  como constante local de LGA_NKS_CreateV000 (ALL_TASKS / CLIENT_TASKS) y
  ninguna otra tool podia consultarlo, asi que cada una mantenia su propia
  lista en paralelo y todas derivaron.

  Deliberadamente NO importa hiero: lo usan tanto scripts que corren dentro
  de NKS como los tests y los modulos compartidos. El import de contexto es
  lazy y tolerante a fallas, igual que en LGA_NKS_Flow_NamingUtils.

  El espejo de esta tabla son las constantes TRACK_*_EXR / TRACK_*_REV de
  LGA_NKS_GetClip.py, que no se pueden importar aca (ese modulo si importa
  hiero). La consistencia entre las dos la verifica
  tests/test_task_scope.py leyendo GetClip.py como texto.

  v1.00: Version inicial. Tabla TRACK_TASKS con scope por contexto,
         resolucion de nombre de track y de carpeta por task.
____________________________________________________________________

"""

MODE_STUDIO = "studio"
MODE_CLIENT = "client"

BOTH = (MODE_STUDIO, MODE_CLIENT)
STUDIO_ONLY = (MODE_STUDIO,)
CLIENT_ONLY = (MODE_CLIENT,)


# Tasks que tienen TRACK propio en el timeline, en el orden vertical del stack
# (la primera va mas arriba, debajo de BurnIn). Cada entrada es:
#   (task, nombre de carpeta en disco, contextos donde existe)
#
# CG existe solo en client y agrupa todas las entregas 3D de los vendors
# (layout, lighting, anim, fx, ...); roto y cleanup existen solo en studio.
# Comp existe en los dos.
TRACK_TASKS = (
    ("comp", "Comp", BOTH),
    ("roto", "Roto", STUDIO_ONLY),
    ("cleanup", "Cleanup", STUDIO_ONLY),
    ("cg", "CG", CLIENT_ONLY),
)

# Nombre de la task que agrupa las entregas 3D de los vendors en client.
# Espejo de CG_TASK_NAME de GetClip.py (que lo deriva de TRACK_cg_EXR); la
# consistencia la verifica tests/test_task_scope.py.
CG_TASK_NAME = "cg"


# Centinela para distinguir "no me pasaron default" de "me pasaron None".
_UNSET = object()


def _clean_task_key(task_name):
    """Normaliza un nombre de task a su clave de lookup, o None si no sirve.

    Castea a str a proposito: los callers vienen de filenames, de la DB y de
    widgets de Qt, y un valor no-string reventaba con AttributeError en el
    .strip(). Un string de solo espacios tampoco es una task: devuelve None
    en vez de degenerar en "".
    """
    if task_name is None:
        return None
    key = str(task_name).strip().lower()
    return key or None


def _normalize_mode(mode):
    return MODE_CLIENT if str(mode or "").strip().lower() == MODE_CLIENT else MODE_STUDIO


def resolve_mode(mode=None):
    """Devuelve el modo activo. Si no se pasa uno, lo lee del contexto.

    El import es lazy y tolerante: este modulo tiene que seguir funcionando
    sin la cadena de imports de contexto (scripts sueltos, tests). Ante
    cualquier falla cae a studio, que es el comportamiento historico.
    """
    if mode is not None:
        return _normalize_mode(mode)
    try:
        try:
            from LGA_NKS_ContextProfile import get_context_mode
        except ImportError:
            from LGA_NKS_Shared.LGA_NKS_ContextProfile import get_context_mode
        return _normalize_mode(get_context_mode())
    except Exception:
        return MODE_STUDIO


def all_track_task_names():
    """Todas las tasks con track registrado, sin filtrar por contexto."""
    return tuple(task for task, _folder, _contexts in TRACK_TASKS)


def active_track_tasks(mode=None):
    """Tasks con track que existen en el contexto activo.

    studio -> ("comp", "roto", "cleanup")
    client -> ("comp", "cg")

    El orden es el del stack de tracks del timeline, asi que sirve tambien
    para decidir donde insertar un track nuevo.
    """
    active = resolve_mode(mode)
    return tuple(
        task for task, _folder, contexts in TRACK_TASKS if active in contexts
    )


def is_track_task_active(task_name, mode=None):
    """True si esa task tiene track y existe en el contexto activo."""
    key = _clean_task_key(task_name)
    if key is None:
        return False
    return key in active_track_tasks(mode)


def task_folder_name(task_name, default=_UNSET):
    """Nombre de la carpeta de la task en el disco del shot ("cg" -> "CG").

    Devuelve `default` si la task no esta registrada; si no se pasa uno,
    devuelve el nombre capitalizado, que es la convencion del pipeline.
    Pasar `default=None` explicitamente devuelve None, que es distinto de
    no pasar nada.
    """
    key = _clean_task_key(task_name)
    if key is None:
        return None if default is _UNSET else default
    for task, folder, _contexts in TRACK_TASKS:
        if task == key:
            return folder
    if default is _UNSET:
        return key.capitalize()
    return default


def exr_track_for_task(task_name):
    """Nombre del track EXR de una task ("cg" -> "_cg_")."""
    key = _clean_task_key(task_name)
    if key is None or key not in all_track_task_names():
        return None
    return "_%s_" % key


def rev_track_for_task(task_name):
    """Nombre del track de review de una task ("cg" -> "_cgRev_")."""
    key = _clean_task_key(task_name)
    if key is None or key not in all_track_task_names():
        return None
    return "_%sRev_" % key


def task_for_track(track_name):
    """Task a la que pertenece un track EXR ("_cg_" -> "cg"). None si no aplica."""
    key = _clean_task_key(track_name)
    if key is None:
        return None
    for task in all_track_task_names():
        if key == "_%s_" % task:
            return task
    return None


__all__ = [
    "MODE_STUDIO",
    "MODE_CLIENT",
    "BOTH",
    "STUDIO_ONLY",
    "CLIENT_ONLY",
    "TRACK_TASKS",
    "CG_TASK_NAME",
    "resolve_mode",
    "all_track_task_names",
    "active_track_tasks",
    "is_track_task_active",
    "task_folder_name",
    "exr_track_for_task",
    "rev_track_for_task",
    "task_for_track",
]
