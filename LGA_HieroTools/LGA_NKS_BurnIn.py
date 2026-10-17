"""
____________________________________________________________________

  LGA_NKS_BurnIn v1.05 | Lega

  Registra los soft effects LGA_BurnIn (BlinkScript + Text2, paneles
  redondeados) y LGA_BurnIn_v0 (solo Text2) en el menu Effects del
  timeline de NKS. Muestran metadata del clip visible y pintan en
  rojo resolucion/fps cuando no coinciden con el objetivo del
  proyecto. La config vive en AppData y el override por proyecto en
  un tag que viaja en el .hrox.

  Mecanismo de registro: QAction con objectName prefijado
  "foundry.timeline.effect." + setData(clase del nodo), via
  hiero.ui.registerAction (patron oficial de custom_soft_effect.py).

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
        "effect_v0": "Version anterior del burn-in de LGA (solo Text2, "
        "fondos rectangulares nativos)",
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
# nudge() en el modulo Blink.

# Knobs bi_* que no cambian el render.
_KNOBS_SIN_RENDER = ("bi_open_panel",)

_state = {"in_handler": False}


def _apply_layout_change(gizmo, name):
    """Re-aplica fuente/rotacion segun el knob bi_* que cambio."""
    try:
        import LGA_NKS_BurnIn_Blink as bi_blink
    except Exception:
        return
    if name == "bi_weight":
        # El peso cambia la fuente Y las metricas: re-aplicar ambas y ensuciar
        # el nodo (el bi_font seteado por codigo no siempre invalida solo).
        bi_blink.apply_font(gizmo)
        bi_blink.apply_rotation(gizmo)
        bi_blink.nudge(gizmo)
    elif name.endswith("_rot"):
        # bi_<campo>_rot: reescribir el literal del campo tocado. El write
        # del blob animation_layers no ensucia el nodo solo: nudge.
        field = name[3:-4]
        if field in bi_blink.FIELDS:
            bi_blink.apply_rotation(gizmo, fields=(field,))
            bi_blink.nudge(gizmo)
    elif name.endswith(("_x", "_y", "_size", "_text")):
        # Mover el ancla, el tamano o el texto custom corre el pivote (ancho
        # o centro del panel): re-aplicar el campo (con rot=0 es inocuo).
        field = name[3:].rsplit("_", 1)[0]
        if field in bi_blink.FIELDS:
            bi_blink.apply_rotation(gizmo, fields=(field,))
    elif name in ("bi_scale", "bi_text_pad"):
        # Cambian el alto de TODOS los paneles (y sus centros).
        bi_blink.apply_rotation(gizmo)


def _on_knob_changed():
    """knobChanged de la clase LGA_BurnIn (registrado en _register)."""
    import nuke

    if _state["in_handler"]:
        # Re-entrada: los writes que hace este mismo handler (ax/ay del
        # pivote, el nudge de opacidad) vuelven a disparar el callback.
        return
    n = nuke.thisNode()
    k = nuke.thisKnob()
    if n is None or k is None:
        return
    name = k.name()
    if not name.startswith("bi_") or name in _KNOBS_SIN_RENDER:
        return
    _state["in_handler"] = True
    try:
        _apply_layout_change(n, name)
    except Exception as exc:
        _log("ERROR en knobChanged {}: {}".format(name, exc))
    finally:
        _state["in_handler"] = False


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

    action = QAction(QtGui.QIcon("icons:Text.png"), "LGA BurnIn", None)
    action.setObjectName("foundry.timeline.effect.addLGABurnIn")
    action.setToolTip(_tooltip("effect"))
    action.setData("LGA_BurnIn")
    registerAction(action)

    action_v0 = QAction(QtGui.QIcon("icons:Text.png"), "LGA BurnIn v0", None)
    action_v0.setObjectName("foundry.timeline.effect.addLGABurnInV0")
    action_v0.setToolTip(_tooltip("effect_v0"))
    action_v0.setData("LGA_BurnIn_v0")
    registerAction(action_v0)

    # Un cambio de knob del gizmo (panel, script o UI) re-aplica fuente y
    # rotacion segun corresponda (el viewer re-renderiza solo).
    nuke.addKnobChanged(_on_knob_changed, nodeClass="LGA_BurnIn")

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
