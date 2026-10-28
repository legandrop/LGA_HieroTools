"""
____________________________________________________________________

  LGA_NKS_ShotMarks_Nav v1.05 | Lega

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

  v1.05: Seguir al playhead con marcas de un cuadro (fila con IN = OUT o
         sin OUT): llegan hasta la siguiente marca, porque al arrastrar casi
         nunca se pisaba su unico cuadro y la ventana no cambiaba. El log
         anota cuantas se estiraron y cada vez que el playhead entra en un
         cuadro sin marca.
  v1.04: Marcas ubicadas con EDL: una linea con el clip de camara y el
         SRC TC IN/OUT del plano (el evento del EDL, en el tooltip).
  v1.03: Marcas ubicadas desde thumbnails: la ventana muestra el thumb de
         la planilla y si el cuadro fue aceptado solo, confirmado a mano o
         quedo sin confirmar. El status de omit va en rojo y el de posible
         omit en ambar, para verlos de un vistazo al navegar.
  v1.02: Una celda con varios vendors ("Vendor A, Vendor B") pinta cada
         uno con su color; antes se buscaba la celda entera y salia sin
         color. El alto se recalcula invalidando los layouts: al pasar a
         una marca con mas lineas en el encabezado la ventana quedaba con
         el alto viejo, la descripcion recortada y restos del pie abajo.
  v1.01: La ventana sigue al playhead: al entrar en otra marca (scrub o
         playback) muestra esa sin tocar Previous/Next. Engancha la
         senal timeChanged del visor y busca la marca con
         mark_index_at sobre listas cacheadas; solo redibuja cuando
         cambia de marca. El vendor sale con el color de su grupo en
         PipeSync (contexto studio o client). Letra 2 px mas grande
         (15 px, titulo 19 px) y ventana mas ancha.
  v1.00: Version inicial.
____________________________________________________________________
"""

import html
import importlib.util
import logging
from pathlib import Path

import hiero.core
import hiero.ui

from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtCore, QtGui, QtWidgets, Qt
from LGA_NKS_Shared.LGA_UI_Style_HieroTools import (
    Color,
    Metric,
    Style,
    apply_ui_font,
    semibold,
    semibold_css,
)
from LGA_NKS_Shared.LGA_NKS_MessageBox import show_info

DEBUG = False

WINDOW_NAME = "LGA_ShotMarkInfo"
# Sube cuando cambia la API de la ventana: el panel re-ejecuta este modulo en
# cada click, y una ventana creada por una version vieja se reemplaza.
WINDOW_API = 5

# Tooltips en castellano, separados del widget para que pasar a bilingue sea
# un cambio de datos.
TOOLTIPS = {
    "edl_event": "Clip de camara y SRC TC del plano, del EDL del armado (evento %s).",
}
WINDOW_WIDTH = 520
SCREEN_MARGIN = 24
# Lega pidio la letra mas grande: con el tamano del host (~12 px en NKS) no
# llegaba a leerla. Va por apply_ui_font (QFont), no por font-size en la hoja.
INFO_FONT_PX = Metric.FORM_FONT_SIZE + 1
TITLE_FONT_PX = INFO_FONT_PX + 4

