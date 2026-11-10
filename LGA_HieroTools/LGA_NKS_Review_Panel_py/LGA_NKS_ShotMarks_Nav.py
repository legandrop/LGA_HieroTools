"""
____________________________________________________________________

  LGA_NKS_ShotMarks_Nav v1.14 | Lega

  Previous / Next Mark: Click en Previous / Next Mark del panel Review
  (con Shift esos botones navegan anotaciones). Salta el playhead a la
  marca de Shot Marks anterior o siguiente y muestra su info de la
  planilla (shot, REC TC, notas, descripcion, brief, status, vendor,
  escena, categoria) en una ventanita. Find Shot Mark salta por aca tambien.

  Existe porque el salto nativo (Viewer > Next Tag) no muestra la nota, y
  la del tag de Hiero sale recortada. La ventana es una sola: cada salto
  la actualiza en el lugar, sin apilar ventanas, y se muestra sin
  activarse, asi el teclado sigue en NKS. Los datos salen de la metadata
  que Shot Marks guarda en cada tag, no del Excel: el salto es inmediato
  y la info queda en el proyecto aunque la planilla se mueva.

  Log: logs/DebugPy_LGA_NKS_ShotMarks_Nav.log.

  v1.14: Group (columna Grupo) en la linea de status. Una marca por clip
         muestra el clip del timeline (el edit ref) y su SRC TC, con su
         propio tooltip en vez del de evento del EDL.
  v1.13: Cambios locales desde la ventanita, sin salir de NKS: la
         dificultad en cinco pildoras siempre a la vista (un click la
         cambia), Notes y Budget Alternative (ex Notes 2) se editan con un
         click en el texto o se agregan desde la caja punteada, y preguntas
         en un campo al pie. Se guardan en el archivo de cambios del
         proyecto (LGA_NKS_ShotMarks_Edits), nunca en la planilla, y se
         muestran encima de la marca con "EDITED" y lo que dice la planilla.
         Export Changes los baja a un CSV. Un cambio que ya llego a la
         planilla se cierra solo. Pie fijo con los cambios pendientes.
  v1.12: Tooltip propio en vez del nativo (EDL del clip).
         Dificultad del shot en la linea de datos, despues del status: un
         punto y el texto en el color de su nivel, de verde (very easy) a
         rojo (very hard). Un valor desconocido va como texto comun.
  v1.11: Brief numerado: un parrafo por item con un poco de aire entre
         uno y otro, y el numero en Color.TEXT_MARKER, un escalon mas claro
         que el texto. Mas facil de leer item por item.
  v1.10: El thumb se busca en la carpeta del proyecto (ruta relativa al
         .hrox) y, si no esta, por nombre en la cache de Locate. Una ruta
         relativa ya no se abre tal cual: se resolvia contra el directorio
         actual de NKS y el thumb aparecia o no segun como se abrio NKS.
  v1.09: Seccion Comments: los comentarios de la planilla en la fila del
         shot (autor, fecha, columna, respuestas). Los resueltos van en
         gris. Sin comentarios no aparece.
  v1.08: Notes y Notes 2 arriba de todo, cada una en una caja con borde
         de color (ambar y celeste): son lo eventual del shot, lo que hay
         que mirar con atencion. Sin texto (o sin columna) no aparecen.
  v1.07: show_mark_at: saltar a una marca dada y mostrarla, compartido
         con la ventana Find Shot Mark. Los botones pasan a ser Previous /
         Next Mark: el salto entre marcas es el Click normal.
  v1.06: Linea con el cambio contra la corrida anterior de Shot Marks, en
         el color del tag (que campos cambiaron, o por que una marca roja
         no se ubico), y el texto anterior debajo de la descripcion o el
         brief que cambiaron.
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

import datetime
import html
import importlib.util
import logging
import os
import re
from pathlib import Path

import hiero.core
import hiero.ui

from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtCore, QtGui, QtWidgets, Qt
from LGA_NKS_Shared.LGA_UI_CustomTooltip_HieroTools import set_custom_tooltip
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
WINDOW_API = 11

_LOCAL = Path(os.getenv("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")) / "LGA" / "HieroTools"
# Cache de thumbs de Locate (la misma carpeta que cache_root() de Locate):
# donde se busca por nombre el thumb de una marca que no esta junto al proyecto.
LOCATE_THUMBS = _LOCAL / "ShotMarks_Locate" / "thumbs"
# Cambios locales de un proyecto que todavia no se guardo (sin .hrox).
EDITS_FALLBACK = _LOCAL / "ShotMarks_Edits"

# Tooltips en castellano, separados del widget para que pasar a bilingue sea
# un cambio de datos.
TOOLTIPS = {
    "edl_event": "Clip de camara y SRC TC del plano, del EDL del armado (evento %s).",
    "timeline_clip": "Clip del timeline que lleva esta marca y su SRC TC.",
    "edit_note": "Click para editar. El cambio queda guardado en tu PC,\n"
                 "no en la planilla: se pasa despues con Export Changes.",
    "add_note": "Agregar %s a este shot. Queda guardado en tu PC,\nno en la planilla.",
    "ask": "Pregunta sobre este shot, para pasarla despues a la planilla.\n"
           "Enter la guarda, Esc la borra.",
    "export": "Bajar a un CSV todos los cambios de este proyecto que\n"
              "todavia no estan en la planilla, para revisarlos y pasarlos.",
    "remove_question": "Borrar esta pregunta.",
    "difficulty": "Cambiar la dificultad. Queda guardada en tu PC, no en la planilla.\n"
                  "La de borde punteado es la que dice la planilla.",
    "revert": "Descartar tu cambio y volver a lo que dice la planilla.",
}
# Dato, no estilo: lo cambiado aca y que todavia no esta en la planilla.
LOCAL_EDIT_COLOR = "#A58BFF"
# Dificultades si ninguna marca de la secuencia trae una (nivel 1 a 5).
DEFAULT_DIFFICULTIES = ("Very Easy", "Easy", "Mid", "Hard", "Very Hard")
NOTE_PLACEHOLDER = "Write the %s for this shot."
QUESTION_PLACEHOLDER = "Ask a question about this shot, then Enter"
EMPTY_HINTS = {"notes": "Add notes", "notes2": "Add a budget alternative"}
# Cancel y Save del editor, del mismo alto.
EDITOR_BUTTON_HEIGHT = 28
WINDOW_WIDTH = 520
SCREEN_MARGIN = 24
# Lega pidio la letra mas grande: con el tamano del host (~12 px en NKS) no
# llegaba a leerla. Va por apply_ui_font (QFont), no por font-size en la hoja.
INFO_FONT_PX = Metric.FORM_FONT_SIZE + 1
TITLE_FONT_PX = INFO_FONT_PX + 4
# Aire entre los items del brief numerado: separa un pedido del otro sin
# llegar a media linea en blanco (Lega, 2026-11-03).
BRIEF_ITEM_GAP = 5
# Un renglon "1. ..." del brief numerado (numbered_brief del nucleo).
BRIEF_ITEM = re.compile(r"^(\d+)\.\s(.*)$")

LOGGER_NAME = "LGA_NKS_ShotMarks_Nav"

# Notes y Notes 2: (titulo, color del titulo, color del borde). Es dato, no
# estilo: cada caja se reconoce por su color, como el cambio por el del tag.
NOTE_SECTIONS = (
    ("notes", "Notes", Color.WARNING_TEXT, Color.WARNING),
    ("notes2", "Budget Alternative", Color.INFO, Color.INFO),
)

_modules = {}


def _module(name):
    if name not in _modules:
        path = Path(__file__).resolve().parent / (name + ".py")
        spec = importlib.util.spec_from_file_location(name, str(path))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _modules[name] = module
    return _modules[name]


def _sheet_module():
    return _module("LGA_NKS_ShotMarks_Sheet")


def _edits_module():
    return _module("LGA_NKS_ShotMarks_Edits")


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
    project = sequence.project()
    hrox = project.path() if project is not None else ""
    # Cambios locales (dificultad, notas, preguntas): un archivo por proyecto.
    info["edits_path"] = _edits_module().edits_path(
        hrox, project.name() if project is not None else "", str(EDITS_FALLBACK))
    info["timeline"] = sequence.name()
    if info.get("thumb"):
        # Ruta relativa al .hrox (o, en marcas viejas, la de la cache de
        # Locate): resuelta aca a una absoluta que existe, o "" si no hay.
        info["thumb_file"] = module.resolve_thumb(
            info["thumb"], [os.path.dirname(hrox) if hrox else "", str(LOCATE_THUMBS)])
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

class DifficultyStrip(QtWidgets.QWidget):
    """Las cinco dificultades como pildoras, siempre a la vista: un click
    cambia la de la marca. Dibujadas a mano porque el color de cada una es
    dato (verde a rojo), no estilo de boton. La que dice la planilla lleva
    borde punteado; la elegida, el borde y el texto en su color."""

    picked = QtCore.Signal(str)

    PAD_X = 9
    DOT = 8
    GAP = 5
    SPACING = 6

    def __init__(self, parent=None):
        super(DifficultyStrip, self).__init__(parent)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self._names = list(DEFAULT_DIFFICULTIES)
        self._selected = None
        self._sheet = None
        self._hover = None
        self._rects = []

    def set_state(self, names, selected, sheet):
        """names: texto de cada nivel 1..5; selected y sheet: nivel o None."""
        self._names = list(names)
        self._selected = selected
        self._sheet = sheet
        self._layout_pills()
        self.updateGeometry()
        self.update()

    def _bold(self):
        return semibold(QtGui.QFont(self.font()))

    def _layout_pills(self):
        metrics = QtGui.QFontMetrics(self._bold())
        height = metrics.height() + 8
        x = 0
        self._rects = []
        for name in self._names:
            width = self.PAD_X * 2 + self.DOT + self.GAP + metrics.horizontalAdvance(name)
            self._rects.append(QtCore.QRectF(x + 0.5, 2.5, width - 1, height - 1))
            x += width + self.SPACING
        self._size = QtCore.QSize(max(0, x - self.SPACING), height + 4)

    def sizeHint(self):
        if not self._rects:
            self._layout_pills()
        return self._size

    def minimumSizeHint(self):
        return self.sizeHint()

    def changeEvent(self, event):
        if event.type() == QtCore.QEvent.FontChange:
            self._layout_pills()
            self.updateGeometry()
        super(DifficultyStrip, self).changeEvent(event)

    def _index_at(self, pos):
        for index, rect in enumerate(self._rects):
            if rect.contains(QtCore.QPointF(pos)):
                return index
        return None

    def mouseMoveEvent(self, event):
        index = self._index_at(event.pos())
        if index != self._hover:
            self._hover = index
            self.update()

    def leaveEvent(self, event):
        self._hover = None
        self.update()

    def mouseReleaseEvent(self, event):
        index = self._index_at(event.pos())
        if index is not None and event.button() == Qt.LeftButton and index + 1 != self._selected:
            self.picked.emit(self._names[index])

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        regular, bold = QtGui.QFont(self.font()), self._bold()
        for index, (name, rect) in enumerate(zip(self._names, self._rects)):
            level = index + 1
            color = QtGui.QColor(DIFFICULTY_COLORS[level])
            on = level == self._selected
            radius = rect.height() / 2.0
            fill = Color.SURFACE_RAISED if on else (Color.SURFACE_HOVER if index == self._hover
                                                   else None)
            pen = QtGui.QPen(color if on else QtGui.QColor(
                Color.BORDER_HOVER if level == self._sheet else Color.BORDER))
            if level == self._sheet and not on:
                pen.setStyle(Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(QtGui.QColor(fill) if fill else Qt.NoBrush)
            painter.drawRoundedRect(rect, radius, radius)
            dot = QtGui.QColor(color)
            if not on:
                dot.setAlphaF(0.6)
            painter.setPen(Qt.NoPen)
            painter.setBrush(dot)
            cy = rect.center().y()
            painter.drawEllipse(QtCore.QRectF(rect.left() + self.PAD_X, cy - self.DOT / 2.0,
                                              self.DOT, self.DOT))
            painter.setFont(bold if on else regular)
            painter.setPen(color if on else QtGui.QColor(
                Color.TEXT_STRONG if index == self._hover else Color.TEXT))
            text_rect = QtCore.QRectF(rect.left() + self.PAD_X + self.DOT + self.GAP, rect.top(),
                                      rect.width(), rect.height())
            painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, name)
        painter.end()


class _FieldEditor(QtWidgets.QWidget):
    """Texto de varias lineas con Use Sheet Value / Cancel / Save. Ctrl+Enter
    guarda y Esc cancela."""

    def __init__(self, on_save, on_cancel, on_revert, parent=None):
        super(_FieldEditor, self).__init__(parent)
        self._on_save = on_save
        self._on_cancel = on_cancel
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 0)
        layout.setSpacing(6)
        self.text = QtWidgets.QPlainTextEdit()
        self.text.setTabChangesFocus(True)
        self.text.installEventFilter(self)
        layout.addWidget(self.text)
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(6)
        self.revert = QtWidgets.QPushButton("Use Sheet Value")
        self.revert.setStyleSheet(Style.BTN_SMALL)
        set_custom_tooltip(self.revert, TOOLTIPS["revert"])
        self.revert.clicked.connect(on_revert)
        row.addWidget(self.revert)
        row.addStretch(1)
        cancel = QtWidgets.QPushButton("Cancel")
        cancel.setStyleSheet(Style.BTN_SMALL)
        cancel.clicked.connect(on_cancel)
        save = QtWidgets.QPushButton("Save")
        save.setStyleSheet(Style.BTN_PRIMARY)
        save.clicked.connect(on_save)
        # Mismo alto los dos: BTN_PRIMARY es el boton grande de un dialogo.
        for button in (cancel, save):
            button.setFixedHeight(EDITOR_BUTTON_HEIGHT)
        row.addWidget(cancel)
        row.addWidget(save)
        layout.addLayout(row)
        hint = QtWidgets.QLabel("Ctrl+Enter saves · Esc cancels")
        hint.setStyleSheet("color: %s;" % Color.TEXT_DIM)
        layout.addWidget(hint)
        self.hide()

    def begin(self, text, placeholder, can_revert):
        self.text.setPlainText(text or "")
        self.text.setPlaceholderText(placeholder)
        # Cuatro renglones de la letra de la ventana, mas el padding de la hoja.
        self.text.setFixedHeight(self.text.fontMetrics().lineSpacing() * 4 + 16)
        cursor = self.text.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        self.text.setTextCursor(cursor)
        self.revert.setVisible(can_revert)
        self.show()

    def value(self):
        return self.text.toPlainText().strip()

    def eventFilter(self, obj, event):
        if obj is self.text and event.type() == QtCore.QEvent.KeyPress:
            if event.key() == Qt.Key_Escape:
                self._on_cancel()
                return True
            if (event.key() in (Qt.Key_Return, Qt.Key_Enter)
                    and event.modifiers() & Qt.ControlModifier):
                self._on_save()
                return True
        return super(_FieldEditor, self).eventFilter(obj, event)


class ShotMarkInfoWindow(QtWidgets.QWidget):
    """Ventanita de info de la marca actual. Una sola, actualizada en el lugar.

    Muestra lo que Shot Marks guardo en el tag (los valores de la planilla) con
    los cambios locales encima: dificultad, Notes, Budget Alternative y
    preguntas. Esos cambios van al archivo de cambios del proyecto, nunca a
    la planilla.
    """

    lga_api = WINDOW_API

    def __init__(self, parent=None):
        super(ShotMarkInfoWindow, self).__init__(parent)
        self.setObjectName(WINDOW_NAME)
        # Tool: flota sobre NKS y se esconde con el. Sin activarse al
        # mostrarse: el teclado y los atajos siguen en el visor/timeline.
        # Se activa solo cuando el usuario hace click para escribir.
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
        # Marca tal como la guardo Shot Marks (_base) y con los cambios locales
        # encima (_shown); campo que se esta editando; error del archivo.
        self._base = None
        self._shown = None
        self._editing = None
        self._edits_error = ""
        # {nivel 1..5: texto como lo escribe la planilla}, de las marcas de la
        # secuencia: el cambio se guarda con la misma ortografia.
        self._difficulty_names = {}
        self._click_targets = {}
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
        self.difficulty = DifficultyStrip()
        set_custom_tooltip(self.difficulty, TOOLTIPS["difficulty"])
        self.difficulty.picked.connect(self._on_difficulty)
        head.addWidget(self.difficulty)
        # "Sheet says Mid · edited", o el aviso si la planilla cambio despues.
        self.difficulty_note = self._label(head)
        # Cambio contra la corrida anterior de Shot Marks (color del tag).
        self.change = self._label(head)
        layout.addWidget(header)

        body = QtWidgets.QVBoxLayout()
        body.setContentsMargins(margin, 12, margin, margin - 8)
        body.setSpacing(4)
        # Thumb de la planilla (solo marcas ubicadas desde thumbnails): se
        # compara con el visor mientras se navega.
        self.thumb = QtWidgets.QLabel()
        self.thumb.setAlignment(Qt.AlignLeft)
        body.addWidget(self.thumb)
        self.thumb_caption = self._label(body)
        self._thumb_gap = QtWidgets.QSpacerItem(0, 8)
        body.addItem(self._thumb_gap)
        # {campo: {holder, box, text, local, before, editor, empty, border}}
        self.note_boxes = {}
        for field, title, title_color, border_color in NOTE_SECTIONS:
            self.note_boxes[field] = self._note_box(body, field, title, title_color, border_color)
        # Comentarios de la planilla (Google Sheets / Excel) en la fila del shot.
        self.comments_holder = QtWidgets.QWidget()
        comments_layout = QtWidgets.QVBoxLayout(self.comments_holder)
        comments_layout.setContentsMargins(0, 0, 0, 10)
        comments_layout.setSpacing(4)
        self.comments_title = QtWidgets.QLabel()
        self.comments_title.setStyleSheet("color: %s; %s" % (Color.TEXT_STRONG, semibold_css()))
        comments_layout.addWidget(self.comments_title)
        self.comments = self._label(comments_layout)
        body.addWidget(self.comments_holder)
        self.description = self._section(body, "Description")
        self.description_before = self._label(body)
        body.addSpacing(8)
        self.brief = self._section(body, "Brief")
        self.brief_before = self._label(body)
        body.addSpacing(8)
        # Preguntas hechas aca: una lista y el campo para sumar otra.
        self.questions_holder = QtWidgets.QWidget()
        questions_layout = QtWidgets.QVBoxLayout(self.questions_holder)
        questions_layout.setContentsMargins(0, 0, 0, 6)
        questions_layout.setSpacing(6)
        questions_title = QtWidgets.QLabel("Questions")
        questions_title.setStyleSheet("color: %s; %s" % (LOCAL_EDIT_COLOR, semibold_css()))
        questions_layout.addWidget(questions_title)
        self.questions_list = QtWidgets.QVBoxLayout()
        self.questions_list.setSpacing(6)
        questions_layout.addLayout(self.questions_list)
        self.question_line = QtWidgets.QLineEdit()
        self.question_line.setPlaceholderText(QUESTION_PLACEHOLDER)
        # Solo con click: si no, es el primer control y se queda con el foco.
        self.question_line.setFocusPolicy(Qt.ClickFocus)
        set_custom_tooltip(self.question_line, TOOLTIPS["ask"])
        self.question_line.returnPressed.connect(self._add_question)
        self.question_line.installEventFilter(self)
        questions_layout.addWidget(self.question_line)
        body.addWidget(self.questions_holder)
        layout.addLayout(body)

        # Pie fijo: numero de marca, cambios pendientes y Export Changes.
        bar = QtWidgets.QWidget()
        bar.setObjectName("shotMarkFooter")
        bar.setAttribute(Qt.WA_StyledBackground, True)
        bar.setStyleSheet("QWidget#shotMarkFooter { background: %s; border-top: 1px solid %s; }"
                          % (Color.SURFACE, Color.BORDER))
        row = QtWidgets.QHBoxLayout(bar)
        row.setContentsMargins(margin, 8, margin, 8)
        row.setSpacing(8)
        self.footer = self._label(row)
        row.addStretch(1)
        self.pending = QtWidgets.QLabel()
        self.pending.setTextFormat(Qt.RichText)
        row.addWidget(self.pending)
        self.export = QtWidgets.QPushButton("Export Changes…")
        self.export.setStyleSheet(Style.BTN_SMALL)
        set_custom_tooltip(self.export, TOOLTIPS["export"])
        self.export.clicked.connect(self._export)
        row.addWidget(self.export)
        layout.addWidget(bar)

    def _label(self, layout):
        label = QtWidgets.QLabel()
        label.setWordWrap(True)
        label.setTextFormat(Qt.RichText)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(label)
        return label

    def _note_box(self, layout, field, title, title_color, border_color):
        """Caja de Notes / Budget Alternative. Click en el texto la edita; sin
        texto queda una caja punteada "+ Add ..." para agregarla."""
        holder = QtWidgets.QWidget()
        outer = QtWidgets.QVBoxLayout(holder)
        outer.setContentsMargins(0, 0, 0, 10)
        outer.setSpacing(0)
        box = QtWidgets.QWidget()
        box.setObjectName("shotMarkNote")
        box.setAttribute(Qt.WA_StyledBackground, True)
        inner = QtWidgets.QVBoxLayout(box)
        inner.setContentsMargins(10, 6, 10, 8)
        inner.setSpacing(3)
        heading_row = QtWidgets.QHBoxLayout()
        heading_row.setSpacing(8)
        heading = QtWidgets.QLabel(title)
        heading.setStyleSheet("color: %s; %s" % (title_color, semibold_css()))
        heading_row.addWidget(heading)
        edited = QtWidgets.QLabel("EDITED")
        edited.setStyleSheet("color: %s; border: 1px solid %s; border-radius: 3px; "
                             "padding: 0px 5px; %s" % (LOCAL_EDIT_COLOR, LOCAL_EDIT_COLOR,
                                                       semibold_css()))
        heading_row.addWidget(edited)
        heading_row.addStretch(1)
        inner.addLayout(heading_row)
        # Sin seleccion de texto: el click es para editar.
        text = QtWidgets.QLabel()
        text.setWordWrap(True)
        text.setTextFormat(Qt.RichText)
        text.setStyleSheet("color: %s;" % Color.TEXT_STRONG)
        text.setCursor(Qt.IBeamCursor)
        inner.addWidget(text)
        local = self._label(inner)
        before = self._label(inner)
        editor = _FieldEditor(self._save_edit, self._cancel_edit, self._revert_edit)
        inner.addWidget(editor)
        outer.addWidget(box)
        empty = QtWidgets.QLabel()
        empty.setObjectName("shotMarkEmpty")
        empty.setAttribute(Qt.WA_StyledBackground, True)
        empty.setStyleSheet("QLabel#shotMarkEmpty { color: %s; border: 1px dashed %s; "
                            "border-radius: %dpx; padding: 6px 10px; }"
                            % (Color.TEXT_DIM, Color.BORDER_STRONG, Metric.RADIUS_SMALL))
        empty.setText("+ " + EMPTY_HINTS[field])
        empty.setCursor(Qt.PointingHandCursor)
        set_custom_tooltip(empty, TOOLTIPS["add_note"] % title)
        outer.addWidget(empty)
        for target in (box, text, empty):
            target.installEventFilter(self)
            self._click_targets[target] = field
        set_custom_tooltip(text, TOOLTIPS["edit_note"])
        layout.addWidget(holder)
        return {"holder": holder, "box": box, "text": text, "local": local, "before": before,
                "editor": editor, "empty": empty, "edited": edited, "border": border_color}

    def _set_box_style(self, parts, editing):
        border = parts["border"]
        style = ("QWidget#shotMarkNote { background: %s; border-left: 3px solid %s; "
                 "border-radius: %dpx;" % (Color.SURFACE, border, Metric.RADIUS_SMALL))
        if editing:
            style += " border-top: 1px solid {0}; border-right: 1px solid {0}; " \
                     "border-bottom: 1px solid {0};".format(Color.ACCENT_HOVER)
        parts["box"].setStyleSheet(style + " }")

    def _section(self, layout, title):
        heading = QtWidgets.QLabel(title)
        heading.setStyleSheet("color: %s; %s" % (Color.TEXT_STRONG, semibold_css()))
        layout.addWidget(heading)
        return self._label(layout)

    # -- mostrar -----------------------------------------------------------

    def show_mark(self, info):
        """Muestra una marca. Si se estaba escribiendo en otra, lo escrito se
        guarda antes de cambiar (nada se pierde por apretar Next)."""
        if self._base is not None and info.get("shot") != self._base.get("shot"):
            self._commit_drafts()
        self._editing = None
        self._base = info
        self._render()

    def _render(self):
        edits = _edits_module()
        data, self._edits_error = self._load_edits()
        shown = edits.overlay(self._base, data)
        if shown["applied"] and not self._edits_error:
            # Ya estan en la planilla (se volvio a correr Shot Marks): se cierran.
            edits.mark_applied(data, shown["applied"])
            try:
                edits.save(self._base["edits_path"], data)
                logging.getLogger(LOGGER_NAME).info(
                    "%s: %d cambios ya estan en la planilla, cerrados", shown["shot"],
                    len(shown["applied"]))
            except Exception as exc:
                logging.getLogger(LOGGER_NAME).warning("No se pudieron cerrar cambios: %s", exc)
        shown["pending_total"] = len(edits.pending(data))
        self._shown = shown
        self._paint(shown)

    def _load_edits(self):
        edits = _edits_module()
        path = (self._base or {}).get("edits_path") or ""
        if not path:
            return edits.empty(), ""
        try:
            return edits.load(path), ""
        except Exception as exc:
            logging.getLogger(LOGGER_NAME).warning("Archivo de cambios ilegible %s: %s", path, exc)
            return edits.empty(), "Local changes file could not be read: %s" % exc

    def _can_edit(self):
        return bool(self._base and self._base.get("edits_path") and not self._edits_error)

    def _paint(self, info):
        esc = _escape
        editable = self._can_edit()
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
            # Marca por clip: el clip es el del timeline (el edit ref), no un
            # plano del EDL.
            if _sheet_module().is_clip_event(source["event"]):
                set_custom_tooltip(self.source, TOOLTIPS["timeline_clip"])
            else:
                set_custom_tooltip(self.source, TOOLTIPS["edl_event"] % source["event"])
        self.source.setVisible(bool(source))
        meta = []
        for field, label in (("status", "Status"), ("vendor", "Vendor"), ("scene", "Scene"),
                             ("category", "Category"), ("group", "Group")):
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
        self._paint_difficulty(info, editable)
        self._show_thumb(info)
        self.change.setText(_change_html(info.get("change"), info.get("changed") or {},
                                         info.get("change_reason"), info))
        self.change.setVisible(bool(info.get("change")))
        self.description.setText(_body(info.get("description")))
        self.brief.setText(_brief_html(info.get("brief")))
        changed = info.get("changed") or {}
        befores = [("description", self.description_before), ("brief", self.brief_before)]
        for field, parts in self.note_boxes.items():
            self._paint_note(field, parts, info, editable)
            befores.append((field, parts["before"]))
        threads = _sheet_module().parse_comments(info.get("comments"))
        self.comments_holder.setVisible(bool(threads))
        if threads:
            open_count = sum(1 for t in threads if not t.get("resolved"))
            title = "Comments"
            if not open_count:
                title += " (resolved)"
            elif open_count != len(threads):
                title += " (%d open)" % open_count
            self.comments_title.setText(title)
            self.comments.setText(_comments_html(threads))
        # El texto anterior de lo que cambio, para ver que cambio sin abrir la planilla.
        for field, label in befores:
            label.setText(_dim("Before: ") + _dim(_escape(changed[field]) or "&mdash;")
                          if field in changed else "")
            label.setVisible(field in changed)
        self._paint_questions(info, editable)
        footer = "Mark %d of %d" % (info["index"] + 1, info["total"])
        if not info["complete"]:
            footer += ". Run Shot Marks again to see every column of the sheet here."
        self.footer.setText(_dim(footer))
        if self._edits_error:
            self.footer.setText('<span style="color:%s">%s</span>' % (
                Color.ERROR_TEXT, _escape(self._edits_error)))
        pending = info.get("pending_total", 0)
        self.pending.setText('<span style="color:%s">&#9679;</span> %d local change%s' % (
            LOCAL_EDIT_COLOR, pending, "" if pending == 1 else "s"))
        self.pending.setVisible(bool(pending))
        self.export.setVisible(bool(pending))
        self._fit()

    def _paint_difficulty(self, info, editable):
        level = _sheet_module().difficulty_level
        sheet_value = (self._base or {}).get("difficulty") or ""
        shown = info.get("difficulty") or ""
        visible = editable and bool(shown or self._difficulty_names)
        self.difficulty.setVisible(visible)
        edited = "difficulty" in info.get("edited", {})
        note = ""
        if visible:
            names = [self._difficulty_names.get(n, DEFAULT_DIFFICULTIES[n - 1]) for n in range(1, 6)]
            self.difficulty.set_state(names, level(shown), level(sheet_value))
            if edited:
                note = _dim("Sheet says %s &middot; " % (_escape(sheet_value) or "nothing")) + \
                    '<span style="color:%s">&#9998; edited</span>' % LOCAL_EDIT_COLOR
            elif shown and level(shown) is None:
                # Un valor que no es un nivel conocido: se muestra tal cual.
                note = _dim("Sheet says ") + _escape(shown)
        elif shown:
            # Sin archivo de cambios (marca suelta): la dificultad, solo lectura.
            note = _dim("Difficulty ") + _difficulty_html(shown)
        if "difficulty" in info.get("conflict", {}):
            note += '<br><span style="color:%s">The sheet changed after your edit.</span>' % (
                Color.WARNING_TEXT) + _dim(" You changed it from %s." % (
                    _escape(info["conflict"]["difficulty"]) or "nothing"))
        self.difficulty_note.setText(note)
        self.difficulty_note.setVisible(bool(note))

    def _paint_note(self, field, parts, info, editable):
        value = info.get(field) or ""
        editing = self._editing == field
        edited = field in info.get("edited", {})
        # Sin texto: la caja punteada para agregar (solo si se puede editar).
        parts["holder"].setVisible(bool(value) or editing or editable)
        parts["box"].setVisible(bool(value) or editing)
        parts["empty"].setVisible(not value and not editing and editable)
        self._set_box_style(parts, editing)
        parts["edited"].setVisible(edited)
        parts["text"].setVisible(not editing)
        parts["text"].setText(_escape(value))
        local = ""
        if edited and not editing:
            local = _dim("In the sheet: ") + _dim(_escape(info["edited"][field]) or "empty")
        if field in info.get("conflict", {}) and not editing:
            local += ('<br><span style="color:%s">The sheet changed after your edit.</span> %s'
                      % (Color.WARNING_TEXT, _dim("When you edited it, it said: %s" % (
                          _escape(info["conflict"][field]) or "empty"))))
        parts["local"].setText(local)
        parts["local"].setVisible(bool(local))
        if not editing:
            parts["editor"].hide()

    def _paint_questions(self, info, editable):
        while self.questions_list.count():
            item = self.questions_list.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        questions = info.get("questions") or []
        for question in questions:
            row = QtWidgets.QWidget()
            line = QtWidgets.QHBoxLayout(row)
            line.setContentsMargins(0, 0, 0, 0)
            line.setSpacing(8)
            who = " · ".join(p for p in (question.get("author"), question.get("when")) if p)
            text = QtWidgets.QLabel("%s<br>%s" % (_strong(question.get("after")), _dim(_escape(who))))
            text.setWordWrap(True)
            text.setTextFormat(Qt.RichText)
            text.setTextInteractionFlags(Qt.TextSelectableByMouse)
            line.addWidget(text, 1)
            remove = QtWidgets.QPushButton("×")
            remove.setStyleSheet(Style.BTN_ICON)
            remove.setFixedSize(22, 22)
            set_custom_tooltip(remove, TOOLTIPS["remove_question"])
            remove.clicked.connect(lambda _checked=False, qid=question.get("id"): self._remove(qid))
            line.addWidget(remove, 0, Qt.AlignTop)
            apply_ui_font(row, INFO_FONT_PX)
            self.questions_list.addWidget(row)
        self.questions_holder.setVisible(editable or bool(questions))
        self.question_line.setVisible(editable)

    def _show_thumb(self, info):
        path = info.get("thumb") or ""
        found = info.get("thumb_file", path) or ""
        image = QtGui.QImage(found) if os.path.isabs(found) else QtGui.QImage()
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
        # Todos los layouts, no solo el de arriba: al abrir el editor dentro de
        # una caja de nota, el layout de la caja seguia con el alto de antes y
        # la ventana quedaba aplastada.
        for child in self.findChildren(QtWidgets.QLayout):
            child.invalidate()
        for child in self.findChildren(QtWidgets.QWidget):
            if child.layout() is not None:
                child.updateGeometry()
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

    # -- cambios locales -----------------------------------------------------
    #
    # Todo se escribe en el archivo de cambios del proyecto (Edits), relee el
    # archivo antes de escribir y redibuja con _render. Nunca toca la planilla
    # ni el tag: el tag sigue diciendo lo que dice la planilla, y la ventana
    # muestra el cambio encima.

    def eventFilter(self, obj, event):
        field = self._click_targets.get(obj)
        if (field is not None and event.type() == QtCore.QEvent.MouseButtonRelease
                and event.button() == Qt.LeftButton):
            self._begin_edit(field)
            return True
        # getattr: el filtro ya recibe eventos mientras _build arma la ventana.
        line = getattr(self, "question_line", None)
        if (line is not None and obj is line and event.type() == QtCore.QEvent.KeyPress
                and event.key() == Qt.Key_Escape):
            self.question_line.clear()
            self._return_focus()
            return True
        return super(ShotMarkInfoWindow, self).eventFilter(obj, event)

    def _begin_edit(self, field):
        if not self._can_edit() or self._editing == field:
            return
        if self._editing:
            self._commit_drafts()
            self._render()
        self._editing = field
        parts = self.note_boxes[field]
        title = dict((f, t) for f, t, _c, _b in NOTE_SECTIONS)[field]
        parts["editor"].begin(self._shown.get(field) or "", NOTE_PLACEHOLDER % title.lower(),
                              field in self._shown.get("edited", {}))
        self._paint_note(field, parts, self._shown, True)
        self._fit()
        # Click del usuario para escribir: recien aca la ventana toma el teclado.
        self.activateWindow()
        parts["editor"].text.setFocus()

    def _save_edit(self):
        field, self._editing = self._editing, None
        if field:
            self._store(field, self.note_boxes[field]["editor"].value())
        self._render()
        self._return_focus()

    def _cancel_edit(self):
        self._editing = None
        self._render()
        self._return_focus()

    def _revert_edit(self):
        field, self._editing = self._editing, None
        if field:
            self._store(field, (self._base or {}).get(field) or "")
        self._render()
        self._return_focus()

    def _on_difficulty(self, name):
        self._store("difficulty", name)
        self._render()

    def _add_question(self):
        text = self.question_line.text().strip()
        if not text:
            return
        self._store(_edits_module().QUESTION, text)
        self.question_line.clear()
        self._render()

    def _remove(self, edit_id):
        def change(data):
            _edits_module().remove(data, edit_id)
        self._write(change, "pregunta borrada %s" % edit_id)
        self._render()

    def _commit_drafts(self):
        """Lo escrito y no guardado (nota abierta o pregunta en el campo) se
        guarda: se llama antes de cambiar de marca."""
        if self._editing and self._shown is not None:
            value = self.note_boxes[self._editing]["editor"].value()
            if value != (self._shown.get(self._editing) or "").strip():
                self._store(self._editing, value)
        self._editing = None
        if self.question_line.text().strip():
            self._store(_edits_module().QUESTION, self.question_line.text())
            self.question_line.clear()

    def _store(self, field, value):
        edits = _edits_module()
        base = self._base or {}
        common = {"timeline": base.get("timeline", ""), "source": base.get("source", "")}

        def change(data):
            if field == edits.QUESTION:
                edits.add_question(data, base.get("shot"), base.get("row"), value, **common)
            else:
                edits.set_value(data, base.get("shot"), base.get("row"), field,
                                base.get(field) or "", value, **common)
        self._write(change, "%s %s -> %r" % (base.get("shot"), field, value[:80]))

    def _write(self, change, description):
        if not self._can_edit():
            return
        edits = _edits_module()
        path = self._base["edits_path"]
        try:
            data = edits.load(path)
            change(data)
            edits.save(path, data)
            logging.getLogger(LOGGER_NAME).info("Cambio local: %s (%s)", description, path)
        except Exception as exc:
            logging.getLogger(LOGGER_NAME).error("No se pudo guardar %s: %s", description, exc)
            show_info(self, "Shot Marks", "The change could not be saved:\n%s" % exc)

    def _return_focus(self):
        # Guardado o cancelado: el teclado vuelve a NKS (visor y timeline).
        try:
            main = hiero.ui.mainWindow()
            if main is not None:
                main.activateWindow()
        except Exception:
            pass

    def _export(self):
        edits = _edits_module()
        path = (self._base or {}).get("edits_path") or ""
        if not path:
            return
        try:
            data = edits.load(path)
        except Exception as exc:
            show_info(self, "Shot Marks", "The local changes file could not be read:\n%s" % exc)
            return
        count = len(edits.pending(data))
        if not count:
            return
        name = os.path.basename(path).replace(edits.FILE_SUFFIX, "")
        default = os.path.join(os.path.dirname(path), "%s_ShotMarks_Changes_%s.csv" % (
            name, datetime.date.today().isoformat()))
        target, _filter = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Local Changes", default, "CSV files (*.csv)")
        if not target:
            return
        now = self._sheet_values()
        try:
            written = edits.export_csv(target, data, lambda shot, field: now.get(shot, {}).get(field))
        except Exception as exc:
            logging.getLogger(LOGGER_NAME).error("Export fallo %s: %s", target, exc)
            show_info(self, "Shot Marks", "The changes could not be exported:\n%s" % exc)
            return
        logging.getLogger(LOGGER_NAME).info("Export: %d cambios a %s", written, target)
        show_info(self, "Shot Marks",
                  "Exported %d change%s to:\n%s\n\nThey stay pending here until the sheet has them "
                  "and Shot Marks runs again." % (written, "" if written == 1 else "s", target))

    def _sheet_values(self):
        """{shot: {campo: valor}} que dice la planilla, de las marcas de la
        secuencia: la columna "Sheet now" del CSV."""
        sheet = _sheet_module()
        values = {}
        for tag in self._tags:
            try:
                data = tag.metadata()
                values[tag.name()] = dict(
                    (field, str(data.value(sheet.meta_key(field))) if data.hasKey(
                        sheet.meta_key(field)) else "") for field in _edits_module().EDITABLE)
            except Exception:
                continue
        return values

    # -- seguimiento del playhead ------------------------------------------
    #
    # Mientras la ventana esta abierta escucha Viewer.timeChanged. El costo
    # por cuadro (tambien en playback) es leer viewer.time() y una busqueda
    # binaria sobre enteros: no se tocan los tags ni se loguea. Solo cuando el
    # playhead entra en OTRA marca se arma la info y se redibuja. Entre dos
    # marcas la ventana queda mostrando la ultima. Mientras se escribe una
    # nota o una pregunta no se cambia de marca: se terminaria guardando en
    # el shot equivocado.

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
        self._difficulty_names = _difficulty_names(self._tags)
        single = sum(1 for start, end in zip(self._starts, ends) if end <= start)
        if self._tags:
            logging.getLogger(LOGGER_NAME).info(
                "Siguiendo %s: %d marcas, %d de un cuadro estiradas hasta la siguiente, "
                "dificultades %s", sequence.name() if sequence is not None else "-",
                len(self._tags), single, self._difficulty_names or "-")

    def _on_sequence_changed(self, *args):
        try:
            _viewer, sequence = _viewer_and_sequence()
            self._set_marks(sequence, mark_tags(sequence) if sequence is not None else [])
        except Exception as exc:
            logging.getLogger(LOGGER_NAME).warning("Cambio de secuencia: %s", exc)
            self._set_marks(None, [])

    def _writing(self):
        return bool(self._editing or self.question_line.text().strip())

    def _on_time_changed(self, *args):
        if not self._starts or self._viewer is None or not self.isVisible():
            return
        if self._writing():
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
        self._commit_drafts()
        self.unfollow()
        super(ShotMarkInfoWindow, self).closeEvent(event)


def _difficulty_names(tags):
    """{nivel: texto} como lo escribe la planilla, de los tags de la secuencia."""
    sheet = _sheet_module()
    key = sheet.meta_key("difficulty")
    names = {}
    for tag in tags:
        try:
            data = tag.metadata()
            if not data.hasKey(key):
                continue
            value = str(data.value(key)).strip()
        except Exception:
            continue
        level = sheet.difficulty_level(value)
        if level and level not in names:
            names[level] = value
    return names


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
# Dato, no estilo: la dificultad de 1 (very easy) a 5 (very hard), de verde a rojo.
DIFFICULTY_COLORS = {1: "#4FC3A1", 2: "#8CC85A", 3: "#E8C547", 4: "#F2913D", 5: "#E5534B"}


def _difficulty_html(text):
    """La dificultad con un punto y el texto en el color de su nivel. Un valor
    que no es un nivel conocido va como texto comun."""
    level = _sheet_module().difficulty_level(text)
    if level is None:
        return _escape(text)
    return '<span style="color:%s; %s">&#9679; %s</span>' % (
        DIFFICULTY_COLORS[level], semibold_css(), _escape(text))
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


# Dato, no estilo: el mismo color que el icono del tag.
CHANGE_COLORS = {
    "unchanged": Color.OK_TEXT,
    "changed": Color.WARNING_TEXT,
    "new": "#FFA24D",
    "removed": Color.ERROR_TEXT,
}
CHANGE_TEXTS = {
    "unchanged": "No changes since the previous run",
    "changed": "Changed since the previous run",
    "new": "New since the previous run",
    "removed": "No longer in the sheet",
}
FIELD_LABELS = {"brief": "Brief", "description": "Description", "notes": "Notes",
                "notes2": "Budget Alternative", "status": "Status", "scene": "Scene",
                "vendor": "Vendor", "category": "Category", "group": "Group",
                "difficulty": "Difficulty"}
# Textos largos: el anterior va debajo de su seccion, no en la linea de cambio.
LONG_FIELDS = ("description", "brief", "notes", "notes2")


def _change_html(change, changed, reason="", current=None):
    """'Changed since the previous run: Description, Status (was X)'."""
    current = current or {}
    if change not in CHANGE_TEXTS:
        return ""
    label = CHANGE_TEXTS[change]
    if change == "removed" and reason:
        # El shot sigue en la planilla pero no se pudo ubicar (otro corte).
        label = "In the sheet, but not placed: %s" % reason
    text = '<span style="color:%s; %s">%s</span>' % (
        CHANGE_COLORS[change], semibold_css(), _escape(label))
    if change == "changed" and changed:
        fields = []
        for field in _sheet_module().CHANGE_FIELDS:
            if field not in changed:
                continue
            item = FIELD_LABELS[field]
            # Los textos largos se muestran debajo de su seccion; los cortos aca.
            # Una nota que se borro no tiene caja: su texto anterior va aca.
            if field not in LONG_FIELDS or (field.startswith("notes") and not current.get(field)):
                item += _dim(" (was %s)" % (_escape(changed[field]) or "empty"))
            fields.append(item)
        text += ": " + ", ".join(fields)
    return text


def _comment_line(author, date, extra=""):
    parts = [p for p in (author, date, extra) if p]
    return _dim(" &middot; ".join(_escape(p) for p in parts))


def _comments_html(threads):
    """Un hilo por bloque: autor, fecha y columna; el texto; las respuestas.

    Los resueltos van enteros en gris: siguen siendo contexto, pero ya no
    piden nada.
    """
    blocks = []
    for thread in threads:
        column = thread.get("column")
        extra = ("on %s" % column) if column else ""
        if thread.get("resolved"):
            extra = (extra + " · resolved").strip(" ·")
        text = _escape(thread.get("text"))
        lines = [_comment_line(thread.get("author"), thread.get("date"), extra),
                 _dim(text) if thread.get("resolved") else text]
        for reply in thread.get("replies") or []:
            reply_text = _escape(reply.get("text"))
            lines.append("&nbsp;&nbsp;&#8627; %s %s" % (
                _comment_line(reply.get("author"), reply.get("date")),
                _dim(reply_text) if thread.get("resolved") else reply_text))
        blocks.append("<br>".join(lines))
    return "<br><br>".join(blocks)


def _body(text):
    return _escape(text) if text else _dim("&mdash;")


def _brief_html(text):
    """Brief numerado: un parrafo por item, con BRIEF_ITEM_GAP de aire arriba
    y el numero un escalon mas claro que el texto (TEXT_MARKER). Un brief sin
    numerar (un solo renglon, o una marca de antes) va como cualquier cuerpo."""
    lines = str(text or "").split("\n")
    if not any(BRIEF_ITEM.match(line) for line in lines):
        return _body(text)
    paragraphs = []
    for line in lines:
        match = BRIEF_ITEM.match(line)
        if match:
            content = '<span style="color:%s">%s.</span> %s' % (
                Color.TEXT_MARKER, match.group(1), _escape(match.group(2)))
        else:
            # Un renglon vacio separa grupos ("wishlist:"): queda como renglon.
            content = _escape(line) or "&nbsp;"
        gap = BRIEF_ITEM_GAP if paragraphs else 0
        paragraphs.append('<p style="margin-top:%dpx; margin-bottom:0px">%s</p>' % (gap, content))
    return "".join(paragraphs)


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
    info = show_mark_at(viewer, sequence, tags, index)
    log.info("%s: %s %d -> %d (%s, marca %d de %d, metadata completa %s, vendor %s)",
             sequence.name(), direction, current, starts[index], info["shot"], index + 1,
             len(tags), info["complete"],
             ", ".join("%s %s" % (name, color or "sin color")
                       for name, color in info["vendor_colors"]) or "-")
    return True


def show_mark_at(viewer, sequence, tags, index):
    """Salta el playhead al IN de tags[index] y la muestra en la ventanita.

    La usan Previous / Next Mark y Find Shot Mark. Devuelve la info mostrada.
    """
    info = mark_info(sequence, tags[index], index, len(tags))
    window = info_window()
    # El seguimiento se arma ANTES del salto: setTime dispara timeChanged y la
    # ventana ya tiene que saber que esa marca es la que esta mostrando.
    window.follow(viewer, sequence, tags, index)
    window.show_mark(info)
    if not window.isVisible():
        window.show()
    viewer.setTime(int(tags[index].inTime()))
    return info


def main(direction="next"):
    if direction not in ("next", "previous"):
        raise ValueError("La direccion debe ser 'next' o 'previous'.")
    go_to_mark(direction)


if __name__ == "__main__":
    main()
