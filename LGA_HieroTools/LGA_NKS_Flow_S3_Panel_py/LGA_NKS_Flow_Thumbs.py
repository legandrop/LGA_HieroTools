"""
____________________________________________________________________

  LGA_NKS_Flow_Thumbs v1.03 | Lega

  Crea un snapshot del viewer actual con zoom to fill y lo guarda en <drive>/<proyecto>/Thumbs.
  Organiza por nombre de proyecto extraído del archivo.
  Maneja el track burn-in temporalmente para la captura y lo restaura al final.
  Actualizado para ser compatible con ambos sistemas de nomenclatura:
  - PROYECTO_SEQ_SHOT_DESC1_DESC2 (5 bloques con descripción)
  - PROYECTO_SEQ_SHOT (3 bloques simplificado)

  v1.03: La captura compartida apaga el VideoTrack BurnIn, espera el refresco
         del viewer antes de leerlo y restaura el estado aun si falla.
  v1.02: Project name extraído desde el segmento VFX-NOMBRE del path del archivo
         (con fallback al primer bloque del filename si el path no contiene VFX-).
         Corrige proyectos como PROJALT cuyos shots tienen prefijo PROJA en el filename.
____________________________________________________________________
"""

import hiero.core
import hiero.ui
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui, QtCore, Qt
QApplication = QtWidgets.QApplication
QRect = QtCore.QRect
QTimer = QtCore.QTimer

# Importar utilidades de naming
sys.path.append(str(Path(__file__).parent.parent / "LGA_NKS_Shared"))
from LGA_NKS_Flow_NamingUtils import (
    extract_shot_code,
    extract_project_name,
    extract_project_name_from_path,
    clean_base_name,
)
from SecureConfig_Reader import read_secure_config
from LGA_NKS_Shared.LGA_NKS_ThumbnailCapture import (
    BurnInTrackError,
    capture_viewer_image_without_burnin,
)

DEBUG = False
LOG_DIR = Path(__file__).parent / "logs"
LOG_PATH = LOG_DIR / "DebugPy_LGA_NKS_Flow_Thumbs.log"
_LOG_STARTED_AT = None


def _reset_log():
    global _LOG_STARTED_AT
    _LOG_STARTED_AT = time.monotonic()
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        LOG_PATH.write_text(
            f"Fecha: {datetime.now():%Y-%m-%d %H:%M:%S}\n",
            encoding="utf-8",
        )
    except Exception:
        pass


def debug_print(*message):
    text = " ".join(str(part) for part in message)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        elapsed = time.monotonic() - (_LOG_STARTED_AT or time.monotonic())
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(f"[{elapsed:.3f}s] {text}\n")
    except Exception:
        pass
    if DEBUG:
        print(text)


def get_work_root_drive():
    """
    Obtiene el root de trabajo desde App.AltTPath en config.secure.
    Fallback: T:
    """
    try:
        config = read_secure_config() or {}
        app_cfg = config.get("App", {}) if isinstance(config, dict) else {}
        raw_path = str(app_cfg.get("AltTPath", "")).strip()
        if raw_path:
            normalized = raw_path.replace("\\", "/").rstrip("/")
            if re.match(r"^[A-Za-z]:$", normalized):
                return normalized
            if re.match(r"^[A-Za-z]:/.*", normalized):
                return normalized
    except Exception as exc:
        debug_print(f"No se pudo leer AltTPath desde config.secure: {exc}")
    return "T:"


