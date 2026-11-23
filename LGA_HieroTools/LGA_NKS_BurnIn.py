"""
____________________________________________________________________

  LGA_NKS_BurnIn v1.11 | Lega

  Registra el soft effect LGA_BurnIn (solo Text2; fondos redondeados
  con la fuente LGA Shapes) en el menu Effects del timeline de NKS. Muestra
  metadata del clip visible y pinta en rojo resolucion/fps cuando no
  coinciden con el objetivo del proyecto. La config vive en AppData y el override por proyecto en
  un tag que viaja en el .hrox.

  Mecanismo de registro: QAction con objectName prefijado
  "foundry.timeline.effect." + setData(clase del nodo), via
  hiero.ui.registerAction (patron oficial de custom_soft_effect.py).

  v1.11: Registro de tiempos [Perf]: el vigia de 500 ms anota cuando el
         hilo principal estuvo trabado (con la ultima actividad del
         efecto) y escribe el resumen del render cada ~2 s; el
         knobChanged marca el knob que cambio.
  v1.10: Sin BlinkScript: importa LGA_NKS_BurnIn_Effect (antes
         LGA_NKS_BurnIn_Blink). bi_bg_radius pasa a pedir actualizacion
         (el radio va en el mensaje de los fondos de glifos).
  v1.09: Performance: el knobChanged solo anota el pedido
         (Blink.schedule_update, agrupado por ciclo de eventos) e ignora los
         knobs que van directo al render y los writes de la propia
         actualizacion. Antes cada write interno volvia a entrar con su
         apply_rotation + nudge.
  v1.08: Fuera LGA BurnIn v0 (la version solo Text2): ya no se registra
         y se borro su gizmo.
  v1.07: Vigia de la mascara del viewer (QTimer de 500 ms en el hilo
         principal): con una mascara Half o Full, de cualquier aspect, los
         LGA_BurnIn de la secuencia activa se acomodan dentro del area
         visible (bi_mask_aspect). La mascara sola no tiene evento.
  v1.06: knobChanged del panel con mapa: bi_layout y bi_bg_mode
         re-aplican el mapa a los knobs de cada campo (apply_layout);
         bi_size y bi_text_pad re-escriben los pivotes de los costados
         girados. Fuera los branches de x/y/size por campo (inertes).
  v1.05: Fuera el refresh con Viewer.flushCache(): la pausa del cacheo
         que trae flushCache llega asincronica, el resumeCaching()
         inmediato no la deshacia y el viewer quedaba pausado. Con el
         cacheo pausado el viewer no dibuja frames nuevos: al agregar el
         efecto (el onCreate escribe knobs bi_*) mover el playhead dejaba
         de actualizar la imagen hasta cambiar de timeline. Medido que el
         setValue de un knob del gizmo ya re-renderiza el frame actual.
  v1.04: Refresco del viewer SIN abrir tabs. Tras cualquier cambio de
         un knob bi_* (del panel, de un script o de la UI) se programa
         UN refresh_viewer() diferido (QTimer de 0 ms: una rafaga de
         writes termina en un solo refresh) que descarta los frames
         cacheados del viewer actual (Viewer.flushCache) y le pide que
         se redibuje (hiero.ui.updateViewer). OJO: flushCache ademas
         PAUSA el cacheo (doc de la API), por eso se llama
         resumeCaching() enseguida. El nudge de opacidad sigue como
         respaldo para ensuciar el hash del nodo. Guardia de re-entrada
         en el knobChanged: apply_rotation escribe bi_<f>_ax/ay y el
         nudge escribe bi_opacity, y cada write vuelve a disparar el
         callback. El texto de los custom (bi_<f>_text) tambien
         re-aplica el pivote (cambia el ancho del panel) y los sufijos
         de campo se validan contra FIELDS.
  v1.03: el knobChanged tambien re-aplica la rotacion por campo
         (bi_<f>_rot y todo lo que mueve el pivote: x/y/size, scale,
         text_pad) via apply_rotation() del modulo Blink.
  v1.02: addKnobChanged por nodeClass LGA_BurnIn: al cambiar el peso
         de la fuente (bi_weight) re-aplica apply_font() para que el
         fondo se recalcule con las metricas del nuevo peso de Inter.
  v1.01: Registra LGA_BurnIn (version BlinkScript con paneles
         redondeados) y renombra la version solo-Text2 a LGA_BurnIn_v0.
  v1.00: Version inicial.
____________________________________________________________________
"""

import os
import sys
import traceback

