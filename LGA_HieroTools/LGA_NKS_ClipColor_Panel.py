"""
____________________________________________________________________

  LGA_colorPanel v1.10 | Lega

  Panel para etiquetar visualmente los clips seleccionados sin enviar cambios
  a Flow. Conserva los colores de trabajo locales y ofrece estados de review
  con el mismo color que Flow Review.

  v1.10: Migra al estilo comun, suma cuatro colores de Flow Review, evita
         reconstrucciones innecesarias al redimensionar y registra errores.
  v1.09: Actualizado para usar estilos dinámicos con bordes y hover
____________________________________________________________________
"""

import os
from datetime import datetime

import hiero.ui
import hiero.core
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui
from LGA_NKS_Shared.LGA_NKS_Flow_Status_Config import get_status_color
from LGA_NKS_Shared.LGA_NKS_StyleUtils import (
    create_data_button_stylesheet,
    ensure_max_luminance,
)
from LGA_NKS_Shared.LGA_UI_Style_HieroTools import (
    Color,
    Metric,
    Style,
    apply_ui_font,
    semibold_css,
)


DEBUG = False
LOG_PATH = os.path.join(
    os.path.dirname(__file__), "logs", "DebugPy_LGA_NKS_ClipColor_Panel.log"
)


def debug_log(messages):
    """Registra una corrida completa sin ensuciar la consola por defecto."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = ["[%s] %s" % (timestamp, message) for message in messages]
    try:
        directory = os.path.dirname(LOG_PATH)
        if not os.path.isdir(directory):
            os.makedirs(directory)
        with open(LOG_PATH, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    except OSError:
        pass
    if DEBUG:
        for line in lines:
            print(line)


LOCAL_COLOR_BUTTONS = (
    ("v_00", "#8a8a8a"),
    ("Plate", "#42616d"),
    ("EditRef", "#aa9e54"),
    ("Reference", "#80533d"),
    ("Error", "#c25252"),
    ("Violet", "#840bd4"),
    ("Magenta", "#d13bff"),
    ("Cyan", "#4da2ca"),
)

# `apr` es el estado final de entrega. La etiqueta corta "Approved" se
# conserva por continuidad con este panel, pero el color sale del catalogo
# compartido que tambien alimenta Flow Review.
FLOW_REVIEW_COLOR_BUTTONS = (
    ("Corrections", "corr"),
    ("Review Lega", "revleg"),
    ("Review Dir", "rev_di"),
    ("Approved", "apr"),
)


# Mismo criterio que Flow Review: el QColor queda intacto para el clip, pero
# un fondo demasiado claro se oscurece antes de dibujar texto claro encima.
MAX_STATUS_BG_LUMINANCE = 135


class ColorChangeWidget(QtWidgets.QWidget):
    def __init__(self):
        super(ColorChangeWidget, self).__init__()

        self.setObjectName("com.lega.colorChangePanel")
        self.setWindowTitle("ClipColor")

        self.setStyleSheet(Style.WINDOW)

        self.layout = QtWidgets.QGridLayout()
        self.layout.setContentsMargins(
            Metric.WINDOW_MARGIN,
            Metric.WINDOW_MARGIN,
            Metric.WINDOW_MARGIN,
            Metric.WINDOW_MARGIN,
        )
        self.layout.setSpacing(Metric.SPACING)
        self.setLayout(self.layout)

        self.buttons = self._build_buttons()
        self.num_columns = 1
        self.button_width_hint = 0
        self._create_buttons()
        apply_ui_font(self)
        # La fuente comun puede cambiar el ancho de un label. Re-medimos antes
        # de decidir cuantas columnas entran para no calcular con la del host.
        self._create_buttons()
        self.adjust_columns_on_resize()

    @staticmethod
    def _build_buttons():
        buttons = []
        for name, color_hex in LOCAL_COLOR_BUTTONS:
            buttons.append((name, QtGui.QColor(color_hex), color_hex))
        for name, status_code in FLOW_REVIEW_COLOR_BUTTONS:
            color_hex = get_status_color(status_code)
            buttons.append((name, QtGui.QColor(color_hex), color_hex))
        return buttons

    def resizeEvent(self, event):
        super(ColorChangeWidget, self).resizeEvent(event)
        self.adjust_columns_on_resize()

    def _create_buttons(self):
        while self.layout.count():
            item = self.layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        max_button_width = 0
        for index, (name, color, style) in enumerate(self.buttons):
            display_style = ensure_max_luminance(style, MAX_STATUS_BG_LUMINANCE)
            button = QtWidgets.QPushButton(name)
            button.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
            )
            button.setStyleSheet(
                create_data_button_stylesheet(
                    display_style,
                    Color.TEXT_STRONG,
                    Color.ACCENT,
                    Metric.BUTTON_HEIGHT,
                    Metric.RADIUS,
                    semibold_css(),
                )
            )
            button.clicked.connect(self.create_button_click_handler(color))
            max_button_width = max(max_button_width, button.sizeHint().width())
            row = index // self.num_columns
            column = index % self.num_columns
            self.layout.addWidget(button, row, column)

        self.button_width_hint = max_button_width

    def create_button_click_handler(self, color):
        def button_click_handler(_):
            self.change_clip_color(color)

        return button_click_handler

    def adjust_columns_on_resize(self, event=None):
        margins = self.layout.contentsMargins()
        available_width = max(1, self.width() - margins.left() - margins.right())
        button_width = max(1, self.button_width_hint)
        columns = max(
            1,
            (available_width + self.layout.horizontalSpacing())
            // (button_width + self.layout.horizontalSpacing()),
        )

        if columns != self.num_columns:
            self.num_columns = columns
            self._create_buttons()

    def change_clip_color(self, color):
        log_messages = ["Color solicitado: %s." % color.name()]
        try:
            sequence = hiero.ui.activeSequence()
            if not sequence:
                log_messages.append("No hay secuencia activa; no se cambio ningun color.")
                return

            timeline = hiero.ui.getTimelineEditor(sequence)
            selected_items = timeline.selection()
            project = sequence.project()
            if not project:
                log_messages.append("La secuencia activa no tiene proyecto; no se cambio ningun color.")
                return
            if not selected_items:
                log_messages.append("No hay clips seleccionados; no se cambio ningun color.")
                return

            changed = 0
            skipped = 0
            project.beginUndo("Change Clip Color")
            try:
                for item in selected_items:
                    if isinstance(item, hiero.core.EffectTrackItem):
                        skipped += 1
                        continue
                    try:
                        source = item.source()
                        bin_item = source.binItem()
                        media_source = source.mediaSource()
                        if not bin_item or not media_source.isMediaPresent():
                            skipped += 1
                            continue
                        if not bin_item.activeVersion():
                            skipped += 1
                            continue
                        bin_item.setColor(color)
                        changed += 1
                    except Exception as error:
                        skipped += 1
                        log_messages.append("No se pudo colorear un clip: %s" % error)
            finally:
                project.endUndo()
            log_messages.append(
                "Color aplicado a %d clip(s); omitidos: %d." % (changed, skipped)
            )
        except Exception as error:
            log_messages.append("Error al cambiar el color de clips: %s" % error)
        finally:
            debug_log(log_messages)


# Crear la instancia del panel y agregarlo al windowManager de Hiero
colorChanger = ColorChangeWidget()
wm = hiero.ui.windowManager()
wm.addWindow(colorChanger)
