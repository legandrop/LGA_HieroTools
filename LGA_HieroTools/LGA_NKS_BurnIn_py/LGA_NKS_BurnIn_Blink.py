"""
____________________________________________________________________

  LGA_NKS_BurnIn_Blink v1.08 | Lega

  Puente entre los knobs del soft effect LGA_BurnIn y su BlinkScript
  interno. setup() es el onCreate del BlinkScript: compila el kernel
  LGA_RoundedPanels y ata sus params, fuente, mascara del viewer y
  layout. apply_layout() traduce el mapa a los knobs on/bg/rot de cada
  campo y apply_rotation() escribe el giro de los costados en los Text2.
  schedule_update() junta los pedidos del panel y del knobChanged en una
  sola actualizacion por ciclo de eventos.

  v1.08: Performance. Centinela del kernel v0.08 (param kver: recompila
         instancias viejas). nudge() escribe UN knob (bi_rev, que el
         kernel y las cajas de los Text2 leen); el toque de opacidad que
         ensucia los Text2 queda solo para cuando apply_rotation cambio de
         verdad algun blob, y apply_rotation ya no reescribe blobs ni
         pivotes iguales. schedule_update/update_now: actualizacion
         agrupada; mientras corre, el knobChanged ignora los writes propios
         (is_busy).
  v1.07: Mascara del viewer: viewer_mask_aspect() lee la mascara visible
         (estilo Half o Full, cualquier aspect) y apply_mask() la escribe
         en bi_mask_aspect; el pivote de los costados girados la suma.
  v1.06: Panel con mapa. Once campos (FIELDS sale del modulo de layout).
         x/y/w/h de cada panel se atan a field_geo() de la logica (la
         misma geometria que las cajas de los Text2), las franjas del
         modo Band (band_t/b/l/r) y el formato (fmt_w/fmt_h = width /
         height del nodo). apply_layout() traduce el mapa (bi_layout) y
         el modo de fondo a los knobs on/bg/rot de cada campo. La
         rotacion ya no mide nada: los campos de un costado girado rotan
         alrededor de un pivote FIJO por costado (Layout.compute), que
         solo depende del formato, del tamano y del padding.
         _timeline_format() busca la secuencia que contiene el efecto y
         descarta formatos 0x0 (una secuencia vacia activa dejaba el
         pivote en 9.6, 9.6 y los costados fuera del cuadro).
  v1.05: Auditoria de la rotacion. (a) apply_rotation NO pisa el pivote
         de un campo rotado cuando no puede medirlo: en el onCreate el
         Input todavia no tiene stream y bi_text() devuelve '' (medido
         en el log), asi que panel_geo('w') daba 0 y el pivote de los
         campos left/right caia en el borde en vez del centro (los
         center no dependen del ancho: por eso "algunos si, otros no").
         Lo mismo si el formato del timeline no se puede resolver: ya no
         cae a los 640x480 del gizmo. (b) _bind_params re-ata los params
         cuya expresion no es la esperada (instancias viejas quedaban
         con el bind de v1.03 o sin ax/ay/rot). (c) _compile_kernel
         recompila si el kernel cargado no tiene los params de rotacion.
  v1.04: El pivote pasa a knobs literales del gizmo (bi_<f>_ax/ay),
         escritos por apply_rotation y leidos por el kernel: UNA sola
         fuente para texto y fondo (antes cada uno lo calculaba por su
         lado y podian divergir). Radio default de esquinas 11.
  v1.03: Rotacion por campo CABLEADA: apply_rotation() escribe el
         literal en animation_layers[10] del grupo "root transform" de
         cada Text2 (con el grupo seleccionado), pivote = centro del
         panel, mismo pivote bindeado a ax/ay del kernel (texto y
         fondo giran juntos). _timeline_format() para el formato real
         (por API el gizmo reporta 640x480). VALIDADO en NKS (90/270).
  v1.02: 8 campos (agrega custom1/custom2), alto del panel por campo
         (_h_expr, depende del size), y apply_font() que setea el peso
         de Inter (Regular/SemiBold/Bold) en el bi_font invisible.
  v1.01: Los paneles abrazan al texto: w y x medidos por python
         (panel_geo de la logica, con cache) y h/y por expresion
         compartida con los box de los Text2.
  v1.00: Version inicial.
____________________________________________________________________
"""

import os