# Capa intermedia de tooltips (regla del repo: no hardcodear el texto en el
# widget, para que la futura migracion bilingue sea un cambio de datos).
TOOLTIPS = {
    "es": {
        "effect": "Aplica el burn-in de LGA: metadata del clip visible con "
        "paneles redondeados de fondo; resolucion y fps en rojo si no "
        "coinciden con el proyecto",
    },
}


def _tooltip(key, lang="es"):
    return TOOLTIPS.get(lang, {}).get(key, "")


def _log(message):
    """Log al archivo de la logica (DebugPy_LGA_NKS_BurnIn.log)."""
    try:
        import LGA_NKS_BurnIn_Logic as bi_logic

        bi_logic._log("[Registro] " + message)
    except Exception:
        pass


# ── Refresco del viewer del timeline ─────────────────────────────────────────
#
# NO se llama a Viewer.flushCache(). Medido en NKS 17.0v4 (2026-10-17): la
# pausa del cacheo que trae flushCache aterriza ASINCRONICA (~140 ms despues;
# ni un QTimer de 0 ms llega antes), asi que el resumeCaching() inmediato no
# hace nada y el viewer queda pausado. Con el cacheo pausado el viewer no
# dibuja ningun frame nuevo: mover el playhead no cambia la imagen hasta pasar
# a otro timeline (que resetea el viewer). Como el onCreate escribe knobs bi_*
# (bi_font, pivotes), el viewer se congelaba apenas se agregaba el efecto.
#
# Tampoco hace falta: un setValue en un knob del gizmo cambia el hash del nodo
# y el viewer re-renderiza el frame actual solo (medido: frameDisplayed se
# dispara y la imagen refleja la opacidad y la rotacion nuevas). Lo unico que
# no ensucia el nodo es el write del blob animation_layers, y para eso esta
# nudge() en LGA_NKS_BurnIn_Effect.

# Knobs bi_* que llegan al render por expresiones TCL directas (o que escribe
# el propio update): no necesitan re-aplicar nada ni ensuciar el efecto.
# bi_bg_radius NO va aca: el radio entra en el mensaje de los fondos (glifos
# de LGA Shapes), que se re-evalua solo con el nudge de bi_rev.
_KNOBS_DIRECTOS = (
    "bi_open_panel", "bi_rev", "bi_font", "bi_shape_font", "bi_color",
    "bi_opacity", "bi_bg_color", "bi_bg_opacity",
)
# Por campo (bi_<campo>_<sufijo>): on/bg/rot/ax/ay los deriva apply_layout
# del mapa; x/y/size quedaron inertes desde el panel con mapa. _text (custom)
# SI cambia el layout.
_SUFIJOS_DIRECTOS = ("ax", "ay", "on", "bg", "rot", "x", "y", "size")

_state = {}


def _es_derivado(name, fields):
    parts = name[3:].rsplit("_", 1)
    return len(parts) == 2 and parts[0] in fields and parts[1] in _SUFIJOS_DIRECTOS


def _on_knob_changed():
    """knobChanged de la clase LGA_BurnIn (registrado en _register).

    Solo ANOTA el pedido: LGA_NKS_BurnIn_Effect.schedule_update lo resuelve
    una vez por efecto al volver al loop de eventos (una rafaga del panel o de
    un script termina en una sola actualizacion y un solo nudge). Los writes
    que hace la propia actualizacion no vuelven a entrar (is_busy)."""
    import nuke

    try:
        import LGA_NKS_BurnIn_Effect as bi_effect
    except Exception:
        return
    if bi_effect.is_busy():
        return
    k = nuke.thisKnob()
    if k is None:
        return
    name = k.name()
    if not name.startswith("bi_") or name in _KNOBS_DIRECTOS:
        return
    if _es_derivado(name, bi_effect.FIELDS):
        return
    try:
        import LGA_NKS_BurnIn_Logic as bi_logic

        bi_logic.perf_mark("knob " + name)
    except Exception:
        pass
    try:
        bi_effect.schedule_update(nuke.thisNode(), font=(name == "bi_weight"))
    except Exception as exc:
        _log("ERROR en knobChanged {}: {}".format(name, exc))


# ── Vigia de la mascara del viewer ───────────────────────────────────────────
#
# La mascara se elige desde el viewer (o con el boton del panel Viewer | TL) y
# no hay un evento de hiero que avise: el viewer tiene senales propias, pero
# se destruye y se recrea al cambiar de timeline. Un QTimer en el hilo
# principal mira cada 500 ms el aspect visible y la secuencia activa (tres
# lecturas baratas); solo cuando algo cambia recorre los efectos LGA_BurnIn
# de la secuencia y les escribe bi_mask_aspect.

_MASK_POLL_MS = 500