LOGGER_NAME = "LGA_NKS_ShotMarks_Nav"

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
    logger = logging.getLogger(LOGGER_NAME)
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
    # [(vendor, color o None)]: una celda puede traer varios vendors.
    info["vendor_colors"] = []
    if info.get("vendor"):
        try:
            # Import aca: el modulo resuelve la DB por contexto con imports que
            # solo existen con el startup del pack (no en el harness de UI).
            from LGA_NKS_Shared.LGA_NKS_Vendor_Colors_Config import find_vendor_colors

            project = sequence.project()
            info["vendor_colors"] = find_vendor_colors(
                info["vendor"], project.name() if project is not None else None)
        except Exception as exc:
            # Sin color no es un error de la marca: se muestra el texto solo.
            logging.getLogger(LOGGER_NAME).warning("Color de vendor no disponible: %s", exc)
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
        # Seguimiento del playhead: visor enganchado y marcas de su secuencia
        # (IN y OUT como enteros, para no tocar los tags en cada cuadro).
        self._viewer = None
        self._sequence = None
        self._tags = []
        self._starts = []
        self._ends = []
        self._index = None
        self._in_gap = False
        self._build()
        apply_ui_font(self, INFO_FONT_PX)
        # Despues de apply_ui_font, que le pisa la familia a todos los hijos.
        title_font = semibold(self.title.font())
        title_font.setPixelSize(TITLE_FONT_PX)
        self.title.setFont(title_font)

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
        self._header = header
        margin = Metric.WINDOW_MARGIN
        head.setContentsMargins(margin, margin - 4, margin, 10)
        head.setSpacing(4)
        self.title = QtWidgets.QLabel()
        # Sin lgaTitle: esa regla de la hoja fija 11 pt y quedaba mas chica que
        # el cuerpo agrandado. El tamano va por QFont en __init__.
        self.title.setStyleSheet("color: %s;" % Color.TEXT_STRONG)
        self.title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        head.addWidget(self.title)
        self.timecode = self._label(head)
        # Clip de camara y SRC TC (solo marcas ubicadas con el EDL del armado).
        self.source = self._label(head)
        self.meta = self._label(head)
        layout.addWidget(header)

        body = QtWidgets.QVBoxLayout()
        body.setContentsMargins(margin, 12, margin, margin - 4)
        body.setSpacing(4)
        # Thumb de la planilla (solo marcas ubicadas desde thumbnails): se
        # compara con el visor mientras se navega.
        self.thumb = QtWidgets.QLabel()
        self.thumb.setAlignment(Qt.AlignLeft)
        body.addWidget(self.thumb)
        self.thumb_caption = self._label(body)
        self._thumb_gap = QtWidgets.QSpacerItem(0, 8)
        body.addItem(self._thumb_gap)
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
        source = _sheet_module().parse_clip(info.get("clip"))
        if source:
            # Dos renglones fijos: un nombre de clip de camara real (~30
            # caracteres) partia el SRC TC por la mitad. El evento del EDL, en
            # el tooltip.
            self.source.setText("%s %s<br>%s %s &ndash; %s" % (
                _dim("Clip"), _strong(source["clip"]), _dim("SRC"), _strong(source["src_in"]),
                _strong(source["src_out"])))
            self.source.setToolTip(TOOLTIPS["edl_event"] % source["event"])
        self.source.setVisible(bool(source))
        meta = []
        for field, label in (("status", "Status"), ("vendor", "Vendor"),
                             ("scene", "Scene"), ("category", "Category")):
            if not info.get(field):
                continue
            value = esc(info[field])
            if field == "status":
                color = STATUS_COLORS.get(_sheet_module().status_kind(info[field]))
                if color:
                    value = '<span style="color:%s; %s">%s</span>' % (color, semibold_css(), value)
            if field == "vendor" and any(color for _name, color in info.get("vendor_colors", ())):
                value = ", ".join(_vendor_html(name, color)
                                  for name, color in info["vendor_colors"])
            meta.append("%s %s" % (_dim(label), value))
        self.meta.setText(" &nbsp;&middot;&nbsp; ".join(meta))
        self.meta.setVisible(bool(meta))
        self._show_thumb(info)
        self.description.setText(_body(info.get("description")))
        self.brief.setText(_body(info.get("brief")))
        footer = "Mark %d of %d" % (info["index"] + 1, info["total"])
        if not info["complete"]:
            footer += ". Run Shot Marks again to see every column of the sheet here."
        self.footer.setText(_dim(footer))
        self._fit()

    def _show_thumb(self, info):
        path = info.get("thumb") or ""
        image = QtGui.QImage(path) if path else QtGui.QImage()
        has_thumb = not image.isNull()
        self.thumb.setVisible(has_thumb)
        self.thumb_caption.setVisible(bool(path))
        self._thumb_gap.changeSize(0, 8 if path else 0)
        if has_thumb:
            width = WINDOW_WIDTH - 2 * Metric.WINDOW_MARGIN
            self.thumb.setPixmap(QtGui.QPixmap.fromImage(image).scaledToWidth(
                width, Qt.SmoothTransformation))
        if path:
            self.thumb_caption.setText(_located_html(info.get("located"), has_thumb))

    def _fit(self):
        # Ancho fijo y alto segun el texto: una descripcion larga crece hacia
        # abajo en vez de recortarse.
        # invalidate() antes de medir: el cambio de texto de un label solo
        # pide re-layout por un evento que todavia no se proceso, y el layout
        # devuelve el alto cacheado de la marca anterior. Medido en NKS 16:
        # sin esto, si Vendor/Category pasaba a dos lineas, la ventana quedaba
        # con el alto viejo, la descripcion recortada y restos del pie abajo.
        self.setFixedWidth(WINDOW_WIDTH)
        self._header.layout().invalidate()
        self._header.updateGeometry()
        self.layout().invalidate()
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

    # -- seguimiento del playhead ------------------------------------------
    #
    # Mientras la ventana esta abierta escucha Viewer.timeChanged. El costo
    # por cuadro (tambien en playback) es leer viewer.time() y una busqueda
    # binaria sobre enteros: no se tocan los tags ni se loguea. Solo cuando el
    # playhead entra en OTRA marca se arma la info y se redibuja. Entre dos
    # marcas la ventana queda mostrando la ultima.

    def follow(self, viewer, sequence, tags, index):
        """Engancha el visor (una sola vez) y cachea las marcas de la secuencia."""
        if viewer is not self._viewer:
            self.unfollow()
            try:
                viewer.timeChanged.connect(self._on_time_changed)
                viewer.sequenceChanged.connect(self._on_sequence_changed)
                self._viewer = viewer
            except Exception as exc:
                # Sin la senal la ventana sigue andando con Previous/Next.
                logging.getLogger(LOGGER_NAME).warning(
                    "No se pudo seguir el playhead: %s", exc)
        self._set_marks(sequence, tags)
        self._index = index

    def unfollow(self):
        viewer, self._viewer = self._viewer, None
        if viewer is None:
            return
        for signal, slot in (("timeChanged", self._on_time_changed),
                             ("sequenceChanged", self._on_sequence_changed)):
            try:
                getattr(viewer, signal).disconnect(slot)
            except Exception:
                # El visor ya no existe (tab cerrado): Qt corto la conexion.
                pass

    def _set_marks(self, sequence, tags):
        self._sequence = sequence
        self._tags = list(tags)
        self._starts = [int(t.inTime()) for t in self._tags]
        ends = [int(t.outTime()) for t in self._tags]
        last_frame = 0
        if sequence is not None:
            try:
                last_frame = int(sequence.duration()) - 1
            except Exception:
                last_frame = max(ends or [0])
        # Las marcas de un cuadro (fila sin TC OUT valido) llegan hasta la
        # siguiente: si no, al arrastrar el playhead la ventana no cambiaba.
        self._ends = _sheet_module().follow_ends(self._starts, ends, last_frame)
        self._index = None
        self._in_gap = False
        single = sum(1 for start, end in zip(self._starts, ends) if end <= start)
        if self._tags:
            logging.getLogger(LOGGER_NAME).info(
                "Siguiendo %s: %d marcas, %d de un cuadro estiradas hasta la siguiente",
                sequence.name() if sequence is not None else "-", len(self._tags), single)

    def _on_sequence_changed(self, *args):
        try:
            _viewer, sequence = _viewer_and_sequence()
            self._set_marks(sequence, mark_tags(sequence) if sequence is not None else [])
        except Exception as exc:
            logging.getLogger(LOGGER_NAME).warning("Cambio de secuencia: %s", exc)
            self._set_marks(None, [])

    def _on_time_changed(self, *args):
        if not self._starts or self._viewer is None or not self.isVisible():
            return
        try:
            frame = int(self._viewer.time())
        except Exception:
            return
        index = _sheet_module().mark_index_at(self._starts, self._ends, frame)
        if index is None:
            # Se loguea solo al ENTRAR en un hueco, no en cada cuadro: en
            # playback serian 24 lineas por segundo.
            if not self._in_gap:
                self._in_gap = True
                logging.getLogger(LOGGER_NAME).info(
                    "Playhead %d: sin marca, queda la ultima mostrada", frame)
            return
        self._in_gap = False
        if index == self._index:
            return
        try:
            info = mark_info(self._sequence, self._tags[index], index, len(self._tags))
        except Exception:
            # Tag borrado (Shot Marks se volvio a correr): se releen las marcas.
            self._on_sequence_changed()
            return
        self._index = index
        self.show_mark(info)
        logging.getLogger(LOGGER_NAME).info("Playhead %d: marca %s (%d de %d)", frame,
                                            info["shot"], index + 1, len(self._tags))

    def closeEvent(self, event):
        self.unfollow()
        super(ShotMarkInfoWindow, self).closeEvent(event)


