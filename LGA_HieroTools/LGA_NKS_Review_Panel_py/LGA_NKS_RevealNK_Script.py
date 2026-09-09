"""
____________________________________________________________________

  LGA_NKS_RevealNK_Script v1.01 | Lega

  Revela el script NKS asociado al clip seleccionado en el explorador de archivos

  v1.01: La carpeta "Comp" de get_project_path() se resuelve contra el disco
         del shot con resolve_task_folder() de LGA_NKS_TaskScope, para que
         los shots viejos con "comp/" en minuscula se sigan encontrando en
         macOS. Sin poder importar TaskScope, cae al canonico "Comp".
  v1.00: Version inicial.
____________________________________________________________________

"""

import hiero.core
import hiero.ui
import os
import subprocess

DEBUG = False

def debug_print(*message):
    if DEBUG:
        print(*message)

def open_file_explorer(path):
    if os.name == 'nt':  # Windows
        os.startfile(os.path.dirname(path))
    elif os.name == 'posix':  # macOS
        subprocess.Popen(['open', os.path.dirname(path)])
    else:
        debug_print("Sistema operativo no soportado para abrir el explorador de archivos.")

def _comp_folder_name(shot_root):
    """Nombre de la carpeta de la task comp para ESTE shot ("Comp" o, en un
    shot viejo, "comp"), resuelto contra el disco via resolve_task_folder()
    de LGA_NKS_TaskScope. Sin shot_root o sin poder importar TaskScope, cae
    al canonico "Comp" (comportamiento historico de esta tool)."""
    try:
        try:
            from LGA_NKS_TaskScope import resolve_task_folder
        except ImportError:
            from LGA_NKS_Shared.LGA_NKS_TaskScope import resolve_task_folder
        return resolve_task_folder(shot_root, "comp", default="Comp")
    except Exception as exc:
        # No se silencia del todo: resolve_task_folder solo atrapa OSError y
        # ValueError, asi que cualquier otra cosa que caiga aca es un error
        # de programacion y tiene que quedar en el log.
        debug_print("No se pudo resolver la carpeta de comp, se usa 'Comp': %s" % exc)
        return "Comp"

def get_project_path(file_path):
    # Dividir el path en partes usando '/' como separador
    path_parts = file_path.split('/')
    # Construir la nueva ruta agregando '/<Comp>/1_projects'
    shot_root = '/'.join(path_parts[:4])
    project_path = shot_root + '/' + _comp_folder_name(shot_root) + '/1_projects'
    return project_path

def main():
    try:
        seq = hiero.ui.activeSequence()
        if not seq:
            debug_print("No hay una secuencia activa.")
            return

        te = hiero.ui.getTimelineEditor(seq)
        selected_clips = te.selection()

        if len(selected_clips) == 0:
            debug_print("*** No hay clips seleccionados en la pista ***")
            return
        else:
            for shot in selected_clips:
                if isinstance(shot, hiero.core.EffectTrackItem):  # Verificar si es un efecto
                    pass  
                else:
                    # Obtener el file path del clip seleccionado
                    file_path = shot.source().mediaSource().fileinfos()[0].filename() if shot.source().mediaSource().fileinfos() else None
                    if file_path:
                        debug_print(f"Path original del archivo: {file_path}")

                        # Obtener la nueva ruta del proyecto
                        project_path = get_project_path(file_path)
                        
                        # Asegurarnos de que la ruta termina con '/'
                        if not project_path.endswith('/'):
                            project_path += '/'
                        
                        debug_print(f"Ruta del proyecto: {project_path}")

                        # Abre el explorador de archivos en la nueva ruta del proyecto
                        open_file_explorer(project_path)
    except Exception as e:
        debug_print(f"Error: {e}")
