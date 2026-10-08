"""
____________________________________________________________________

  LGA_Contact_Sheet_OpenInNukeX v0.06 | Lega

  Copia los clips seleccionados en Hiero/Nuke Studio y le pide a NukeX,
  por el puerto de LGA_OpenInNukeX, que cree un LGA Contact Sheet con ellos.

  v0.06 - Fix: los inputs del Contact Sheet salian en orden inverso al del
          timeline (el input 0 era el ultimo clip). Dos causas: el Ctrl+C de
          Hiero ordena por track y despues por tiempo, y NukeX conecta los
          Reads en el orden de nuke.selectedNodes(), que es el inverso al de
          creacion. Ahora se reordena el clipboard antes de enviarlo: tiempo
          ascendente y, a igual tiempo, track ascendente. Solo se reordenan
          los Reads: los nodos de efecto del texto se descartan y las lineas
          sueltas (set, push, version) se ignoran. El clipboard se vacia antes
          del Ctrl+C para no reordenar una copia vieja. Ver el .md.
  v0.05 - La unica conexion TCP corre completa en background y devuelve los
          errores al hilo principal mediante una senal Qt. Se elimina el ping
          sincrono de hasta 10 segundos que congelaba la UI de Nuke Studio.
  v0.04 - show_message pasa al helper LGA_NKS_MessageBox con el estilo del pack
  v0.03 - Fix copy: key event Ctrl+C al QAbstractScrollArea del timeline
  v0.02 - Logging system + multiple approaches para trigger_hiero_copy
____________________________________________________________________

"""

import re
import socket
import logging
import queue
import os
import time
import traceback
import threading
from logging.handlers import QueueHandler, QueueListener

import hiero.core
import hiero.ui
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtCore, QtGui
from LGA_NKS_Shared.LGA_NKS_MessageBox import styled_message_box


HOST = "localhost"
PORT = 54325

DEBUG = True
DEBUG_CONSOLE = False
DEBUG_LOG = True

# NukeX (LGA_OpenInNukeX, paste_clipboard) conecta los Reads en el orden de
# nuke.selectedNodes(), que tras un nodePaste es el INVERSO al del texto pegado.
# Para que el input 0 sea el primer clip se escribe el clipboard al reves.
# Si OpenInNukeX se corrige para conectar en orden de creacion, poner False.
NUKE_PASTE_REVERSES_ORDER = True

# Reintentos del Ctrl+C sobre el timeline (ver trigger_hiero_copy).
COPY_MAX_ATTEMPTS = 5

script_start_time = None
debug_log_listener = None
_debug_file_handler = None


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

class RelativeTimeFormatter(logging.Formatter):
    def format(self, record):
        global script_start_time
        if script_start_time is None:
            script_start_time = record.created
        relative_time = record.created - script_start_time
        record.relative_time = f"{relative_time:.3f}s"
        return super().format(record)


def setup_debug_logging(script_name="ContactSheet"):
    global debug_log_listener, _debug_file_handler

    log_filename = f"debugPy_{script_name}.log"
    log_file_path = os.path.join(
        os.path.dirname(__file__), "..", "logs", log_filename
    )
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

    try:
        with open(log_file_path, "w", encoding="utf-8") as f:
            f.write(f"Fecha: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    except Exception as e:
        print(f"Warning: No se pudo limpiar el log: {e}")

    logger_name = f"{script_name.lower()}_logger"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    if logger.handlers:
        logger.handlers.clear()

    _debug_file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    _debug_file_handler.setLevel(logging.DEBUG)
    formatter = RelativeTimeFormatter("[%(relative_time)s] %(message)s")
    _debug_file_handler.setFormatter(formatter)

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
        log_queue, _debug_file_handler, respect_handler_level=True
    )
    debug_log_listener.daemon = True
    debug_log_listener.start()

    return logger


debug_logger = setup_debug_logging(script_name="ContactSheet")
_active_paste_jobs = set()
_reordered_mime = None


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


def _flush_log():
    try:
        if debug_log_listener and hasattr(debug_log_listener, "queue"):
            deadline = time.time() + 0.5
            while not debug_log_listener.queue.empty() and time.time() < deadline:
                time.sleep(0.005)
        if _debug_file_handler:
            _debug_file_handler.flush()
            if hasattr(_debug_file_handler, "stream"):
                os.fsync(_debug_file_handler.stream.fileno())
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

def show_message(title, message):
    # Cartel estandar con el estilo del pack (LGA_NKS_MessageBox)
    msg_box = styled_message_box(None, title, message)
    msg_box.setTextFormat(QtCore.Qt.TextFormat.PlainText)
    msg_box.setText(message)
    msg_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
    msg_box.exec_()


