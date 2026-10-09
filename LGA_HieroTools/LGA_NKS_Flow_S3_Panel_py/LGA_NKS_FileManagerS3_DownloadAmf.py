"""
____________________________________________________________________

  LGA_NKS_FileManagerS3_DownloadAmf v1.10 | Lega

  Descarga desde Wasabi S3 la carpeta _input/Look_Files del shot (los
  .amf/.cdl/.clf/.cube que hacen falta para ver bien los renders de comp).
  Reutiliza la deteccion de shot y el launcher de FileManagerS3 de
  LGA_NKS_FileManagerS3_Download.py.

  De que shots:
    - DOS o mas clips seleccionados -> el shot de cada uno, todos en UNA sola
      llamada al CLI (`--download <Look_Files 1> <Look_Files 2> ...`), con
      una carpeta por shot aunque haya varios clips del mismo.
    - UNO o ninguno -> el shot bajo el playhead, como siempre. Hiero
      autoselecciona el clip bajo el playhead, asi que "uno seleccionado" no
      distingue una eleccion del usuario (ver SELECCION_MINIMA).

  v1.10: Descarga en tanda. Con dos o mas clips seleccionados baja la
         Look_Files de todos esos shots de una vez, igual que Download Clip
         con los clips. Antes tomaba un solo clip y habia que ir shot por
         shot. El CLI de FileManagerS3 ya aceptaba varias rutas en
         `--download`; lo que faltaba era pasarselas.
  v1.00: version inicial.
____________________________________________________________________
"""

from pathlib import Path
import sys
import os
import subprocess
import logging
import queue
from logging.handlers import QueueHandler, QueueListener
import datetime
import time
import re

# Agregar ruta del módulo utilitario
utils_path = Path(__file__).parent.parent / "LGA_NKS_Shared"
if utils_path.exists():
    sys.path.insert(0, str(utils_path))
    from LGA_NKS_Shared.LGA_NKS_GetClip import get_clip_to_process, get_selected_clips
    from LGA_NKS_Shared import LGA_NKS_GetClip as clip_utils
    from LGA_NKS_Shared.LGA_NKS_FileManagerS3Launcher import (
        build_filemanagers3_command,
        resolve_context_mode,
    )

# Deteccion de la carpeta del shot: el helper central conoce los vendor codes de
# la DB de PipeSync (naming PROYECTO_SEQ_SHOT_VENDOR). Si no se puede importar,
# get_shot_path() cae al regex local, que no entiende vendor.
try:
    from LGA_NKS_Shared.LGA_NKS_Flow_NamingUtils import (
        is_shot_folder_name,
        extract_project_name_from_path,
    )
except ImportError:
    is_shot_folder_name = None
    extract_project_name_from_path = None

# Variables globales de logging (valores por defecto)
DEBUG = True
DEBUG_CONSOLE = False
DEBUG_LOG = True
script_start_time = None
debug_log_listener = None

# Variable de desarrollo para cambiar la ruta del ejecutable
Desarrollo = True

# Cuantos clips seleccionados hacen falta para creerle a la seleccion.
#
# Hiero AUTOSELECCIONA el clip bajo el playhead: parado sobre un shot y sin
# haber hecho click en nada, la seleccion ya trae UN item. Con dos o mas la
# seleccion es deliberada y se bajan todos esos shots; con uno o ninguno manda
# el playhead, que es como funciono siempre este boton. Misma regla que
# LGA_NKS_ApplyAMF (ver Docu_Metodos_Seleccion_Clip.md, Metodo 3).
SELECCION_MINIMA = 2

# Donde vive la carpeta de look, colgando del shot.
LOOK_FILES_SUBPATH = "_input/Look_Files"

class RelativeTimeFormatter(logging.Formatter):
    """Formatter con hora absoluta y tiempo relativo desde el inicio."""

    def format(self, record):
        global script_start_time
        if script_start_time is None:
            script_start_time = record.created

        relative_time = record.created - script_start_time
        record.relative_time = f"{relative_time:.3f}s"
        return super().format(record)


