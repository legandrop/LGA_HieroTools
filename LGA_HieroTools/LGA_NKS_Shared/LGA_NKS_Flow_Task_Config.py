"""
____________________________________________________________________

  LGA_NKS_Flow_Task_Config v1.28 | Lega

  Usado por runtime activo:
  - LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Assignee.py
  - LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Assign_Assignee.py
  - LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Clear_Assignees.py
  - LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot.py

  Configuración centralizada de tasks del pipeline usadas por los paneles de Flow.
  La lista está sincronizada con los scripts de creación/modificación de shots y
  provee colores consistentes para las UIs compactas (assignee panel, create shot, etc.).

  v1.28: Cada task declara en que contextos existe ("contexts") y CG entra al
         catalogo como CLIENT_ONLY, en vez de vivir suelta en _TASK_COLOR_MAP.
         Nuevo get_available_tasks(mode) para que los catalogos de creacion
         filtren por contexto: en client ofrecian Roto/Cleanup/DMP/3D, que en
         ese sitio de Flow no existen, y no ofrecian CG.
  v1.27: Toda la familia 3D pasa al MISMO naranja #CA7A3B: match move, model, retopo,
         rigging, shaders, animation, fx, lighting y cg. La disciplina no se distingue
         por color, y el corte visual queda 2D frias / 3D calidas. De paso saca dos
         colisiones: CG dejo de compartir el cyan de cleanup, y lighting (#3BCA7A)
         estaba a 4 grados de hue de roto (#2abf7e).
         Esta tabla tiene un ESPEJO en C++ que hay que tocar en la misma pasada:
         `TaskVersioningManager::applyTaskColors()` de LGA_FileManagerS3 (le llega a
         PipeSync y a FileManagerS3). Plan y verificador en
         `LGA_PipeSync_2/Docs/Plan_Colores_Task_Unificados.md`.
  v1.26: Color para la task CG (client) en _TASK_COLOR_MAP, sin sumarla a
         AVAILABLE_TASKS: CG no se ofrece en los catalogos de creacion.
  1.25: Actualizado para usar colores de tasks alineados con los colores de create v000
  v1.24: Actualiza la UI para mostrar las tasks y los asignados en Flow.
         Funciona con todas las tasks disponibles en Flow.
____________________________________________________________________

"""

from typing import Dict, List, Optional, Sequence

try:
    from LGA_NKS_TaskScope import (
        BOTH,
        CLIENT_ONLY,
        STUDIO_ONLY,
        resolve_mode,
    )
except ImportError:  # pragma: no cover - depende de como se arme el sys.path
    from LGA_NKS_Shared.LGA_NKS_TaskScope import (
        BOTH,
        CLIENT_ONLY,
        STUDIO_ONLY,
        resolve_mode,
    )


