"""
____________________________________________________________________

  LGA_NKS_BurnIn_Panel v3.03 | Lega

  Panel "Burn-ins" del soft effect LGA_BurnIn, con el diseno del menu
  Burn-ins de Shot Player (LGA Media Tools): cinco distribuciones
  (Corners, Top & bottom, Bottom line, Edge, Left list) con Reset, un
  mapa con los ocho lugares del cuadro donde se arrastran los campos
  (o se elige uno con un click y despues el lugar), la bandeja Hidden,
  el texto de los dos Custom, y el Look en segmentos y sliders de
  marcas. Debajo quedan las secciones propias del efecto: presets con
  nombre y los targets del proyecto (resolucion y fps en rojo).

  Todo es global: los campos comparten tamano, peso, fondo y giro de
  los costados. El mapa vive en el knob bi_layout del efecto (JSON de
  LGA_NKS_BurnIn_Layout) y el render lo convierte en posiciones
  (LGA_NKS_BurnIn_Logic.field_geo). La ventana solo escribe knobs y
  config; los cambios se ven en el visor al instante.

  v3.03: El chip TC lleva el punto rojo como Res y FPS.
  v3.02: Performance. Los cambios pasan por Blink.schedule_update (una sola
         actualizacion y un solo nudge por efecto y por ciclo de eventos, en
         vez de apply_layout directo + el del knobChanged). Los sliders
         escriben a lo sumo cada 33 ms mientras se arrastran (el ultimo
         valor siempre llega) y los de opacidad y radio ya no ensucian el
         efecto: van al render por expresiones directas.
  v3.01: Defaults de fabrica nuevos (Bg opacity 79, Radius 29) para el
         click en el rotulo. Ventana mas ancha (520) y '&' escapado en los
         segmentados.
  v3.00: Rediseno con mapa (reemplaza la tabla X / Y / Size por campo).
         Campos Track, Date y Codec. Background Panels / Band / Text,
         Size S/M/L, Labels, Stack y Sides. Sliders de marcas como los
         de Shot Player. Tooltips propios del pack (antes nativos).
  v2.03: El ancla 3x3 posicionaba la caja visible del campo.
  v2.00: Rediseno tabla + detalle.
  v1.00: Version inicial.
____________________________________________________________________
"""

import json

from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import (
    QtWidgets,
    QtGui,
    QtCore,
    Qt,
)
from LGA_NKS_Shared.LGA_UI_Style_HieroTools import (
    Style,
    Color,
    Metric,
    apply_ui_font,
    emphasis,
    semibold_css,
)
from LGA_NKS_Shared.LGA_UI_CustomTooltip_HieroTools import set_custom_tooltip

import LGA_NKS_BurnIn_Config as bi_config
import LGA_NKS_BurnIn_Layout as bi_layout

_WEIGHTS = ("Regular", "SemiBold", "Bold")

# Intervalo minimo entre writes de un slider arrastrado (~30 por segundo).
_SLIDER_MS = 33

# Defaults de los sliders (los del gizmo). Click en el rotulo vuelve a este.
_SLIDERS = {
    "bg_opacity": ("bi_bg_opacity", 0.0, 100.0, 79.0, 0.01, "%"),
    "text_opacity": ("bi_opacity", 0.0, 100.0, 100.0, 0.01, "%"),
    "radius": ("bi_bg_radius", 0.0, 60.0, 29.0, 1.0, ""),
    "padding": ("bi_text_pad", 0.0, 80.0, 28.0, 1.0, ""),
}

# Capa intermedia de tooltips (regla del repo: castellano, nunca escritos en
# el widget, para la futura migracion bilingue).
TOOLTIPS = {
    "es": {
        "refresh": "Vuelve a buscar el efecto LGA BurnIn en la secuencia activa.",
        "preset": "Distribucion de los campos. Cada una recuerda como la dejaste.",
        "reset": "Vuelve la distribucion activa a como viene de fabrica.",
        "map": "Arrastra un campo a un lugar, o hace click en el campo y despues en el lugar.<br>"
        "Soltarlo al costado de otro lo pone en la misma linea; arriba o abajo, en una linea nueva.<br>"
        "En Hidden se oculta.",
        "custom1": "Texto del campo Custom 1. Escribir lo muestra si estaba oculto.",
        "custom2": "Texto del campo Custom 2. Escribir lo muestra si estaba oculto.",
        "background": "Panels: un panel por campo. Band: una franja por borde usado. Text: sin fondo, con sombra.",
        "bg_opacity": "Opacidad del fondo.<br>Click en el rotulo: vuelve al valor por defecto.",
        "text_opacity": "Opacidad del texto.<br>Click en el rotulo: vuelve al valor por defecto.",
        "radius": "Radio de las esquinas de los paneles, en pixeles del formato.<br>Click en el rotulo: vuelve al valor por defecto.",
        "padding": "Margen del texto dentro de su panel, en pixeles del formato.<br>Click en el rotulo: vuelve al valor por defecto.",
        "size": "Tamano de la letra, relativo al alto del formato.",
        "labels": "Prefijo Frame, TC y Track delante del valor.",
        "weight": "Peso de la fuente Inter.",
        "stack": "Row junta los campos de cada lugar en una linea; Column deja uno por linea.",
        "sides": "Rotated gira los campos de los costados a lo largo del borde.",
        "text_color": "Color del texto de todos los campos.",
        "bg_color": "Color del fondo.",
        "preset_combo": "Presets guardados en AppData.",
        "preset_load": "Aplica el preset elegido al efecto.",
        "preset_name": "Nombre para guardar el estado actual como preset.",
        "preset_save": "Guarda distribucion, look y textos con ese nombre.",
        "res_target": "Resolucion esperada de los plates: timeline o 3840x2160.<br>Si un plate EXR no coincide, Res se pinta de rojo.",
        "fps_target": "FPS esperados: timeline o un numero.<br>Si el clip no coincide, FPS se pinta de rojo.",
        "keep_on_top": "Mantiene esta ventana por encima de las demas.",
        "save_defaults": "Guarda los targets como default del usuario (AppData).",
        "save_project": "Guarda los targets en el proyecto: viajan dentro del .hrox.",
    },
}


def _tip(key, lang="es"):
    return TOOLTIPS.get(lang, {}).get(key, "")


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


# ── Slider de marcas (el de Shot Player) ──────────────────────────────────────


