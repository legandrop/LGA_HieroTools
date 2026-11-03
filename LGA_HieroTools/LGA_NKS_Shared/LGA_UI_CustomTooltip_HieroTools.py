"""
____________________________________________________________________

  LGA_UI_CustomTooltip_HieroTools v1.00 | Lega

  Tooltip propio de los packs LGA: el mismo globo que usan las apps de
  escritorio LGA (PipeSync, FileManagerS3, Mighty Tools, ...). Fondo
  oscuro, borde de 1 px, flechita que apunta al control, sombra suave,
  aparece a los 600 ms y se oculta apenas el mouse sale del control.

  Es un port a Python de CustomTooltip.cpp de LGA_Base_QT_C_Py: mismas
  medidas, mismos colores y la misma medicion con QTextDocument. La
  fuente de verdad del diseno y de las reglas de redaccion es
  LGA_Base_QT_C_Py/docs/Doc_CustomTooltip.md.

  Por que existe: el tooltip nativo de Qt dentro de NKS sale con el tema
  del host (o con el QToolTip de la hoja que tenga la ventana, si tiene
  uno), sin flecha, pegado al cursor y distinto en cada ventana. Ningun
  tooltip de una ventana nueva de los packs usa el nativo.

  Uso:

      from LGA_NKS_Shared.LGA_UI_CustomTooltip_HieroTools import (
          set_custom_tooltip, tooltip_label,
      )
      set_custom_tooltip(boton, "Texto en castellano.<br>Segunda oracion.")
      set_custom_tooltip(boton, tooltip_label("Click:") + " Una cosa<sbr/>"
                                + tooltip_label("Shift+Click:") + " Otra")
      set_custom_tooltip(boton, "")   # lo saca

  Diferencias con el C++, a proposito:
  - No instala un event filter en toda la QApplication. En C++ es gratis;
    en Python haria pasar por el interprete CADA evento de NKS. El
    ocultado robusto queda a cargo del watchdog de 120 ms, que corre solo
    mientras hay un tooltip visible.
  - No lee master switches de settings (TooltipsEnabled / delay): los
    packs no tienen esa pantalla. El delay va siempre.
  - Los limites para no salirse son los de la PANTALLA del control, no los
    de la ventana activa: las ventanas de los packs son chicas y flotan
    sobre NKS sin estar activas.
  - No consume Enter/Leave: el :hover de las hojas del pack sigue andando
    en el control que tiene el tooltip.

  v1.00: Primera version.
____________________________________________________________________
"""

import re

from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import (
    QtCore,
    QtGui,
    QtWidgets,
    Qt,
    is_widget_alive,
)
from LGA_NKS_Shared.LGA_UI_Style_HieroTools import apply_ui_font

# ---------------------------------------------------------------------------
# Medidas y colores. Son los de CustomTooltip.cpp y dark_theme.qss del Base:
# van a mano y no salen del tema del pack porque tienen que dar EXACTAMENTE
# el mismo globo que las apps de escritorio.
# ---------------------------------------------------------------------------
SHOW_DELAY_MS = 600
HIDE_WATCHDOG_MS = 120
SMALL_BREAK_PX = 4
SECTION_BREAK_PX = 10
TRIANGLE_WIDTH = 16
TRIANGLE_HEIGHT = 11
TRIANGLE_OVERLAP = 0.2
BORDER_RADIUS = 6
SHADOW_PADDING = 6
MAX_WIDTH = 1800
# El pico de la flecha queda a ~1 px del control: 7 de solape + 6 de sombra.
ANCHOR_OVERLAP = 7
SCREEN_MARGIN = 10

TOOLTIP_BG = "#242424"
TOOLTIP_BORDER = "#3a3a3a"
TOOLTIP_TEXT = "#B2B2B2"
# Rotulos de accion (Click:, Shift+Click:, Activado:): obligatorio este gris,
# en negrita. Ni blanco ni otro gris.
TOOLTIP_LABEL = "#E8E8E8"

_SMALL_BREAK_RE = re.compile(r"<sbr\s*/?>")
_SECTION_BREAK_RE = re.compile(r"<sBR\s*/?>")


def tooltip_label(text):
    """Rotulo de accion en el formato obligatorio: gris #E8E8E8 en negrita.

    Solo cuando el control tiene DOS o mas interacciones distintas (Click /
    Shift+Click / Doble click). Con una sola accion obvia no va rotulo.
    """
    return "<span style='color:%s'><b>%s</b></span>" % (TOOLTIP_LABEL, text)


