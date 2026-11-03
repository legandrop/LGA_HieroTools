"""
____________________________________________________________________

  LGA_NKS_Heartbeat v1.00 | Lega

  Deja anotado en un archivo chico (el latido) que proyecto y que timeline
  tiene al frente esta sesion de Hiero/NKS, para que otra app de la maquina
  lo lea sin tener que adivinarlo mirando la pantalla.

  - Un QTimer de 5 s en el HILO PRINCIPAL llama a publish(): escribe solo si
    el estado cambio o pasaron 60 s (pulso). Los eventos de Hiero solo
    adelantan ese chequeo a 400 ms; ninguno trae el dato, asi que uno
    perdido cuesta como mucho 5 s y nunca un dato falso.
  - Un archivo por proceso: <AppData>/LGA/Heartbeat/<app>-<pid>.json,
    escrito de forma atomica (temporal + os.replace). NUNCA crea la
    carpeta: sin ella no escribe nada, y donde nadie lee no hace nada.
  - kShutdown borra solo el archivo propio.
  - Prohibido os.kill(pid, 0) para saber si un proceso vive: en Windows
    termina el proceso.

  Formato, vencimiento y por que es asi: docs/Docu_Heartbeat.md.

  v1.00: Primera version.
____________________________________________________________________
"""

import json
import os
import sys
import time
import traceback

import hiero.core
from hiero.core import events

from LGA_NKS_Shared.LGA_NKS_Flow_NamingUtils import extract_project_name_from_path
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtCore, QtWidgets

SCHEMA_VERSION = 1

TICK_MS = 5000   # el timer relee el estado cada 5 s: es la garantia
SETTLE_MS = 400  # un evento adelanta el chequeo a 400 ms (Hiero arma el timeline ~0.16 s despues de kAfterProjectLoad)
PULSE_S = 60     # sin cambios igual se reescribe cada 60 s: el lector no confia en un archivo mas viejo

# Eventos que adelantan el chequeo. Los que un build de Nuke no tenga se saltean.
ACCELERATOR_EVENTS = (
    "kAfterNewProjectCreated",
    "kAfterProjectLoad",
    "kAfterProjectSave",
    "kAfterProjectClose",
    "kCurrentViewerChanged",
    "kContextChanged",
)

START_RETRIES = 20
START_RETRY_MS = 500

DEBUG = False

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(_TOOLS_DIR, "logs", "DebugPy_Heartbeat.log")


def debug_print(*message):
    """Log de SESION: arranque, cada cambio de estado, la carpeta que aparece o desaparece y los errores."""
    linea = "[{0}] {1}".format(time.strftime("%H:%M:%S"), " ".join(str(m) for m in message))
    if DEBUG:
        print(linea)
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(linea + "\n")
    except Exception:
        pass


def _reset_log():
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("Fecha: {0}\n".format(time.strftime("%Y-%m-%d %H:%M:%S")))
    except Exception:
        pass


# -- Donde y con que identidad -------------------------------------------------


def _user_config_root():
    # Misma raiz que LGA_NKS_BurnIn_Config._user_config_root().
    if sys.platform.startswith("win"):
        v = os.getenv("APPDATA")
        if v:
            return v
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support")
    return os.path.expanduser("~/.config")


def heartbeat_dir():
    """Carpeta de los latidos. La crea quien los lee: esta tool nunca."""
    return os.path.join(_user_config_root(), "LGA", "Heartbeat")


def _identity():
    """(app, host): "nukestudio" si es Nuke Studio y no Hiero a secas, y la version del host."""
    try:
        import nuke

        return ("nukestudio" if nuke.env["studio"] else "hiero"), nuke.NUKE_VERSION_STRING
    except Exception:
        return "hiero", None


# -- Estado de la sesion -------------------------------------------------------


def _project_ref(project, with_path=False):
    path = project.path() or ""
    # key = la carpeta VFX-<X> de la ruta; sin guardar la ruta esta vacia y key es None.
    ref = {"name": project.name(), "key": extract_project_name_from_path(path)}
    if with_path:
        ref["path"] = path
    return ref


def snapshot():
    """Estado actual SIN updatedAt: es lo que se compara para saber si cambio.

    El proyecto es el del timeline activo ("timeline"); sin timeline y con un
    solo proyecto abierto, ese ("only-open"); si no, null ("none"). Es la misma
    cadena que ya usa el BurnIn (LGA_NKS_BurnIn_Logic._project_name).
    """
    import hiero.ui

    projects = hiero.core.projects()
    sequence = hiero.ui.activeSequence()
    # shortcut: el proyecto es el del timeline activo aunque se mire el bin de otro;
    # afinarlo con kSelectionChanged si molesta.
    if sequence is not None:
        basis, project, name = "timeline", _project_ref(sequence.project(), True), sequence.name()
    elif len(projects) == 1:
        basis, project, name = "only-open", _project_ref(projects[0], True), None
    else:
        basis, project, name = "none", None, None
    return {
        "basis": basis,
        "project": project,
        "sequence": name,
        "open": [_project_ref(p) for p in projects],
    }


def _iso_now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def write_atomic(path, payload):
    """Temporal en la misma carpeta + os.replace: el lector ve el archivo viejo o el nuevo, nunca uno a medias.

    En Windows os.replace falla si el lector tiene el archivo abierto: el error
    sube y el chequeo siguiente (5 s) reintenta.
    """
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, separators=(",", ":")) + "\n")
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