def get_project_name_from_clip():
    """
    Obtiene el nombre del proyecto desde el clip seleccionado.
    Usa funciones compartidas para extraer el nombre del proyecto.
    """
    sequence = hiero.ui.activeSequence()
    if not sequence:
        debug_print("No se encontró una secuencia activa.")
        return None

    timeline_editor = hiero.ui.getTimelineEditor(sequence)
    selected_clips = timeline_editor.selection()

    if not selected_clips:
        debug_print("No hay clips seleccionados en el timeline.")
        return None

    # Tomar el primer clip seleccionado
    clip = selected_clips[0]

    try:
        # Obtener el path del archivo
        file_path = clip.source().mediaSource().fileinfos()[0].filename()
        debug_print(f"File path: {file_path}")

        # Extraer nombre base del archivo usando función compartida
        filename = os.path.basename(file_path)
        base_name = clean_base_name(filename)
        
        # Usar función compartida para extraer el nombre del proyecto
        project_name = extract_project_name_from_path(file_path)
        if project_name:
            debug_print(f"Nombre del proyecto extraído (from path): {project_name}")
            return project_name
        project_name = extract_project_name(base_name)
        if project_name:
            debug_print(f"Nombre del proyecto extraído (from filename fallback): {project_name}")
            return project_name
        debug_print("No se pudo extraer el nombre del proyecto")
        return None

    except Exception as e:
        debug_print(f"Error extrayendo nombre del proyecto: {e}")
        return None


def get_shot_name_from_selected_clip():
    """
    Obtiene el nombre del shot desde el clip seleccionado o desde el path del archivo.
    Retorna el shot name o None si no se encuentra.
    """
    sequence = hiero.ui.activeSequence()
    if not sequence:
        debug_print("No se encontró una secuencia activa.")
        return None

    timeline_editor = hiero.ui.getTimelineEditor(sequence)
    selected_clips = timeline_editor.selection()

    if not selected_clips:
        debug_print("No hay clips seleccionados en el timeline.")
        # Si no hay clips seleccionados, usar el nombre de la secuencia
        sequence_name = sequence.name()
        debug_print(f"Usando nombre de secuencia: {sequence_name}")
        return sequence_name

    # Tomar el primer clip seleccionado
    clip = selected_clips[0]

    try:
        # Intentar obtener el shot name del clip
        shot_name = clip.name()
        if shot_name:
            debug_print(f"Shot name desde clip.name(): {shot_name}")
            return shot_name
    except:
        pass

    try:
        # Si no hay shot name, extraerlo del path del archivo
        file_path = clip.source().mediaSource().fileinfos()[0].filename()
        debug_print(f"File path: {file_path}")

        # Extraer nombre base del archivo usando utilidades de naming
        exr_name = os.path.basename(file_path)
        base_name = clean_base_name(exr_name)

        # Extraer shot_code usando detección automática de formato
        shot_code = extract_shot_code(base_name)
        if shot_code:
            debug_print(f"Shot code extraído del path: {shot_code}")
            return shot_code
        else:
            debug_print(f"Nombre base del archivo: {base_name}")
            return base_name

    except Exception as e:
        debug_print(f"Error extrayendo shot name del path: {e}")

    # Como último recurso, usar el nombre de la secuencia
    sequence_name = sequence.name()
    debug_print(f"Usando nombre de secuencia como fallback: {sequence_name}")
    return sequence_name


def force_viewer_refresh_conservative():
    """
    Fuerza el refresh del viewer usando métodos conservadores que no rompan el player.
    """
    debug_print("🔄 Iniciando refresh conservador del viewer...")

    try:
        viewer = hiero.ui.currentViewer()
        if not viewer:
            debug_print("❌ No hay viewer activo")
            return False

        # Método 1: Solo flush cache básico
        viewer.flushCache()
        debug_print("✅ viewer.flushCache() aplicado")

        # Método 2: Procesar eventos Qt una sola vez
        QApplication.processEvents()
        debug_print("✅ QApplication.processEvents() ejecutado")

        # NO usar hiero.ui.flushAllViewersCache() - puede ser demasiado agresivo
        # NO mover el tiempo del viewer - puede causar problemas
        # NO usar QTimer.singleShot - puede causar conflictos

        return True
    except Exception as e:
        debug_print(f"❌ Error en force_viewer_refresh_conservative: {e}")
        return False