class _PasteResultNotifier(QtCore.QObject):
    """Entrega el resultado del socket en el hilo Qt que creo el objeto."""

    result = QtCore.Signal(bool, str)

    def __init__(self):
        super(_PasteResultNotifier, self).__init__(QtWidgets.QApplication.instance())
        self.result.connect(self._deliver_result)

    @QtCore.Slot(bool, str)
    def _deliver_result(self, success, message):
        try:
            if not success:
                show_message("Contact Sheet", message)
        finally:
            _active_paste_jobs.discard(self)
            self.deleteLater()


def get_selected_clips():
    debug_print("=== get_selected_clips ===")
    seq = hiero.ui.activeSequence()
    if not seq:
        debug_print("No hay secuencia activa", level="warning")
        show_message("Contact Sheet", "No active sequence.")
        return []

    timeline_editor = hiero.ui.getTimelineEditor(seq)
    if not timeline_editor:
        debug_print("No se pudo obtener el Timeline Editor", level="warning")
        show_message("Contact Sheet", "Could not get the Timeline Editor.")
        return []

    selected_items = timeline_editor.selection()
    selected_clips = [
        item
        for item in selected_items
        if not isinstance(item, hiero.core.EffectTrackItem)
    ]

    debug_print(f"Items totales: {len(selected_items)}  Clips (sin efectos): {len(selected_clips)}")

    if not selected_clips:
        debug_print("No hay clips seleccionados", level="warning")
        show_message("Contact Sheet", "No clips selected.")
        return []

    return selected_clips


def _get_clipboard_formats():
    """Lee formatos MIME actuales. Mantiene referencia para evitar GC crash de PySide2."""
    app = QtWidgets.QApplication.instance()
    if not app:
        return set()
    clipboard = app.clipboard()
    mime = clipboard.mimeData()
    if mime is None:
        return set()
    try:
        return set(list(mime.formats()))
    except RuntimeError:
        return set()


def _pump_events(seconds):
    """Procesa eventos de Qt durante un rato corto (sin dormir el hilo)."""
    app = QtWidgets.QApplication.instance()
    deadline = time.time() + seconds
    while time.time() < deadline:
        app.processEvents()
        time.sleep(0.005)


def trigger_hiero_copy(timeline_editor):
    """
    Copia los clips seleccionados al clipboard usando un Ctrl+C key event
    dirigido al QAbstractScrollArea interno del timeline de Hiero.

    Descubrimiento (v0.03): ui.TimelineEditor NO es un QWidget. Su .window()
    devuelve la ventana principal de Hiero. Tras activarla y llamar setFocus(),
    el focusWidget() pasa a ser el QAbstractScrollArea interno del timeline,
    que es quien maneja los key events. Enviarle Ctrl+C produce el formato
    correcto en el clipboard: {'x-foundry/x-clips', 'text/x-nuke-script'}.
    """
    debug_print("=== trigger_hiero_copy ===")

    app = QtWidgets.QApplication.instance()
    if not app:
        raise RuntimeError("No se pudo obtener la instancia de QApplication.")

    main_window = timeline_editor.window()
    if not main_window:
        raise RuntimeError("No se pudo obtener la ventana principal de Hiero.")

    debug_print(f"main_window tipo: {type(main_window).__name__}")
    debug_print(f"focusWidget antes: {type(app.focusWidget()).__name__ if app.focusWidget() else 'None'}")

    hiero_formats = {"x-foundry/x-clips", "text/x-nuke-script"}
    formats_despues = set()
    focus_widget = None

    # A veces, tras activar la ventana, el foco queda en un QWidget generico y
    # el Ctrl+C no llega al timeline (medido: ~1 de cada 4 corridas seguidas).
    # Se reintenta hasta que el foco sea el QAbstractScrollArea del timeline.
    for intento in range(1, COPY_MAX_ATTEMPTS + 1):
        main_window.raise_()
        main_window.activateWindow()
        main_window.setFocus()
        _pump_events(0.05)

        focus_widget = app.focusWidget()
        focus_name = type(focus_widget).__name__ if focus_widget else "None"
        debug_print(f"Intento {intento}: focusWidget despues de activateWindow: {focus_name}")
        if focus_widget is None or not isinstance(focus_widget, QtWidgets.QAbstractScrollArea):
            _pump_events(0.1)
            continue

        formats_antes = _get_clipboard_formats()
        debug_print(f"Formatos clipboard antes del copy: {formats_antes}")

        # Se vacia el clipboard antes del Ctrl+C: si Hiero no llega a copiar,
        # el chequeo de formatos falla en vez de validar contenido viejo (una
        # copia anterior o la que dejo la corrida previa de este mismo boton).
        app.clipboard().clear()
        app.processEvents()

        for ev_type in (QtCore.QEvent.KeyPress, QtCore.QEvent.KeyRelease):
            app.sendEvent(
                focus_widget,
                QtGui.QKeyEvent(ev_type, QtCore.Qt.Key_C, QtCore.Qt.ControlModifier, ""),
            )
        app.processEvents()

        formats_despues = _get_clipboard_formats()
        debug_print(f"Formatos clipboard despues del copy: {formats_despues}")
        if hiero_formats.intersection(formats_despues):
            break
        _pump_events(0.1)

    if not hiero_formats.intersection(formats_despues):
        raise RuntimeError(
            f"El clipboard no tiene formatos de Hiero tras el Ctrl+C "
            f"({COPY_MAX_ATTEMPTS} intentos).\n"
            f"focusWidget target: {type(focus_widget).__name__ if focus_widget else 'None'}\n"
            f"Formatos obtenidos: {formats_despues}"
        )

    debug_print(f"Copy exitoso. Formatos Hiero en clipboard: {hiero_formats.intersection(formats_despues)}")


