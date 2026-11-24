"""
____________________________________________________________________

  LGA_NKS_ShotInfoOnReview v1.03 | Lega

  Punto de entrada UNICO del Shot Info del Flow Review Panel. Todas las
  formas de abrirlo pasan por open_shot_info():
  - Boton Shot Info del panel Flow y su shortcut Shift+T.
  - Prev/Next Rev del panel Viewer | TL, al terminar el salto (solo para
    los reviewers de REVIEWERS_WITH_AUTO_SHOT_INFO).
  - Click en una fila del Flow Pull, con su checkbox Shot Info prendido.

  Siempre hay UNA sola ventana: si esta abierta, se le reemplaza el
  contenido en su lugar (posicion y tamano que le haya dado el usuario);
  si no, se abre contra el borde IZQUIERDO de la pantalla, porque centrada
  tapa el viewer.

  La ventana NUNCA toma el foco al abrirse ni al recargarse, aunque quede
  on top (checkbox Keep on top de la propia ventana, prendido por defecto):
  si lo tomara, los shortcuts de Prev/Next Rev dejarian de llegar a NKS.

  Para habilitarlo en Prev/Next Rev a otro reviewer, agregar su clave a
  REVIEWERS_WITH_AUTO_SHOT_INFO. Las claves son las normalizadas que ya usan
  ViewerTL y Pull: lega, sebas, juano, javi, charly.

  v1.03: Ventana unica para todas las entradas (tambien el boton y
         Shift+T, que antes abrian una ventana suelta y centrada). Si esta
         abierta se recarga en su lugar con GUIWindow.reload() en vez de
         cerrarla y abrir otra. Nunca se activa. El on top lo decide el
         checkbox de la ventana: se saca el parametro keep_on_top.
  v1.02: open_shot_info(activate=False) abre el Shot Info sin activarlo,
         para que el foco siga en el Flow Pull. El Pull ya no consulta
         REVIEWERS_WITH_AUTO_SHOT_INFO: lo decide su checkbox Shot Info;
         la lista queda para Prev/Next Rev del ViewerTL.
  v1.01: La ventana se abre alineada a la izquierda. De la anterior se
         hereda la posicion y el ancho, ya no la geometria entera: el alto
         ahora lo calcula el Shot Info (v2.03) y se le pasa todo por
         main(align_left=..., previous_placement=...) para que la ventana
         se muestre ya en su lugar en vez de moverse despues de abrir.
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
        # SWP_NOACTIVATE: sin el, SetWindowPos tambien activa la ventana y le
        # saca el foco al Pull. Activar es decision de open_shot_info.
        flags = 0x0002 | 0x0001 | 0x0010  # SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
        return bool(set_window_pos(int(widget.winId()), insert_after, 0, 0, 0, 0, flags))
    except Exception as e:
        debug_print("SetWindowPos fallo: {0}".format(e))
        return False


def _reusable_window():
    """La ventana abierta, si se le puede reemplazar el contenido; si no, None.

    Se reusa si esta visible, en tamano normal y viene de una version del
    Shot Info que sabe recargarse. Una minimizada o maximizada se cierra:
    no es un lugar que tenga sentido conservar.
    """
    global _current_window
    window = _current_window
    if window is None:
        return None
    try:
        if not window.isVisible():
            _current_window = None
            return None
        if window.isMinimized() or window.isMaximized() or not hasattr(window, "reload"):
            window.close()
            _current_window = None
            return None
        return window
    except RuntimeError:
        # El objeto C++ ya no existe (la ventana se destruyo antes).
        _current_window = None
        return None


def open_shot_info(source, task_name=None):
    """Muestra el Shot Info del shot del playhead en la ventana unica.

    source: quien lo pide, solo para el log ("FlowPanel", "ViewerTL", "Pull").
    task_name: task a mostrar ('comp', 'roto', ...). Si viene, el Shot Info no
        pregunta; si es None, la resuelve en el playhead como el boton normal.

    Nunca activa la ventana: el foco sigue donde estaba (NKS o el Pull).
    """
    global _current_window
    try:
        debug_print("Pedido desde {0} | task={1}".format(source, task_name))

        window = _reusable_window()
        if window is not None:
            window.reload(task_name)
            # Por si otra ventana topmost (el Pull) quedo arriba: se reafirma
            # sin activar.
            window.apply_keep_on_top()
            debug_print("Contenido reemplazado en la ventana abierta.")
            return window

        if not os.path.exists(_SHOT_INFO_PATH):
            debug_print("Shot Info no encontrado en la ruta: {0}".format(_SHOT_INFO_PATH))
            return None

        spec = importlib.util.spec_from_file_location(
            "LGA_NKS_Flow_Shot_info", _SHOT_INFO_PATH
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # Contra el borde izquierdo. Se le pasa a main() en vez de mover la
        # ventana despues: asi se muestra ya ubicada, sin el salto desde el
        # centro. main() aplica el Keep on top de la ventana.
        module.main(task_name=task_name, align_left=True, activate=False)

        window = getattr(module, "window", None)
        _current_window = window
        if window is None:
            debug_print("El Shot Info no dejo ventana (DB ausente o error previo).")
            return None
        debug_print("Shot Info abierto a la izquierda, sin activar.")
        return window
    except Exception as e:
        debug_print("Error abriendo Shot Info: {0}".format(e))
        return None
    finally:
        _volcar_log()
