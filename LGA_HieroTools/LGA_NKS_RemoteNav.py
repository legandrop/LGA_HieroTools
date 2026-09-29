"""
____________________________________________________________________

  LGA_NKS_RemoteNav v1.00 | Lega

  Server local que deja a otra app de la maquina (PipeSync) pedirle a
  Hiero/NKS que lleve el timeline a un shot: "Show shot in NukeStudio".

  - QTcpServer en el HILO PRINCIPAL, solo en 127.0.0.1:54327. Los slots ya
    corren en el main, asi que no hay hilos de Python ni
    executeInMainThreadWithResult.
  - Protocolo: una linea JSON por mensaje, terminada en "\\n" (UTF-8). El
    cliente manda un pedido; el server contesta cero o mas lineas
    intermedias ("opening") y UNA final, y cierra.
  - Lista fija de comandos: "ping" y "goto_shot". Nunca exec.
  - Un pedido a la vez: si llega otro mientras se navega, contesta "busy".

  Contrato completo, estados y por que es asi: docs/Docu_RemoteNav.md.

  v1.00: Primera version.
____________________________________________________________________
"""

import json
import os
import sys
import time
import traceback

import hiero.core

from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtCore, QtNetwork, QtWidgets

SERVER_NAME = "LGA_NKS_RemoteNav"
SERVER_VERSION = "1.00"
PROTOCOL_VERSION = 1

HOST = "127.0.0.1"
PORT = 54327  # 54321/54322 MCP, 54325 OpenInNukeX, 54326 dev-link

MAX_LINE_BYTES = 64 * 1024
MAX_FIELD_CHARS = 256
# Sin una linea completa en este tiempo se corta la conexion: un cliente
# colgado no puede dejar sockets abiertos para siempre.
READ_TIMEOUT_MS = 5000
# Tope de un pedido entero, apertura de proyecto incluida. Si la navegacion
# nunca contesta (por ejemplo, el usuario abrio otro proyecto a mano y la
# post-apertura se quedo con el suyo), se libera el "busy" y se avisa.
REQUEST_TIMEOUT_MS = 170 * 1000

DEBUG = False

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(_TOOLS_DIR, "logs", "DebugPy_RemoteNav.log")


def debug_print(*message):
    """Log de SESION del server (arranque + un renglon por pedido)."""
    linea = "[{0}] {1}".format(time.strftime("%H:%M:%S"), " ".join(str(m) for m in message))
    if DEBUG:
        print(linea)
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(linea + "\n")
    except Exception:
        pass


def console_print(text):
    """
    Aviso para la consola del host, como el "OpenInNukeX active on port" de
    OpenInNukeX. El server arranca con la ventana ya creada, y para entonces
    NKS redirige sys.stdout al Script Editor: un print() comun no llega a la
    ventana de consola. Por eso va tambien a sys.__stdout__, la salida original
    del proceso, que es esa ventana.
    """
    targets = []
    for stream in (getattr(sys, "__stdout__", None), sys.stdout):
        if stream is not None and all(stream is not t for t in targets):
            targets.append(stream)
    for stream in targets:
        try:
            stream.write(text + "\n")
            stream.flush()
        except Exception:
            pass


def _reset_log():
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("Fecha: {0}\n".format(time.strftime("%Y-%m-%d %H:%M:%S")))
    except Exception:
        pass


