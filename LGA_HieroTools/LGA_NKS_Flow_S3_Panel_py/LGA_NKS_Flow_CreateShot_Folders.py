"""
____________________________________________________________________

  LGA_NKS_Flow_CreateShot_Folders v1.36 | Lega

  Módulo para creación automática de estructura de carpetas por task.
  Se integra con CreateShot y ModifyShot para mantener consistencia.
  - Creación automática de carpetas según task
  - Estructura jerárquica para 2D (comp, roto, cleanup, DMP) y 3D
  - Logging detallado de carpetas creadas/existentes
  - Normalización de paths para verificación de existencia

  v1.36: Las carpetas de las tasks 2D pasan a capitalizadas (`Comp`, `Roto`,
         `Cleanup`, `CG`), que es como arman la ruta TODOS los lectores del
         pipeline; esta tool era la unica que las creaba en minuscula. En
         Windows daba igual, pero en macOS `comp/` y `Comp/` son dos
         carpetas distintas y el lector no encontraba nada. Antes de crear
         se resuelve el caso de lo que YA exista (resolve_existing_case),
         asi que un shot historico con `comp/` no queda partido en dos. Esa
         resolucion mira solo DIRECTORIOS y desempata de forma determinista
         si coexisten dos variantes de caso.
  v1.35: Estructura de carpetas para la task CG (solo client). Una sola
         carpeta para todas las disciplinas: los streams se distinguen por
         el nombre de la version, no por la ruta.
  v1.34: Creación automática de estructura de carpetas por task
         Integración completa con CreateShot y ModifyShot
         Soporte para todas las tasks 2D y 3D del pipeline
____________________________________________________________________
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Set

# Configuración de logging
logger = logging.getLogger(__name__)

# Estructura de carpetas por task
# Formato: task_name -> lista de subcarpetas relativas
TASK_FOLDER_STRUCTURE = {
    # Tasks 2D - van directamente bajo SHOTNAME/
    "Comp": [
        "Comp/0_assets",
        "Comp/1_projects",
        "Comp/2_prerenders",
        "Comp/3_review",
        "Comp/4_publish"
    ],
    "Roto": [
        "Roto/0_assets",
        "Roto/1_projects",
        "Roto/2_prerenders",
        "Roto/3_review",
        "Roto/4_publish"
    ],
    "Cleanup": [
        "Cleanup/0_assets",
        "Cleanup/1_projects",
        "Cleanup/2_prerenders",
        "Cleanup/3_review",
        "Cleanup/4_publish"
    ],
    # CG (solo client): una sola task agrupa todas las entregas 3D de los
    # vendors (layout, lighting, anim, fx, ...), asi que lleva UNA carpeta,
    # no una por disciplina. Los streams se distinguen por el nombre de la
    # version, no por la ruta.
    "CG": [
        "CG/0_assets",
        "CG/1_projects",
        "CG/2_prerenders",
        "CG/3_review",
        "CG/4_publish"
    ],
    "DMP": [
        "DMP/0_assets",
        "DMP/1_projects",
        "DMP/2_prerenders",
        "DMP/3_review",
        "DMP/4_publish"
    ],
    # Tasks 3D - van bajo SHOTNAME/3D/
    "Model": [
        "3D/2_model/0_assets",
        "3D/2_model/1_projects",
        "3D/2_model/2_prerenders",
        "3D/2_model/3_review",
        "3D/2_model/4_publish"
    ],
    "Retopo": [
        "3D/3_retopo/0_assets",
        "3D/3_retopo/1_projects",
        "3D/3_retopo/2_prerenders",
        "3D/3_retopo/3_review",
        "3D/3_retopo/4_publish"
    ],
    "Rigging": [
        "3D/4_rigging/0_assets",
        "3D/4_rigging/1_projects",
        "3D/4_rigging/2_prerenders",
        "3D/4_rigging/3_review",
        "3D/4_rigging/4_publish"
    ],
    "Shaders": [
        "3D/5_shaders/0_assets",
        "3D/5_shaders/1_projects",
        "3D/5_shaders/2_prerenders",
        "3D/5_shaders/3_review",
        "3D/5_shaders/4_publish"
    ],
    "Match Move": [
        "3D/1_matchMove/0_assets",
        "3D/1_matchMove/1_projects",
        "3D/1_matchMove/2_prerenders",
        "3D/1_matchMove/3_review",
        "3D/1_matchMove/4_publish"
    ],
    "Animation": [
        "3D/6_animation/0_assets",
        "3D/6_animation/1_projects",
        "3D/6_animation/2_prerenders",
        "3D/6_animation/3_review",
        "3D/6_animation/4_publish"
    ],
    "FX": [
        "3D/7_fx/0_assets",
        "3D/7_fx/1_projects",
        "3D/7_fx/2_prerenders",
        "3D/7_fx/3_review",
        "3D/7_fx/4_publish"
    ],
    "Lighting": [
        "3D/8_lighting/0_assets",
        "3D/8_lighting/1_projects",
        "3D/8_lighting/2_prerenders",
        "3D/8_lighting/3_review",
        "3D/8_lighting/4_publish"
    ]
}


def resolve_existing_case(base_path: str, relative_folder: str) -> str:
    """Devuelve `relative_folder` con el caso REAL de lo que ya existe en disco.

    La tabla de arriba es la convencion canonica y va capitalizada (`Comp`,
    `CG`), que es como arman la ruta todos los lectores del pipeline. Pero
    esta herramienta creo carpetas en minuscula durante mucho tiempo, y en
    macOS `comp/` y `Comp/` son DOS carpetas distintas: crear la canonica al
    lado de la que ya existe partiria el shot en dos.

    Por eso, segmento por segmento, si ya hay uno que coincide sin importar
    mayusculas, se usa ese. Los segmentos que no existen se crean con el
    caso canonico. En Windows la funcion no cambia nada porque el filesystem
    no distingue.
    """
    partes = [p for p in relative_folder.replace("\\", "/").split("/") if p]
    actual = base_path
    resueltas = []
    for parte in partes:
        encontrada = parte
        try:
            objetivo = parte.lower()
            # Solo DIRECTORIOS: un archivo que se llame igual que la carpeta
            # no es la carpeta, y tomarlo mandaba a crear adentro de un
            # archivo (el error quedaba tapado como "ya existia").
            candidatos = sorted(
                entrada
                for entrada in os.listdir(actual)
                if entrada.lower() == objetivo
                and os.path.isdir(os.path.join(actual, entrada))
            )
            if candidatos:
                # En un filesystem case-sensitive pueden coexistir `comp` y
                # `Comp`. El orden de os.listdir no esta garantizado, asi que
                # gana el canonico si esta y si no el primero alfabetico.
                encontrada = parte if parte in candidatos else candidatos[0]
        except (OSError, ValueError):
            # Todavia no existe ese nivel: se sigue con el caso canonico.
            pass
        resueltas.append(encontrada)
        actual = os.path.join(actual, encontrada)
    return "/".join(resueltas)


def normalize_path(path: str) -> str:
    """
    Normaliza un path para comparación consistente.
    Convierte separadores, resuelve rutas relativas, etc.
    """
    return os.path.normpath(path)


def ensure_folder_exists(folder_path: str) -> tuple[bool, str]:
    """
    Asegura que una carpeta existe, creándola si es necesario.

    Args:
        folder_path: Path completo de la carpeta

    Returns:
        tuple: (bool: True si la carpeta fue creada, False si ya existía, str: mensaje de log)
    """
    folder_path = normalize_path(folder_path)

    if os.path.exists(folder_path):
        return False, f"📁 Carpeta ya existe: {folder_path}"
    else:
        try:
            os.makedirs(folder_path, exist_ok=True)
            return True, f"✅ Carpeta creada: {folder_path}"
        except Exception as e:
            error_msg = f"❌ Error creando carpeta {folder_path}: {e}"
            logger.error(error_msg)
            return False, error_msg


def create_task_folders(shot_base_path: str, task_names: List[str]) -> tuple[Dict[str, List[str]], List[str]]:
    """
    Crea la estructura de carpetas para las tasks especificadas.

    Args:
        shot_base_path: Path base del shot (ej: /project/seq/shot/)
        task_names: Lista de nombres de tasks para crear carpetas

    Returns:
        tuple: (Dict con resumen de carpetas, List con mensajes de log)
    """
    log_messages = []
    log_messages.append(f"🏗️  Creando estructura de carpetas para shot: {shot_base_path}")
    log_messages.append(f"📋 Tasks a procesar: {', '.join(task_names)}")

    created_folders = []
    existing_folders = []

    for task_name in task_names:
        if task_name not in TASK_FOLDER_STRUCTURE:
            warning_msg = f"⚠️  Task '{task_name}' no tiene estructura de carpetas definida"
            log_messages.append(warning_msg)
            logger.warning(warning_msg)
            continue

        log_messages.append(f"🔧 Procesando task: {task_name}")

        # Obtener la estructura de carpetas para esta task
        task_folders = TASK_FOLDER_STRUCTURE[task_name]

        for relative_folder in task_folders:
            # Respetar el caso de las carpetas que ya existan en el shot, para
            # no duplicar `Comp/` al lado de un `comp/` historico en macOS.
            relative_folder = resolve_existing_case(shot_base_path, relative_folder)
            # Construir path completo
            full_folder_path = os.path.join(shot_base_path, relative_folder)

            # Crear la carpeta
            was_created, log_msg = ensure_folder_exists(full_folder_path)
            log_messages.append(log_msg)

            if was_created:
                created_folders.append(full_folder_path)
            else:
                existing_folders.append(full_folder_path)

    # Resumen final
    summary = {
        "created": created_folders,
        "existing": existing_folders
    }

    total_created = len(created_folders)
    total_existing = len(existing_folders)
    log_messages.append("🎯 Resumen de carpetas:")
    log_messages.append(f"   ✅ Creadas: {total_created}")
    log_messages.append(f"   📁 Existentes: {total_existing}")

    if created_folders:
        log_messages.append("📂 Carpetas creadas:")
        for folder in created_folders:
            log_messages.append(f"   • {folder}")

    return summary, log_messages


def get_task_folder_structure(task_name: str) -> List[str]:
    """
    Obtiene la estructura de carpetas para una task específica.

    Args:
        task_name: Nombre de la task

    Returns:
        Lista de paths relativos de carpetas para esta task
    """
    return TASK_FOLDER_STRUCTURE.get(task_name, [])


def get_all_available_tasks() -> List[str]:
    """
    Obtiene lista de todas las tasks que tienen estructura de carpetas definida.

    Returns:
        Lista de nombres de tasks
    """
    return list(TASK_FOLDER_STRUCTURE.keys())


def validate_shot_base_path(shot_base_path: str) -> tuple[bool, List[str]]:
    """
    Valida que el path base del shot sea válido y accesible.

    Args:
        shot_base_path: Path a validar

    Returns:
        tuple: (bool: True si válido, List[str]: mensajes de log)
    """
    log_messages = []
    shot_base_path = normalize_path(shot_base_path)

    if not os.path.exists(shot_base_path):
        error_msg = f"❌ Path del shot no existe: {shot_base_path}"
        log_messages.append(error_msg)
        logger.error(error_msg)
        return False, log_messages

    if not os.path.isdir(shot_base_path):
        error_msg = f"❌ Path del shot no es un directorio: {shot_base_path}"
        log_messages.append(error_msg)
        logger.error(error_msg)
        return False, log_messages

    # Verificar permisos de escritura
    if not os.access(shot_base_path, os.W_OK):
        error_msg = f"❌ No hay permisos de escritura en: {shot_base_path}"
        log_messages.append(error_msg)
        logger.error(error_msg)
        return False, log_messages

    log_messages.append(f"✅ Path del shot validado: {shot_base_path}")

    return True, log_messages


# Funciones de compatibilidad para integración con código existente
def create_folders_for_shot_tasks(shot_path: str, enabled_tasks: List[str]) -> tuple[Dict[str, List[str]], List[str]]:
    """
    Función de compatibilidad para integración con CreateShot/ModifyShot.

    Args:
        shot_path: Path completo del shot
        enabled_tasks: Lista de tasks habilitadas

    Returns:
        tuple: (Dict con resumen de carpetas, List con mensajes de log)
    """
    all_log_messages = []

    # Agregar mensaje inicial
    all_log_messages.append(f"create_folders_for_shot_tasks called with shot_path='{shot_path}', tasks={enabled_tasks}")

    # Validar el path
    is_valid, validation_logs = validate_shot_base_path(shot_path)
    all_log_messages.extend(validation_logs)

    if not is_valid:
        return {"created": [], "existing": []}, all_log_messages

    # Crear las carpetas
    all_log_messages.append("validate_shot_base_path passed, calling create_task_folders")
    try:
        task_result = create_task_folders(shot_path, enabled_tasks)
        
        if not isinstance(task_result, tuple) or len(task_result) != 2:
            all_log_messages.append(f"ERROR: create_task_folders devolvió formato inválido: {type(task_result)}")
            return {"created": [], "existing": []}, all_log_messages
        
        summary, folder_logs = task_result
        
        if not isinstance(summary, dict) or not isinstance(folder_logs, (list, tuple)):
            all_log_messages.append(f"ERROR: Tipos inválidos - summary: {type(summary)}, folder_logs: {type(folder_logs)}")
            return {"created": [], "existing": []}, all_log_messages
        
        all_log_messages.extend(folder_logs)
        return summary, all_log_messages
        
    except Exception as e:
        import traceback
        error_msg = f"ERROR creando carpetas: {e}"
        all_log_messages.append(error_msg)
        all_log_messages.append(traceback.format_exc())
        return {"created": [], "existing": []}, all_log_messages


if __name__ == "__main__":
    # Ejemplo de uso para testing
    import sys

    def test_debug_print(msg):
        print(f"[DEBUG] {msg}")

    # Ejemplo de uso
    test_shot_path = "/test/project/seq/shot_001"
    test_tasks = ["Comp", "Model", "Lighting"]

    print("=== Test de creación de carpetas ===")
    result, logs = create_task_folders(test_shot_path, test_tasks)
    print("\nResultado:", result)
    print("\nLogs:")
    for log in logs:
        print(f"  {log}")
