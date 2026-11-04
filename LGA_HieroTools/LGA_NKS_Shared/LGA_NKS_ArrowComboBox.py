"""
____________________________________________________________________

  LGA_NKS_ArrowComboBox v1.01 | Lega

  QComboBox de HieroTools con la flecha del pack a la vista.

  Style.COMBO oculta la flecha nativa de Qt (cambia con el tema del host y no
  se parece en Nuke, Hiero y las apps Qt), asi que un combo que solo lleva esa
  hoja no muestra flecha: parece un campo de texto y nadie descubre que
  despliega opciones. Este combo usa la misma hoja y dibuja encima un chevron
  de trazo fino (gris; claro con el mouse encima o la lista abierta; apagado
  si esta deshabilitado).

  Sirve editable o no. Editable, el texto se escribe en el campo y la flecha
  (el drop-down de Style.COMBO, 22 px a la derecha) abre la lista.

      combo = ArrowComboBox(parent)
      combo.addItems(["WIP", "FINAL"])

  v1.01: Chevron de trazo fino en vez del triangulo SVG con linea separadora.
  v1.00: Version inicial (selectores del slate de entrega en Flow Push).
____________________________________________________________________
"""

from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui, QtCore
from LGA_NKS_Shared.LGA_UI_Style_HieroTools import Color, Style

Qt = QtCore.Qt

# Ancho de la zona de la flecha: el `QComboBox::drop-down` de Style.COMBO.
ARROW_ZONE = 22
# Chevron: ancho total y grosor del trazo, en px.
CHEVRON_SIZE = 8
CHEVRON_STROKE = 1.5


class ArrowComboBox(QtWidgets.QComboBox):
    """QComboBox con la hoja del pack y un chevron dibujado encima."""

    def __init__(self, parent=None):
        super(ArrowComboBox, self).__init__(parent)
        # Lista con la hoja del pack (sin QListView el popup toma el estilo nativo).
        self.setView(QtWidgets.QListView())
        # El drop-down de Style.COMBO ya reserva la zona de la flecha: el texto (y el
        # campo editable) terminan antes. Sumarle padding achicaba el campo de mas.
        self.setStyleSheet(Style.COMBO)

    def paintEvent(self, event):
        super(ArrowComboBox, self).paintEvent(event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
        # Chevron de trazo fino, sin linea separadora: el triangulo relleno de
        # 10 px con su separador se leia pesado al lado del texto de 14 px.
        rect = QtCore.QRectF(self.rect())
        if not self.isEnabled():
            color = Color.BORDER_HOVER
        elif self.underMouse() or self.view().isVisible():
            color = Color.TEXT_STRONG
        else:
            color = Color.TEXT_HEADER
        pen = QtGui.QPen(QtGui.QColor(color), CHEVRON_STROKE)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        cx = rect.right() - ARROW_ZONE / 2.0
        cy = rect.center().y() + 0.5
        half_w, half_h = CHEVRON_SIZE / 2.0, CHEVRON_SIZE / 4.0
        painter.drawPolyline(QtGui.QPolygonF([
            QtCore.QPointF(cx - half_w, cy - half_h),
            QtCore.QPointF(cx, cy + half_h),
            QtCore.QPointF(cx + half_w, cy - half_h)]))
        painter.end()

    def enterEvent(self, event):
        super(ArrowComboBox, self).enterEvent(event)
        self.update()

    def leaveEvent(self, event):
        super(ArrowComboBox, self).leaveEvent(event)
        self.update()