class _Connection(QtCore.QObject):
    """Un cliente: junta bytes hasta el primer "\\n", despacha y contesta."""

    def __init__(self, socket, server):
        super(_Connection, self).__init__(server)
        self._socket = socket
        self._server = server
        self._buffer = bytearray()
        self._dispatched = False
        self._closed = False
        socket.readyRead.connect(self._on_ready_read)
        socket.disconnected.connect(self._on_disconnected)
        self._read_timer = QtCore.QTimer(self)
        self._read_timer.setSingleShot(True)
        self._read_timer.timeout.connect(self._on_read_timeout)
        self._read_timer.start(READ_TIMEOUT_MS)

    def _on_ready_read(self):
        if self._dispatched or self._closed:
            return
        self._buffer.extend(bytes(self._socket.readAll()))
        newline = self._buffer.find(b"\n")
        if newline < 0:
            if len(self._buffer) > MAX_LINE_BYTES:
                self.send({"status": "error", "detail": "Mensaje demasiado largo."}, final=True)
            return
        self._read_timer.stop()
        self._dispatched = True
        line = bytes(self._buffer[:newline])
        # Diferido: el switch de secuencia procesa eventos, y hacerlo adentro
        # del slot de readyRead lo reentraria.
        QtCore.QTimer.singleShot(0, lambda: self._server.dispatch(self, line))

    def _on_read_timeout(self):
        if not self._dispatched:
            self.send({"status": "error", "detail": "No llego un pedido completo."}, final=True)

    def _on_disconnected(self):
        self._closed = True
        self._read_timer.stop()
        try:
            self._socket.deleteLater()
        except Exception:
            pass
        self.deleteLater()

    def send(self, payload, final):
        """Escribe una linea JSON. En la final cierra. Si el cliente se fue, no hace nada."""
        if self._closed:
            return
        try:
            # Un cliente que se fue sin esperar la respuesta deja el socket
            # destruido del lado C++: tocarlo tira RuntimeError, y se ignora.
            state = self._socket.state()
            if state != QtNetwork.QAbstractSocket.ConnectedState:
                return
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n"
            self._socket.write(data)
            self._socket.flush()
            if final:
                self._socket.disconnectFromHost()
        except Exception as e:
            debug_print("Error escribiendo al cliente: {0}".format(e))


