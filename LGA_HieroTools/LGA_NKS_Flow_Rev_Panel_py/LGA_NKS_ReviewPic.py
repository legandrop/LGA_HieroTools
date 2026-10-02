"""
____________________________________________________________________

  LGA_NKS_ReviewPic v1.25 | Lega

  Crea un snapshot de la imagen actual del viewer y lo guarda en ReviewPic_Cache
  organizando por clips del track EXR de la task activa con numeracion de frames,
  y lo abre en FrameRev para anotarlo en el mismo archivo.
  Actualizado para ser compatible con ambos sistemas de nomenclatura:
  - PROYECTO_SEQ_SHOT_DESC1_DESC2 (5 bloques con descripción)
  - PROYECTO_SEQ_SHOT (3 bloques simplificado)

  v1.25: Se captura el viewer entero y solo se recorta el negro que lo rodea,
         de cualquier lado (LGA_NKS_ViewerCrop). Antes se recortaba centrado al
         aspect ratio de la secuencia, que con zoom o paneo cortaba imagen o
         dejaba negro.
  v1.24: El JPG se abre en FrameRev (--edit-image, ver LGA_NKS_FrameRev) en vez
         del ShareX ImageEditor LGA que viajaba en el pack. Funciona tambien en
         macOS, y si FrameRev falta o es viejo se avisa con un cartel.
  v1.23: El debug por consola queda apagado por default.
  v1.22: Se tiene en cuenta el pixel aspect ratio (PAR) del formato. El viewer.image()
         ya entrega la imagen con el PAR aplicado (proporciones de display), por lo que
         el crop ahora se hace contra el DISPLAY aspect (storage * PAR) en lugar del
         storage aspect. Antes, en timelines con PAR != 1, se recortaban los lados de
         la imagen (canvas muy chico en X). No se estira la imagen (eso la distorsiona).
  v1.21: Task alias normalizado (compo → comp) en resolve_task_with_mismatch_check
         para evitar falsa advertencia de mismatch en clips con _Compo_ en el filename.
  v1.20: Imports de TaskSelectionDialog movidos a lazy (dentro de main()) para evitar
         "QWidget: Must construct a QApplication before a QWidget" en Nuke 15 (PySide2).
         Compatible con Nuke 15 y 16 usando LGA_QtAdapter_HieroTools.
  v1.10: Usa TaskSelectionDialog para detectar la task activa en el playhead (comp/roto/cleanup).
         Si hay múltiples tasks, muestra selector. Si hay mismatch filename/track, avisa y excluye.
  v1.01: Usa el módulo utilitario LGA_NKS_GetClip para obtener el clip a partir del playhead (no permite selecciones múltiples)
____________________________________________________________________

"""

import hiero.core
import hiero.ui
import os
import re
import glob
from pathlib import Path
# Importar compatibilidad Qt para Hiero Panels (PySide2/PySide6)
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets

# Reasignar clases para compatibilidad con código existente
QApplication = QtWidgets.QApplication
import sys

DEBUG = False

def debug_print(*message):
    if DEBUG:
        print(*message)


# Importar utilidades base (sin Qt, seguras en cualquier contexto de carga)
utils_path = Path(__file__).parent.parent / "LGA_NKS_Shared"
if utils_path.exists():
    sys.path.insert(0, str(utils_path))
    from LGA_NKS_Shared.LGA_NKS_GetClip import get_clip_to_process
    # Sincronizar el debug con el módulo utilitario
    from LGA_NKS_Shared import LGA_NKS_GetClip as clip_utils
    clip_utils.DEBUG = DEBUG
else:
    debug_print("ERROR: No se encontró el módulo LGA_NKS_GetClip")


def parse_exr_name(file_name):
    """
    Extrae el nombre base y numero de version de un archivo EXR.
    """
    version_match = re.search(r"_v(\d+)", file_name)
    version_number = version_match.group(1) if version_match else "Unknown"
    base_name = re.sub(r"_v\d+_%04d\.exr", "", file_name)
    return base_name, version_number


def get_clip_info_from_clip(clip):
    """
    Extrae información del clip (base_name, version_number, frame_number).
    Retorna (base_name, version_number, frame_number) o None si hay error.
    """
    if not clip:
        return None
    
    try:
        viewer = hiero.ui.currentViewer()
        if not viewer:
            debug_print("No se encontró un visor activo.")
            return None

        current_time = viewer.time()
        debug_print(f"Tiempo actual del playhead: {current_time}")

        file_path = clip.source().mediaSource().fileinfos()[0].filename()
        fileinfo = clip.source().mediaSource().fileinfos()[0]
        exr_name = os.path.basename(file_path)
        base_name, version_number = parse_exr_name(exr_name)

        start_frame = fileinfo.startFrame()
        frame_offset = current_time - clip.timelineIn()
        frame_number = int(start_frame + frame_offset)

        debug_print(f"Clip encontrado: {base_name}_v{version_number}")
        debug_print(f"Frame calculado: {frame_number:04d}")

        return base_name, version_number, frame_number
    except Exception as e:
        debug_print(f"Error extrayendo información del clip: {e}")
        return None


