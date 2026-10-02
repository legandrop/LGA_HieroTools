"""
____________________________________________________________________

  LGA_NKS_FrameRev v1.00 | Lega

  Ubica FrameRev, la app de anotacion de imagenes de LGA, y le pasa
  imagenes para anotar. Es el editor de Review Pic y del Shift+Click
  de Snapshot; reemplaza al ShareX ImageEditor LGA que viajaba dentro
  del pack.

  FrameRev se instala aparte y NO viaja en el pack. Su ubicacion sale
  del registro compartido de apps LGA: cada app escribe al arrancar
  un <App>.json con su ejecutable y su version en
      Windows  %APPDATA%\\LGA\\FrameRev.json
      macOS    ~/Library/Application Support/LGA/FrameRev.json
  No hay ruta de instalacion clavada como respaldo: si el JSON falta,
  se avisa al usuario nombrando que hacer.

  Dos entradas de FrameRev, segun lo que se quiere al guardar:
      --edit-image <ruta>     abre un archivo propio; Save lo pisa en su
                              lugar (Review Pic: el JPG anotado queda
                              donde Flow Push lo busca).
      --open-capture <ruta>   abre un TEMPORAL que FrameRev borra apenas
                              lo lee; Save pregunta donde guardar
                              (Snapshot: captura sin archivo propio).
  Las dos abren una ventana SECUNDARIA (sin bandeja ni atajos globales).
  Lanzar FrameRev.exe a secas con la app ya abierta arrancaria una
  segunda copia completa: por eso se exige MIN_VERSION, la primera que
  entiende --edit-image. Una version vieja ignora el flag en silencio.

  v1.00: Version inicial.
____________________________________________________________________
"""

import json
import os
import subprocess
import sys
import tempfile
import time

DEBUG = False

APP_NAME = "FrameRev"
# Primera version de FrameRev con --edit-image (ver docstring).
MIN_VERSION = (0, 265)
# Nombre de app que FrameRev usa para sugerir el nombre en Save As de una captura.
CAPTURE_APP_NAME = "Hiero"

_HIEROTOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_PATH = os.path.join(_HIEROTOOLS_DIR, "logs", "DebugPy_LGA_NKS_FrameRev.log")

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
            handle.write("Fecha: {0}\n".format(time.strftime("%Y-%m-%d %H:%M:%S")))
            handle.write("\n".join(_LOG_LINES) + "\n")
    except Exception:
        pass
    del _LOG_LINES[:]


# ------------------------------------------------------------------ registro


def registry_file(platform_name=None, environ=None, home=None):
    """Ruta del FrameRev.json del registro compartido de apps LGA."""
    platform_name = platform_name or sys.platform
    environ = os.environ if environ is None else environ
    home = home or os.path.expanduser("~")
    if platform_name.startswith("win"):
        base = environ.get("APPDATA") or os.path.join(home, "AppData", "Roaming")
        return os.path.join(base, "LGA", APP_NAME + ".json")
    if platform_name == "darwin":
        return os.path.join(home, "Library", "Application Support", "LGA", APP_NAME + ".json")
    return os.path.join(home, ".local", "share", "LGA", APP_NAME + ".json")


def parse_version(text):
    """'0.265' -> (0, 265). Devuelve None si no es un numero de version."""
    try:
        return tuple(int(part) for part in str(text).strip().split("."))
    except (TypeError, ValueError):
        return None


def _format_version(version):
    return ".".join(str(part) for part in version)