class TickSlider(QtWidgets.QWidget):
    """Slider de marcas: la misma pieza que Exposure, Gamma y Opacity de Shot
    Player (AdjustmentTickSlider, Media Tools), en Python. Marcas de 2 px
    cada 8,5 px, la elegida mas alta y clara; al pasar el mouse por la
    elegida, ella y sus tres vecinas crecen (100 ms). Click o arrastre fijan
    el valor; las flechas lo mueven de a uno. Solo pinta al cambiar el valor
    o el hover: no consume nada en reposo."""

    valueChanged = QtCore.Signal(float)

    _SPACING = 8.5
    _TICK_W = 2
    _H_NORMAL = 5
    _H_SEL = 10
    _H_SEL_HOVER = 16
    _H_NEAR = (13, 10, 7)
    _HEIGHT = 24
    _Y_OFFSET = 2
    _HANDLE_RADIUS = 8

    def __init__(self, minimo, maximo, parent=None):
        super(TickSlider, self).__init__(parent)
        self._min = float(minimo)
        self._max = float(maximo)
        self._value = float(minimo)
        self._hover = 0.0
        self._dragging = False
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumHeight(self._HEIGHT)
        self.setMinimumWidth(80)
        self.setCursor(Qt.PointingHandCursor)
        self._anim = QtCore.QVariantAnimation(self)
        self._anim.setDuration(100)
        self._anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)

    def sizeHint(self):
        return QtCore.QSize(200, self._HEIGHT)

    def value(self):
        return self._value

    def setValue(self, v, emit=False):
        v = _clamp(round(float(v)), self._min, self._max)
        if v == self._value:
            return
        self._value = v
        self.update()
        if emit:
            self.valueChanged.emit(v)

    # geometria
    def _span(self):
        left = self._HANDLE_RADIUS
        right = self.width() - self._HANDLE_RADIUS
        return left, max(left + 1, right)

    def _x_for(self, v):
        left, right = self._span()
        t = (v - self._min) / (self._max - self._min) if self._max > self._min else 0.0
        return left + t * (right - left)

    def _value_at(self, x):
        left, right = self._span()
        t = _clamp((x - left) / float(right - left), 0.0, 1.0)
        return self._min + t * (self._max - self._min)

    # hover
    def _on_anim(self, value):
        self._hover = float(value)
        self.update()

    def _set_hover(self, on):
        target = 1.0 if on else 0.0
        if self._anim.endValue() == target and self._anim.state() == self._anim.Running:
            return
        if abs(self._hover - target) < 1e-3:
            return
        self._anim.stop()
        self._anim.setStartValue(self._hover)
        self._anim.setEndValue(target)
        self._anim.start()

    def _event_x(self, event):
        try:
            return event.position().x()
        except AttributeError:  # PySide2
            return event.pos().x()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self.setValue(self._value_at(self._event_x(event)), emit=True)
            self._set_hover(True)
            event.accept()
            return
        super(TickSlider, self).mousePressEvent(event)

    def mouseMoveEvent(self, event):
        x = self._event_x(event)
        if self._dragging:
            self.setValue(self._value_at(x), emit=True)
        else:
            self._set_hover(abs(x - self._x_for(self._value)) <= self._HANDLE_RADIUS)
        super(TickSlider, self).mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._dragging = False
        self._set_hover(abs(self._event_x(event) - self._x_for(self._value)) <= self._HANDLE_RADIUS)
        super(TickSlider, self).mouseReleaseEvent(event)

    def leaveEvent(self, event):
        if not self._dragging:
            self._set_hover(False)
        super(TickSlider, self).leaveEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Right, Qt.Key_Up):
            self.setValue(self._value + 1, emit=True)
        elif event.key() in (Qt.Key_Left, Qt.Key_Down):
            self.setValue(self._value - 1, emit=True)
        else:
            super(TickSlider, self).keyPressEvent(event)

    def paintEvent(self, _event):
        left, right = self._span()
        span = right - left
        half = max(1, int(span / (2.0 * self._SPACING) + 1e-6))
        n = 2 * half
        step = span / float(n)
        active_x = self._x_for(self._value)
        active_i = int(round((active_x - left) / step))
        base_y = self.height() / 2.0 + self._Y_OFFSET + self._H_NORMAL / 2.0
        dpr = self.devicePixelRatioF()
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, False)
        p.setPen(Qt.NoPen)
        p.setBrush(QtGui.QColor(Color.BORDER_HOVER))
        for i in range(n + 1):
            x = round((left + i * step) * dpr) / dpr
            if abs(x - active_x) <= self._TICK_W:
                continue
            target = self._H_NORMAL
            dist = abs(i - active_i)
            if 1 <= dist <= len(self._H_NEAR):
                target = self._H_NEAR[dist - 1]
            h = round(self._H_NORMAL + (target - self._H_NORMAL) * self._hover)
            p.drawRect(QtCore.QRectF(x - self._TICK_W / 2.0, base_y - h, self._TICK_W, h))
        h = round(self._H_SEL + (self._H_SEL_HOVER - self._H_SEL) * self._hover)
        p.setBrush(QtGui.QColor(Color.TEXT_STRONG))
        p.drawRect(QtCore.QRectF(active_x - self._TICK_W / 2.0, base_y - h, self._TICK_W, h))
        p.end()


# ── Segmentado (pastillas del pack) ───────────────────────────────────────────


class Segmented(QtWidgets.QWidget):
    """Una decision de varias opciones: contenedor hundido y una sola opcion
    violeta (Style.PILL_*, el mismo switch del Projects Panel)."""

    picked = QtCore.Signal(str)

    def __init__(self, options, parent=None):
        super(Segmented, self).__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(Style.PILL_CONTAINER_SUNKEN)
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(2, 2, 2, 2)
        row.setSpacing(0)
        self._buttons = {}
        self._current = None
        for key, label in options:
            # & escapado: un QPushButton toma "&" como atajo de teclado
            # ("Top & bottom" salia "Top_bottom").
            b = QtWidgets.QPushButton(label.replace("&", "&&"))
            b.setCursor(Qt.PointingHandCursor)
            b.setFlat(True)
            b.clicked.connect(lambda _c=False, k=key: self.picked.emit(k))
            row.addWidget(b, 1)
            self._buttons[key] = b
        self.setCurrent(None)

    def setCurrent(self, key):
        self._current = key
        for k, b in self._buttons.items():
            b.setStyleSheet(Style.PILL_ACTIVE if k == key else Style.PILL_INACTIVE)


class _ClickLabel(QtWidgets.QLabel):
    """Rotulo de un slider: un click vuelve al valor por defecto (como los
    indicadores de Shot Player)."""

    clicked = QtCore.Signal()

    def __init__(self, text, parent=None):
        super(_ClickLabel, self).__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super(_ClickLabel, self).mousePressEvent(event)


# ── Mapa de lugares + bandeja Hidden ──────────────────────────────────────────