KERNEL_NAME = "LGARoundedPanels"
KERNEL_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "LGA_RoundedPanels.blink"
)

import LGA_NKS_BurnIn_Layout as bi_layout

FIELDS = bi_layout.FIELDS

# Grados -> radianes para el knob de rotacion por campo (bi_<f>_rot en grados).
_DEG2RAD = 0.017453292519943295


def _log(message):
    try:
        import LGA_NKS_BurnIn_Logic as bi_logic

        bi_logic._log("[Blink] " + message)
    except Exception:
        pass


def _py_geo(field, comp):
    """Misma llamada que las cajas de los Text2 (generador, geo_expr)."""
    return (
        "[python {__import__('LGA_NKS_BurnIn_Logic')"
        ".field_geo('%s', '%s', nuke.thisParent(), nuke.frame())}]" % (field, comp)
    )


def _bindings():
    """Sufijo del knob del kernel -> expresion sobre los knobs del padre.

    x/y/w/h salen del mapa via field_geo (python, cacheado por frame): el
    mismo calculo que ubica las cajas de los Text2.
    """
    binds = {}
    for f in FIELDS:
        for comp in ("x", "y", "w", "h"):
            binds["%s_%s" % (f, comp)] = _py_geo(f, comp)
        binds["%s_on" % f] = "parent.bi_%s_on*parent.bi_%s_bg" % (f, f)
        # Pivote de rotacion (ax, ay): knobs literales del gizmo, escritos por
        # apply_rotation() — LA MISMA fuente que usa el blob del Text2. Si el
        # kernel lo calculara por expresion y el texto por python, cualquier
        # divergencia (formato del stream, medicion) separa el fondo del texto
        # al rotar. Con rot=0 el kernel es la SDF axis-aligned y no se usan.
        binds["%s_ax" % f] = "parent.bi_%s_ax" % f
        binds["%s_ay" % f] = "parent.bi_%s_ay" % f
        binds["%s_rot" % f] = "parent.bi_%s_rot*%s" % (f, _DEG2RAD)
    binds["corner_radius"] = "parent.bi_bg_radius"
    binds["color_r"] = "parent.bi_bg_color.r"
    binds["color_g"] = "parent.bi_bg_color.g"
    binds["color_b"] = "parent.bi_bg_color.b"
    binds["bg_opacity"] = "parent.bi_bg_opacity"
    for edge in ("t", "b", "l", "r"):
        binds["band_%s" % edge] = _py_geo("_band", edge)
    binds["fmt_w"] = "width"
    binds["fmt_h"] = "height"
    # Sin uso en el calculo: hace que el hash del kernel cambie con nudge().
    binds["rev"] = "parent.bi_rev"
    return binds


# Param que solo existe en el kernel de la version actual (v0.08, kver): si el nodo tiene el nombre del kernel pero no este knob, es una
# instancia compilada con un kernel viejo y hay que recompilar.
_KERNEL_SENTINEL = "kver"


def _find_param(node, suffix):
    """Nombre del knob del kernel para un sufijo (prefijado con el nombre del
    kernel), o None. Busca por sufijo porque el prefijo lo pone Nuke."""
    try:
        names = list(node.knobs())
    except Exception:
        return None
    for name in names:
        if name == suffix or name.endswith("_" + suffix):
            return name
    return None


def _compile_kernel(node):
    """Compila el kernel via Load si el nodo no lo tiene ya. True si quedo."""
    try:
        if node["kernelName"].value() == KERNEL_NAME:
            if _find_param(node, _KERNEL_SENTINEL) is not None:
                return True
            _log("kernel viejo (sin '{}'): recompilo".format(_KERNEL_SENTINEL))
    except Exception:
        pass
    try:
        node["kernelSourceFile"].setValue(KERNEL_FILE.replace("\\", "/"))
        node["reloadKernelSourceFile"].execute()
    except Exception as exc:
        _log("ERROR compilando kernel: {}".format(exc))
        return False
    try:
        ok = node["kernelName"].value() == KERNEL_NAME
    except Exception:
        ok = False
    _log("kernel compilado: {}".format("si" if ok else "NO"))
    return ok


def _norm_expr(text):
    """Normaliza una expresion para compararla: sin llaves externas ni blancos."""
    text = str(text or "").strip()
    while text.startswith("{") and text.endswith("}"):
        text = text[1:-1].strip()
    return "".join(text.split())