def find_framerev(json_path=None, file_exists=os.path.isfile):
    """Busca FrameRev en el registro de apps LGA.

    Devuelve (ejecutable, None) si esta instalado y alcanza MIN_VERSION, o
    (None, mensaje) con el texto en ingles para mostrarle al usuario.
    """
    json_path = json_path or registry_file()
    debug_print("Registro:", json_path)
    not_installed = (
        "FrameRev is not installed, or it has not been opened yet on this computer.\n"
        "Install FrameRev, open it once, and try again."
    )
    if not file_exists(json_path):
        debug_print("No existe el registro de FrameRev.")
        return None, not_installed
    try:
        # utf-8-sig: un JSON editado a mano en Windows puede traer BOM.
        with open(json_path, "r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as error:
        debug_print("No se pudo leer el registro:", error)
        return None, not_installed
    if not isinstance(data, dict):
        debug_print("El registro no es un objeto JSON:", type(data).__name__)
        return None, not_installed

    executable = str(data.get("executable") or "")
    version = parse_version(data.get("version"))
    debug_print("Registro dice: ejecutable =", executable, "| version =", data.get("version"))
    if not executable or not file_exists(executable):
        debug_print("El ejecutable registrado no existe.")
        return None, (
            "FrameRev is not where it was registered:\n{0}\n"
            "Open FrameRev once so it registers its current location, and try again."
        ).format(executable or "(empty)")
    if version is None or version < MIN_VERSION:
        debug_print("Version insuficiente.")
        return None, (
            "This tool needs FrameRev {0} or later, and version {1} is installed.\n"
            "Update FrameRev and try again."
        ).format(_format_version(MIN_VERSION), data.get("version") or "unknown")
    return executable, None


# ------------------------------------------------------------------ lanzamiento


def _launch(command):
    """Lanza FrameRev desacoplado de Hiero. Devuelve None o el mensaje de error."""
    debug_print("Comando:", command)
    kwargs = {"close_fds": True}
    if sys.platform.startswith("win"):
        # Sin consola heredada y en su propio grupo: cerrar Hiero no cierra FrameRev.
        kwargs["creationflags"] = (
            getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        )
    try:
        subprocess.Popen(command, **kwargs)
    except OSError as error:
        debug_print("Fallo el lanzamiento:", error)
        return "FrameRev could not be started:\n{0}".format(error)
    return None


def edit_image(image_path, json_path=None):
    """Abre `image_path` en FrameRev para anotarlo y guardarlo en el MISMO archivo.

    Devuelve None si FrameRev arranco, o el mensaje para el usuario.
    """
    try:
        image_path = os.path.abspath(image_path)
        debug_print("edit_image:", image_path)
        executable, error = find_framerev(json_path)
        if error:
            return error
        return _launch([executable, "--edit-image", image_path])
    finally:
        _volcar_log()


def open_capture(qimage, json_path=None, temp_dir=None):
    """Abre una captura (QImage) en FrameRev SIN dejar archivo propio.

    Se escribe a un PNG temporal que FrameRev borra apenas lo lee
    (--open-capture). Si FrameRev no arranca, el temporal se borra aca.
    Devuelve None si FrameRev arranco, o el mensaje para el usuario.
    """
    temp_path = None
    try:
        executable, error = find_framerev(json_path)
        if error:
            return error
        handle, temp_path = tempfile.mkstemp(
            prefix="LGA_HieroTools_Snapshot_", suffix=".png", dir=temp_dir
        )
        os.close(handle)
        # Calidad 80 = compresion zlib baja: es un temporal de un solo uso y esto
        # corre en el hilo de la UI de Hiero (FrameRev hace lo mismo con los suyos).
        if not qimage.save(temp_path, "PNG", 80):
            debug_print("No se pudo escribir el temporal:", temp_path)
            return "The snapshot could not be written to a temporary file."
        debug_print("Temporal:", temp_path)
        error = _launch([executable, "--open-capture", temp_path,
                         "--capture-app-name", CAPTURE_APP_NAME])
        if error is None:
            temp_path = None  # ahora es de FrameRev: lo borra al leerlo
        return error
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        _volcar_log()


def warn_user(error, parent=None):
    """Muestra `error` con el cartel estandar del pack."""
    from LGA_NKS_Shared.LGA_NKS_MessageBox import show_warning

    show_warning(parent, "FrameRev", error)