class BurnInMap(QtWidgets.QWidget):
    """Mapa del cuadro con los ocho lugares y, debajo, la bandeja Hidden.

    Pintado a mano (QPainter) con tokens del modulo de estilo. Un campo se
    arrastra a un lugar, o se elige con un click y despues se hace click en
    el lugar. Soltarlo junto a otro campo: a su izquierda o derecha queda en
    la misma linea, arriba o abajo en una linea nueva (el lado sale de la
    posicion relativa al centro del chip, normalizada por su medio ancho y
    medio alto, igual que Shot Player). Emite changed() tras cada cambio."""

    changed = QtCore.Signal()
    # El alto depende del ancho (mapa 16:9) y de las filas de Hidden.
    heightChanged = QtCore.Signal()

    _ZONES = {
        "tl": (0.02, 0.03, 0.31, 0.24), "tc": (0.345, 0.03, 0.31, 0.24),
        "tr": (0.67, 0.03, 0.31, 0.24),
        "ml": (0.02, 0.30, 0.22, 0.40), "mr": (0.76, 0.30, 0.22, 0.40),
        "bl": (0.02, 0.73, 0.31, 0.24), "bc": (0.345, 0.73, 0.31, 0.24),
        "br": (0.67, 0.73, 0.31, 0.24),
    }
    _CHIP_H = 16
    _CHIP_GAP = 3
    _TRAY_GAP = 22  # espacio para el rotulo HIDDEN

    def __init__(self, parent=None):
        super(BurnInMap, self).__init__(parent)
        self.arr = bi_layout.fresh_arrangement(bi_layout.DEFAULT_PRESET)
        self.bad = set()
        self.sel = None
        self._chips = []  # (QRectF, campo, lugar)
        self._zones = {}  # lugar -> QRectF (incluye 'hidden')
        self._press = None
        self._drag = None  # (campo, QPointF)
        self._hover_zone = None
        self._drop = None  # (campo destino, lado) o (None, lugar)
        self.setMouseTracking(True)
        self.setMinimumHeight(260)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

    # datos
    def set_arrangement(self, arr, bad=None):
        self.arr = arr
        self.bad = set(bad or ())
        if self.sel and bi_layout.slot_of(self.arr, self.sel) is None:
            self.sel = None
        self._relayout()
        self.update()

    # geometria
    def _font(self):
        f = QtGui.QFont(self.font())
        f.setPixelSize(11)
        return f

    def _chip_w(self, field):
        fm = QtGui.QFontMetricsF(self._font())
        return fm.horizontalAdvance(bi_layout.SHORT[field]) + 12.0

    def _map_rect(self):
        w = float(self.width())
        return QtCore.QRectF(0.5, 0.5, w - 1.0, round(w * 0.56))

    def _relayout(self):
        self._chips = []
        self._zones = {}
        mr = self._map_rect()
        for slot, (zx, zy, zw, zh) in self._ZONES.items():
            rect = QtCore.QRectF(
                mr.x() + zx * mr.width(), mr.y() + zy * mr.height(),
                zw * mr.width(), zh * mr.height(),
            )
            self._zones[slot] = rect
            lines = self.arr["slots"].get(slot) or []
            block_h = len(lines) * self._CHIP_H + max(0, len(lines) - 1) * self._CHIP_GAP
            if slot[0] == "t":
                y = rect.top() + 4
            elif slot[0] == "b":
                y = rect.bottom() - 4 - block_h
            else:
                y = rect.center().y() - block_h / 2.0
            for line in lines:
                widths = [self._chip_w(f) for f in line]
                total = sum(widths) + self._CHIP_GAP * (len(line) - 1)
                if slot[1] == "l":
                    x = rect.left() + 4
                elif slot[1] == "r":
                    x = rect.right() - 4 - total
                else:
                    x = rect.center().x() - total / 2.0
                for f, cw in zip(line, widths):
                    self._chips.append((QtCore.QRectF(x, y, cw, self._CHIP_H), f, slot))
                    x += cw + self._CHIP_GAP
                y += self._CHIP_H + self._CHIP_GAP
        # Bandeja Hidden: chips que envuelven en filas.
        top = mr.bottom() + self._TRAY_GAP
        x0 = 6.0
        x, y = x0, top + 5
        right = self.width() - 6.0
        for f in self.arr["hidden"]:
            cw = self._chip_w(f)
            if x + cw > right and x > x0:
                x, y = x0, y + self._CHIP_H + self._CHIP_GAP
            self._chips.append((QtCore.QRectF(x, y, cw, self._CHIP_H), f, "hidden"))
            x += cw + self._CHIP_GAP
        tray_h = (y + self._CHIP_H + 5) - top
        tray_h = max(tray_h, self._CHIP_H + 10)
        self._zones["hidden"] = QtCore.QRectF(0.5, top, self.width() - 1.0, tray_h)
        total_h = int(top + tray_h + 1)
        if self.minimumHeight() != total_h:
            self.setFixedHeight(total_h)
            self.heightChanged.emit()

    def resizeEvent(self, event):
        self._relayout()
        super(BurnInMap, self).resizeEvent(event)

    def sizeHint(self):
        return QtCore.QSize(360, self.minimumHeight())

    # hit test
    def _chip_at(self, pos):
        for rect, f, slot in self._chips:
            if rect.contains(pos):
                return rect, f, slot
        return None

    def _zone_at(self, pos):
        for slot, rect in self._zones.items():
            if rect.contains(pos):
                return slot
        return None

    @staticmethod
    def _side(rect, pos):
        dx = (pos.x() - rect.center().x()) / max(1.0, rect.width() / 2.0)
        dy = (pos.y() - rect.center().y()) / max(1.0, rect.height() / 2.0)
        if abs(dx) >= abs(dy):
            return "l" if dx < 0 else "r"
        return "t" if dy < 0 else "b"

    def _pos(self, event):
        try:
            return event.position()
        except AttributeError:  # PySide2
            return QtCore.QPointF(event.pos())

    # eventos
    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        pos = self._pos(event)
        hit = self._chip_at(pos)
        self._press = (pos, hit[1] if hit else None)
        event.accept()

    def mouseMoveEvent(self, event):
        pos = self._pos(event)
        if self._press and self._press[1] and self._drag is None:
            if (pos - self._press[0]).manhattanLength() > 4:
                self._drag = (self._press[1], pos)
                self.setCursor(Qt.ClosedHandCursor)
        if self._drag is not None:
            self._drag = (self._drag[0], pos)
            self._drop = self._drop_target(pos)
        else:
            self._hover_zone = self._zone_at(pos)
            self.setCursor(Qt.PointingHandCursor if (self._chip_at(pos) or self._hover_zone) else Qt.ArrowCursor)
        self.update()

    def _drop_target(self, pos):
        field = self._drag[0] if self._drag else self.sel
        hit = self._chip_at(pos)
        if hit and hit[1] != field and hit[2] != "hidden":
            return (hit[1], self._side(hit[0], pos))
        zone = self._zone_at(pos)
        if zone:
            return (None, zone)
        return None

    def mouseReleaseEvent(self, event):
        pos = self._pos(event)
        if self._drag is not None:
            field = self._drag[0]
            target = self._drop_target(pos)
            self._drag = None
            self._drop = None
            self.setCursor(Qt.PointingHandCursor)
            if target:
                self._apply_drop(field, target)
            self._press = None
            self.update()
            return
        pressed = self._press[1] if self._press else None
        self._press = None
        if pressed:
            # Click en un chip: lo elige (o lo suelta si ya estaba elegido).
            self.sel = None if self.sel == pressed else pressed
            self.update()
            return
        zone = self._zone_at(pos)
        if self.sel and zone:
            self._apply_drop(self.sel, (None, zone))
            self.sel = None
        self.update()

    def leaveEvent(self, event):
        self._hover_zone = None
        self.update()
        super(BurnInMap, self).leaveEvent(event)

    def _apply_drop(self, field, target):
        other, where = target
        if other is not None:
            bi_layout.move_next_to(self.arr, field, other, where)
        elif where != bi_layout.slot_of(self.arr, field) or where != "hidden":
            bi_layout.move_to(self.arr, field, where)
        self._relayout()
        self.changed.emit()

    # pintado
    def paintEvent(self, _event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        p.setFont(self._font())
        mr = self._map_rect()
        p.setPen(QtGui.QPen(QtGui.QColor(Color.BORDER), 1))
        p.setBrush(QtGui.QColor(Color.SURFACE_SUNKEN))
        p.drawRoundedRect(mr, Metric.RADIUS_SMALL, Metric.RADIUS_SMALL)

        picking = self.sel is not None or self._drag is not None
        drop_zone = self._drop[1] if (self._drop and self._drop[0] is None) else None
        for slot, rect in self._zones.items():
            hot = slot == drop_zone or (self._drag is None and slot == self._hover_zone and picking)
            pen = QtGui.QPen(QtGui.QColor(Color.ACCENT_HOVER if hot else (Color.ACCENT if picking else Color.BORDER_STRONG)), 1)
            pen.setStyle(Qt.DashLine)
            p.setPen(pen)
            fill = QtGui.QColor(Color.ACCENT)
            fill.setAlpha(60 if hot else 0)
            p.setBrush(fill)
            p.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), 3, 3)

        # Rotulos de la bandeja y pista del mapa.
        p.setPen(QtGui.QColor(Color.TEXT_HEADER))
        tray = self._zones["hidden"]
        p.drawText(QtCore.QRectF(2, tray.top() - self._TRAY_GAP + 3, 200, 16),
                   Qt.AlignLeft | Qt.AlignVCenter, "HIDDEN")
        if self.sel:
            hint = "Click a spot for %s" % bi_layout.SHORT[self.sel]
        elif not self.arr["hidden"] and False:
            hint = ""
        else:
            hint = "Drag a field to a spot"
        p.setPen(QtGui.QColor(Color.TEXT_DIM))
        p.drawText(QtCore.QRectF(mr.x(), mr.center().y() - 9, mr.width(), 18), Qt.AlignCenter, hint)
        if not self.arr["hidden"]:
            p.drawText(tray.adjusted(8, 0, 0, 0), Qt.AlignLeft | Qt.AlignVCenter, "Drop a field here to hide it")

        drop_chip = self._drop if (self._drop and self._drop[0] is not None) else None
        dragging = self._drag[0] if self._drag else None
        for rect, f, slot in self._chips:
            hidden = slot == "hidden"
            if f == self.sel:
                bg, fg = QtGui.QColor(Color.ACCENT), QtGui.QColor(Color.TEXT_ON_ACCENT)
            elif hidden:
                bg, fg = QtGui.QColor(Color.SURFACE), QtGui.QColor(Color.TEXT_DIM)
            else:
                bg, fg = QtGui.QColor(Color.SURFACE_RAISED), QtGui.QColor(Color.TEXT_STRONG)
            if f == dragging:
                bg.setAlpha(90)
                fg.setAlpha(120)
            p.setPen(Qt.NoPen)
            p.setBrush(bg)
            p.drawRoundedRect(rect, 3, 3)
            p.setPen(fg)
            p.drawText(rect, Qt.AlignCenter, bi_layout.SHORT[f])
            if f in self.bad:
                p.setPen(Qt.NoPen)
                p.setBrush(QtGui.QColor(Color.ERROR_TEXT))
                p.drawEllipse(QtCore.QPointF(rect.right() - 1, rect.top() + 1), 2.5, 2.5)
            if drop_chip and drop_chip[0] == f:
                p.setPen(QtGui.QPen(QtGui.QColor(Color.ACCENT_HOVER), 2))
                side = drop_chip[1]
                if side == "l":
                    p.drawLine(rect.topLeft() + QtCore.QPointF(-2, 0), rect.bottomLeft() + QtCore.QPointF(-2, 0))
                elif side == "r":
                    p.drawLine(rect.topRight() + QtCore.QPointF(2, 0), rect.bottomRight() + QtCore.QPointF(2, 0))
                elif side == "t":
                    p.drawLine(rect.topLeft() + QtCore.QPointF(0, -2), rect.topRight() + QtCore.QPointF(0, -2))
                else:
                    p.drawLine(rect.bottomLeft() + QtCore.QPointF(0, 2), rect.bottomRight() + QtCore.QPointF(0, 2))

        # Chip arrastrado bajo el puntero, semitransparente.
        if self._drag is not None:
            f, pos = self._drag
            cw = self._chip_w(f)
            ghost = QtCore.QRectF(pos.x() - cw / 2.0, pos.y() - self._CHIP_H / 2.0, cw, self._CHIP_H)
            c = QtGui.QColor(Color.ACCENT)
            c.setAlpha(170)
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            p.drawRoundedRect(ghost, 3, 3)
            p.setPen(QtGui.QColor(Color.TEXT_ON_ACCENT))
            p.drawText(ghost, Qt.AlignCenter, bi_layout.SHORT[f])
        p.end()


