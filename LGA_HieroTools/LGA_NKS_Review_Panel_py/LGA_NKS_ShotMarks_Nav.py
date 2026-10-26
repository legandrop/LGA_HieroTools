"""
____________________________________________________________________

  LGA_NKS_ShotMarks_Nav v1.00 | Lega

  Previous / Next Mark: Shift+Click en Previous / Next Annotation del
  panel Review. Salta el playhead a la marca de Shot Marks anterior o
  siguiente y muestra su info de la planilla (shot, REC TC, descripcion,
  brief, status, vendor, escena, categoria) en una ventanita.

  Existe porque el salto nativo (Viewer > Next Tag) no muestra la nota, y
  la del tag de Hiero sale recortada. La ventana es una sola: cada salto
  la actualiza en el lugar, sin apilar ventanas, y se muestra sin
  activarse, asi el teclado sigue en NKS. Los datos salen de la metadata
  que Shot Marks guarda en cada tag, no del Excel: el salto es inmediato
  y la info queda en el proyecto aunque la planilla se mueva.

  Log: logs/DebugPy_LGA_NKS_ShotMarks_Nav.log.

  v1.00: Version inicial.
____________________________________________________________________
"""

import html
import importlib.util
import logging
from pathlib import Path

import hiero.core
import hiero.ui

from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtCore, QtWidgets, Qt
from LGA_NKS_Shared.LGA_UI_Style_HieroTools import (
    Color,
    Metric,
    Style,
    apply_ui_font,
    semibold_css,
)
from LGA_NKS_Shared.LGA_NKS_MessageBox import show_info

DEBUG = False

WINDOW_NAME = "LGA_ShotMarkInfo"
# Sube cuando cambia la API de la ventana: el panel re-ejecuta este modulo en
# cada click, y una ventana creada por una version vieja se reemplaza.
WINDOW_API = 1
WINDOW_WIDTH = 460
SCREEN_MARGIN = 24

_sheet = None


def _sheet_module():
    global _sheet
    if _sheet is None:
        path = Path(__file__).resolve().parent / "LGA_NKS_ShotMarks_Sheet.py"
        spec = importlib.util.spec_from_file_location("LGA_NKS_ShotMarks_Sheet", str(path))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _sheet = module
    return _sheet


