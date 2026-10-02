"""
____________________________________________________________________

  LGA_NKS_ArrowComboBox v1.00 | Lega

  QComboBox de HieroTools con la flecha del pack a la vista.

  Style.COMBO oculta la flecha nativa de Qt (cambia con el tema del host y no
  se parece en Nuke, Hiero y las apps Qt), asi que un combo que solo lleva esa
  hoja no muestra flecha: parece un campo de texto y nadie descubre que
  despliega opciones. Este combo usa la misma hoja y dibuja encima la linea
  separadora y la flecha SVG del pack (LGA_NKS_Shared/icons/dropdown_arrow_white.svg),
  igual que ColoredStatusComboBox de Create Shot.

  Sirve editable o no. Editable, el texto se escribe en el campo y la flecha
  (el drop-down de Style.COMBO, 22 px a la derecha) abre la lista.

      combo = ArrowComboBox(parent)
      combo.addItems(["WIP", "FINAL"])

  v1.00: Version inicial (selectores del slate de entrega en Flow Push).
____________________________________________________________________
"""

from pathlib import Path

from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui, QtCore
from LGA_NKS_Shared.LGA_UI_Style_HieroTools import Color, Style

ICONS_DIR = Path(__file__).parent / "icons"

# Ancho de la zona de la flecha: el `QComboBox::drop-down` de Style.COMBO.
ARROW_ZONE = 22
ARROW_SIZE = 10


class ArrowComboBox(QtWidgets.QComboBox):
    """QComboBox con la hoja del pack y la flecha del pack dibujada encima."""

    _arrow = None

    def __init__(self, parent=None):
        super(ArrowComboBox, self).__init__(parent)
        if ArrowComboBox._arrow is None:
            ArrowComboBox._arrow = QtGui.QPixmap(str(ICONS_DIR / "dropdown_arrow_white.svg"))
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
        rect = self.rect()
        line_x = rect.right() - ARROW_ZONE
        separator = QtGui.QColor(Color.TEXT if self.isEnabled() else Color.TEXT_DIM)
        separator.setAlpha(90)
        painter.setPen(separator)
        painter.drawLine(line_x, rect.top() + 5, line_x, rect.bottom() - 5)
        arrow = ArrowComboBox._arrow
        if arrow is not None and not arrow.isNull():
            if not self.isEnabled():
                painter.setOpacity(0.4)
            x = rect.right() - (ARROW_ZONE + ARROW_SIZE) // 2 + 1
            y = rect.center().y() - ARROW_SIZE // 2 + 1
            painter.drawPixmap(QtCore.QRect(x, y, ARROW_SIZE, ARROW_SIZE), arrow)
        painter.end()
