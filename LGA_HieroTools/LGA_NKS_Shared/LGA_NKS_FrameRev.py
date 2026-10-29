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

  Al frente (solo Windows): la ventana de FrameRev la abre un proceso
  NUEVO, y Windows no le deja tomar el foco solo -- su activateWindow()
  apenas hace titilar el boton de la barra de tareas y la ventana queda
  detras de Hiero. Quien SI puede ceder el frente es Hiero, que es la
  app del frente cuando el usuario hace click. Por eso, despues de
  lanzar, un QTimer en el hilo de la UI espera la ventana de FrameRev y
  la trae con SetForegroundWindow. Si mientras tanto el usuario se fue a
  otra app, no se le roba el foco.

  v1.01: FrameRev se abre al frente y con foco, no detras de Hiero.
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
        process = subprocess.Popen(command, **kwargs)
    except OSError as error:
        debug_print("Fallo el lanzamiento:", error)
        return "FrameRev could not be started:\n{0}".format(error)
    debug_print("FrameRev lanzado, pid", process.pid)
    if sys.platform.startswith("win"):
        _bring_to_front_when_ready(process)
    return None


# ------------------------------------------------------------------ al frente

# Cada cuanto se busca la ventana de FrameRev y cuanto se la espera. Arranca en
# ~1 s; 15 s cubre una maquina lenta o el primer arranque tras instalar.
FRONT_POLL_MS = 100
FRONT_TIMEOUT_MS = 15000

# Los QTimer vivos: sin una referencia, Python los recolecta y dejan de sonar.
_FRONT_WATCHERS = []


def pick_main_window(windows):
    """Elige la ventana principal de FrameRev entre sus ventanas de nivel superior.

    `windows` es una lista de dicts con hwnd, visible, owned, tool, cloaked y
    area. Se descartan las invisibles, las que tienen dueño (dialogos), las
    tool windows (toasts, popovers) y las encapadas: FrameRev encapa la ventana
    mientras ajusta el zoom, y Windows no trae al frente una ventana encapada.
    De las que quedan, la mas grande. Devuelve el hwnd o None.
    """
    candidates = [
        w for w in windows
        if w["visible"] and not w["owned"] and not w["tool"] and not w["cloaked"] and w["area"] > 0
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda w: w["area"])["hwnd"]


def front_step(foreground_pid, own_pid, child_pid, child_alive, main_window):
    """Decide que hacer en cada vuelta del QTimer. Pura, para poder probarla.

    Devuelve "done" (FrameRev ya esta al frente), "user_left" (el usuario se
    fue a otra app: no se le roba el foco), "exited" (FrameRev se cerro),
    "raise" (Hiero esta al frente y la ventana ya existe) o "wait".
    """
    if foreground_pid == child_pid:
        return "done"
    if not child_alive:
        return "exited"
    # 0 = sin ventana de frente (transicion): no dice nada, se sigue esperando.
    if foreground_pid and foreground_pid != own_pid:
        return "user_left"
    if main_window is None:
        return "wait"
    # Solo Hiero, siendo el proceso del frente, puede ceder el foco.
    return "raise" if foreground_pid == own_pid else "wait"


def _win32():
    """Funciones de user32/dwmapi con sus tipos. None si no se pueden cargar."""
    try:
        import ctypes
        from ctypes import wintypes
    except ImportError:
        return None
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetWindow.restype = wintypes.HWND
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongW.restype = ctypes.c_long
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.AllowSetForegroundWindow.argtypes = [wintypes.DWORD]
    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [enum_proc, wintypes.LPARAM]
    try:
        dwmapi = ctypes.WinDLL("dwmapi")
        dwmapi.DwmGetWindowAttribute.argtypes = [
            wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD
        ]
    except OSError:
        dwmapi = None
    return ctypes, wintypes, user32, dwmapi, enum_proc


def _window_pid(api, hwnd):
    ctypes, wintypes, user32 = api[0], api[1], api[2]
    if not hwnd:
        return 0
    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def _windows_of(api, pid):
    """Ventanas de nivel superior del proceso `pid`, en el formato de pick_main_window."""
    ctypes, wintypes, user32, dwmapi, enum_proc = api
    gw_owner, gwl_exstyle, ws_ex_toolwindow, dwmwa_cloaked = 4, -20, 0x00000080, 14
    found = []

    def collect(hwnd, _lparam):
        if _window_pid(api, hwnd) != pid:
            return True
        cloaked = ctypes.c_int(0)
        if dwmapi is not None:
            dwmapi.DwmGetWindowAttribute(hwnd, dwmwa_cloaked, ctypes.byref(cloaked),
                                         ctypes.sizeof(cloaked))
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        found.append({
            "hwnd": hwnd,
            "visible": bool(user32.IsWindowVisible(hwnd)),
            "owned": bool(user32.GetWindow(hwnd, gw_owner)),
            "tool": bool(user32.GetWindowLongW(hwnd, gwl_exstyle) & ws_ex_toolwindow),
            "cloaked": bool(cloaked.value),
            "area": max(0, rect.right - rect.left) * max(0, rect.bottom - rect.top),
        })
        return True

    user32.EnumWindows(enum_proc(collect), 0)
    return found


def _append_log(*message):
    """Suma una linea al log de la corrida, que ya se escribio al lanzar."""
    try:
        with open(LOG_PATH, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(" ".join(str(m) for m in message) + "\n")
    except Exception:
        pass
    if DEBUG:
        print(" ".join(str(m) for m in message))


def _bring_to_front_when_ready(process):
    """Espera la ventana de FrameRev sin bloquear Hiero y la trae al frente."""
    api = _win32()
    if api is None:
        debug_print("Sin ctypes: FrameRev queda donde Windows lo ponga.")
        return
    user32 = api[2]
    # Primero el permiso: si Windows se lo respeta, FrameRev se activa solo.
    user32.AllowSetForegroundWindow(process.pid)
    try:
        from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtCore
    except ImportError:
        debug_print("Sin Qt: no se espera la ventana de FrameRev.")
        return

    own_pid = os.getpid()
    timer = QtCore.QTimer()
    timer.setInterval(FRONT_POLL_MS)
    started = time.time()
    state = {"raises": 0}

    def finish(reason):
        timer.stop()
        if timer in _FRONT_WATCHERS:
            _FRONT_WATCHERS.remove(timer)
        _append_log("Al frente: {0} a los {1:.1f} s ({2} SetForegroundWindow)".format(
            reason, time.time() - started, state["raises"]))

    def tick():
        try:
            foreground_pid = _window_pid(api, user32.GetForegroundWindow())
            alive = process.poll() is None
            main_window = None
            if alive and foreground_pid != process.pid:
                main_window = pick_main_window(_windows_of(api, process.pid))
            action = front_step(foreground_pid, own_pid, process.pid, alive, main_window)
            if action not in ("raise", "wait"):
                finish(action)
            elif (time.time() - started) * 1000 > FRONT_TIMEOUT_MS:
                finish("timeout")
            elif action == "raise":
                state["raises"] += 1
                user32.SetForegroundWindow(main_window)
        except Exception as error:
            finish("error {0}".format(error))

    timer.timeout.connect(tick)
    _FRONT_WATCHERS.append(timer)
    timer.start()


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
