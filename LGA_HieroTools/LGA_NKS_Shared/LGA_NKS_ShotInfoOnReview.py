"""
____________________________________________________________________

  LGA_NKS_ShotInfoOnReview v1.00 | Lega

  Abre el Shot Info del Flow Review Panel cuando un reviewer llega a un
  shot que esta en SU estado de review, para revisar en cadena sin un
  segundo click.

  Lo usan dos puntos de entrada:
  - Prev/Next Rev del panel Viewer | TL, al terminar el salto.
  - Click en una fila del Flow Pull cuyo estado es el review del usuario.

  Los dos comparten UNA sola ventana: si sigue abierta la del shot anterior,
  se cierra y la nueva toma su geometria, asi no se apilan ventanas.

  Para habilitarlo a otro reviewer, agregar su clave a
  REVIEWERS_WITH_AUTO_SHOT_INFO. Las claves son las normalizadas que ya usan
  ViewerTL y Pull: lega, sebas, juano, javi, charly.

  v1.00: Primera version. Extrae de LGA_ViewerPanel v1.77 la apertura del
         Shot Info y la generaliza por reviewer.
____________________________________________________________________
"""

import os
import sys
import time
import importlib.util

DEBUG = False

# Reviewers que reciben el Shot Info automatico. Ver docs/LGA_NKS_Flow_Shot_Info.md.
REVIEWERS_WITH_AUTO_SHOT_INFO = {"lega"}

_HIEROTOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SHOT_INFO_PATH = os.path.join(
    _HIEROTOOLS_DIR, "LGA_NKS_Flow_Rev_Panel_py", "LGA_NKS_Flow_Shot_info.py"
)
LOG_PATH = os.path.join(_HIEROTOOLS_DIR, "logs", "DebugPy_ShotInfoOnReview.log")

_LOG_LINES = []

# Ventana abierta por este flujo (compartida entre ViewerTL y Pull).
_current_window = None


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


def is_enabled_for(user_key):
    """True si ese reviewer (clave normalizada) tiene el Shot Info automatico."""
    return bool(user_key) and str(user_key).lower() in REVIEWERS_WITH_AUTO_SHOT_INFO


def _set_topmost_native(widget, on):
    """'Always on top' via Win32 SetWindowPos, sin recrear la ventana.

    Mismo mecanismo que GUI_Table._set_topmost_native del Flow Pull: si la
    ventana del Pull es topmost, una ventana normal nunca puede quedar arriba
    de ella, asi que el Shot Info tiene que ser topmost tambien. Los argtypes
    son obligatorios: sin ellos ctypes trunca el HWND de 64 bits.
    """
    if not sys.platform.startswith("win"):
        return False
    try:
        import ctypes
        import ctypes.wintypes

        set_window_pos = ctypes.windll.user32.SetWindowPos
        set_window_pos.restype = ctypes.wintypes.BOOL
        set_window_pos.argtypes = [
            ctypes.wintypes.HWND,
            ctypes.wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.wintypes.UINT,
        ]
        insert_after = ctypes.wintypes.HWND(-1 if on else -2)  # TOPMOST / NOTOPMOST
        flags = 0x0002 | 0x0001  # SWP_NOMOVE | SWP_NOSIZE
        return bool(set_window_pos(int(widget.winId()), insert_after, 0, 0, 0, 0, flags))
    except Exception as e:
        debug_print("SetWindowPos fallo: {0}".format(e))
        return False


def _close_previous_window():
    """Cierra la ventana anterior de este flujo y devuelve su geometria si estaba visible."""
    global _current_window
    previous = _current_window
    _current_window = None
    if previous is None:
        return None
    try:
        if previous.isVisible():
            geometry = previous.geometry()
            previous.close()
            return geometry
    except RuntimeError:
        # El objeto C++ ya no existe (la ventana se destruyo antes).
        pass
    return None


def open_shot_info(source, task_name=None, keep_on_top=False):
    """Abre el Shot Info del shot del playhead, reemplazando la ventana anterior.

    source: quien lo pide, solo para el log ("ViewerTL", "Pull").
    task_name: task a mostrar ('comp', 'roto', ...). Si viene, el Shot Info no
        pregunta; si es None, la resuelve en el playhead como el boton normal.
    keep_on_top: dejar la ventana topmost (hace falta sobre el Pull topmost).
    """
    global _current_window
    try:
        debug_print(
            "Pedido desde {0} | task={1} | keep_on_top={2}".format(
                source, task_name, keep_on_top
            )
        )
        previous_geometry = _close_previous_window()

        if not os.path.exists(_SHOT_INFO_PATH):
            debug_print("Shot Info no encontrado en la ruta: {0}".format(_SHOT_INFO_PATH))
            return None

        spec = importlib.util.spec_from_file_location(
            "LGA_NKS_Flow_Shot_info", _SHOT_INFO_PATH
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.main(task_name=task_name)

        window = getattr(module, "window", None)
        _current_window = window
        if window is None:
            debug_print("El Shot Info no dejo ventana (DB ausente o error previo).")
            return None

        if previous_geometry is not None:
            window.setGeometry(previous_geometry)
        if keep_on_top:
            applied = _set_topmost_native(window, True)
            if not applied:
                # Fuera de Windows el Pull usa WindowStaysOnTopHint: mismo recurso.
                from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtCore

                window.setWindowFlags(window.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
                window.show()
            debug_print("Topmost aplicado (nativo={0})".format(applied))
        window.raise_()
        window.activateWindow()
        debug_print(
            "Shot Info abierto (reemplaza anterior: {0})".format(
                previous_geometry is not None
            )
        )
        return window
    except Exception as e:
        debug_print("Error abriendo Shot Info: {0}".format(e))
        return None
    finally:
        _volcar_log()