def _burnins_of(seq):
    out = []
    try:
        for track in seq.videoTracks():
            for sub in track.subTrackItems():
                for item in sub:
                    try:
                        node = item.node()
                    except Exception:
                        continue
                    if node is not None and node.Class() == "LGA_BurnIn":
                        out.append(node)
    except Exception:
        pass
    return out


# Un tick que llega mas de _FREEZE_MS tarde significa que el hilo principal
# estuvo trabado (los timers de Qt no se atienden mientras tanto). Se anota con
# la ultima actividad del efecto: es la pista para diagnosticar una maquina
# donde todo anda lento. Cada _PERF_EVERY ticks se escribe el resumen del render.
_FREEZE_MS = 700
_PERF_EVERY = 4


def _perf_tick():
    try:
        import time
        import LGA_NKS_BurnIn_Logic as bi_logic

        now = time.perf_counter()
        prev = _state.get("tick_t")
        _state["tick_t"] = now
        if prev is not None:
            late = (now - prev) * 1000.0 - _MASK_POLL_MS
            if late > _FREEZE_MS:
                bi_logic.perf_flush()
                bi_logic.perf_log(
                    "NKS trabado ~{:.0f} ms (ultima actividad del efecto: {})".format(
                        late, bi_logic.perf_last()
                    )
                )
        _state["ticks"] = _state.get("ticks", 0) + 1
        if _state["ticks"] % _PERF_EVERY == 0:
            bi_logic.perf_flush()
    except Exception:
        pass


def _mask_tick():
    _perf_tick()
    try:
        import hiero.ui
        import LGA_NKS_BurnIn_Effect as bi_effect

        aspect = round(bi_effect.viewer_mask_aspect(), 4)
        seq = hiero.ui.activeSequence()
        key = (aspect, id(seq) if seq is not None else None)
        if key == _state.get("mask_key") or seq is None:
            _state["mask_key"] = key
            return
        _state["mask_key"] = key
        changed = 0
        for node in _burnins_of(seq):
            if bi_effect.apply_mask(node, aspect):
                changed += 1
        if changed:
            _log("mascara del viewer {} -> {} efecto(s)".format(aspect, changed))
    except Exception as exc:
        _log("ERROR en el vigia de mascara: {}".format(exc))


def _start_mask_watcher():
    from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtCore

    old = _state.get("mask_timer")
    if old is not None:
        try:
            old.stop()
        except Exception:
            pass
    timer = QtCore.QTimer()
    timer.setInterval(_MASK_POLL_MS)
    timer.timeout.connect(_mask_tick)
    timer.start()
    # Referencia viva: sin ella PySide destruye el timer.
    _state["mask_timer"] = timer


def _register():
    import nuke
    from hiero.ui import registerAction
    from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtGui, QAction

    package_dir = os.path.join(os.path.dirname(__file__), "LGA_NKS_BurnIn_py")

    # El paquete entra a sys.path para que las expresiones del gizmo puedan
    # hacer __import__('LGA_NKS_BurnIn_Logic') por nombre pelado, y a los
    # plugin paths de Nuke para que la clase LGA_BurnIn (el .gizmo) exista.
    if package_dir not in sys.path:
        sys.path.insert(0, package_dir)
    nuke.pluginAddPath(package_dir)

    import LGA_NKS_BurnIn_Logic as bi_logic

    bi_logic.perf_header()

    action = QAction(QtGui.QIcon("icons:Text.png"), "LGA BurnIn", None)
    action.setObjectName("foundry.timeline.effect.addLGABurnIn")
    action.setToolTip(_tooltip("effect"))
    action.setData("LGA_BurnIn")
    registerAction(action)

    # Un cambio de knob del gizmo (panel, script o UI) re-aplica fuente y
    # rotacion segun corresponda (el viewer re-renderiza solo).
    nuke.addKnobChanged(_on_knob_changed, nodeClass="LGA_BurnIn")

    # La mascara del viewer acomoda los burn-ins dentro del area visible.
    _start_mask_watcher()

    # La config cacheada por proyecto se invalida en los eventos de proyecto:
    # al cargar (los tags ya estan disponibles), al guardar (por si la ventana
    # de settings estampo un override nuevo) y al cerrar.
    from hiero.core import events

    def _on_project_event(event):
        bi_logic.invalidate_cache()

    for event_type in (
        events.EventType.kAfterProjectLoad,
        events.EventType.kAfterProjectSave,
        events.EventType.kAfterProjectClose,
    ):
        events.registerInterest(event_type, _on_project_event)


try:
    _register()
except Exception:
    print("[LGA_NKS_BurnIn] Error registrando el soft effect")
    traceback.print_exc()