# ---------------------------------------------------------------------------
# Orden de los clips
# ---------------------------------------------------------------------------

def _track_index(item):
    """Indice del track del item (V1 = 0), o 0 si la API no lo da."""
    try:
        return int(item.parentTrack().trackIndex())
    except Exception:
        return 0


def _timeline_in(item):
    try:
        return int(item.timelineIn())
    except Exception:
        return 0


def _compute_clipboard_permutation(keys, reverse_for_nuke):
    """
    keys: lista de (track_index, timeline_in), uno por clip, en cualquier orden.

    Devuelve, para cada posicion del texto que se debe escribir en el
    clipboard, la posicion que ese bloque tiene en el texto que genera el
    Ctrl+C de Hiero (que ordena por track y despues por tiempo).

    Orden de inputs deseado: tiempo ascendente y, a igual tiempo, track
    ascendente.
    """
    idx = range(len(keys))
    hiero_order = sorted(idx, key=lambda i: (keys[i][0], keys[i][1]))
    desired = sorted(idx, key=lambda i: (keys[i][1], keys[i][0]))
    if reverse_for_nuke:
        desired = desired[::-1]
    return [hiero_order.index(i) for i in desired]


_NODE_HEADER = re.compile(r"^([A-Za-z_]\w*) \{[ \t]*\r?$")


def _brace_delta(line, in_string):
    """
    Cuenta llaves de una linea ignorando las que estan dentro de strings
    entre comillas (un string puede seguir en la linea siguiente).
    Devuelve (delta, in_string).
    """
    delta = 0
    escaped = False
    for ch in line:
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch == "{":
            delta += 1
        elif ch == "}":
            delta -= 1
    return delta, in_string


def _split_node_blocks(text):
    """
    Parte el texto de un clipboard de Hiero/Nuke en bloques de nodo
    (clase, texto). Cada bloque va de su encabezado `Clase {` hasta la llave
    que lo cierra, contando llaves (el cuerpo puede venir sin indentar). Las
    lineas sueltas fuera de bloques (`set`, `push`, `version`, vacias) se
    descartan. Devuelve None si un bloque no cierra.
    """
    blocks = []
    current = None  # [clase, lineas, profundidad, in_string]
    for line in text.splitlines(True):
        if current is None:
            m = _NODE_HEADER.match(line.rstrip("\n"))
            if m:
                current = [m.group(1), [line], 1, False]
            continue
        current[1].append(line)
        delta, current[3] = _brace_delta(line, current[3])
        current[2] += delta
        if current[2] <= 0:
            blocks.append((current[0], "".join(current[1])))
            current = None
    if current is not None:
        return None
    return blocks


def _read_chunks(text):
    """Bloques Read del texto, en el orden en que vienen. None si el parseo falla."""
    blocks = _split_node_blocks(text)
    if blocks is None:
        return None
    chunks = []
    for cls, body in blocks:
        if cls == "Read":
            chunks.append(body.rstrip() + "\n\n")
        else:
            debug_print(f"Nodo {cls} descartado del clipboard (el Contact Sheet solo usa Reads)")
    return chunks