def _escape(text):
    return html.escape(str(text or "")).replace("\n", "<br>")


def _strong(text):
    return '<span style="color:%s">%s</span>' % (Color.TEXT_STRONG, _escape(text))


def _dim(text):
    return '<span style="color:%s">%s</span>' % (Color.TEXT_DIM, text)


def _vendor_html(name, color):
    # Dato, no estilo: el color del vendor en PipeSync. Sin color, texto comun.
    if not color:
        return _escape(name)
    return '<span style="color:%s; %s">%s</span>' % (color, semibold_css(), _escape(name))


# Dato, no estilo: un omit en rojo y un posible omit en ambar.
STATUS_COLORS = {"omit": Color.ERROR_TEXT, "maybe_omit": Color.WARNING_TEXT}
LOCATED_LABELS = {
    "auto": ("accepted automatically", Color.TEXT_DIM),
    "confirmed": ("confirmed by hand", Color.OK_TEXT),
    "review": ("not confirmed: check it against the viewer", Color.WARNING_TEXT),
}


def _located_html(located, has_thumb):
    """'Sheet thumbnail · <como se ubico>' a partir de 'nivel puntaje'."""
    parts = (located or "").split()
    level = parts[0] if parts else ""
    label, color = LOCATED_LABELS.get(level, ("", Color.TEXT_DIM))
    text = _dim("Sheet thumbnail" if has_thumb else "Sheet thumbnail not found on this computer")
    if label:
        text += _dim(" &middot; ") + '<span style="color:%s">%s</span>' % (color, label)
        if len(parts) > 1 and level != "confirmed":
            text += _dim(" (%s)" % _escape(parts[1]))
    return text


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
    info = mark_info(sequence, tag, index, len(tags))
    log.info("%s: %s %d -> %d (%s, marca %d de %d, metadata completa %s, vendor %s)",
             sequence.name(), direction, current, starts[index], tag.name(), index + 1,
             len(tags), info["complete"],
             ", ".join("%s %s" % (name, color or "sin color")
                       for name, color in info["vendor_colors"]) or "-")
    window = info_window()
    # El seguimiento se arma ANTES del salto: setTime dispara timeChanged y la
    # ventana ya tiene que saber que esa marca es la que esta mostrando.
    window.follow(viewer, sequence, tags, index)
    window.show_mark(info)
    if not window.isVisible():
        window.show()
    viewer.setTime(starts[index])
    return True


def main(direction="next"):
    if direction not in ("next", "previous"):
        raise ValueError("La direccion debe ser 'next' o 'previous'.")
    go_to_mark(direction)


if __name__ == "__main__":
    main()