# -- El latido -----------------------------------------------------------------


class Heartbeat(object):
    """El latido de esta sesion: un archivo por proceso, escrito desde el hilo principal."""

    def __init__(self):
        self.pid = os.getpid()
        self.app, self.host = _identity()
        self._last_state = None
        self._last_at = 0.0
        self._closed = False
        self._folder_seen = None  # solo para loguear cuando la carpeta aparece o desaparece
        self._last_error = None   # idem: un error repetido se loguea una sola vez
        self._tick = None
        self._settle = None
        self._interests = []      # (evento, callback), para poder sacarlos

    def path(self):
        return os.path.join(heartbeat_dir(), "{0}-{1}.json".format(self.app, self.pid))

    def start(self):
        app = QtWidgets.QApplication.instance()
        self._tick = QtCore.QTimer(app)
        self._tick.timeout.connect(self.publish)
        self._tick.start(TICK_MS)
        self._settle = QtCore.QTimer(app)
        self._settle.setSingleShot(True)
        self._settle.timeout.connect(self.publish)
        for name in ACCELERATOR_EVENTS:
            self._register(name, self._on_event)
        self._register("kShutdown", self._on_shutdown)
        debug_print("Arranca el latido: app={0} host={1} pid={2}".format(self.app, self.host, self.pid))
        self.publish()

    def _register(self, name, callback):
        event_type = getattr(events.EventType, name, None)
        if event_type is None:
            debug_print("El evento {0} no existe en este Nuke: se saltea.".format(name))
            return
        events.registerInterest(event_type, callback)
        self._interests.append((event_type, callback))

    def _on_event(self, event):
        # Solo adelanta el chequeo: el dato sale siempre de snapshot(), nunca del evento.
        if not self._closed:
            self._settle.start(SETTLE_MS)

    def _on_shutdown(self, event):
        self.shutdown()

    def publish(self, now=None):
        """Un chequeo; True si escribio. Nunca levanta: corre adentro de un slot de Qt."""
        if self._closed:
            return False
        try:
            return self._publish(time.monotonic() if now is None else now)
        except Exception:
            error = traceback.format_exc()
            if error != self._last_error:
                self._last_error = error
                debug_print("Error publicando el latido (se reintenta en el proximo chequeo):\n" + error)
            return False

    def _publish(self, now):
        folder = heartbeat_dir()
        exists = os.path.isdir(folder)
        if exists != self._folder_seen:
            self._folder_seen = exists
            debug_print("Carpeta {0}: {1}".format(
                folder, "existe, se escribe" if exists else "no existe, no se escribe nada"))
        if not exists:
            return False
        state = snapshot()
        changed = state != self._last_state
        if not changed and now - self._last_at < PULSE_S:
            return False
        payload = {
            "v": SCHEMA_VERSION,
            "app": self.app,
            "host": self.host,
            "pid": self.pid,
            "updatedAt": _iso_now(),
        }
        payload.update(state)
        # shortcut: la escritura (~300 bytes en AppData local) corre en el hilo principal;
        # pasarla a un worker si AppData alguna vez fuera de red.
        write_atomic(self.path(), payload)
        self._last_state, self._last_at, self._last_error = state, now, None
        if changed:
            project = state["project"]
            debug_print("Latido escrito: basis={0} proyecto={1} timeline={2} abiertos={3}".format(
                state["basis"], project["name"] if project else None, state["sequence"],
                [p["name"] for p in state["open"]]))
        return True

    def stop(self):
        """Corta los timers y no vuelve a publicar. No toca el archivo ni los eventos."""
        self._closed = True
        for timer in (self._tick, self._settle):
            if timer is not None:
                timer.stop()

    def shutdown(self):
        """kShutdown: borra SOLO el archivo propio.

        No desregistra los eventos: sacar un handler en pleno despacho hace que
        Hiero se saltee al siguiente de la lista.
        """
        self.stop()
        try:
            os.remove(self.path())
            debug_print("kShutdown: archivo del latido borrado.")
        except OSError:
            pass  # la carpeta no estaba o nunca llego a escribir

    def unregister(self):
        """Saca los handlers de eventos. Solo al reemplazar este latido tras un reimport."""
        for event_type, callback in self._interests:
            events.unregisterInterest(event_type, callback)
        self._interests = []


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


def start_heartbeat():
    """Arranca el latido (o lo reemplaza si el modulo se recargo)."""
    previous = getattr(hiero.core, "_lga_heartbeat", None)
    if previous is not None:
        try:
            previous.stop()
            previous.unregister()
        except Exception:
            pass
    beat = Heartbeat()
    # Guardado en hiero.core para sobrevivir a un reimport y poder cortarlo.
    hiero.core._lga_heartbeat = beat
    beat.start()
    return beat


def _start_deferred(attempt=0):
    # Al importar desde el startup la ventana principal todavia puede no
    # existir. Sin ventana despues de los reintentos no es una sesion con UI
    # (Nuke -t, workers del frame server) y no se escribe nada.
    if not _has_gui():
        if attempt < START_RETRIES:
            QtCore.QTimer.singleShot(START_RETRY_MS, lambda: _start_deferred(attempt + 1))
        return
    _reset_log()
    try:
        start_heartbeat()
    except Exception:
        debug_print("Error arrancando el latido:\n" + traceback.format_exc())


if QtCore.QCoreApplication.instance() is not None:
    QtCore.QTimer.singleShot(0, _start_deferred)