def _current_expr(knob):
    """Expresion actual del knob (texto), o '' si no tiene."""
    try:
        if not knob.hasExpression():
            return ""
    except Exception:
        return ""
    try:
        return str(knob.animation(0).expression())
    except Exception:
        pass
    try:
        return str(knob.toScript())
    except Exception:
        return ""


def _bind_params(node):
    """Ata los params del kernel (prefijados con el nombre del kernel) al padre.

    Se re-ata todo knob cuya expresion no sea la esperada: una instancia
    creada con una version anterior conserva los binds viejos en el .hrox
    (v1.03 ataba ax/ay a una cuenta por python que podia divergir del texto)
    y antes se salteaba por tener "alguna" expresion.
    """
    binds = _bindings()
    bound = 0
    for suffix, expr in binds.items():
        target = _find_param(node, suffix)
        if target is None:
            _log("param no encontrado para sufijo '{}'".format(suffix))
            continue
        knob = node[target]
        if _norm_expr(_current_expr(knob)) == _norm_expr(expr):
            continue
        try:
            knob.setExpression(expr)
            bound += 1
        except Exception as exc:
            _log("ERROR atando {} -> {}: {}".format(target, expr, exc))
    if bound:
        _log("{} parametros atados al padre".format(bound))


# La fuente del burn-in es Inter (la del pack). El peso se elige con el knob
# bi_weight (enum 0/1/2). El knob font de Text2 es un FreeType_Knob: se setea
# con setValue(family, style), NO acepta un path. Lo maneja apply_font, que
# corre en el onCreate (via setup) y en el knobChanged de bi_weight (registrado
# en LGA_NKS_BurnIn.py). Los Text2 heredan por la expresion [value parent.bi_font].
_WEIGHT_STYLES = ["Regular", "SemiBold", "Bold"]


def _gizmo_of(node):
    """Grupo LGA_BurnIn que contiene a un nodo interno, o None."""
    try:
        import nuke

        full = node.fullName()
        if "." in full:
            return nuke.toNode(full.rsplit(".", 1)[0])
    except Exception:
        pass
    return None


def apply_font(gizmo):
    """Setea el knob bi_font a Inter con el estilo del peso elegido.

    bi_weight es un Enumeration_Knob: value() devuelve el LABEL, que a
    proposito ES el estilo de Inter ('Regular'/'SemiBold'/'Bold').
    """
    if gizmo is None:
        return
    try:
        style = str(gizmo["bi_weight"].value())
    except Exception:
        style = "SemiBold"
    if style not in _WEIGHT_STYLES:
        style = "SemiBold"
    try:
        gizmo["bi_font"].setValue("Inter", style)
    except Exception as exc:
        _log("ERROR seteando bi_font a Inter {}: {}".format(style, exc))


# ── Rotacion por campo ────────────────────────────────────────────────────────
#
# El transform tab del Text2 NO renderiza en soft effects. Lo que SI renderiza
# es el transform del GRUPO "root transform" del propio Text2, serializado en
# el blob animation_layers:
#
#     {1 11 <cx> <cy> <tx> <ty> <sx> <sy> <skewX> <skewY> <ROT> <?>}
#
# La rotacion va en la posicion [10] y tiene que ser un LITERAL (una expresion
# ahi rompe el layer y el texto desaparece; medido). Ademas el grupo tiene que
# estar SELECCIONADO (group_animations ... selected: 0). Mecanismo capturado de
# un Text2 rotado a mano en la UI (tab Groups). Por eso la rotacion no puede
# vivir solo en el .gizmo: la escribe apply_rotation() leyendo bi_<f>_rot, en
# el onCreate (setup) y en el knobChanged (LGA_NKS_BurnIn.py).
#
# El pivote (cx, cy) se escribe en bi_<f>_ax/ay. Desde v1.06 es fijo por
# costado (ver _side_pivot) y solo los costados girados rotan. El panel de
# fondo de un campo girado lo calcula la logica con el mismo pivote
# (Layout.compute), asi que texto y fondo quedan juntos.