def _display_html(text):
    """Convierte los tags propios <sbr/> y <sBR/> en parrafos con margen.

    Qt rich text no trata <div> como bloque, pero si respeta <p> con
    margin-top: por eso los cortes se vuelven limites de parrafo.
    """
    html = _SECTION_BREAK_RE.sub(
        '</p><p style="margin-top:%dpx; margin-bottom:0px;">' % SECTION_BREAK_PX, text
    )
    html = _SMALL_BREAK_RE.sub(
        '</p><p style="margin-top:%dpx; margin-bottom:0px;">' % SMALL_BREAK_PX, html
    )
    return '<p style="margin:0px;">' + html + "</p>"


class _TooltipWidget(QtWidgets.QLabel):
    """El globo: un QLabel translucido que se pinta su propia caja y flecha."""

    UP = 0  # flecha arriba: el globo va DEBAJO del control (default)
    DOWN = 1  # flecha abajo: el globo va ARRIBA (cuando abajo no entra)

    def __init__(self):
        super().__init__(
            None,
            Qt.ToolTip
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.NoDropShadowWindowHint,
        )
        self.setObjectName("lgaCustomTooltip")
        self.setTextFormat(Qt.RichText)
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setWordWrap(True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setStyleSheet(
            "QLabel#lgaCustomTooltip { color: %s; background: transparent; }"
            % TOOLTIP_TEXT
        )
        apply_ui_font(self)
        self._direction = self.UP
        self._triangle_offset = 0
        self._apply_margins()

    def _apply_margins(self):
        # El alto total no cambia al voltear: solo se mueve el hueco de la
        # flecha de arriba a abajo. Margen derecho menor que el izquierdo:
        # el texto va a la izquierda y la sobra de medicion cae a la derecha.
        top = 10 + (TRIANGLE_HEIGHT if self._direction == self.UP else 0)
        bottom = 10 + (TRIANGLE_HEIGHT if self._direction == self.DOWN else 0)
        self.setContentsMargins(10 + SHADOW_PADDING, top, 6 + SHADOW_PADDING, bottom)

    def set_direction(self, direction):
        if direction != self._direction:
            self._direction = direction
            self._apply_margins()
            self.update()

    def set_triangle_offset(self, offset):
        if offset != self._triangle_offset:
            self._triangle_offset = offset
            self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)

        w, h = self.width(), self.height()
        tri_x = (w // 2) + self._triangle_offset - TRIANGLE_WIDTH // 2
        min_x = SHADOW_PADDING + BORDER_RADIUS
        max_x = w - SHADOW_PADDING - BORDER_RADIUS - TRIANGLE_WIDTH
        tri_x = max(min_x, min(tri_x, max_x))

        up = self._direction == self.UP
        rect_top = SHADOW_PADDING + (TRIANGLE_HEIGHT if up else 0)
        rect_bottom = h - SHADOW_PADDING - (0 if up else TRIANGLE_HEIGHT)
        main = QtCore.QRectF(
            SHADOW_PADDING, rect_top, w - 2 * SHADOW_PADDING, rect_bottom - rect_top
        )

        peak_y = float(SHADOW_PADDING) if up else float(h - SHADOW_PADDING)
        base_fill_y = (
            rect_top + TRIANGLE_OVERLAP if up else rect_bottom - TRIANGLE_OVERLAP
        )
        left_x = float(tri_x)
        right_x = float(tri_x + TRIANGLE_WIDTH)
        mid_x = left_x + TRIANGLE_WIDTH / 2.0

        rect_path = QtGui.QPainterPath()
        rect_path.addRoundedRect(main, BORDER_RADIUS, BORDER_RADIUS)
        tri_fill = QtGui.QPainterPath()
        tri_fill.moveTo(left_x, base_fill_y)
        tri_fill.lineTo(mid_x, peak_y)
        tri_fill.lineTo(right_x, base_fill_y)
        tri_fill.closeSubpath()
        fill_path = rect_path.united(tri_fill)

        # Borde exterior continuo trazado a mano: sube al pico y baja sin
        # trazar la base de la flecha (si no, queda una raya en la union).
        r = float(BORDER_RADIUS)
        L, R, T, B = main.left(), main.right(), main.top(), main.bottom()
        border = QtGui.QPainterPath()
        border.moveTo(L + r, T)
        if up:
            border.lineTo(left_x, T)
            border.lineTo(mid_x, peak_y)
            border.lineTo(right_x, T)
        border.lineTo(R - r, T)
        border.arcTo(R - 2 * r, T, 2 * r, 2 * r, 90, -90)
        border.lineTo(R, B - r)
        border.arcTo(R - 2 * r, B - 2 * r, 2 * r, 2 * r, 0, -90)
        if not up:
            border.lineTo(right_x, B)
            border.lineTo(mid_x, peak_y)
            border.lineTo(left_x, B)
        border.lineTo(L + r, B)
        border.arcTo(L, B - 2 * r, 2 * r, 2 * r, 270, -90)
        border.lineTo(L, T + r)
        border.arcTo(L, T, 2 * r, 2 * r, 180, -90)

        # 1) Sombra: cuatro trazos concentricos detras del relleno.
        painter.save()
        painter.setBrush(Qt.NoBrush)
        for i in range(4):
            pen = QtGui.QPen(QtGui.QColor(0, 0, 0, 11 - i * 2), (i + 1) * 2.2)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawPath(border)
        painter.restore()

        # 2) Relleno de caja + flecha, sin borde.
        painter.setPen(Qt.NoPen)
        painter.setBrush(QtGui.QColor(TOOLTIP_BG))
        painter.drawPath(fill_path)

        # 3) Borde.
        pen = QtGui.QPen(QtGui.QColor(TOOLTIP_BORDER), 1)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(border)
        painter.end()

        # 4) El texto lo dibuja el QLabel dentro de los margenes.
        super().paintEvent(event)


class CustomTooltip(QtCore.QObject):
    """Registro de tooltips por widget. Una sola instancia: instance()."""

    _instance = None

    @classmethod
    def instance(cls):
        if cls._instance is None or not is_widget_alive(cls._instance._tip):
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        super().__init__()
        self._tip = _TooltipWidget()
        self._tip.hide()
        self._texts = {}  # id(widget) -> (widget, texto)
        self._pending = None
        self._anchor = None
        self._show_timer = QtCore.QTimer(self)
        self._show_timer.setSingleShot(True)
        self._show_timer.timeout.connect(self._show_pending)
        self._watchdog = QtCore.QTimer(self)
        self._watchdog.setInterval(HIDE_WATCHDOG_MS)
        self._watchdog.timeout.connect(self._watchdog_tick)

    # --- registro ----------------------------------------------------------
    def set_tooltip(self, widget, text):
        if widget is None:
            return
        # Nada de tooltip nativo en paralelo.
        widget.setToolTip("")
        key = id(widget)
        if text:
            if key not in self._texts:
                widget.installEventFilter(self)
                widget.destroyed.connect(lambda _obj=None, k=key: self._forget(k))
            self._texts[key] = (widget, text)
        else:
            if key in self._texts:
                widget.removeEventFilter(self)
                self._forget(key)

    def refresh_if_visible(self, widget, text):
        """Cambia el texto y, si el globo de ese widget esta a la vista, lo repinta."""
        self.set_tooltip(widget, text)
        if text and self._anchor is widget and self._tip.isVisible():
            self._show(widget, text)

    def _forget(self, key):
        entry = self._texts.pop(key, None)
        if entry is None:
            return
        widget = entry[0]
        if self._pending is widget:
            self._cancel_pending()
        if self._anchor is widget:
            self.hide_tooltip()

    # --- eventos de los widgets registrados ----------------------------------
    def eventFilter(self, watched, event):
        entry = self._texts.get(id(watched))
        if entry is None or entry[0] is not watched:
            return False
        etype = event.type()
        if etype == QtCore.QEvent.Enter:
            # Un Enter repetido (hijos que entran y salen) NO reinicia el
            # timer: si no, el tooltip nunca llega a aparecer.
            if not (self._pending is watched and self._show_timer.isActive()):
                self._pending = watched
                self._show_timer.start(SHOW_DELAY_MS)
        elif etype == QtCore.QEvent.Leave:
            # Qt manda Leave al padre cuando el cursor entra a un hijo: solo
            # se cancela si el cursor salio de verdad de la geometria.
            if not self._cursor_over(watched):
                if self._pending is watched:
                    self._cancel_pending()
                if self._anchor is watched:
                    self.hide_tooltip()
        elif etype in (QtCore.QEvent.Hide, QtCore.QEvent.Close,
                       QtCore.QEvent.MouseButtonPress):
            # Al hacer click el globo se va: el control ya hizo lo suyo.
            if self._pending is watched:
                self._cancel_pending()
            if self._anchor is watched:
                self.hide_tooltip()
        elif etype == QtCore.QEvent.ToolTip:
            return True  # el nativo, nunca
        return False

    @staticmethod
    def _cursor_over(widget, tolerance=0):
        if not is_widget_alive(widget) or not widget.isVisible():
            return False
        local = widget.mapFromGlobal(QtGui.QCursor.pos())
        rect = widget.rect().adjusted(-tolerance, -tolerance, tolerance, tolerance)
        return rect.contains(local)

    def _cancel_pending(self):
        self._show_timer.stop()
        self._pending = None

    def _show_pending(self):
        widget, self._pending = self._pending, None
        if widget is None or not is_widget_alive(widget):
            return
        entry = self._texts.get(id(widget))
        if entry is None or not self._cursor_over(widget):
            return
        self._show(widget, entry[1])

    # --- mostrar y ocultar ---------------------------------------------------
    def _measure(self, html):
        """Ancho y alto del contenido, medidos como los va a dibujar el label."""
        doc = QtGui.QTextDocument()
        doc.setDocumentMargin(0)  # sin esto sobran 4 px por lado
        doc.setDefaultFont(self._tip.font())
        doc.setHtml(html)
        h_margins = (10 + SHADOW_PADDING) + (6 + SHADOW_PADDING)
        max_content = max(50, MAX_WIDTH - h_margins)
        doc.setTextWidth(max_content)
        width = min(int(doc.idealWidth() + 0.999), max_content)
        doc.setTextWidth(width)
        height = int(doc.size().height() + 0.999)
        return width, height, h_margins

    def _show(self, widget, text):
        html = _display_html(text)
        self._tip.setText(html)
        content_w, content_h, h_margins = self._measure(html)
        v_margins = 10 + TRIANGLE_HEIGHT + 10
        width = max(80, content_w + h_margins + 4)
        height = max(40, content_h + v_margins + 4)
        self._tip.setFixedSize(width, height)

        anchor_bottom = widget.mapToGlobal(QtCore.QPoint(widget.width() // 2, widget.height()))
        anchor_top_y = widget.mapToGlobal(QtCore.QPoint(0, 0)).y()
        screen = QtWidgets.QApplication.screenAt(anchor_bottom) or (
            QtWidgets.QApplication.primaryScreen()
        )
        bounds = screen.availableGeometry()

        x = anchor_bottom.x() - width // 2
        offset = 0
        if x < bounds.left() + SCREEN_MARGIN:
            offset = x - (bounds.left() + SCREEN_MARGIN)
            x = bounds.left() + SCREEN_MARGIN
        elif x + width > bounds.right() - SCREEN_MARGIN:
            offset = (x + width) - (bounds.right() - SCREEN_MARGIN)
            x = bounds.right() - SCREEN_MARGIN - width
        self._tip.set_triangle_offset(offset)

        below_y = anchor_bottom.y() - ANCHOR_OVERLAP
        above_y = anchor_top_y + ANCHOR_OVERLAP - height
        place_above = False
        if below_y + height > bounds.bottom():
            if above_y >= bounds.top():
                place_above = True
            else:
                place_above = (anchor_top_y - bounds.top()) > (
                    bounds.bottom() - anchor_bottom.y()
                )
        self._tip.set_direction(_TooltipWidget.DOWN if place_above else _TooltipWidget.UP)
        self._tip.move(x, above_y if place_above else below_y)
        self._tip.show()
        self._anchor = widget
        self._watchdog.start()

    def hide_tooltip(self):
        self._cancel_pending()
        self._watchdog.stop()
        self._anchor = None
        if is_widget_alive(self._tip) and self._tip.isVisible():
            self._tip.hide()

    def _watchdog_tick(self):
        # Respaldo del Leave, que Qt no entrega siempre al mover rapido.
        anchor = self._anchor
        if not self._tip.isVisible():
            self._watchdog.stop()
            return
        if anchor is None or not self._cursor_over(anchor, tolerance=2):
            self.hide_tooltip()

    # --- capturas sin mouse ---------------------------------------------------
    def debug_show(self, widget, text):
        """Muestra el globo de un widget ya, sin delay ni mouse (harness)."""
        self._show(widget, text)
        self._watchdog.stop()  # sin mouse real el watchdog lo ocultaria
        return self._tip


def set_custom_tooltip(widget, text):
    """Pone (o con "" saca) el tooltip propio de un widget."""
    CustomTooltip.instance().set_tooltip(widget, text)


def refresh_custom_tooltip(widget, text):
    """Como set_custom_tooltip, y si el globo esta a la vista lo actualiza."""
    CustomTooltip.instance().refresh_if_visible(widget, text)


def hide_custom_tooltip():
    CustomTooltip.instance().hide_tooltip()