def zoom_to_fill_simple():
    """
    Aplica zoom to fill al viewer actual (compatible con Nuke 15/16).
    En Nuke 16: viewer.zoomToFill()
    En Nuke 15: viewer.player().zoomToFill()
    """
    debug_print("🔍 Aplicando zoom to fill...")

    viewer = hiero.ui.currentViewer()
    if not viewer:
        debug_print("❌ No hay viewer activo")
        return False

    try:
        # Intentar método de Nuke 16 primero (viewer.zoomToFill)
        if hasattr(viewer, 'zoomToFill'):
            viewer.zoomToFill()
            debug_print("✅ Zoom to Fill aplicado con éxito (Nuke 16)")

        # Fallback a método de Nuke 15 (player.zoomToFill)
        elif hasattr(viewer, 'player'):
            player = viewer.player()
            if player and hasattr(player, 'zoomToFill'):
                player.zoomToFill()
                debug_print("✅ Zoom to Fill aplicado con éxito (Nuke 15)")
            else:
                debug_print("⚠️ zoomToFill no disponible en player - continuando sin zoom")
                return False
        else:
            debug_print("⚠️ zoomToFill no disponible en viewer - continuando sin zoom")
            return False

        # Solo un procesamiento básico de eventos
        QApplication.processEvents()
        debug_print("✅ Procesamiento básico de eventos Qt después del zoom")

        return True
    except Exception as e:
        debug_print(f"❌ Error aplicando zoom: {e}")
        return False


def crop_to_aspect_ratio(qimage, target_aspect):
    """
    Recorta la imagen a la relacion de aspecto especificada.
    """
    width = qimage.width()
    height = qimage.height()

    current_aspect = width / height

    if current_aspect > target_aspect:
        new_width = int(height * target_aspect)
        offset_x = int((width - new_width) / 2)
        rect = QRect(offset_x, 0, new_width, height)
        cropped = qimage.copy(rect)
        return cropped
    else:
        new_height = int(width / target_aspect)
        offset_y = int((height - new_height) / 2)
        rect = QRect(0, offset_y, width, new_height)
        cropped = qimage.copy(rect)
        return cropped


def get_next_available_filename(base_path, shot_name):
    """
    Obtiene el siguiente nombre de archivo disponible.
    Si existe, agrega _2, _3, etc.
    """
    # Nombre base: shotname.jpg
    base_filename = f"{shot_name}.jpg"
    full_path = os.path.join(base_path, base_filename)

    if not os.path.exists(full_path):
        return full_path, base_filename

    # Si existe, probar con sufijos
    counter = 2
    while True:
        suffix_filename = f"{shot_name}_{counter}.jpg"
        full_path = os.path.join(base_path, suffix_filename)

        if not os.path.exists(full_path):
            debug_print(f"Archivo con sufijo generado: {suffix_filename}")
            return full_path, suffix_filename

        counter += 1
        if counter > 999:  # Seguridad para evitar bucle infinito
            raise Exception("Demasiados archivos duplicados")