def _owner_sequences(gizmo):
    """Secuencias que contienen un efecto con el nombre de este nodo. El
    nombre (LGA_BurnIn1...) se repite entre secuencias, asi que puede haber
    varias; el que llama elige."""
    found = []
    try:
        import hiero.core

        name = gizmo.name()
        for project in hiero.core.projects():
            for seq in project.sequences():
                hit = False
                for track in seq.videoTracks():
                    for sub in track.subTrackItems():
                        for item in sub:
                            try:
                                if item.node().name() == name:
                                    hit = True
                                    break
                            except Exception:
                                continue
                        if hit:
                            break
                    if hit:
                        break
                if hit:
                    found.append(seq)
    except Exception:
        pass
    return found


def _seq_format(seq):
    try:
        fmt = seq.format()
        w, h = float(fmt.width()), float(fmt.height())
        return (w, h) if w > 0 and h > 0 else None
    except Exception:
        return None


def _timeline_format(gizmo):
    """(width, height) del formato del timeline del efecto, o None.

    Orden: la secuencia activa si contiene el efecto; si no, la primera que
    lo contenga; si no, la activa. Una secuencia sin formato (0x0, medido en
    una secuencia vacia) no cuenta: el pivote de los costados girados sale
    de este formato y con 0x0 quedaba en (9.6, 9.6) y los campos girados
    fuera del cuadro.

    OJO: gizmo.width()/height() por API devuelve el formato default (640x480),
    NO el del stream (medido): no se usa. Sin formato conocido el que llama
    conserva el pivote guardado."""
    try:
        import hiero.ui

        active = hiero.ui.activeSequence()
    except Exception:
        active = None
    owners = _owner_sequences(gizmo)
    ordered = []
    if active is not None and any(active == s for s in owners):
        ordered.append(active)
    ordered.extend(owners)
    if active is not None:
        ordered.append(active)
    for seq in ordered:
        fmt = _seq_format(seq)
        if fmt is not None:
            return fmt
    return None


def _layout_arr(gizmo):
    import LGA_NKS_BurnIn_Logic as bi_logic

    return bi_layout.active(bi_layout.parse(bi_logic.layout_text(gizmo)))


def _rotation_of(arr, field):
    """Rotacion en grados del campo segun el mapa: 90 en el costado izquierdo
    girado (se lee de abajo hacia arriba), 270 en el derecho, 0 el resto."""
    if arr.get("sides") != "rotated":
        return 0.0
    slot = bi_layout.slot_of(arr, field)
    if slot == "ml":
        return 90.0
    if slot == "mr":
        return 270.0
    return 0.0


def _side_pivot(gizmo, field, arr, fmt):
    """Pivote fijo del costado del campo: el mismo de Layout.compute."""
    import LGA_NKS_BurnIn_Logic as bi_logic

    fmt_w, fmt_h = fmt
    h = bi_logic.line_height_px(gizmo, fmt_h)
    edge = "l" if bi_layout.slot_of(arr, field) == "ml" else "r"
    inset_x = bi_logic.mask_inset_px(gizmo, fmt_w, fmt_h)[0]
    return bi_layout.side_pivot(edge, fmt_w, fmt_h, h, inset_x)


def _blob_nums(text):
    """Numeros del blob animation_layers, redondeados (toScript escribe
    '1024' donde el literal propio dice '1024.0')."""
    out = []
    for tok in str(text or "").replace("{", " ").replace("}", " ").split():
        try:
            out.append(round(float(tok), 3))
        except ValueError:
            out.append(tok)
    return out