def setup_debug_logging(script_name="FileManagerS3_DownloadAmf"):
    """Configura el logging para escribir SOLO en archivo."""
    global debug_log_listener

    log_filename = f"debugPy_{script_name}.log"
    log_file_path = os.path.join(
        os.path.dirname(__file__), "..", "logs", log_filename
    )

    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

    # Limpieza diaria: si el log no es de hoy, se borra y se agrega encabezado con fecha
    today_str = datetime.date.today().isoformat()
    should_reset = True
    if os.path.exists(log_file_path):
        try:
            with open(log_file_path, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
            should_reset = first_line != f"Fecha: {today_str}"
        except Exception:
            should_reset = True

    if should_reset:
        try:
            with open(log_file_path, "w", encoding="utf-8") as f:
                f.write(f"Fecha: {today_str}\n")
        except Exception as e:
            print(f"Warning: No se pudo resetear el log: {e}")

    logger_name = f"{script_name.lower()}_logger"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    if logger.handlers:
        logger.handlers.clear()

    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    formatter = RelativeTimeFormatter(
        "[%(asctime)s] [%(relative_time)s] %(message)s", datefmt="%H:%M:%S"
    )
    file_handler.setFormatter(formatter)

    log_queue = queue.Queue()
    queue_handler = QueueHandler(log_queue)
    queue_handler.setLevel(logging.DEBUG)
    logger.addHandler(queue_handler)

    if debug_log_listener:
        try:
            debug_log_listener.stop()
        except Exception:
            pass

    debug_log_listener = QueueListener(
        log_queue, file_handler, respect_handler_level=True
    )
    debug_log_listener.daemon = True
    debug_log_listener.start()

    return logger


debug_logger = setup_debug_logging(script_name="FileManagerS3_DownloadAmf")


def debug_print(*message, level="info"):
    global script_start_time

    msg = " ".join(str(arg) for arg in message)

    if DEBUG and DEBUG_LOG:
        if script_start_time is None:
            script_start_time = time.time()
        if level == "debug":
            debug_logger.debug(msg)
        elif level == "warning":
            debug_logger.warning(msg)
        elif level == "error":
            debug_logger.error(msg)
        else:
            debug_logger.info(msg)

    if DEBUG and DEBUG_CONSOLE:
        if script_start_time is None:
            script_start_time = time.time()
        relative_time = time.time() - script_start_time
        print(f"[{relative_time:.3f}s] {msg}")


def get_shot_path(file_path):
    normalized_path = os.path.normpath(file_path)
    path_parts = normalized_path.replace("\\", "/").split("/")
    debug_print(f"Partes de la ruta: {path_parts}")

    # 1) Deteccion por patron de nombre de shot (ej: PROJF_050_010)
    # El helper central valida el vendor code contra la DB de PipeSync; el regex
    # queda como fallback para cuando NamingUtils no se pudo importar.
    shot_pattern = re.compile(
        r"^[A-Za-z0-9]+(?:_[A-Za-z]+|_[0-9]{3,5}[A-Za-z]?)?_[0-9]{3,5}[A-Za-z]?_[0-9]{3,4}$"
    )
    project_name = (
        extract_project_name_from_path(file_path)
        if extract_project_name_from_path
        else None
    )
    for i in range(len(path_parts) - 1, -1, -1):
        segmento = path_parts[i]
        if is_shot_folder_name:
            es_shot = is_shot_folder_name(segmento, project_name)
        else:
            es_shot = bool(shot_pattern.match(segmento))
        if es_shot:
            shot_path = "/".join(path_parts[: i + 1])
            debug_print(f"Ruta del shot detectada por patron: {shot_path}")
            return shot_path

    # 2) Deteccion por estructura de ruta (root + proyecto/grupo/shot)
    root_len = 0
    if len(path_parts) >= 2 and path_parts[0] == "" and path_parts[1] == "Volumes":
        root_len = 3  # /Volumes/<volumen>
        if len(path_parts) > 3 and re.match(r"^[A-Za-z]$", path_parts[3]):
            root_len = 4  # /Volumes/<volumen>/<drive>
    elif path_parts and re.match(r"^[A-Za-z]:$", path_parts[0]):
        root_len = 1  # T:
    elif len(path_parts) >= 4 and path_parts[0] == "" and path_parts[1] == "":
        root_len = 4  # //server/share
    else:
        root_len = 1 if path_parts and path_parts[0] else 0

    expected_len = root_len + 3
    if expected_len > 0 and len(path_parts) >= expected_len:
        shot_path = "/".join(path_parts[:expected_len])
        debug_print(f"Ruta del shot por estructura: {shot_path}")
        return shot_path

    # 3) Fallback si no hay suficientes partes
    debug_print("Ruta no tiene suficientes partes, usando fallback")
    clip_folder = os.path.dirname(file_path)
    input_folder = os.path.dirname(clip_folder)
    return os.path.dirname(input_folder)


def build_filemanagers3_cmd(action_flag, paths):
    """Arma la llamada al CLI con una o varias rutas detras del mismo flag."""
    try:
        context_mode = resolve_context_mode()
        cmd = build_filemanagers3_command(
            [action_flag] + list(paths),
            desarrollo=Desarrollo,
            script_dir=Path(__file__).parent,
            context_mode=context_mode,
        )
        debug_print(f"Contexto FileManagerS3 resuelto: {context_mode}")
        return cmd
    except Exception as exc:
        debug_print(f"No se pudo construir comando de FileManagerS3: {exc}", level="error")
        return None


def get_target_clips():
    """Los clips de los que hay que bajar el look, y de donde salieron.

    Devuelve (clips, origen) con origen en {'seleccion', 'playhead'}. La regla
    es por CANTIDAD (ver SELECCION_MINIMA): con menos de dos seleccionados se
    usa el metodo hibrido de siempre (playhead primero, seleccion de respaldo).
    """
    seleccionados = get_selected_clips()
    if len(seleccionados) >= SELECCION_MINIMA:
        return seleccionados, "seleccion"

    clip = get_clip_to_process(track_name=None, prioritize_multiple_selection=False)
    return ([clip] if clip else []), "playhead"


def clip_file_path(clip):
    """Ruta de la media del clip, o None si no tiene."""
    try:
        fileinfos = clip.source().mediaSource().fileinfos()
        return fileinfos[0].filename() if fileinfos else None
    except Exception as e:
        debug_print(f"No se pudo leer la media del clip: {e}", level="warning")
        return None


def look_files_paths(clips):
    """Las carpetas Look_Files a bajar: una por shot, en el orden de los clips.

    Varios clips del mismo shot (aPlate, bPlate, _comp_) comparten carpeta, asi
    que se deduplica: mandarla repetida al CLI abriria la misma descarga varias
    veces. No se chequea si existe localmente: el punto del boton es bajarla
    justamente cuando no esta en disco.
    """
    paths = []
    vistos = set()
    for clip in clips:
        try:
            nombre = clip.name()
        except Exception:
            nombre = "<sin nombre>"
        file_path = clip_file_path(clip)
        if not file_path:
            debug_print(f"Clip '{nombre}' sin ruta de media: se omite", level="warning")
            continue

        # La estructura es: unidad:/proyecto/grupo/shot/_input/version/archivo
        shot_path = get_shot_path(file_path)
        look_path = shot_path.rstrip("/") + "/" + LOOK_FILES_SUBPATH
        debug_print(f"Clip '{nombre}': {file_path}")
        debug_print(f"  shot: {shot_path}")

        clave = look_path.lower()
        if clave in vistos:
            debug_print("  Look_Files de ese shot ya esta en la tanda")
            continue
        vistos.add(clave)
        debug_print(f"  Look_Files: {look_path}")
        paths.append(look_path)
    return paths


def main():
    """Descarga desde Wasabi S3 la carpeta _input/Look_Files de uno o varios shots."""
    debug_print("=== FILEMANAGER DOWNLOAD AMF (Look_Files) ===")

    try:
        clips, origen = get_target_clips()
        if not clips:
            debug_print("No se encontró clip para procesar")
            return
        debug_print(f"Clips a mirar: {len(clips)} (por {origen})")

        paths = look_files_paths(clips)
        if not paths:
            debug_print("No se pudo resolver ninguna carpeta Look_Files", level="warning")
            return

        # Una sola llamada con todas las carpetas: el CLI acepta varias rutas
        # detras de --download y encola una descarga por cada una.
        cmd = build_filemanagers3_cmd("--download", paths)
        if not cmd:
            return

        debug_print(f"Ejecutando: {' '.join(cmd)}")

        try:
            # No se espera a que termine: FileManagerS3 abre su GUI.
            subprocess.Popen(cmd, shell=False)
            debug_print(f"FileManagerS3 iniciado para descargar Look_Files de {len(paths)} shot(s)")
        except Exception as cmd_error:
            debug_print(f"Error al ejecutar FileManagerS3: {cmd_error}", level="error")

    except Exception as e:
        debug_print(f"Error al procesar los clips: {e}", level="error")


if __name__ == "__main__":
    main()
