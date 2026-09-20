"""
____________________________________________________________________

  LGA_NKS_RevealNKS_Project v1.01 | Lega

  Revela el proyecto NKS activo en el explorador de archivos

  v1.01: Resuelve el proyecto desde la secuencia activa. Si no hay secuencia,
         solo usa fallback cuando existe un unico proyecto abierto.
____________________________________________________________________

"""

import hiero.core
import hiero.ui
import os
import subprocess
import sys

DEBUG = False

def debug_print(*message):
    if DEBUG:
        print(*message)

def open_file_explorer(path):
    folder = os.path.dirname(path)
    if sys.platform == "darwin":
        subprocess.Popen(["open", folder])
    elif os.name == "nt":
        os.startfile(folder)
    else:
        subprocess.Popen(["xdg-open", folder])

def get_active_project():
    """
    Obtiene el proyecto activo en Hiero.

    Returns:
    - hiero.core.Project o None: El proyecto activo, o None si no se encuentra ningun proyecto activo.
    """
    try:
        sequence = hiero.ui.activeSequence()
        if sequence is not None:
            return sequence.project()
    except Exception as exc:
        debug_print(f"No se pudo resolver el proyecto de la secuencia activa: {exc}")

    projects = hiero.core.projects()
    return projects[0] if len(projects) == 1 else None

def main():
    try:
        # Obtener el proyecto activo
        project = get_active_project()
        if project:
            # Obtener el directorio del proyecto activo
            project_path = project.path()
            if not project_path:
                debug_print("El proyecto activo todavia no fue guardado.")
                return

            # Imprimir el directorio del proyecto activo
            debug_print(f"El directorio del proyecto activo es: {project_path}")
            open_file_explorer(project_path)
        else:
            debug_print("No se encontro un proyecto activo en Hiero.")
    except Exception as e:
        debug_print(f"Error: {e}")