def reorder_clipboard_reads(selected_clips):
    """
    Reescribe text/x-nuke-script del clipboard con los Reads en el orden de
    inputs deseado. Si algo no cuadra deja el clipboard como esta (el orden
    queda como lo dio Hiero) y lo registra en el log.
    """
    global _reordered_mime
    app = QtWidgets.QApplication.instance()
    mime = app.clipboard().mimeData() if app else None
    if mime is None or "text/x-nuke-script" not in list(mime.formats()):
        debug_print("Reorden omitido: no hay text/x-nuke-script en el clipboard", level="warning")
        return False

    text = bytes(mime.data("text/x-nuke-script")).decode("utf-8", errors="replace")
    chunks = _read_chunks(text)
    if chunks is None:
        debug_print("Reorden omitido: el texto del clipboard no se pudo partir en nodos", level="warning")
        return False
    if len(chunks) != len(selected_clips):
        debug_print(
            f"Reorden omitido: {len(chunks)} Reads en el clipboard vs "
            f"{len(selected_clips)} clips seleccionados",
            level="warning",
        )
        return False

    keys = [(_track_index(c), _timeline_in(c)) for c in selected_clips]
    perm = _compute_clipboard_permutation(keys, NUKE_PASTE_REVERSES_ORDER)
    new_text = "".join(chunks[p] for p in perm)
    debug_print(f"Claves (track, tiempo) de la seleccion: {keys}")
    debug_print(f"Permutacion aplicada al clipboard: {perm}")

    new_mime = QtCore.QMimeData()
    for fmt in list(mime.formats()):
        if fmt == "text/x-nuke-script":
            new_mime.setData(fmt, QtCore.QByteArray(new_text.encode("utf-8")))
        else:
            new_mime.setData(fmt, mime.data(fmt))
    app.clipboard().setMimeData(new_mime)
    _reordered_mime = new_mime  # evita el GC temprano de PySide2
    debug_print("Clipboard reescrito con los Reads en orden de timeline")
    return True


def _send_paste_request():
    """Envia el unico request TCP de la operacion y espera su confirmacion."""
    debug_print("Thread paste: conectando...")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(10)
        sock.connect((HOST, PORT))
        sock.settimeout(120)
        sock.sendall(b"paste_clipboard")
        response = sock.recv(4096).decode(errors="replace")
    debug_print(f"Thread paste: respuesta recibida: '{response[:80]}'")
    if "successfully" not in response.lower():
        raise RuntimeError(
            "NukeX did not confirm Contact Sheet creation: "
            f"{response.strip() or 'empty response'}"
        )
    return response


def _send_paste_in_thread():
    """Ejecuta red y nodePaste remoto sin bloquear el hilo principal de NKS."""
    notifier = _PasteResultNotifier()
    _active_paste_jobs.add(notifier)

    def _worker():
        try:
            _send_paste_request()
            debug_print("Thread paste: LGA Contact Sheet completado exitosamente")
            notifier.result.emit(True, "")
        except (socket.timeout, ConnectionRefusedError, OSError) as exc:
            debug_print(f"Thread paste: error de conexion: {exc}", level="error")
            notifier.result.emit(
                False,
                "Could not connect to NukeX through OpenInNukeX.",
            )
        except Exception as exc:
            debug_print(f"Thread paste: error inesperado: {exc}", level="error")
            debug_print(traceback.format_exc(), level="error")
            notifier.result.emit(False, f"Error creating Contact Sheet:\n{exc}")
        finally:
            _flush_log()

    t = threading.Thread(target=_worker, name="ContactSheet-paste", daemon=True)
    t.start()
    debug_print("Thread paste lanzado, Hiero continua sin bloqueo")


def main():
    debug_print("=== LGA_Contact_Sheet_OpenInNukeX v0.06: main ===")

    seq = hiero.ui.activeSequence()
    if not seq:
        show_message("Contact Sheet", "No active sequence.")
        return

    timeline_editor = hiero.ui.getTimelineEditor(seq)
    if not timeline_editor:
        show_message("Contact Sheet", "Could not get the Timeline Editor.")
        return

    selected_items = timeline_editor.selection()
    selected_clips = [
        item for item in selected_items
        if not isinstance(item, hiero.core.EffectTrackItem)
    ]

    debug_print(f"Clips seleccionados: {len(selected_clips)}")

    if not selected_clips:
        show_message("Contact Sheet", "No clips selected.")
        return

    try:
        trigger_hiero_copy(timeline_editor)
        # El Ctrl+C de Hiero ordena por track; se reordena por tiempo.
        reorder_clipboard_reads(selected_clips)
        # La conexion, el envio y la espera del trabajo de NukeX ocurren en el
        # worker. El hilo principal solo hace la copia local, que requiere Qt.
        _send_paste_in_thread()
        debug_print("=== main: copy OK, paste enviado en background ===")
    except Exception as exc:
        debug_print(f"Error en main: {exc}", level="error")
        debug_print(traceback.format_exc(), level="error")
        show_message("Contact Sheet", f"Error creating Contact Sheet:\n{exc}")


if __name__ == "__main__":
    main()