def apply_rotation(gizmo, fields=None):
    """Escribe la rotacion literal de cada campo en su Text2 interno y el
    pivote en bi_<f>_ax/ay. Idempotente; con rot=0
    escribe el layer identidad.

    El pivote de un campo girado es fijo por costado: no depende del ancho
    del texto (que cambia de clip a clip), solo del formato, del tamano y
    del padding. Sin formato conocido se conserva el pivote guardado.
    """
    if gizmo is None:
        return False
    changed = False
    arr = _layout_arr(gizmo)
    fmt = _timeline_format(gizmo)
    if fmt is None:
        _log("formato del timeline desconocido: conservo los pivotes guardados")
    for f in fields if fields is not None else FIELDS:
        try:
            text_node = gizmo.node("Text_%s" % f.capitalize())
            if text_node is None:
                continue
            rot = float(gizmo["bi_%s_rot" % f].value())
            if rot != 0.0 and fmt is not None:
                cx, cy = _side_pivot(gizmo, f, arr, fmt)
                # Solo si cambia: cada setValue invalida el cache del viewer.
                for comp, val in (("ax", round(cx, 4)), ("ay", round(cy, 4))):
                    knob = gizmo["bi_%s_%s" % (f, comp)]
                    if abs(float(knob.value()) - val) > 1e-4:
                        knob.setValue(val)
            else:
                cx = float(gizmo["bi_%s_ax" % f].value())
                cy = float(gizmo["bi_%s_ay" % f].value())
            blob = "{1 11 %s %s 0 0 1 1 0 0 %s 0}" % (
                repr(round(cx, 4)), repr(round(cy, 4)), repr(round(rot, 4))
            )
            if _blob_nums(text_node["animation_layers"].toScript()) == _blob_nums(blob):
                continue
            text_node["group_animations"].fromScript(
                '{0} imported: 0 selected: 0 items: "root transform"'
            )
            text_node["animation_layers"].fromScript(blob)
            changed = True
        except Exception as exc:
            _log("ERROR rotando campo {}: {}".format(f, exc))
    if changed:
        # El write del blob no ensucia el Text2: un toque de opacidad si.
        _touch_texts(gizmo)
    return changed


def apply_layout(gizmo, do_nudge=True):
    """Traduce el mapa (bi_layout) y el modo de fondo (bi_bg_mode) a los
    knobs de cada campo: on (esta en el mapa), bg (modo Panels) y rot
    (costado girado). Despues re-escribe las rotaciones. Lo llaman el panel,
    el knobChanged del registro y el onCreate."""
    if gizmo is None:
        return
    arr = _layout_arr(gizmo)
    visible = set(bi_layout.visible_fields(arr))
    try:
        panels = int(gizmo["bi_bg_mode"].getValue()) == 0
    except Exception:
        panels = True
    for f in FIELDS:
        try:
            on = 1.0 if f in visible else 0.0
            if gizmo["bi_%s_on" % f].value() != on:
                gizmo["bi_%s_on" % f].setValue(on)
            bg = 1.0 if panels else 0.0
            if gizmo["bi_%s_bg" % f].value() != bg:
                gizmo["bi_%s_bg" % f].setValue(bg)
            rot = _rotation_of(arr, f)
            if float(gizmo["bi_%s_rot" % f].value()) != rot:
                gizmo["bi_%s_rot" % f].setValue(rot)
        except Exception as exc:
            _log("ERROR aplicando layout a {}: {}".format(f, exc))
    apply_rotation(gizmo)
    if do_nudge:
        nudge(gizmo)


def nudge(gizmo):
    """Ensucia el gizmo para que el timeline re-renderice.

    Incrementa bi_rev. Las expresiones de geometria del gizmo son [python] y
    Nuke no ve que dependen del mapa: sin un valor que cambie, el timeline
    reusaba el render cacheado y los paneles quedaban donde estaban antes
    (medido en NKS 17 al pasar a Edge). Cada una suma 0*parent.bi_rev: esa
    dependencia TCL hace que Nuke la vuelva a evaluar.

    UN solo write: cada write invalida el cache del viewer y NKS vuelve a
    renderizar los frames cacheados alrededor del playhead (medido: con los
    tres writes de antes, mover un slider costaba ~450 ms de CPU)."""
    try:
        rev = float(gizmo["bi_rev"].value())
        gizmo["bi_rev"].setValue((rev + 1.0) % 100000.0)
    except Exception:
        pass


def _touch_texts(gizmo):
    """Ensucia los Text2: el write por API de animation_layers no dispara el
    re-render solo (medido)."""
    try:
        value = gizmo["bi_opacity"].value()
        gizmo["bi_opacity"].setValue(value - 0.001)
        gizmo["bi_opacity"].setValue(value)
    except Exception:
        pass


# ── Actualizacion agrupada ────────────────────────────────────────────────────
#
# Cada setValue en un knob del gizmo invalida el cache del viewer y NKS vuelve
# a renderizar los frames cacheados alrededor del playhead. Antes un cambio
# del panel disparaba en cadena: el write del panel, apply_layout del panel,
# apply_layout del knobChanged, y cada _rot / ax / ay que esos escribian volvia
# a entrar al knobChanged con su propio apply_rotation + nudge (tres writes).
# Ahora todo pedido (knobChanged, panel) se anota en _pending y se resuelve
# UNA vez por efecto al volver al loop de eventos; mientras corre, el
# knobChanged ignora los writes propios (_busy).