# ── Acceso al efecto real (stubbeable para el harness) ────────────────────────


class HieroController(object):
    """Acceso al efecto y a la config reales. Se stubbea para el harness."""

    def __init__(self):
        self.node = None
        self.label = "No effect found"
        self.project_name = ""

    def attach(self):
        import hiero.ui

        self.node = None
        self.label = "No LGA BurnIn effect in the active sequence"
        self.project_name = ""
        seq = hiero.ui.activeSequence()
        if seq is None:
            self.label = "No active sequence"
            return False
        self.project_name = seq.project().name()
        for track in seq.videoTracks():
            for sub in track.subTrackItems():
                for item in sub:
                    try:
                        node = item.node()
                    except Exception:
                        continue
                    if node is not None and node.Class() == "LGA_BurnIn":
                        self.node = node
                        self.label = "%s  (track %s)" % (item.name(), track.name())
                        return True
        return False

    def get(self, knob, default=0.0):
        try:
            return self.node[knob].value()
        except Exception:
            return default

    def get_index(self, knob, default=0):
        try:
            return int(self.node[knob].getValue())
        except Exception:
            return default

    def set(self, knob, value):
        try:
            self.node[knob].setValue(value)
        except Exception:
            pass

    def get_text(self, knob, default=""):
        # getText y no value(): value() de un String_Knob evalua corchetes
        # como TCL (un JSON o un texto con [ ] vuelve roto).
        try:
            return str(self.node[knob].getText())
        except Exception:
            return default

    def get_color(self, knob):
        try:
            v = self.node[knob].value()
            if not isinstance(v, (list, tuple)):
                v = (v, v, v)
            return (float(v[0]), float(v[1]), float(v[2]))
        except Exception:
            return (1.0, 1.0, 1.0)

    def set_color(self, knob, rgb):
        try:
            k = self.node[knob]
            for i, c in enumerate(rgb):
                k.setValue(c, i)
            k.setValue(1.0, 3)
        except Exception:
            pass

    def get_weight(self):
        try:
            return str(self.node["bi_weight"].value())
        except Exception:
            return "SemiBold"

    def set_weight(self, style):
        try:
            self.node["bi_weight"].setValue(style)
        except Exception:
            pass
        self._schedule(font=True)

    def get_layout(self):
        return self.get_text("bi_layout", "")

    def set_layout(self, text):
        """Escribe el mapa y pide aplicarlo a los knobs de cada campo."""
        self.set("bi_layout", text)
        self.apply_layout()

    def _schedule(self, font=False):
        """Una sola actualizacion por ciclo de eventos (Blink.schedule_update):
        el knobChanged del registro pide la misma y se juntan."""
        try:
            import LGA_NKS_BurnIn_Blink as bi_blink

            bi_blink.schedule_update(self.node, font=font)
        except Exception:
            pass

    def apply_layout(self):
        self._schedule()

    def field_ok(self, field):
        """1.0/0.0 del campo (res/fps) para el punto rojo del chip. Por API el
        stream no tiene metadata y da 1.0: no grita rojo sin datos."""
        try:
            import LGA_NKS_BurnIn_Logic as bi_logic
            import nuke

            return bi_logic.bi_ok(field, self.node, nuke.frame())
        except Exception:
            return 1.0

    def load_targets(self):
        user_data, _error = bi_config.load_user_file()
        import LGA_NKS_BurnIn_ProjectTag as bi_tag

        tag_json = bi_tag.read_config_json(bi_tag.find_project(self.project_name))
        cfg, _warns = bi_config.resolve(user_data, self.project_name, tag_json)
        return str(cfg.get("res_target", "timeline")), str(cfg.get("fps_target", "timeline"))

    def save_targets_project(self, res_target, fps_target):
        import LGA_NKS_BurnIn_ProjectTag as bi_tag

        proj = bi_tag.find_project(self.project_name)
        current = bi_tag.read_config_json(proj)
        try:
            data = json.loads(current) if current else {}
        except Exception:
            data = {}
        data["res_target"] = res_target
        data["fps_target"] = fps_target
        error = bi_tag.write_config(proj, data)
        self._invalidate()
        return error

    def save_targets_defaults(self, res_target, fps_target):
        data, _error = bi_config.load_user_file()
        data.setdefault("default", {})
        data["default"]["res_target"] = res_target
        data["default"]["fps_target"] = fps_target
        error = bi_config.save_user_file(data)
        self._invalidate()
        return error

    def _invalidate(self):
        try:
            import LGA_NKS_BurnIn_Logic as bi_logic

            bi_logic.invalidate_cache()
        except Exception:
            pass

    def nudge(self):
        """Ensucia el efecto para que el timeline re-renderice (agrupado)."""
        self._schedule()

    def list_presets(self):
        return bi_config.list_presets()

    def load_preset(self, name):
        return bi_config.load_preset(name)

    def save_preset(self, name, preset):
        return bi_config.save_preset(name, preset)