def get_next_available_filename(base_path, base_name, frame_number):
    """
    Obtiene el siguiente nombre de archivo disponible.
    Si existe, agrega _2, _3, etc.
    """
    # Nombre base: clipname_vXX_frameXXXX.jpg
    base_filename = f"{base_name}_{frame_number:04d}.jpg"
    full_path = os.path.join(base_path, base_filename)

    if not os.path.exists(full_path):
        return full_path, base_filename

    # Si existe, probar con sufijos
    counter = 2
    while True:
        suffix_filename = f"{base_name}_{frame_number:04d}_{counter}.jpg"
        full_path = os.path.join(base_path, suffix_filename)

        if not os.path.exists(full_path):
            debug_print(f"Archivo con sufijo generado: {suffix_filename}")
            return full_path, suffix_filename

        counter += 1
        if counter > 999:  # Seguridad para evitar bucle infinito
            raise Exception("Demasiados archivos duplicados")


def main():
    # Imports lazy para evitar "QWidget: Must construct a QApplication before a QWidget"
    # en Nuke 15 (PySide2). Se importan aquí y no al cargar el módulo para garantizar
    # que QApplication ya existe cuando se ejecutan (igual que en LGA_NKS_Flow_Push.py).
    from LGA_NKS_Shared.LGA_NKS_TaskSelectionDialog import (
        resolve_task_with_mismatch_check,
        track_for_task,
    )
    from LGA_NKS_Shared.LGA_NKS_Flow_NamingUtils import extract_task_name, clean_base_name, normalize_task_name

    def _extract_task_normalized(base_name):
        raw = extract_task_name(base_name)
        return normalize_task_name(raw) if raw else raw

    # Resolver task activa en el playhead (comp/roto/cleanup) con chequeo de mismatch
    seq = hiero.ui.activeSequence()
    if not seq:
        print("❌ No hay secuencia activa")
        return

    task = resolve_task_with_mismatch_check(
        seq, _extract_task_normalized, clean_base_name,
        title="Review Pic — Seleccionar task"
    )
    if task is None:
        print("❌ No se seleccionó ninguna task o no hay clips en el playhead")
        return

    debug_print(f"Task seleccionada para Review Pic: {task}")

    # Obtener el clip del track correspondiente a la task seleccionada
    clip = get_clip_to_process(track_name=track_for_task(task), prioritize_multiple_selection=False)
    if not clip:
        print("❌ No se pudo obtener información del clip en el track")
        return

    # Extraer información del clip
    clip_info = get_clip_info_from_clip(clip)
    if not clip_info:
        print("❌ No se pudo extraer información del clip")
        return

    base_name, version_number, frame_number = clip_info
    clip_folder_name = f"{base_name}_v{version_number}"

    # Crear carpeta de cache relativa al script
    script_dir = os.path.dirname(__file__)
    cache_dir = os.path.join(script_dir, "ReviewPic_Cache")
    clip_dir = os.path.join(cache_dir, clip_folder_name)

    # Crear directorios si no existen
    os.makedirs(clip_dir, exist_ok=True)
    debug_print(f"Carpeta de destino: {clip_dir}")

    # Obtener imagen del viewer
    viewer = hiero.ui.currentViewer()
    if not viewer:
        print("❌ No hay viewer activo")
        return

    qimage = viewer.image()
    if qimage is None or qimage.isNull():
        print("❌ viewer.image() devolvió None o imagen nula")
        return

    # Se captura el viewer entero y solo se le saca el negro que lo rodea, de
    # cualquier lado (ver LGA_NKS_ViewerCrop): con zoom o paneo, recortar al
    # aspect ratio de la secuencia cortaba imagen o dejaba negro.
    from LGA_NKS_Shared.LGA_NKS_ViewerCrop import crop_black_borders

    qimage_cropped = crop_black_borders(qimage)
    debug_print(
        f"Snapshot size (cropped): {qimage_cropped.width()} × {qimage_cropped.height()}"
    )

    # Generar nombre de archivo con verificacion de duplicados
    try:
        full_path, filename = get_next_available_filename(
            clip_dir, clip_folder_name, frame_number
        )
        debug_print(f"Archivo de destino: {filename}")

        # Guardar imagen
        ok = qimage_cropped.save(full_path, "JPEG")

        if ok and os.path.exists(full_path):
            print(f"✅ ReviewPic guardado: {clip_folder_name}/{filename}")
            debug_print(f"Ruta completa: {full_path}")

            # Abrir el JPG en FrameRev para anotarlo: Save lo pisa en su lugar, que es
            # donde Flow Push lo busca (ver LGA_NKS_FrameRev).
            from LGA_NKS_Shared import LGA_NKS_FrameRev

            error = LGA_NKS_FrameRev.edit_image(full_path)
            if error:
                print(f"❌ No se pudo abrir FrameRev: {error}")
                LGA_NKS_FrameRev.warn_user(
                    "The review picture was saved, but it could not be opened for annotation.\n\n"
                    + error
                )

        else:
            print("❌ No se pudo crear el archivo.")
            debug_print(f"save() result: {ok}, exists: {os.path.exists(full_path)}")

    except Exception as e:
        print(f"❌ Error al guardar: {e}")
        debug_print(f"Error completo: {e}")


# --- Main Execution ---
if __name__ == "__main__":
    main()