_busy = [False]
_pending = {}
_timer_holder = []


def is_busy():
    return _busy[0]


def schedule_update(gizmo, font=False):
    """Pide una actualizacion (fuente, layout, rotacion, nudge) del efecto,
    agrupada con todas las que lleguen en el mismo ciclo de eventos."""
    if gizmo is None:
        return
    try:
        key = gizmo.fullName()
    except Exception:
        return
    prev = _pending.get(key)
    _pending[key] = (gizmo, font or (prev[1] if prev else False))
    if _timer_holder and _timer_holder[0].isActive():
        return
    try:
        from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtCore

        if not _timer_holder:
            timer = QtCore.QTimer()
            timer.setSingleShot(True)
            timer.setInterval(0)
            timer.timeout.connect(_flush_pending)
            _timer_holder.append(timer)
        _timer_holder[0].start()
    except Exception:
        _flush_pending()


def _flush_pending():
    items = list(_pending.values())
    _pending.clear()
    for gizmo, font in items:
        update_now(gizmo, font)


def update_now(gizmo, font=False):
    """Aplica fuente (si se pidio), mapa y rotacion, y ensucia el efecto con
    un solo write. Los writes de aca no re-entran al knobChanged."""
    if gizmo is None:
        return
    _busy[0] = True
    try:
        if font:
            apply_font(gizmo)
        apply_layout(gizmo, do_nudge=False)
        nudge(gizmo)
    except Exception as exc:
        _log("ERROR en update_now: {}".format(exc))
    finally:
        _busy[0] = False


def _aspect_from_name(name):
    """'3:2' -> 1.5, '2.35' -> 2.35; 0.0 si no se entiende."""
    try:
        text = str(name or "").strip()
        if ":" in text:
            num, den = text.split(":", 1)
            return float(num) / float(den)
        return float(text)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


def viewer_mask_aspect():
    """Aspect de la mascara que se ve en el viewer actual, o 0.0 sin mascara.

    Cuenta como mascara cualquier estilo que no sea None (Half, al 50%, ya
    tapa los burn-ins) con los overlays a la vista. El nombre de la mascara
    (maskOverlayName) queda puesto aunque el estilo sea None: por eso se mira
    el estilo (medido en NKS 17: '3:2' con estilo 0). Solo hilo principal."""
    try:
        import hiero.ui

        viewer = hiero.ui.currentViewer()
        if viewer is None or not viewer.overlaysShown():
            return 0.0
        style = viewer.maskOverlayStyle()
        if style == hiero.ui.Player.MaskOverlayStyle.eMaskOverlayNone:
            return 0.0
        return _aspect_from_name(viewer.maskOverlayName())
    except Exception:
        return 0.0


def apply_mask(gizmo, aspect):
    """Escribe el aspect de la mascara en el efecto y re-ubica los pivotes de
    los costados girados (dependen del area visible). No hace nada si ya
    tenia ese valor."""
    try:
        aspect = round(float(aspect), 4)
        if abs(float(gizmo["bi_mask_aspect"].value()) - aspect) < 1e-4:
            return False
    except Exception:
        return False
    _busy[0] = True
    try:
        gizmo["bi_mask_aspect"].setValue(aspect)
        apply_rotation(gizmo)
        nudge(gizmo)
    finally:
        _busy[0] = False
    return True


def setup(node):
    """onCreate del BlinkScript interno del gizmo: compila el kernel y ata sus
    params (si hace falta), fuente, mascara del viewer y layout (on/bg/rot por
    campo y rotaciones). Corre al agregar el efecto y al cargar un proyecto."""
    try:
        gizmo = _gizmo_of(node)
        if gizmo is None:
            return
        _busy[0] = True
        try:
            if _compile_kernel(node):
                _bind_params(node)
            apply_font(gizmo)
            # Un efecto recien agregado arranca con la mascara que ya tiene
            # el viewer (el vigia del registro solo avisa cambios).
            aspect = round(viewer_mask_aspect(), 4)
            if abs(float(gizmo["bi_mask_aspect"].value()) - aspect) > 1e-4:
                gizmo["bi_mask_aspect"].setValue(aspect)
            apply_layout(gizmo)
        finally:
            _busy[0] = False
    except Exception as exc:
        _log("ERROR en setup: {}".format(exc))
