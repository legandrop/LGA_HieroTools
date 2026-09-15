"""
____________________________________________________________________

  LGA_NKS_TimelineMemory v1.02 | Lega

  Memoria de vista por timeline para el Projects Panel.

  El switch de secuencia destruye el viewer y el timeline viejos, y con
  ellos el zoom, el scroll y el playhead. Este modulo los guarda justo
  antes de destruirlos y los vuelve a aplicar cuando se reabre la misma
  secuencia. Tambien recuerda el ultimo timeline de cada contexto
  (studio / client), para que el toggle vuelva a donde se estaba.

  La memoria vive en un JSON dentro de logs/ con el PID del proceso en el
  nombre, y dura una sesion de NKS: sobrevive al reimport del panel, no a
  reabrir NKS, y dos NKS abiertos a la vez no se pisan.

  Lo que se guarda por timeline:
    - zoom: el slider del contenedor horizontal del TimelineView
    - scroll horizontal y vertical
    - playhead
  Gain/gamma/saturation NO: siguen pasando de un timeline al siguiente.

  Log propio: logs/DebugPy_TimelineMemory.log. NO se reinicia en cada
  switch (el log del panel si), asi que conserva la historia completa de la
  sesion: que se guardo al salir de cada timeline y que se restauro al
  volver, con el valor pedido y el que quedo.

  v1.02: El zoom se reintenta en el lugar hasta que el slider acepta el
         valor: recien abierto el timeline, su rango todavia no esta armado y
         el valor quedaba recortado (629 pedido, 187 aplicado). Nuevo
         has_view() para que el switch sepa si hay vista que aplicar.
  v1.01: Nada se guardaba: leer el slider tiraba "Internal C++ object
         (QSlider) already deleted" y esa excepcion cortaba el guardado
         entero, playhead incluido. Ahora cada dato se lee por separado,
         los wrappers muertos se descartan con is_widget_alive() antes de
         usarlos (primero children(), como las tools viejas; findChildren()
         de respaldo) y cada paso queda en el log propio.
  v1.00: Version inicial.
____________________________________________________________________
"""

import json
import os
import time

import hiero.core
import hiero.ui
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtCore, is_widget_alive
from LGA_NKS_Projects_Panel_py.LGA_NKS_ProjectsPanel_Logging import debug_print

_LOGS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs"
)
# Un archivo por proceso: con dos NKS abiertos a la vez, un JSON compartido
# haria que cada sesion descarte y pise la memoria de la otra.
_MEMORY_PATH = os.path.join(_LOGS_DIR, f"ProjectsPanel_TimelineMemory_{os.getpid()}.json")
_LOG_PATH = os.path.join(_LOGS_DIR, "DebugPy_TimelineMemory.log")

# Intentos de aplicar el zoom procesando eventos entre cada uno. Con el timeline
# recien abierto el slider todavia no tiene su rango final y recorta el valor.
ZOOM_SETTLE_TRIES = 8


# =========================
#          LOG
# =========================