class RemoteNavServer(QtCore.QObject):
    def __init__(self, parent=None):
        super(RemoteNavServer, self).__init__(parent)
        self._server = QtNetwork.QTcpServer(self)
        self._server.newConnection.connect(self._on_new_connection)
        self._busy = False
        self._request_id = 0
        self._watchdog = QtCore.QTimer(self)
        self._watchdog.setSingleShot(True)
        self._watchdog.timeout.connect(self._on_watchdog)
        self._pending = None  # (request_id, connection)

    def start(self):
        # QTcpServer.listen() en Windows abre el puerto con SO_EXCLUSIVEADDRUSE
        # (modo por defecto de Qt): un segundo NKS no puede quedar escuchando
        # el mismo puerto, que es lo que si pasa con SO_REUSEADDR.
        address = QtNetwork.QHostAddress(HOST)
        if not self._server.listen(address, PORT):
            debug_print(
                "No se pudo escuchar en {0}:{1} ({2}). Si hay otro NKS abierto, "
                "ese es el que atiende los pedidos.".format(HOST, PORT, self._server.errorString())
            )
            # Consola del host, como OpenInNukeX: deja claro cual sesion atiende.
            console_print("{0} inactive: port {1} already in use ({2}). Another Hiero / "
                          "NukeStudio is answering PipeSync.".format(
                              SERVER_NAME, PORT, self._server.errorString()))
            return False
        debug_print("Escuchando en {0}:{1} (pid {2})".format(HOST, PORT, os.getpid()))
        console_print("{0} active on port {1}".format(SERVER_NAME, PORT))
        return True

    def close(self):
        try:
            self._server.close()
        except Exception:
            pass

    def is_listening(self):
        return self._server.isListening()

    def _on_new_connection(self):
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            if socket is None:
                break
            _Connection(socket, self)

    # ------------------------------------------------------------------
    def dispatch(self, connection, line):
        try:
            message = json.loads(line.decode("utf-8"))
        except Exception as e:
            connection.send({"status": "error", "detail": "JSON invalido: {0}".format(e)}, final=True)
            return
        if not isinstance(message, dict):
            connection.send({"status": "error", "detail": "El pedido no es un objeto JSON."}, final=True)
            return

        cmd = message.get("cmd")
        if cmd == "ping":
            connection.send(self._ping_payload(), final=True)
            return
        if cmd == "goto_shot":
            self._goto_shot(connection, message)
            return
        connection.send({"status": "error", "detail": "Comando desconocido: {0!r}".format(cmd)}, final=True)

    def _ping_payload(self):
        return {
            "status": "ok",
            "server": SERVER_NAME,
            "version": SERVER_VERSION,
            "protocol": PROTOCOL_VERSION,
            "pid": os.getpid(),
            "busy": self._busy,
        }

    @staticmethod
    def _field(message, name, required):
        value = message.get(name)
        if value is None or value == "":
            if required:
                raise ValueError("Falta el campo '{0}'.".format(name))
            return None
        if not isinstance(value, str):
            raise ValueError("El campo '{0}' tiene que ser texto.".format(name))
        value = value.strip()
        if len(value) > MAX_FIELD_CHARS:
            raise ValueError("El campo '{0}' es demasiado largo.".format(name))
        if required and not value:
            raise ValueError("Falta el campo '{0}'.".format(name))
        return value or None

    def _goto_shot(self, connection, message):
        try:
            project = self._field(message, "project", True)
            shot = self._field(message, "shot", True)
            sequence = self._field(message, "sequence", False)
            task = self._field(message, "task", False)
        except ValueError as e:
            connection.send({"status": "error", "detail": str(e)}, final=True)
            return

        if self._busy:
            connection.send(
                {"status": "busy", "detail": "NKS todavia esta atendiendo el pedido anterior."},
                final=True,
            )
            return

        self._busy = True
        self._request_id += 1
        request_id = self._request_id
        self._pending = (request_id, connection)
        self._watchdog.start(REQUEST_TIMEOUT_MS)
        debug_print(
            "goto_shot #{0}: project='{1}' sequence='{2}' shot='{3}' task='{4}'".format(
                request_id, project, sequence, shot, task
            )
        )

        def _on_progress(payload):
            if self._pending and self._pending[0] == request_id:
                connection.send(payload, final=False)

        def _on_result(payload):
            if not (self._pending and self._pending[0] == request_id):
                # Ya lo libero el watchdog: el cliente recibio el timeout.
                debug_print("goto_shot #{0}: resultado tardio descartado ({1})".format(
                    request_id, payload.get("status")))
                return
            self._finish_request(payload)

        try:
            from LGA_NKS_Shared import LGA_NKS_ShotNavigation as navigation

            navigation.goto_shot(
                project, shot, sequence, task,
                on_result=_on_result,
                on_progress=_on_progress,
                # Si el watchdog ya libero este pedido, no se mueve el timeline:
                # un salto tardio pisaria al pedido que haya entrado despues.
                is_current=lambda: bool(self._pending and self._pending[0] == request_id),
            )
        except Exception:
            self._finish_request({"status": "error", "detail": traceback.format_exc()})

    def _finish_request(self, payload):
        request_id, connection = self._pending
        self._pending = None
        self._busy = False
        self._watchdog.stop()
        debug_print("goto_shot #{0}: {1} | {2}".format(
            request_id, payload.get("status"), payload.get("detail")))
        connection.send(payload, final=True)

    def _on_watchdog(self):
        if not self._pending:
            return
        self._finish_request({
            "status": "error",
            "detail": "La navegacion no termino en {0} s; se libera NKS para otro pedido.".format(
                REQUEST_TIMEOUT_MS // 1000),
        })


def _has_gui():
    """Solo la sesion de Hiero/NKS con ventana: nunca procesos -t ni workers."""
    app = QtWidgets.QApplication.instance()
    if app is None or not isinstance(app, QtWidgets.QApplication):
        return False
    try:
        import hiero.ui

        return hiero.ui.mainWindow() is not None
    except Exception:
        return False


def start_server():
    """Arranca el server (o lo reemplaza si el modulo se recargo)."""
    if QtNetwork is None:
        debug_print("QtNetwork no esta disponible en este Nuke: el server no arranca.")
        return None

    previous = getattr(hiero.core, "_lga_remote_nav_server", None)
    if previous is not None:
        try:
            previous.close()
            previous.deleteLater()
        except Exception:
            pass
        hiero.core._lga_remote_nav_server = None

    server = RemoteNavServer(QtWidgets.QApplication.instance())
    if not server.start():
        server.deleteLater()
        return None
    # Guardado en hiero.core para sobrevivir a un reimport y poder cerrarlo.
    hiero.core._lga_remote_nav_server = server
    return server


START_RETRIES = 20
START_RETRY_MS = 500


def _start_deferred(attempt=0):
    # Al importar desde el startup la ventana principal todavia puede no
    # existir. Sin ventana despues de los reintentos no es una sesion con UI
    # (Nuke -t, workers del frame server) y no se arranca nada.
    if not _has_gui():
        if attempt < START_RETRIES:
            QtCore.QTimer.singleShot(START_RETRY_MS, lambda: _start_deferred(attempt + 1))
        return
    _reset_log()
    try:
        start_server()
    except Exception:
        debug_print("Error arrancando el server:\n" + traceback.format_exc())


if QtCore.QCoreApplication.instance() is not None:
    QtCore.QTimer.singleShot(0, _start_deferred)