def main():
    _reset_log()
    debug_print("🚀 Iniciando LGA_NKS_Flow_Thumbs v1.03...")

    # Obtener el nombre del proyecto
    project_name = get_project_name_from_clip()
    if not project_name:
        print("❌ No se pudo obtener el nombre del proyecto")
        return

    # Resolver drive de trabajo por perfil (studio/project) desde config.secure.
    work_root = get_work_root_drive()
    if re.match(r"^[A-Za-z]:$", work_root):
        thumbs_dir = f"{work_root}/{project_name}/Thumbs"
    else:
        thumbs_dir = os.path.join(work_root, project_name, "Thumbs")
    debug_print(f"📁 Carpeta de destino: {thumbs_dir}")

    # Crear directorio si no existe
    try:
        os.makedirs(thumbs_dir, exist_ok=True)
        debug_print(f"✅ Directorio verificado/creado: {thumbs_dir}")
    except Exception as e:
        print(f"❌ No se pudo crear el directorio {thumbs_dir}: {e}")
        return

    try:
        # PASO 1: Obtener información del shot
        debug_print("📸 PASO 1: Obteniendo información del shot...")
        shot_name = get_shot_name_from_selected_clip()
        if not shot_name:
            print("❌ No se pudo obtener el nombre del shot")
            return

        # Limpiar el shot name para usarlo como nombre de archivo
        shot_name = re.sub(
            r'[<>:"/\\|?*]', "_", shot_name
        )  # Remover caracteres inválidos
        debug_print(f"🎬 Shot name limpio: {shot_name}")

        # PASO 2: Capturar imagen del viewer sin burn-in
        debug_print("📷 PASO 2: Capturando imagen del viewer sin burn-in...")
        viewer = hiero.ui.currentViewer()
        if not viewer:
            print("❌ No hay viewer activo")
            return

        sequence = hiero.ui.activeSequence()

        def capture_after_track_settles():
            debug_print("Aplicando zoom con el track BurnIn apagado")
            if not zoom_to_fill_simple():
                debug_print("No se pudo aplicar zoom to fill; se captura igualmente")
            debug_print("Esperando 0.5 s con el track BurnIn apagado")
            QApplication.processEvents()
            time.sleep(0.5)
            QApplication.processEvents()
            return viewer.image()

        qimage = capture_viewer_image_without_burnin(
            sequence,
            capture_after_track_settles,
            process_events=QApplication.processEvents,
            logger=debug_print,
        )
        if qimage is None or qimage.isNull():
            print("❌ viewer.image() devolvió None o imagen nula")
            return

        debug_print(f"✅ Imagen capturada: {qimage.width()} × {qimage.height()}")

        # PASO 3: Obtener relación de aspecto y crop
        debug_print("✂️ PASO 3: Aplicando crop de aspecto...")
        if sequence is None:
            debug_print("⚠️ No hay ninguna secuencia activa, usando 16:9 por defecto")
            target_aspect = 16 / 9
        else:
            format = sequence.format()
            width = format.width()
            height = format.height()
            target_aspect = width / height
            debug_print(
                f"📐 Relación de aspecto de la secuencia: {width} x {height} ({target_aspect:.2f})"
            )

        # Aplicar crop
        qimage_cropped = crop_to_aspect_ratio(qimage, target_aspect)
        debug_print(
            f"✅ Imagen cropped: {qimage_cropped.width()} × {qimage_cropped.height()}"
        )

        # PASO 4: Guardar archivo
        debug_print("💾 PASO 4: Guardando thumbnail...")
        try:
            full_path, filename = get_next_available_filename(thumbs_dir, shot_name)
            debug_print(f"📄 Archivo de destino: {filename}")

            # Guardar imagen
            ok = qimage_cropped.save(full_path, "JPEG")

            if ok and os.path.exists(full_path):
                print(
                    f"✅ Shot Thumbnail guardado en {project_name}/Thumbs: {filename}"
                )
                debug_print(f"📍 Ruta completa: {full_path}")
            else:
                print("❌ No se pudo crear el archivo")
                debug_print(
                    f"❌ save() result: {ok}, exists: {os.path.exists(full_path)}"
                )

        except Exception as e:
            print(f"❌ Error al guardar: {e}")
            debug_print(f"❌ Error completo: {e}")

    except BurnInTrackError as e:
        print(f"❌ No se pudo ocultar el track burn-in: {e}")
        debug_print(f"❌ Captura cancelada para evitar un thumbnail con burn-in: {e}")
    except Exception as e:
        print(f"❌ Error durante la operación principal: {e}")
        debug_print(f"❌ Error completo: {e}")

    finally:
        debug_print("🏁 Script completado")


# --- Main Execution ---
if __name__ == "__main__":
    main()