def _log(message, level="info"):
    """Escribe al log propio (acumulativo por sesion) y al log del panel."""
    debug_print(f"[Memoria] {message}", level=level)
    try:
        os.makedirs(_LOGS_DIR, exist_ok=True)
        # El log se reinicia la primera vez que escribe este proceso: si todavia
        # no existe el JSON de este PID, es una sesion nueva de NKS.
        mode = "a" if os.path.exists(_MEMORY_PATH) or _log.started else "w"
        _log.started = True
        with open(_LOG_PATH, mode, encoding="utf-8", newline="\n") as f:
            if mode == "w":
                f.write(f"Sesion NKS PID {os.getpid()} - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"[{time.strftime('%H:%M:%S')}] {level.upper()} {message}\n")
    except Exception:
        pass


_log.started = False


# =========================
#       PERSISTENCIA
# =========================


def _empty_memory():
    return {"pid": os.getpid(), "timelines": {}, "contexts": {}}


def _load():
    try:
        with open(_MEMORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return _empty_memory()
    except Exception as e:
        _log(f"No se pudo leer {_MEMORY_PATH}: {e}", level="warning")
        return _empty_memory()


def _save(data):
    try:
        os.makedirs(_LOGS_DIR, exist_ok=True)
        with open(_MEMORY_PATH, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        _log(f"No se pudo escribir {_MEMORY_PATH}: {e}", level="error")
        return False


def _norm_path(path):
    return os.path.normcase(os.path.normpath(path or ""))


def _sequence_key(seq):
    """Clave estable de una secuencia: ruta del .hrox + nombre de la secuencia."""
    try:
        return f"{_norm_path(seq.project().path())}::{seq.name()}"
    except Exception:
        return None


# =========================
#     CONTROLES DE VISTA
# =========================


def _live_children(parent, qt_class):
    """
    Hijos directos de `parent` del tipo pedido y VIVOS en C++.

    Devuelve (vivos, muertos). Un wrapper de PySide puede seguir apuntando a un
    widget que Hiero ya destruyo: usarlo tira "Internal C++ object already
    deleted", que es justo lo que rompia el guardado en v1.00.
    """
    alive, dead = [], 0
    try:
        candidates = list(parent.children())
    except Exception:
        candidates = []
    for child in candidates:
        if not isinstance(child, qt_class):
            continue
        if is_widget_alive(child):
            alive.append(child)
        else:
            dead += 1
    if not alive:
        # Respaldo: busqueda recursiva, tambien filtrando muertos
        try:
            for child in parent.findChildren(qt_class):
                if is_widget_alive(child):
                    alive.append(child)
                else:
                    dead += 1
        except Exception:
            pass
    return alive, dead


def _find_view_controls(timeline_editor):
    """
    Devuelve {"zoom", "scroll_h", "scroll_v"} con los widgets vivos que se
    encontraron (los que no, quedan en None) y registra cada paso en el log.

    Recorrido de LGA_NKS_Timeline_Refresh_Wrap y LGA_NKS_ScrollTo_TopTrack:
    ventana -> QSplitter -> QWidget -> QAbstractScrollArea. Hiero no expone el
    zoom del timeline por API; el slider del contenedor horizontal es el zoom.
    """
    controls = {"zoom": None, "scroll_h": None, "scroll_v": None}
    try:
        window = timeline_editor.window()
        if not is_widget_alive(window):
            _log("Controles: la ventana del timeline esta muerta", level="warning")
            return controls

        splitters, _ = _live_children(window, QtWidgets.QSplitter)
        if not splitters:
            _log(f"Controles: sin QSplitter vivo en '{window.objectName()}'", level="warning")
            return controls

        view = None
        for child in splitters[0].children():
            if not isinstance(child, QtWidgets.QWidget) or not is_widget_alive(child):
                continue
            areas, _ = _live_children(child, QtWidgets.QAbstractScrollArea)
            if areas:
                view = areas[0]
                break
        if view is None:
            _log("Controles: sin TimelineView (QAbstractScrollArea) vivo", level="warning")
            return controls

        containers = {}
        for child in view.children():
            if is_widget_alive(child):
                containers[child.objectName()] = child
        h_container = containers.get("qt_scrollarea_hcontainer")
        v_container = containers.get("qt_scrollarea_vcontainer")

        report = [f"ventana='{window.objectName()}'"]
        if h_container is not None:
            sliders, dead_sliders = _live_children(h_container, QtWidgets.QSlider)
            h_bars, dead_h = _live_children(h_container, QtWidgets.QScrollBar)
            controls["zoom"] = sliders[0] if sliders else None
            controls["scroll_h"] = h_bars[0] if h_bars else None
            report.append(f"sliders vivos={len(sliders)} muertos={dead_sliders}")
            report.append(f"scroll_h vivos={len(h_bars)} muertos={dead_h}")
        else:
            report.append("sin hcontainer")
        if v_container is not None:
            v_bars, dead_v = _live_children(v_container, QtWidgets.QScrollBar)
            controls["scroll_v"] = v_bars[0] if v_bars else None
            report.append(f"scroll_v vivos={len(v_bars)} muertos={dead_v}")
        else:
            report.append("sin vcontainer")
        _log("Controles: " + " | ".join(report))
    except Exception as e:
        _log(f"Controles: error recorriendo el TimelineView: {e}", level="error")
    return controls


def _read_value(widget, label):
    if widget is None:
        return None
    try:
        return widget.value()
    except Exception as e:
        _log(f"No se pudo leer {label}: {e}", level="warning")
        return None


def _write_value(widget, value, label):
    """Aplica `value` y devuelve el valor que quedo, o None si no se pudo."""
    if widget is None or value is None:
        return None
    try:
        if not is_widget_alive(widget):
            _log(f"No se aplico {label}: el widget murio", level="warning")
            return None
        widget.setValue(int(value))
        return widget.value()
    except Exception as e:
        _log(f"No se pudo aplicar {label}={value}: {e}", level="warning")
        return None


def _apply_zoom(slider, value):
    """Aplica el zoom y reintenta procesando eventos hasta que el slider lo acepta."""
    result = None
    for attempt in range(1, ZOOM_SETTLE_TRIES + 1):
        result = _write_value(slider, value, "zoom")
        QtCore.QCoreApplication.processEvents()
        if result is None or not is_widget_alive(slider):
            return result
        result = slider.value()
        if result == int(value):
            if attempt > 1:
                _log(f"Zoom {value} aceptado en el intento {attempt}")
            return result
    _log(
        f"Zoom {value} no se asento tras {ZOOM_SETTLE_TRIES} intentos: quedo {result} "
        f"(rango del slider {slider.minimum()}..{slider.maximum()})",
        level="warning",
    )
    return result


# =========================
#       API DEL PANEL
# =========================


def has_view(seq):
    """True si hay una vista guardada para `seq`."""
    key = _sequence_key(seq) if seq else None
    return bool(key and _load()["timelines"].get(key))


def capture_active():
    """Guarda la vista del timeline activo. Llamar ANTES de destruirlo."""
    try:
        seq = hiero.ui.activeSequence()
        editor = hiero.ui.getTimelineEditor(seq) if seq else None
    except Exception as e:
        _log(f"Guardar: no se pudo leer la secuencia activa: {e}", level="error")
        return False
    key = _sequence_key(seq) if seq else None
    if not key:
        _log("Guardar: no hay secuencia activa")
        return False

    state = {"playhead": None, "zoom": None, "scroll_h": None, "scroll_v": None}

    # Playhead primero y por separado: no depende de los widgets del timeline
    try:
        viewer = hiero.ui.currentViewer()
        state["playhead"] = viewer.time() if viewer else None
    except Exception as e:
        _log(f"Guardar: no se pudo leer el playhead: {e}", level="warning")

    if editor:
        controls = _find_view_controls(editor)
        for name, widget in controls.items():
            state[name] = _read_value(widget, name)
    else:
        _log(f"Guardar: '{key}' no tiene TimelineEditor", level="warning")

    data = _load()
    data["timelines"][key] = state
    if _save(data):
        _log(f"GUARDADO '{key}': {state}")
    return True


def restore_view(seq, attempt="principal"):
    """
    Aplica la vista guardada de `seq`, si la hay. Devuelve True si aplico algo.

    El zoom va primero: cambia el rango del scroll horizontal, y un scroll
    aplicado antes quedaria recortado al rango viejo.
    """
    key = _sequence_key(seq) if seq else None
    state = _load()["timelines"].get(key) if key else None
    if not state:
        _log(f"Restaurar ({attempt}): sin vista guardada para '{key}'")
        return False

    applied = {}
    editor = hiero.ui.getTimelineEditor(seq)
    controls = _find_view_controls(editor) if editor else {}
    if controls.get("zoom") is not None and state.get("zoom") is not None:
        applied["zoom"] = _apply_zoom(controls["zoom"], state["zoom"])
    for name in ("scroll_h", "scroll_v"):
        applied[name] = _write_value(controls.get(name), state.get(name), name)

    try:
        viewer = hiero.ui.currentViewer()
        if viewer and state.get("playhead") is not None:
            viewer.setTime(int(state["playhead"]))
            applied["playhead"] = viewer.time()
    except Exception as e:
        _log(f"Restaurar ({attempt}): no se pudo aplicar el playhead: {e}", level="warning")

    _log(f"RESTAURADO ({attempt}) '{key}': pedido={state} | quedo={applied}")
    return True


def remember_context(mode):
    """Guarda el timeline activo como el ultimo del contexto `mode`, con su vista."""
    try:
        seq = hiero.ui.activeSequence()
    except Exception:
        seq = None
    if not seq:
        _log(f"Contexto '{mode}': no hay timeline activo para recordar")
        return False
    capture_active()
    data = _load()
    data["contexts"][mode] = {
        "project_path": _norm_path(seq.project().path()),
        "sequence": seq.name(),
    }
    _save(data)
    _log(f"Contexto '{mode}' recordado: {data['contexts'][mode]}")
    return True


def recall_context(mode):
    """
    Devuelve (proyecto, nombre_secuencia) del ultimo timeline del contexto
    `mode`, o None si no hay nada guardado o ese proyecto ya no esta abierto.
    """
    entry = _load()["contexts"].get(mode)
    if not entry:
        _log(f"Contexto '{mode}': nada guardado, el timeline queda donde esta")
        return None

    for project in hiero.core.projects():
        try:
            if _norm_path(project.path()) != entry["project_path"]:
                continue
            if any(s.name() == entry["sequence"] for s in project.sequences()):
                _log(f"Contexto '{mode}': vuelta a {entry}")
                return project, entry["sequence"]
        except Exception:
            continue
    _log(f"Contexto '{mode}': {entry} ya no esta abierto", level="warning")
    return None