def _logger():
    log_dir = Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(exist_ok=True)
    logger = logging.getLogger("LGA_NKS_ShotMarks_Nav")
    logger.setLevel(logging.DEBUG)
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
    logger.propagate = False
    handler = logging.FileHandler(str(log_dir / "DebugPy_LGA_NKS_ShotMarks_Nav.log"),
                                  mode="w", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    if DEBUG:
        logger.addHandler(logging.StreamHandler())
    return logger


# -- datos -----------------------------------------------------------------

def _viewer_and_sequence():
    viewer = hiero.ui.currentViewer()
    sequence = None
    if viewer is not None:
        try:
            sequence = viewer.player().sequence()
        except Exception:
            sequence = None
    if sequence is None:
        sequence = hiero.ui.activeSequence()
    return viewer, sequence


def mark_tags(sequence):
    """Tags de Shot Marks de la secuencia, ordenados por IN."""
    key = _sheet_module().META_KEY
    tags = []
    for tag in sequence.tags():
        try:
            if tag.metadata().hasKey(key):
                tags.append(tag)
        except Exception:
            continue
    return sorted(tags, key=lambda t: (int(t.inTime()), t.name()))


def mark_info(sequence, tag, index, total):
    """Todo lo que muestra la ventana, en texto."""
    module = _sheet_module()
    data = tag.metadata()

    def get(key):
        return data.value(key) if data.hasKey(key) else None

    info = module.mark_info_from_metadata(get)
    rate = sequence.framerate()
    fps = int(round(float(rate.toFloat())))
    frame_in, frame_out = int(tag.inTime()), int(tag.outTime())
    if not info["tc_in"]:
        # Tag de la v1.00: el TC sale del timeline y el brief de la nota.
        info["tc_in"] = module.format_timecode(sequence.timecodeStart() + frame_in, fps)
    if not info["brief"]:
        info["brief"] = tag.note()
    info["shot"] = tag.name()
    info["frames"] = frame_out - frame_in + 1
    info["duration"] = module.format_timecode(info["frames"], fps)
    info["index"] = index
    info["total"] = total
    return info


# -- ventana ---------------------------------------------------------------

class ShotMarkInfoWindow(QtWidgets.QWidget):
    """Ventanita de info de la marca actual. Una sola, actualizada en el lugar."""

    lga_api = WINDOW_API

    def __init__(self, parent=None):
        super(ShotMarkInfoWindow, self).__init__(parent)
        self.setObjectName(WINDOW_NAME)
        # Tool: flota sobre NKS y se esconde con el. Sin activarse al
        # mostrarse: el teclado y los atajos siguen en el visor/timeline.
        self.setWindowFlags(Qt.Tool)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setWindowTitle("Shot Mark")
        self.setStyleSheet(Style.FORM)
        self._placed = False
        self._build()
        apply_ui_font(self)

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QtWidgets.QWidget()
        header.setObjectName("shotMarkHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header.setStyleSheet(
            "QWidget#shotMarkHeader { border-bottom: 1px solid %s; }" % Color.BORDER)
        head = QtWidgets.QVBoxLayout(header)
        margin = Metric.WINDOW_MARGIN
        head.setContentsMargins(margin, margin - 4, margin, 10)
        head.setSpacing(4)
        self.title = QtWidgets.QLabel()
        self.title.setProperty("lgaTitle", True)
        self.title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        head.addWidget(self.title)
        self.timecode = self._label(head)
        self.meta = self._label(head)
        layout.addWidget(header)

        body = QtWidgets.QVBoxLayout()
        body.setContentsMargins(margin, 12, margin, margin - 4)
        body.setSpacing(4)
        self.description = self._section(body, "Description")
        body.addSpacing(8)
        self.brief = self._section(body, "Brief")
        body.addSpacing(8)
        self.footer = self._label(body)
        layout.addLayout(body)

    def _label(self, layout):
        label = QtWidgets.QLabel()
        label.setWordWrap(True)
        label.setTextFormat(Qt.RichText)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(label)
        return label

    def _section(self, layout, title):
        heading = QtWidgets.QLabel(title)
        heading.setStyleSheet("color: %s; %s" % (Color.TEXT_STRONG, semibold_css()))
        layout.addWidget(heading)
        return self._label(layout)

    def show_mark(self, info):
        esc = _escape
        self.title.setText(esc(info["shot"]))
        tc_line = "REC TC %s" % _strong(info["tc_in"])
        if info["tc_out"]:
            tc_line += " &ndash; %s" % _strong(info["tc_out"])
        tc_line += _dim(" &middot; %d frames (%s)" % (info["frames"], info["duration"]))
        self.timecode.setText(tc_line)
        meta = []
        for field, label in (("status", "Status"), ("vendor", "Vendor"),
                             ("scene", "Scene"), ("category", "Category")):
            if info.get(field):
                meta.append("%s %s" % (_dim(label), esc(info[field])))
        self.meta.setText(" &nbsp;&middot;&nbsp; ".join(meta))
        self.meta.setVisible(bool(meta))
        self.description.setText(_body(info.get("description")))
        self.brief.setText(_body(info.get("brief")))
        footer = "Mark %d of %d" % (info["index"] + 1, info["total"])
        if not info["complete"]:
            footer += ". Run Shot Marks again to see every column of the sheet here."
        self.footer.setText(_dim(footer))
        self._fit()

    def _fit(self):
        # Ancho fijo y alto segun el texto: una descripcion larga crece hacia
        # abajo en vez de recortarse.
        self.setFixedWidth(WINDOW_WIDTH)
        self.layout().activate()
        self.setFixedHeight(self.layout().totalHeightForWidth(self.width())
                            if self.layout().hasHeightForWidth()
                            else self.sizeHint().height())
        if not self._placed:
            self._place()

    def _place(self):
        # Primera vez: arriba a la izquierda de la pantalla de NKS, como Shot
        # Info cuando se abre al navegar. Despues queda donde el usuario la deje.
        screen = None
        main = hiero.ui.mainWindow()
        if main is not None and main.windowHandle() is not None:
            screen = main.windowHandle().screen()
        if screen is None:
            screen = QtWidgets.QApplication.primaryScreen()
        area = screen.availableGeometry()
        self.move(area.left() + SCREEN_MARGIN, area.top() + SCREEN_MARGIN * 3)
        self._placed = True


def _escape(text):
    return html.escape(str(text or "")).replace("\n", "<br>")


def _strong(text):
    return '<span style="color:%s">%s</span>' % (Color.TEXT_STRONG, _escape(text))


def _dim(text):
    return '<span style="color:%s">%s</span>' % (Color.TEXT_DIM, text)


def _body(text):
    return _escape(text) if text else _dim("&mdash;")


def info_window(create=True):
    """La ventana existente, o una nueva en el mismo lugar si cambio la API."""
    old = None
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if widget.objectName() == WINDOW_NAME:
            if getattr(widget, "lga_api", None) == WINDOW_API:
                return widget
            old = widget
    if not create:
        return None
    window = ShotMarkInfoWindow(hiero.ui.mainWindow())
    if old is not None:
        window.move(old.pos())
        window._placed = True
        old.close()
        old.deleteLater()
    return window


# -- entrada ---------------------------------------------------------------

def go_to_mark(direction):
    log = _logger()
    viewer, sequence = _viewer_and_sequence()
    if viewer is None or sequence is None:
        log.warning("Sin visor o sin secuencia")
        show_info(hiero.ui.mainWindow(), "Shot Marks", "Open a timeline in the viewer first.")
        return False
    tags = mark_tags(sequence)
    if not tags:
        log.info("%s no tiene marcas de Shot Marks", sequence.name())
        show_info(hiero.ui.mainWindow(), "Shot Marks",
                  "This timeline has no Shot Marks.\n"
                  "Add them with the Shot Marks button of the Review panel.")
        return False
    current = int(viewer.time())
    starts = [int(t.inTime()) for t in tags]
    index = _sheet_module().next_mark_index(starts, current, direction)
    tag = tags[index]
    viewer.setTime(starts[index])
    info = mark_info(sequence, tag, index, len(tags))
    log.info("%s: %s %d -> %d (%s, marca %d de %d, metadata completa %s)", sequence.name(),
             direction, current, starts[index], tag.name(), index + 1, len(tags), info["complete"])
    window = info_window()
    window.show_mark(info)
    if not window.isVisible():
        window.show()
    return True


def main(direction="next"):
    if direction not in ("next", "previous"):
        raise ValueError("La direccion debe ser 'next' o 'previous'.")
    go_to_mark(direction)


if __name__ == "__main__":
    main()