# ── Ventana ───────────────────────────────────────────────────────────────────


class BurnInPanel(QtWidgets.QDialog):
    """Panel Burn-ins de LGA BurnIn (mapa + look + presets + targets)."""

    def __init__(self, controller, parent=None):
        super(BurnInPanel, self).__init__(parent)
        self.ctl = controller
        self._loading = True
        self.state = bi_layout.default_state()
        self.setWindowTitle("Burn-ins")
        self.setStyleSheet(Style.FORM)
        # Mas ancho que el minimo comun: Upright / Rotated y los tres botones
        # de abajo se cortaban a 460 (medido con el harness).
        self.setMinimumWidth(520)
        self._keep_on_top = True
        # Escritura de sliders a lo sumo cada _SLIDER_MS (ver _on_slider).
        self._slider_pend = {}
        self._slider_timer = QtCore.QTimer(self)
        self._slider_timer.setSingleShot(True)
        self._slider_timer.setInterval(_SLIDER_MS)
        self._slider_timer.timeout.connect(self._flush_sliders)
        self._apply_on_top()
        self._armar_ui()
        apply_ui_font(self)
        self._cargar_estado()
        self._loading = False

    # -- armado --------------------------------------------------------------
    def _armar_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        m = Metric.WINDOW_MARGIN
        layout.setContentsMargins(m, m, m, m)
        layout.setSpacing(8)

        cabeza = QtWidgets.QHBoxLayout()
        titulo = QtWidgets.QLabel("Burn-ins")
        titulo.setProperty("lgaTitle", True)
        cabeza.addWidget(titulo)
        self.lbl_efecto = QtWidgets.QLabel("")
        self.lbl_efecto.setStyleSheet("color: %s;" % Color.TEXT_DIM)
        cabeza.addWidget(self.lbl_efecto, 1)
        refresh = QtWidgets.QPushButton("Refresh")
        refresh.setStyleSheet(Style.BTN_SMALL)
        set_custom_tooltip(refresh, _tip("refresh"))
        refresh.clicked.connect(self._refrescar)
        cabeza.addWidget(refresh)
        layout.addLayout(cabeza)

        # PRESETS + mapa + Hidden + Custom
        self.btn_reset = QtWidgets.QPushButton("Reset")
        self.btn_reset.setStyleSheet(Style.BTN_SMALL)
        set_custom_tooltip(self.btn_reset, _tip("reset"))
        self.btn_reset.clicked.connect(self._reset_preset)
        layout.addLayout(self._seccion("Presets", self.btn_reset))
        self.seg_preset = Segmented(bi_layout.PRESETS)
        set_custom_tooltip(self.seg_preset, _tip("preset"))
        self.seg_preset.picked.connect(self._on_preset)
        layout.addWidget(self.seg_preset)
        self.mapa = BurnInMap()
        set_custom_tooltip(self.mapa, _tip("map"))
        self.mapa.changed.connect(self._on_map_changed)
        self.mapa.heightChanged.connect(self._ajustar_alto)
        layout.addWidget(self.mapa)

        grid_c = QtWidgets.QGridLayout()
        grid_c.setHorizontalSpacing(Metric.SPACING)
        grid_c.setVerticalSpacing(6)
        self.edit_custom = {}
        for row, key in enumerate(("custom1", "custom2")):
            grid_c.addWidget(QtWidgets.QLabel(bi_layout.SHORT[key]), row, 0)
            edit = QtWidgets.QLineEdit()
            edit.setPlaceholderText("Text for the %s field" % bi_layout.SHORT[key])
            set_custom_tooltip(edit, _tip(key))
            edit.textEdited.connect(lambda text, k=key: self._on_custom(k, text))
            grid_c.addWidget(edit, row, 1)
            self.edit_custom[key] = edit
        grid_c.setColumnMinimumWidth(0, 86)
        grid_c.setColumnStretch(1, 1)
        layout.addLayout(grid_c)

        # LOOK
        layout.addLayout(self._seccion("Look"))
        layout.addLayout(self._grilla_look())

        # Presets con nombre
        layout.addLayout(self._seccion("Saved presets"))
        fila = QtWidgets.QHBoxLayout()
        fila.setSpacing(6)
        self.combo_presets = QtWidgets.QComboBox()
        self.combo_presets.setStyleSheet(Style.COMBO)
        set_custom_tooltip(self.combo_presets, _tip("preset_combo"))
        fila.addWidget(self.combo_presets, 1)
        cargar = QtWidgets.QPushButton("Load")
        cargar.setStyleSheet(Style.BTN_SMALL)
        set_custom_tooltip(cargar, _tip("preset_load"))
        cargar.clicked.connect(self._cargar_preset)
        fila.addWidget(cargar)
        self.edit_preset = QtWidgets.QLineEdit()
        self.edit_preset.setPlaceholderText("preset name")
        set_custom_tooltip(self.edit_preset, _tip("preset_name"))
        fila.addWidget(self.edit_preset, 1)
        guardar = QtWidgets.QPushButton("Save")
        guardar.setStyleSheet(Style.BTN_SMALL)
        set_custom_tooltip(guardar, _tip("preset_save"))
        guardar.clicked.connect(self._guardar_preset)
        fila.addWidget(guardar)
        layout.addLayout(fila)

        # Project targets
        self.lbl_proyecto = QtWidgets.QLabel("")
        self.lbl_proyecto.setStyleSheet("color: %s;" % Color.TEXT_DIM)
        layout.addLayout(self._seccion("Project targets", self.lbl_proyecto))
        grid_t = QtWidgets.QGridLayout()
        grid_t.setHorizontalSpacing(Metric.SPACING)
        grid_t.addWidget(QtWidgets.QLabel("Plate res"), 0, 0)
        self.edit_res = QtWidgets.QLineEdit()
        set_custom_tooltip(self.edit_res, _tip("res_target"))
        grid_t.addWidget(self.edit_res, 0, 1)
        grid_t.addWidget(QtWidgets.QLabel("FPS"), 0, 2)
        self.edit_fps = QtWidgets.QLineEdit()
        set_custom_tooltip(self.edit_fps, _tip("fps_target"))
        grid_t.addWidget(self.edit_fps, 0, 3)
        grid_t.setColumnMinimumWidth(0, 86)
        grid_t.setColumnStretch(1, 1)
        grid_t.setColumnStretch(3, 1)
        layout.addLayout(grid_t)
        hint = QtWidgets.QLabel(
            "Use %s to compare against the sequence, or values like 3840x2160 / 24."
            % emphasis("timeline")
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: %s;" % Color.TEXT_DIM)
        layout.addWidget(hint)

        layout.addSpacing(4)
        layout.addLayout(self._barra_inferior())

    def _seccion(self, titulo, extra=None):
        """Encabezado de seccion: filete arriba, titulo en mayusculas y, a la
        derecha, un control opcional (Reset, nombre del proyecto)."""
        caja = QtWidgets.QVBoxLayout()
        caja.setSpacing(6)
        caja.setContentsMargins(0, 4, 0, 0)
        linea = QtWidgets.QFrame()
        linea.setFrameShape(QtWidgets.QFrame.HLine)
        caja.addWidget(linea)
        fila = QtWidgets.QHBoxLayout()
        lbl = QtWidgets.QLabel(titulo.upper())
        lbl.setStyleSheet("color: %s; letter-spacing: 1px; %s" % (Color.TEXT_HEADER, semibold_css()))
        fila.addWidget(lbl)
        fila.addStretch(1)
        if extra is not None:
            fila.addWidget(extra)
        caja.addLayout(fila)
        return caja

    def _grilla_look(self):
        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(Metric.SPACING)
        grid.setVerticalSpacing(6)
        grid.setColumnMinimumWidth(0, 86)
        grid.setColumnMinimumWidth(2, 56)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        row = 0

        def label(text):
            return QtWidgets.QLabel(text)

        self.seg_bg = Segmented([(m, m) for m in bi_layout.BG_MODES])
        set_custom_tooltip(self.seg_bg, _tip("background"))
        self.seg_bg.picked.connect(self._on_bg_mode)
        grid.addWidget(label("Background"), row, 0)
        grid.addWidget(self.seg_bg, row, 1, 1, 3)
        row += 1

        self.sliders = {}
        self.slider_vals = {}
        for key, name in (("bg_opacity", "Bg opacity"), ("text_opacity", "Text opacity")):
            self._fila_slider(grid, row, key, name)
            row += 1

        self.seg_size = Segmented([(s, s) for s, _f in bi_layout.SIZE_FRACTIONS])
        set_custom_tooltip(self.seg_size, _tip("size"))
        self.seg_size.picked.connect(self._on_size)
        grid.addWidget(label("Size"), row, 0)
        grid.addWidget(self.seg_size, row, 1)
        self.seg_labels = Segmented([("on", "On"), ("off", "Off")])
        set_custom_tooltip(self.seg_labels, _tip("labels"))
        self.seg_labels.picked.connect(self._on_labels)
        grid.addWidget(label("Labels"), row, 2)
        grid.addWidget(self.seg_labels, row, 3)
        row += 1

        self.seg_weight = Segmented([(w, w) for w in _WEIGHTS])
        set_custom_tooltip(self.seg_weight, _tip("weight"))
        self.seg_weight.picked.connect(self._on_weight)
        grid.addWidget(label("Weight"), row, 0)
        grid.addWidget(self.seg_weight, row, 1, 1, 3)
        row += 1

        self.seg_stack = Segmented([("row", "Row"), ("column", "Column")])
        set_custom_tooltip(self.seg_stack, _tip("stack"))
        self.seg_stack.picked.connect(self._on_stack)
        grid.addWidget(label("Stack"), row, 0)
        grid.addWidget(self.seg_stack, row, 1)
        self.seg_sides = Segmented([("upright", "Upright"), ("rotated", "Rotated")])
        set_custom_tooltip(self.seg_sides, _tip("sides"))
        self.seg_sides.picked.connect(self._on_sides)
        grid.addWidget(label("Sides"), row, 2)
        grid.addWidget(self.seg_sides, row, 3)
        row += 1

        self.btn_text_color = self._swatch(_tip("text_color"), self._elegir_text_color)
        self.btn_bg_color = self._swatch(_tip("bg_color"), self._elegir_bg_color)
        grid.addWidget(label("Text color"), row, 0)
        grid.addWidget(self.btn_text_color, row, 1, Qt.AlignLeft)
        grid.addWidget(label("Bg color"), row, 2)
        grid.addWidget(self.btn_bg_color, row, 3, Qt.AlignLeft)
        row += 1

        for key, name in (("radius", "Radius"), ("padding", "Padding")):
            self._fila_slider(grid, row, key, name)
            row += 1
        return grid

    def _fila_slider(self, grid, row, key, name):
        _knob, lo, hi, _default, _scale, _suf = _SLIDERS[key]
        rot = _ClickLabel(name)
        set_custom_tooltip(rot, _tip(key))
        rot.clicked.connect(lambda k=key: self._reset_slider(k))
        sl = TickSlider(lo, hi)
        sl.valueChanged.connect(lambda v, k=key: self._on_slider(k, v))
        val = QtWidgets.QLabel("")
        val.setMinimumWidth(40)
        val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        cont = QtWidgets.QHBoxLayout()
        cont.setSpacing(8)
        cont.addWidget(sl, 1)
        cont.addWidget(val)
        grid.addWidget(rot, row, 0)
        grid.addLayout(cont, row, 1, 1, 3)
        self.sliders[key] = sl
        self.slider_vals[key] = val

    def _barra_inferior(self):
        fila = QtWidgets.QHBoxLayout()
        self.chk_on_top = QtWidgets.QCheckBox("Keep on top")
        self.chk_on_top.setProperty("lgaLabeled", True)
        set_custom_tooltip(self.chk_on_top, _tip("keep_on_top"))
        self.chk_on_top.setChecked(True)
        self.chk_on_top.toggled.connect(self._on_keep_top)
        fila.addWidget(self.chk_on_top)
        fila.addStretch(1)
        defaults = QtWidgets.QPushButton("Save as Defaults")
        defaults.setStyleSheet(Style.BTN_SECONDARY)
        defaults.setFixedHeight(Metric.BUTTON_HEIGHT)
        set_custom_tooltip(defaults, _tip("save_defaults"))
        defaults.clicked.connect(self._guardar_defaults)
        fila.addWidget(defaults)
        cerrar = QtWidgets.QPushButton("Close")
        cerrar.setStyleSheet(Style.BTN_SECONDARY)
        cerrar.setFixedHeight(Metric.BUTTON_HEIGHT)
        cerrar.clicked.connect(self.reject)
        fila.addWidget(cerrar)
        guardar = QtWidgets.QPushButton("Save to Project")
        guardar.setStyleSheet(Style.BTN_PRIMARY)
        guardar.setFixedHeight(Metric.BUTTON_HEIGHT)
        guardar.setDefault(True)
        set_custom_tooltip(guardar, _tip("save_project"))
        guardar.clicked.connect(self._guardar_proyecto)
        fila.addWidget(guardar)
        return fila

    def _swatch(self, tooltip, slot):
        # El color del swatch es DATA (el valor elegido): background inline.
        boton = QtWidgets.QPushButton()
        boton.setFixedSize(Metric.BUTTON_HEIGHT * 2, Metric.BUTTON_HEIGHT - 8)
        set_custom_tooltip(boton, tooltip)
        boton.clicked.connect(slot)
        return boton

    def _pintar_swatch(self, boton, rgb):
        color = QtGui.QColor.fromRgbF(*[_clamp(c, 0.0, 1.0) for c in rgb])
        boton.setStyleSheet(
            "background-color: %s; border: 1px solid %s; border-radius: %dpx;"
            % (color.name(), Color.BORDER_STRONG, Metric.RADIUS_SMALL)
        )

    # -- estado --------------------------------------------------------------
    @staticmethod
    def _num(value, default):
        """Coercion tolerante a float (un preset viejo puede traer basura)."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    def _arr(self):
        return bi_layout.active(self.state)

    def _cargar_estado(self):
        # try/finally: si algo tira, _loading NO puede quedar en True o todos
        # los setters quedan mudos sin aviso.
        self._loading = True
        try:
            self.lbl_efecto.setText(emphasis(self.ctl.label))
            self.state = bi_layout.parse(self.ctl.get_layout())
            for key in ("custom1", "custom2"):
                self.edit_custom[key].setText(self.ctl.get_text("bi_%s_text" % key))
            for key, (knob, _lo, _hi, default, scale, _suf) in _SLIDERS.items():
                v = self._num(self.ctl.get(knob, default * scale), default * scale) / scale
                self.sliders[key].setValue(v)
                self._pintar_valor(key)
            self.seg_bg.setCurrent(bi_layout.BG_MODES[_clamp(self.ctl.get_index("bi_bg_mode", 0), 0, 2)])
            self.seg_size.setCurrent(bi_layout.SIZE_FRACTIONS[_clamp(self.ctl.get_index("bi_size", 1), 0, 2)][0])
            self.seg_labels.setCurrent("on" if self.ctl.get("bi_labels", True) else "off")
            self.seg_weight.setCurrent(self.ctl.get_weight())
            self._pintar_swatch(self.btn_text_color, self.ctl.get_color("bi_color"))
            self._pintar_swatch(self.btn_bg_color, self.ctl.get_color("bi_bg_color"))
            self._recargar_presets()
            self.lbl_proyecto.setText("Project: %s" % emphasis(self.ctl.project_name or "-"))
            res_t, fps_t = self.ctl.load_targets()
            self.edit_res.setText(res_t)
            self.edit_fps.setText(fps_t)
            self._sync_mapa()
        finally:
            self._loading = False

    def _bad_fields(self):
        return [f for f in ("res", "fps", "tc") if self.ctl.field_ok(f) < 0.5]

    def _sync_mapa(self):
        """Refleja el estado del mapa en los controles que dependen de el."""
        arr = self._arr()
        self.seg_preset.setCurrent(self.state["preset"])
        self.mapa.set_arrangement(arr, self._bad_fields())
        stack = bi_layout.stack_state(arr)
        self.seg_stack.setCurrent(stack if stack in ("row", "column") else None)
        self.seg_sides.setCurrent(arr["sides"])
        self.btn_reset.setEnabled(not bi_layout.is_default(self.state))

    def _escribir_layout(self):
        """Guarda el mapa en el efecto (y re-aplica on/bg/giro por campo)."""
        if self._loading:
            return
        self.ctl.set_layout(bi_layout.dump(self.state))
        self._sync_mapa()

    def _pintar_valor(self, key):
        suf = _SLIDERS[key][5]
        self.slider_vals[key].setText("%d%s" % (int(round(self.sliders[key].value())), suf))

    # -- eventos -------------------------------------------------------------
    def _on_preset(self, key):
        self.state["preset"] = key
        self._escribir_layout()

    def _reset_preset(self):
        self.state["arr"][self.state["preset"]] = bi_layout.fresh_arrangement(self.state["preset"])
        self._escribir_layout()

    def _on_map_changed(self):
        self._escribir_layout()

    def _on_custom(self, key, text):
        if self._loading:
            return
        self.ctl.set("bi_%s_text" % key, text)
        arr = self._arr()
        if text and bi_layout.slot_of(arr, key) == "hidden":
            # Escribir el texto de un Custom oculto lo muestra (abajo al centro).
            bi_layout.move_to(arr, key, "bc")
            self._escribir_layout()
        else:
            self.ctl.nudge()

    def _on_bg_mode(self, mode):
        if self._loading:
            return
        self.ctl.set("bi_bg_mode", bi_layout.BG_MODES.index(mode))
        self.ctl.apply_layout()
        self.seg_bg.setCurrent(mode)

    def _on_size(self, size):
        if self._loading:
            return
        idx = [s for s, _f in bi_layout.SIZE_FRACTIONS].index(size)
        self.ctl.set("bi_size", idx)
        self.ctl.apply_layout()
        self.seg_size.setCurrent(size)

    def _on_labels(self, value):
        if self._loading:
            return
        self.ctl.set("bi_labels", value == "on")
        self.ctl.nudge()
        self.seg_labels.setCurrent(value)

    def _on_weight(self, style):
        if self._loading:
            return
        self.ctl.set_weight(style)
        self.seg_weight.setCurrent(style)

    def _on_stack(self, mode):
        bi_layout.set_stack(self._arr(), mode)
        self._escribir_layout()

    def _on_sides(self, sides):
        self._arr()["sides"] = sides
        self._escribir_layout()

    def _on_slider(self, key, value):
        self._pintar_valor(key)
        if self._loading:
            return
        # Arrastrar un slider emite un valor por movimiento del mouse; cada
        # write re-renderiza. Se escribe a lo sumo cada _SLIDER_MS y el
        # ultimo valor siempre llega (lo escribe el timer al vencer).
        self._slider_pend[key] = value
        if not self._slider_timer.isActive():
            self._flush_sliders()
            self._slider_timer.start()

    def _flush_sliders(self):
        pend, self._slider_pend = self._slider_pend, {}
        for key, value in pend.items():
            knob, _lo, _hi, _default, scale, _suf = _SLIDERS[key]
            self.ctl.set(knob, float(value) * scale)
            if key == "padding":
                # El padding cambia la geometria (python) y el pivote de los
                # costados girados. Opacidades y radio van al render por
                # expresiones directas: no hace falta ensuciar nada.
                self.ctl.apply_layout()

    def _reset_slider(self, key):
        default = _SLIDERS[key][3]
        self.sliders[key].setValue(default, emit=True)

    def _on_keep_top(self, checked):
        self._keep_on_top = bool(checked)
        self._apply_on_top()

    def _apply_on_top(self):
        flags = self.windowFlags()
        if self._keep_on_top:
            flags |= Qt.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowStaysOnTopHint
        # setWindowFlags recrea el handle y el show() posterior RESTAURA el
        # estado maximizado si la ventana lo tuvo alguna vez (medido): guardar
        # la geometria normal y re-mostrar SIEMPRE sin maximizar.
        geo = self.normalGeometry() if self.isMaximized() else self.geometry()
        self.setWindowFlags(flags)
        if self.isVisible():
            self.setWindowState(Qt.WindowNoState)
            self.setGeometry(geo)
            self.show()

    def _ajustar_alto(self):
        """El mapa cambia de alto con el ancho de la ventana: sin esto, al
        achicarse quedaba un hueco debajo de Hidden (medido en NKS). Se
        difiere al proximo ciclo para no redimensionar dentro de un
        resizeEvent."""
        QtCore.QTimer.singleShot(0, self._ajustar_alto_ahora)

    def _ajustar_alto_ahora(self):
        try:
            layout = self.layout()
            if layout is not None:
                layout.activate()
            self.resize(self.width(), self.sizeHint().height())
        except RuntimeError:
            pass  # ventana ya destruida

    def _refrescar(self):
        self.ctl.attach()
        self._cargar_estado()

    def _elegir_text_color(self):
        self._elegir_color("bi_color", self.btn_text_color)

    def _elegir_bg_color(self):
        self._elegir_color("bi_bg_color", self.btn_bg_color)

    def _elegir_color(self, knob, boton):
        actual = QtGui.QColor.fromRgbF(*self.ctl.get_color(knob))
        elegido = QtWidgets.QColorDialog.getColor(actual, self, "Pick color")
        if not elegido.isValid():
            return
        rgb = (elegido.redF(), elegido.greenF(), elegido.blueF())
        self.ctl.set_color(knob, rgb)
        self._pintar_swatch(boton, rgb)
        self.ctl.nudge()

    # -- presets con nombre --------------------------------------------------
    def _recargar_presets(self):
        actual = self.combo_presets.currentText()
        self.combo_presets.clear()
        self.combo_presets.addItems(self.ctl.list_presets())
        if actual:
            idx = self.combo_presets.findText(actual)
            if idx >= 0:
                self.combo_presets.setCurrentIndex(idx)

    def _estado_actual(self):
        estilo = {
            "weight": self.ctl.get_weight(),
            "text_color": list(self.ctl.get_color("bi_color")),
            "bg_color": list(self.ctl.get_color("bi_bg_color")),
            "bg_mode": self.ctl.get_index("bi_bg_mode", 0),
            "size": self.ctl.get_index("bi_size", 1),
            "labels": bool(self.ctl.get("bi_labels", True)),
        }
        for key, (knob, _lo, _hi, default, scale, _suf) in _SLIDERS.items():
            estilo[key] = self._num(self.ctl.get(knob, default * scale), default * scale)
        return {
            "v": 3,
            "layout": json.loads(bi_layout.dump(self.state)),
            "style": estilo,
            "custom": {k: self.ctl.get_text("bi_%s_text" % k) for k in ("custom1", "custom2")},
        }

    def _guardar_preset(self):
        nombre = self.edit_preset.text().strip()
        error = self.ctl.save_preset(nombre, self._estado_actual())
        if error:
            self._avisar(error, "")
            return
        self._recargar_presets()
        idx = self.combo_presets.findText(nombre)
        if idx >= 0:
            self.combo_presets.setCurrentIndex(idx)
        self.edit_preset.clear()

    def _cargar_preset(self):
        nombre = self.combo_presets.currentText()
        if not nombre:
            self._avisar("No preset selected", "")
            return
        preset = self.ctl.load_preset(nombre)
        if not preset:
            self._avisar("Preset '%s' not found" % nombre, "")
            return
        estilo = preset.get("style") or {}
        # Presets de la version con tabla (v2) traen "fields" con x/y por
        # campo: esa parte no tiene equivalente en el mapa y se ignora; el
        # estilo si se aplica.
        try:
            if "weight" in estilo and str(estilo["weight"]) in _WEIGHTS:
                self.ctl.set_weight(str(estilo["weight"]))
            for key, knob in (("bg_mode", "bi_bg_mode"), ("size", "bi_size")):
                if key in estilo:
                    self.ctl.set(knob, int(_clamp(self._num(estilo[key], 0), 0, 2)))
            if "labels" in estilo:
                self.ctl.set("bi_labels", bool(estilo["labels"]))
            for key, (knob, lo, hi, default, scale, _suf) in _SLIDERS.items():
                # v2 guardaba con otros nombres: text_opacity / bg_opacity /
                # bg_radius / text_pad.
                old = {"radius": "bg_radius", "padding": "text_pad"}.get(key, key)
                raw = estilo.get(key, estilo.get(old))
                if raw is not None:
                    v = _clamp(self._num(raw, default * scale), lo * scale, hi * scale)
                    self.ctl.set(knob, v)
            for key, knob in (("text_color", "bi_color"), ("bg_color", "bi_bg_color")):
                if key in estilo:
                    self.ctl.set_color(knob, tuple(estilo[key])[:3])
            for k, text in (preset.get("custom") or {}).items():
                if k in ("custom1", "custom2"):
                    self.ctl.set("bi_%s_text" % k, str(text))
            if isinstance(preset.get("layout"), dict):
                self.ctl.set_layout(json.dumps(preset["layout"]))
            else:
                self.ctl.apply_layout()
        except Exception as exc:
            self._avisar("Preset '%s' could not be applied: %s" % (nombre, exc), "")
        self._cargar_estado()

    # -- targets -------------------------------------------------------------
    def _guardar_proyecto(self):
        error = self.ctl.save_targets_project(
            self.edit_res.text().strip(), self.edit_fps.text().strip()
        )
        if not error:
            self.ctl.nudge()
            self._sync_mapa()
        self._avisar(
            error,
            "Targets saved to the project (travels in the .hrox). Remember to save the project.",
        )

    def _guardar_defaults(self):
        error = self.ctl.save_targets_defaults(
            self.edit_res.text().strip(), self.edit_fps.text().strip()
        )
        if not error:
            self.ctl.nudge()
            self._sync_mapa()
        self._avisar(error, "Targets saved as user defaults.")

    def _avisar(self, error, ok_texto):
        from LGA_NKS_Shared.LGA_NKS_MessageBox import show_error, show_info

        if error:
            show_error(self, "Burn-ins", error)
        else:
            show_info(self, "Burn-ins", ok_texto)


_panel = None


def show_panel():
    """Punto de entrada: lo llama el boton Open Burn-in Panel del gizmo."""
    global _panel
    # Un solo panel vivo: el anterior se cierra en vez de quedar huerfano
    # (sin referencia Python, PySide puede destruirlo a mitad de un evento).
    if _panel is not None:
        try:
            _panel.close()
            _panel.deleteLater()
        except Exception:
            pass
        _panel = None
    ctl = HieroController()
    ctl.attach()
    _panel = BurnInPanel(ctl)
    apply_ui_font(_panel)
    # Nunca abrir maximizada: es una ventana de edicion, no un workspace.
    _panel.setWindowState(Qt.WindowNoState)
    _panel.show()
    _panel.raise_()
    return _panel