# Cada task declara en que CONTEXTOS existe, igual que los estados de
# LGA_NKS_Flow_Status_Config. Todo catalogo de creacion tiene que filtrar por
# ahi con get_available_tasks(): en client solo existen Comp y CG, y ofrecer
# Roto/Cleanup/DMP/3D ahi crea tasks que ese sitio de Flow no usa.
AVAILABLE_TASKS: List[Dict[str, str]] = [
    {
        "name": "Comp",
        "pipeline_step": "Comp",
        "enabled_by_default": True,
        "color": "#3381e0",  # Azul
        "contexts": BOTH,
    },
    {
        "name": "Roto",
        "pipeline_step": "Roto",
        "enabled_by_default": False,
        "color": "#2abf7e",  # Verde
        "contexts": STUDIO_ONLY,
    },
    {
        "name": "Cleanup",
        "pipeline_step": "Cleanup",
        "enabled_by_default": False,
        "color": "#27c8c3",  # Cyan
        "contexts": STUDIO_ONLY,
    },
    {
        "name": "DMP",
        "pipeline_step": "DMP",
        "enabled_by_default": False,
        "color": "#CACA3B",  # Amarillo
        "contexts": STUDIO_ONLY,
    },
    {
        # CG existe SOLO en client y agrupa todas las entregas 3D de los
        # vendors (layout, lighting, anim, fx, ...) en una sola task de Flow.
        # Encabeza la familia 3D y lleva su mismo naranja.
        "name": "CG",
        "pipeline_step": "CG",
        "enabled_by_default": True,
        "color": "#CA7A3B",  # Naranja - familia 3D
        "contexts": CLIENT_ONLY,
    },
    {
        "name": "Model",
        "pipeline_step": "Model",
        "enabled_by_default": False,
        "color": "#CA7A3B",  # Naranja - familia 3D
        "contexts": STUDIO_ONLY,
    },
    {
        "name": "Retopo",
        "pipeline_step": "Retopo",
        "enabled_by_default": False,
        "color": "#CA7A3B",  # Naranja - familia 3D
        "contexts": STUDIO_ONLY,
    },
    {
        "name": "Rigging",
        "pipeline_step": "Rigging",
        "enabled_by_default": False,
        "color": "#CA7A3B",  # Naranja - familia 3D
        "contexts": STUDIO_ONLY,
    },
    {
        "name": "Shaders",
        "pipeline_step": "Shaders",
        "enabled_by_default": False,
        "color": "#CA7A3B",  # Naranja - familia 3D
        "contexts": STUDIO_ONLY,
    },
    {
        "name": "Match Move",
        "pipeline_step": "Match Move",
        "enabled_by_default": False,
        "color": "#CA7A3B",  # Naranja - familia 3D
        "contexts": STUDIO_ONLY,
    },
    {
        "name": "Animation",
        "pipeline_step": "Animation",
        "enabled_by_default": False,
        "color": "#CA7A3B",  # Naranja - familia 3D
        "contexts": STUDIO_ONLY,
    },
    {
        "name": "FX",
        "pipeline_step": "FX",
        "enabled_by_default": False,
        "color": "#CA7A3B",  # Naranja - familia 3D
        "contexts": STUDIO_ONLY,
    },
    {
        "name": "Lighting",
        "pipeline_step": "Lighting",
        "enabled_by_default": False,
        "color": "#CA7A3B",  # Naranja - familia 3D
        "contexts": STUDIO_ONLY,
    },
]

DEFAULT_TASK_NAME = "Comp"
_TASK_ORDER = {task["name"].lower(): index for index, task in enumerate(AVAILABLE_TASKS)}
_TASK_COLOR_MAP = {task["name"].lower(): task["color"] for task in AVAILABLE_TASKS}

def get_available_tasks(mode: Optional[str] = None) -> List[Dict[str, str]]:
    """Tasks que se ofrecen en los catalogos de creacion del contexto activo.

    studio -> Comp, Roto, Cleanup, DMP y la familia 3D.
    client -> Comp y CG.

    Todo dropdown o checkbox que CREE una task tiene que filtrar por aca. Si
    no se pasa `mode`, se lee del contexto activo.
    """
    active = resolve_mode(mode)
    return [task for task in AVAILABLE_TASKS if active in task.get("contexts", BOTH)]


def get_available_task_names(mode: Optional[str] = None) -> List[str]:
    """Nombres de las tasks ofrecidas en el contexto activo, tal cual van a Flow."""
    return [task["name"] for task in get_available_tasks(mode)]


def get_task_color(task_name: str, fallback: str = "#4A4A4A") -> str:
    """Devuelve el color configurado para la task (case insensitive)."""
    if not task_name:
        return fallback
    return _TASK_COLOR_MAP.get(task_name.lower(), fallback)


def sort_tasks_by_pipeline(tasks: List[Dict]) -> List[Dict]:
    """
    Ordena la lista de tasks respetando el orden definido en AVAILABLE_TASKS.
    Tasks que no pertenecen a la lista quedan al final de forma alfabética.
    """

    def sort_key(task: Dict) -> tuple:
        name = (task.get("name") or task.get("content") or "").lower()
        order = _TASK_ORDER.get(name, len(_TASK_ORDER) + 1)
        return (order, name)

    return sorted(tasks, key=sort_key)


__all__ = [
    "AVAILABLE_TASKS",
    "DEFAULT_TASK_NAME",
    "get_available_tasks",
    "get_available_task_names",
    "get_task_color",
    "sort_tasks_by_pipeline",
]
