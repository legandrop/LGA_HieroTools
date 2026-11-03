"""
____________________________________________________________________

  LGA_NKS_ShotMarks_Locate v1.07 | Lega

  Shot Marks sin columna de timecode: ubica el thumbnail de cada fila
  de la planilla en el video del timeline y deja revisar los dudosos
  sobre el visor de NKS antes de poner las marcas.

  Existe porque hay breakdowns que solo traen una foto por shot. El
  trabajo pesado (indexar la pelicula, comparar huellas) lo hace
  LGA_NKS_ShotMarks_Locate_Engine.py en un proceso aparte con el
  Python embebido del pack: un minuto de Python puro en un hilo de NKS
  frenaria la UI por el GIL. Esta ventana lo lanza con QProcess, lee
  el progreso por el pipe y muestra el resultado.

  Revision: la lista ordena primero lo dudoso. Cada fila mueve el
  playhead del timeline al cuadro propuesto; el cuadro lo dibuja el
  visor de NKS y aca se ve al lado del thumb (o mezclado, o como
  diferencia) con la similitud en vivo. Flechas: un cuadro; Shift: un
  segundo; RePag/AvPag: corte anterior/siguiente; 1-5: candidatos;
  Enter: usar este cuadro; N: no esta en el corte.

  Las confirmaciones se guardan por proyecto (clave: hash del thumb y
  shot, una por corte) con la huella del cuadro elegido: al volver a
  correr se respetan, y con un corte nuevo se re-ubican buscando ese
  cuadro.

  Solo Windows por ahora: el Python embebido y ffmpeg_lga.exe viajan
  solo en el pack de Windows.

  Log: logs/DebugPy_LGA_NKS_ShotMarks_Locate.log.

  v1.07: Las decisiones se guardan por corte (store_decision): revisar
         un corte nuevo del mismo proyecto ya no pisa las confirmaciones
         del anterior.
  v1.06: Las decisiones se guardan por foto y shot (decision_key). Al
         pasar los TC, un plano que comparten dos shots distintos se parte
         en el corte que scdet no vio (split_shared_ranges, con scd.bin del
         indice), y las filas repetidas quedan en una marca. Una marca en
         un "plano" de mas de 60 s ya no queda de un cuadro: va entre los
         cortes debiles que lo rodean, o el plano entero si no hay ninguno
         (toma larga) (soft_shot_range). El archivo de decisiones va por
         el nombre del proyecto sin version y suma los de versiones
         anteriores: al subir de v04 a v05 se perdian las confirmaciones.
  v1.05: El log anota cada fila que no se ubica por no tener un nombre de
         shot completo (titulo de grupo como "PROJA_002_", o vacio) y el
         status de la fila: antes se descartaban sin dejar rastro.
  v1.04: Dice que el ultimo paso es Use Timecodes: en las instrucciones
         y, cuando no queda nada por revisar, en el resumen de abajo. Sin
         eso, terminar de revisar parecia el final y las marcas no se
         escribian.
  v1.03: Tira de planos entre vecinas: debajo de la comparacion, un
         cuadro por plano desde la fila ubicada anterior hasta la
         siguiente, con las dos vecinas en color, donde esta hoy la fila y
         donde esta el visor. Click en un plano lo lleva al visor. Ir
         cuadro a cuadro no servia para encontrar un plano de otra toma.
  v1.02: Los TC ubicados salen del TC del clip segun NKS, no del que lee
         ffprobe del archivo. Un MP4 con TC 00:59:50:00 que NKS muestra en
         00:00:00:00 dejaba todas las marcas corridas 86160 cuadros: el
         plan resta el TC de NKS.
  v1.01: EDL opcional: se pasa al motor, la ventana dice si se uso y
         cuantos cortes coinciden con la imagen, el IN/OUT de lo
         confirmado a mano sale del plano del EDL y cada fila muestra y
         pasa a Shot Marks el clip de camara y el SRC TC.
  v1.00: Version inicial.
____________________________________________________________________
"""

import importlib.util
import json
import logging
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import hiero.core
import hiero.ui

from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtCore, QtGui, QtWidgets, Qt
from LGA_NKS_Shared.LGA_UI_Style_HieroTools import (
    Color,
    Metric,
    Style,
    apply_ui_font,
    emphasis,
)

DEBUG = False

WINDOW_NAME = "LGA_ShotMarksLocate"
HERE = Path(__file__).resolve().parent
SHARED = HERE.parent / "LGA_NKS_Shared"
PYTHON = SHARED / "OIIO_Win" / "bin" / "python" / "python.exe"
FFMPEG = SHARED / "FFmpeg_Win" / "bin" / "ffmpeg_lga.exe"
FFPROBE = SHARED / "FFmpeg_Win" / "bin" / "ffprobe.exe"
ENGINE = HERE / "LGA_NKS_ShotMarks_Locate_Engine.py"

INNER = 0.92
THUMB_VIEW_W = 420
# Ancho del cuadro que se decodifica para comparar con el thumb.
FRAME_W = 960
# Tira de planos entre vecinas: ancho de cada cuadro (se achica hasta el
# minimo para que entren las dos vecinas; se decodifica al doble del maximo
# para que se vea nitido) y maximo de planos del medio.
STRIP_TILE_W = 150
STRIP_TILE_MIN_W = 112
STRIP_SPACING = 6
STRIP_DECODE_W = 300
STRIP_LIMIT = 24
# Dato, no estilo: cada vecina y la fila elegida se reconocen por su color,
# en el borde del cuadro y en su rotulo.
STRIP_COLORS = {"prev": Color.INFO, "next": Color.PATH_FIELD, "current": Color.WARNING_TEXT}
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

LEVEL_LABELS = {
    "auto": "Accepted",
    "confirmed": "Confirmed",
    "review": "To review",
    "not_found": "Not found",
    "not_in_cut": "Not in cut",
}
LEVEL_ORDER = {"review": 0, "not_found": 1, "not_in_cut": 2, "confirmed": 3, "auto": 4}
STAGE_LABELS = {
    "index": "Indexing the movie (once per movie)",
    "thumbs": "Reading the thumbnails",
    "match": "Comparing thumbnails with the movie",
    "window": "Checking the doubtful ones in order",
    "refine": "Finding the exact frame",
}

TOOLTIPS = {
    "filter": "Que filas mostrar.",
    "mode": "Como comparar el thumb con el cuadro del visor.",
    "prev_cut": "Ir al corte anterior (RePag).",
    "prev_sec": "Un segundo atras (Shift+Izquierda).",
    "prev_frame": "Un cuadro atras (Izquierda).",
    "next_frame": "Un cuadro adelante (Derecha).",
    "next_sec": "Un segundo adelante (Shift+Derecha).",
    "next_cut": "Ir al corte siguiente (AvPag).",
    "candidate": "Ir a este candidato (tecla %d).",
    "use": "Usar el cuadro actual del visor para este shot (Enter).",
    "not_in_cut": "Este shot no esta en el corte: no se marca (N).",
    "apply": "Pasar los timecodes ubicados a Shot Marks para revisar y agregar las marcas.",
    "cancel": "Cerrar sin usar los resultados. Lo confirmado queda guardado.",
    "strip": "Los planos entre la fila ubicada anterior y la siguiente: si el shot esta en orden, "
             "esta aca.",
    "strip_tile": "Ver este plano en el visor. Despues, Enter para usar ese cuadro.",
}

_log = None
_sheet = None
_thumbs = None
_edl = None


def _load(name):
    path = HERE / (name + ".py")
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sheet_module():
    global _sheet
    if _sheet is None:
        _sheet = _load("LGA_NKS_ShotMarks_Sheet")
    return _sheet


def _edl_module():
    global _edl
    if _edl is None:
        _edl = _load("LGA_NKS_ShotMarks_EDL")
    return _edl


def _thumbs_module():
    global _thumbs
    if _thumbs is None:
        _thumbs = _load("LGA_NKS_ShotMarks_Thumbs")
    return _thumbs


def _logger():
    global _log
    if _log is None:
        log_dir = HERE / "logs"
        log_dir.mkdir(exist_ok=True)
        _log = logging.getLogger("LGA_NKS_ShotMarks_Locate")
        _log.setLevel(logging.DEBUG)
        for handler in list(_log.handlers):
            handler.close()
            _log.removeHandler(handler)
        _log.propagate = False
        handler = logging.FileHandler(str(log_dir / "DebugPy_LGA_NKS_ShotMarks_Locate.log"),
                                      mode="w", encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        _log.addHandler(handler)
        if DEBUG:
            _log.addHandler(logging.StreamHandler())
    return _log


def cache_root():
    """Indices, thumbs y decisiones: datos regenerables, fuera de los repos."""
    root = os.getenv("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(root) / "LGA" / "HieroTools" / "ShotMarks_Locate"


def missing_tools():
    """Nombres de lo que falta para correr el motor (vacio si esta todo)."""
    if sys.platform != "win32":
        return ["Windows (locating from thumbnails is Windows only for now)"]
    return [str(p) for p in (PYTHON, FFMPEG, FFPROBE, ENGINE) if not p.is_file()]


def media_path(sequence):
    """Ruta del unico clip de video del timeline, o None."""
    items = [item for track in sequence.videoTracks() if track.isEnabled() for item in track.items()]
    if len(items) != 1:
        return None
    try:
        path = items[0].source().mediaSource().fileinfos()[0].filename()
    except Exception:
        return None
    # Hiero devuelve un archivo en la raiz de una unidad sin la barra
    # ("Y:clip.mov"): es una ruta relativa al directorio actual de esa unidad
    # y ffmpeg la resolveria contra cualquier carpeta. Medido en NKS 16.
    if re.match(r"^[A-Za-z]:[^\\/]", path or ""):
        path = path[:2] + "/" + path[2:]
    return path


# -- decisiones ---------------------------------------------------------------

def _decisions_path(project_name):
    return cache_root() / "decisions" / (_sheet_module().decisions_base(project_name) + ".json")


def load_decisions(project_name):
    """Las decisiones del proyecto, de cualquier version.

    Hasta v1.06 el archivo llevaba la version del proyecto: los de las
    versiones anteriores se suman primero y el sin version manda.
    """
    path = _decisions_path(project_name)
    sheet = _sheet_module()
    files = []
    if path.parent.is_dir():
        files = sorted((p for p in path.parent.glob("*.json")
                        if sheet.is_versioned_decisions(p.stem, path.stem)),
                       key=lambda p: p.stat().st_mtime)
    decisions = {}
    for item in files + [path]:
        try:
            with open(str(item), encoding="utf-8") as handle:
                decisions.update(json.load(handle))
        except (OSError, ValueError):
            continue
    return decisions


def save_decisions(project_name, decisions):
    path = _decisions_path(project_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(decisions, handle, indent=1)
    os.replace(tmp, str(path))


def frame_prints(index_folder, frame):
    """Huellas guardadas en el indice para un cuadro (d8, g32 en hex)."""
    out = []
    for name, size in (("d8.bin", 72), ("g32.bin", 576)):
        with open(os.path.join(index_folder, name), "rb") as handle:
            handle.seek(frame * size)
            out.append(handle.read(size).hex())
    return out


# -- similitud en vivo -------------------------------------------------------

def _gray_print(image, rect=None):
    """32x18 gris del area de imagen (92 % central), como el motor."""
    if rect is not None:
        image = image.copy(QtCore.QRect(*rect))
    w, h = image.width(), image.height()
    mx, my = int(w * (1 - INNER) / 2), int(h * (1 - INNER) / 2)
    image = image.copy(QtCore.QRect(mx, my, w - 2 * mx, h - 2 * my))
    small = image.scaled(32, 18, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    small = small.convertToFormat(QtGui.QImage.Format_Grayscale8)
    values = []
    for y in range(18):
        values.extend(small.pixelColor(x, y).red() for x in range(32))
    return values


def similarity(a, b):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((x - mb) ** 2 for x in b)
    if va <= 0 or vb <= 0:
        return 0.0
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(va * vb)


# -- hilo para la extraccion de thumbs -----------------------------------------

class _Signals(QtCore.QObject):
    done = QtCore.Signal(object, object)


class _Job(QtCore.QRunnable):
    def __init__(self, func, signals):
        super(_Job, self).__init__()
        self.func = func
        self.signals = signals

    def run(self):
        try:
            result = self.func()
        except Exception as exc:
            self.signals.done.emit(None, exc)
            return
        self.signals.done.emit(result, None)


# -- tira de planos -------------------------------------------------------------

class _StripTile(QtWidgets.QFrame):
    """Un plano de la tira: su cuadro y un rotulo. Click lo lleva al visor."""

    clicked = QtCore.Signal(int)

    def __init__(self, frame, parent=None):
        super(_StripTile, self).__init__(parent)
        self.frame = frame
        self.setObjectName("stripTile")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(TOOLTIPS["strip_tile"])
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 4)
        layout.setSpacing(3)
        self.image = QtWidgets.QLabel()
        self.image.setAlignment(Qt.AlignCenter)
        self.image.setStyleSheet("background: %s;" % Color.SURFACE_SUNKEN)
        layout.addWidget(self.image)
        self.caption = QtWidgets.QLabel()
        self.caption.setTextFormat(Qt.RichText)
        self.caption.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.caption)
        self.border = Color.BORDER
        self.viewer_here = False

    def set_image(self, image, width, height):
        self.image.setFixedSize(width, height)
        self.caption.setFixedWidth(width)
        if image is not None and not image.isNull():
            self.image.setPixmap(QtGui.QPixmap.fromImage(image).scaled(
                width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def set_state(self, border=None, viewer_here=None):
        if border is not None:
            self.border = border
        if viewer_here is not None:
            self.viewer_here = viewer_here
        # El plano donde esta el visor lleva el borde mas grueso.
        self.setStyleSheet("QFrame#stripTile { border: %dpx solid %s; border-radius: %dpx; "
                           "background: %s; }" % (
                               3 if self.viewer_here else 1,
                               Color.TEXT_STRONG if self.viewer_here and self.border == Color.BORDER
                               else self.border,
                               Metric.RADIUS_SMALL, Color.SURFACE))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.frame)
        super(_StripTile, self).mousePressEvent(event)


class _StripRow(QtWidgets.QWidget):
    """La tira avisa cuando cambia de ancho, para recalcular sus cuadros.

    El resizeEvent de la ventana llega antes de que el layout le de el ancho
    nuevo a la tira: medir ahi deja el ultimo cuadro cortado.
    """

    resized = QtCore.Signal()

    def resizeEvent(self, event):
        super(_StripRow, self).resizeEvent(event)
        self.resized.emit()


# -- ventana -------------------------------------------------------------------

class LocateWindow(QtWidgets.QWidget):
    """Ubicar y revisar. `on_done(located)` recibe {fila: {tc_in, tc_out,
    thumb, level}} cuando el usuario pasa los resultados a Shot Marks."""

    def __init__(self, sequence, timeline, table, columns, skip_omit, on_done, parent=None, edl=""):
        super(LocateWindow, self).__init__(parent)
        self.setObjectName(WINDOW_NAME)
        self.setWindowFlags(Qt.Window)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setWindowTitle("Locate Shots from Thumbnails")
        self.setStyleSheet(Style.FORM)
        self.sequence = sequence
        self.timeline = timeline
        self.table = table
        self.columns = columns
        self.skip_omit = skip_omit
        self.on_done = on_done
        self.project_name = sequence.project().name()
        self.video = media_path(sequence)
        self.edl = edl or ""
        self.result = None
        # Planos del EDL (en cuadros del video) si el motor lo uso.
        self.segments = []
        self._seg_starts = []
        self.rows = []
        self.current = None
        self.process = None
        self.decisions = load_decisions(self.project_name)
        self._stdout = b""
        self._thumb_cache = {}
        self._thumb_prints = {}
        self._frame_image = None
        self._mode = "side"
        self._viewer = None
        self._signals = None
        self._frame_timer = QtCore.QTimer(self)
        self._frame_timer.setSingleShot(True)
        self._frame_timer.setInterval(90)
        self._frame_timer.timeout.connect(self._grab_frame)
        # Cada pedido de cuadro lleva un numero: si llega uno viejo (el
        # usuario siguio moviendose), se descarta.
        self._frame_request = 0
        self._frame_signals = _Signals()
        self._frame_signals.done.connect(self._frame_ready)
        # Tira de planos entre vecinas: cuadros decodificados por numero de
        # cuadro (no se vuelven a pedir) y los cuadros de la tira mostrada.
        self._strip_cache = {}
        self._strip_tiles = []
        self._strip_pending = set()
        self._strip_signals = _Signals()
        self._strip_signals.done.connect(self._strip_ready)
        self._build()
        apply_ui_font(self)
        self.resize(1180, 880)
        self._shortcuts()

    # armado
    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        margin = Metric.WINDOW_MARGIN
        layout.setContentsMargins(margin, margin, margin, margin)
        layout.setSpacing(Metric.SPACING)
        title = QtWidgets.QLabel("Locate Shots from Thumbnails")
        title.setProperty("lgaTitle", True)
        layout.addWidget(title)
        self.intro = QtWidgets.QLabel(
            "Finds each thumbnail of the sheet in %s and marks the shot from cut to cut." % emphasis(
                os.path.basename(self.video or "the timeline movie")))
        self.intro.setWordWrap(True)
        layout.addWidget(self.intro)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setStyleSheet(Style.PROGRESS)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        layout.addWidget(self.progress)
        self.status = QtWidgets.QLabel("")
        self.status.setTextFormat(Qt.RichText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        body = QtWidgets.QHBoxLayout()
        body.setSpacing(Metric.SPACING)
        left = QtWidgets.QVBoxLayout()
        self.filter_combo = QtWidgets.QComboBox()
        self.filter_combo.setStyleSheet(Style.COMBO)
        self.filter_combo.setFixedHeight(Metric.BUTTON_HEIGHT)
        self.filter_combo.setToolTip(TOOLTIPS["filter"])
        self.filter_combo.currentIndexChanged.connect(self._fill_list)
        left.addWidget(self.filter_combo)
        self.list = QtWidgets.QTableWidget(0, 5)
        self.list.setHorizontalHeaderLabels(["Row", "Shot", "Status", "Result", "Score"])
        self.list.verticalHeader().setVisible(False)
        self.list.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.list.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        # Sin foco: las flechas son de la navegacion de cuadros (atajos).
        self.list.setFocusPolicy(Qt.NoFocus)
        self.list.setStyleSheet(Style.TABLE)
        header = self.list.horizontalHeader()
        header.setStretchLastSection(False)
        for col in range(5):
            header.setSectionResizeMode(col, QtWidgets.QHeaderView.Stretch if col == 2
                                        else QtWidgets.QHeaderView.ResizeToContents)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.itemSelectionChanged.connect(self._row_selected)
        left.addWidget(self.list, 1)
        body.addLayout(left, 2)

        right = QtWidgets.QVBoxLayout()
        right.setSpacing(8)
        self.detail_title = QtWidgets.QLabel("")
        self.detail_title.setTextFormat(Qt.RichText)
        right.addWidget(self.detail_title)
        images = QtWidgets.QHBoxLayout()
        self.thumb_view = QtWidgets.QLabel()
        self.frame_view = QtWidgets.QLabel()
        for view in (self.thumb_view, self.frame_view):
            view.setAlignment(Qt.AlignCenter)
            view.setMinimumSize(THUMB_VIEW_W // 2, THUMB_VIEW_W // 4)
            view.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
            view.setStyleSheet("background: %s;" % Color.SURFACE_SUNKEN)
            images.addWidget(view, 1)
        right.addLayout(images, 1)
        captions = QtWidgets.QHBoxLayout()
        self.thumb_caption = QtWidgets.QLabel("Thumbnail")
        self.frame_caption = QtWidgets.QLabel("Viewer")
        self.frame_caption.setTextFormat(Qt.RichText)
        for caption in (self.thumb_caption, self.frame_caption):
            caption.setAlignment(Qt.AlignCenter)
            captions.addWidget(caption, 1)
        right.addLayout(captions)

        # Tira: la fila anterior y la siguiente ya ubicadas, y los planos del
        # medio. Si el shot esta en orden, es uno de estos.
        self.strip_title = QtWidgets.QLabel("")
        self.strip_title.setTextFormat(Qt.RichText)
        self.strip_title.setToolTip(TOOLTIPS["strip"])
        right.addWidget(self.strip_title)
        # Las dos vecinas quedan fijas en los extremos; solo los planos del
        # medio se desplazan si no entran.
        self.strip_row = _StripRow()
        self.strip_row.resized.connect(self._relayout_strip)
        row_layout = QtWidgets.QHBoxLayout(self.strip_row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(STRIP_SPACING)
        self.strip_prev_box = QtWidgets.QHBoxLayout()
        self.strip_next_box = QtWidgets.QHBoxLayout()
        self.strip_area = QtWidgets.QScrollArea()
        self.strip_area.setWidgetResizable(True)
        self.strip_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.strip_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.strip_area.setStyleSheet(Style.SCROLLBAR)
        strip_widget = QtWidgets.QWidget()
        self.strip_layout = QtWidgets.QHBoxLayout(strip_widget)
        self.strip_layout.setContentsMargins(0, 0, 0, 4)
        self.strip_layout.setSpacing(STRIP_SPACING)
        self.strip_layout.addStretch(1)
        self.strip_area.setWidget(strip_widget)
        row_layout.addLayout(self.strip_prev_box)
        row_layout.addWidget(self.strip_area, 1)
        row_layout.addLayout(self.strip_next_box)
        for box in (self.strip_prev_box, self.strip_next_box):
            box.setAlignment(Qt.AlignTop)
        right.addWidget(self.strip_row)

        controls = QtWidgets.QHBoxLayout()
        self.mode_switch = QtWidgets.QWidget()
        self.mode_switch.setObjectName("modeSwitch")
        self.mode_switch.setAttribute(Qt.WA_StyledBackground, True)
        self.mode_switch.setStyleSheet(Style.PILL_CONTAINER)
        self.mode_switch.setToolTip(TOOLTIPS["mode"])
        mode_layout = QtWidgets.QHBoxLayout(self.mode_switch)
        mode_layout.setContentsMargins(2, 2, 2, 2)
        mode_layout.setSpacing(2)
        self.mode_buttons = {}
        for mode, label in (("side", "Side by side"), ("blend", "Blend"), ("diff", "Difference")):
            button = QtWidgets.QPushButton(label)
            button.setCheckable(True)
            button.clicked.connect(lambda _c=False, m=mode: self._set_mode(m))
            mode_layout.addWidget(button)
            self.mode_buttons[mode] = button
        controls.addWidget(self.mode_switch)
        controls.addStretch(1)
        self.score_label = QtWidgets.QLabel("")
        self.score_label.setTextFormat(Qt.RichText)
        controls.addWidget(self.score_label)
        right.addLayout(controls)
        self._set_mode("side")

        nav = QtWidgets.QHBoxLayout()
        nav.setSpacing(4)
        for key, label, step in (("prev_cut", "|<", "cut-"), ("prev_sec", "<<", -24),
                                 ("prev_frame", "<", -1), ("next_frame", ">", 1),
                                 ("next_sec", ">>", 24), ("next_cut", ">|", "cut+")):
            button = QtWidgets.QPushButton(label)
            button.setStyleSheet(Style.BTN_SMALL)
            button.setToolTip(TOOLTIPS[key])
            button.clicked.connect(lambda _c=False, s=step: self._step(s))
            nav.addWidget(button)
        nav.addSpacing(12)
        self.candidate_buttons = []
        for k in range(5):
            button = QtWidgets.QPushButton("")
            button.setStyleSheet(Style.BTN_SMALL)
            button.setToolTip(TOOLTIPS["candidate"] % (k + 1))
            button.clicked.connect(lambda _c=False, i=k: self._go_candidate(i))
            nav.addWidget(button)
            self.candidate_buttons.append(button)
        nav.addStretch(1)
        right.addLayout(nav)

        actions = QtWidgets.QHBoxLayout()
        actions.addStretch(1)
        self.not_in_cut_button = QtWidgets.QPushButton("Not in Cut")
        self.not_in_cut_button.setStyleSheet(Style.BTN_SECONDARY)
        self.not_in_cut_button.setFixedHeight(Metric.BUTTON_HEIGHT)
        self.not_in_cut_button.setToolTip(TOOLTIPS["not_in_cut"])
        self.not_in_cut_button.clicked.connect(self._not_in_cut)
        actions.addWidget(self.not_in_cut_button)
        self.use_button = QtWidgets.QPushButton("Use This Frame")
        self.use_button.setStyleSheet(Style.BTN_SECONDARY)
        self.use_button.setFixedHeight(Metric.BUTTON_HEIGHT)
        self.use_button.setToolTip(TOOLTIPS["use"])
        self.use_button.clicked.connect(self._use_frame)
        actions.addWidget(self.use_button)
        right.addLayout(actions)
        body.addLayout(right, 3)
        layout.addLayout(body, 1)

        bottom = QtWidgets.QHBoxLayout()
        self.summary = QtWidgets.QLabel("")
        self.summary.setTextFormat(Qt.RichText)
        bottom.addWidget(self.summary, 1)
        cancel = QtWidgets.QPushButton("Cancel")
        cancel.setStyleSheet(Style.BTN_SECONDARY)
        cancel.setFixedHeight(Metric.BUTTON_HEIGHT)
        cancel.setToolTip(TOOLTIPS["cancel"])
        cancel.clicked.connect(self.close)
        bottom.addWidget(cancel)
        self.apply_button = QtWidgets.QPushButton("Use Timecodes")
        self.apply_button.setStyleSheet(Style.BTN_PRIMARY)
        self.apply_button.setFixedHeight(Metric.BUTTON_HEIGHT)
        self.apply_button.setToolTip(TOOLTIPS["apply"])
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self._apply)
        bottom.addWidget(self.apply_button)
        layout.addLayout(bottom)
        self._set_review_enabled(False)

    def _shortcuts(self):
        keys = (
            ("Left", lambda: self._step(-1)), ("Right", lambda: self._step(1)),
            ("Shift+Left", lambda: self._step(-24)), ("Shift+Right", lambda: self._step(24)),
            ("PgUp", lambda: self._step("cut-")), ("PgDown", lambda: self._step("cut+")),
            ("Up", lambda: self._move_row(-1)), ("Down", lambda: self._move_row(1)),
            ("Return", self._use_frame), ("Enter", self._use_frame), ("N", self._not_in_cut),
        )
        for key, func in keys:
            shortcut = QtGui.QShortcut(QtGui.QKeySequence(key), self)
            shortcut.setContext(Qt.WindowShortcut)
            shortcut.activated.connect(func)
        for k in range(5):
            shortcut = QtGui.QShortcut(QtGui.QKeySequence(str(k + 1)), self)
            shortcut.setContext(Qt.WindowShortcut)
            shortcut.activated.connect(lambda i=k: self._go_candidate(i))

    def _set_review_enabled(self, enabled):
        for widget in [self.use_button, self.not_in_cut_button, self.mode_switch] + self.candidate_buttons:
            widget.setEnabled(enabled)

    # arranque
    def start(self):
        missing = missing_tools()
        if missing:
            self._fail("Cannot locate shots. Missing: %s" % ", ".join(missing))
            return
        if not self.video or not os.path.isfile(self.video):
            self._fail("The timeline needs a single movie clip to compare with. Found: %s"
                       % (self.video or "none"))
            return
        sheet = _sheet_module()
        shot_col, status_col = self.columns.get("shot"), self.columns.get("status")
        wanted = []
        titles = []
        for number, values in self.table.rows:
            shot = values[shot_col].strip() if shot_col is not None and shot_col < len(values) else ""
            status = values[status_col].strip() if status_col is not None and status_col < len(values) else ""
            if not sheet.is_shot_name(shot):
                if shot or status:
                    titles.append((number, shot, status))
                continue
            if self.skip_omit and status and sheet.is_omit(status):
                continue
            wanted.append((number, shot, status))
        self._wanted = wanted
        # Una fila con status y sin nombre completo casi seguro es un shot
        # con el nombre en otra columna: queda en el log, fila por fila.
        _logger().info("Filas sin nombre de shot completo (no se ubican): %d, %d con status",
                       len(titles), sum(1 for t in titles if t[2]))
        for number, shot, status in titles:
            _logger().info("  fila %-5s %-16s sin nombre de shot completo | status %s",
                           number, shot or "(vacio)", status or "-")
        self._set_status("Reading the thumbnails of the sheet...")
        path, sheet_name = self.table.path, self.table.sheet
        out_dir = str(cache_root() / "thumbs_src")
        thumbs = _thumbs_module()

        def extract():
            return thumbs.extract_thumbs(path, sheet_name, [w[0] for w in wanted], out_dir)

        self._signals = _Signals()
        self._signals.done.connect(self._thumbs_ready)
        QtCore.QThreadPool.globalInstance().start(_Job(extract, self._signals))

    @QtCore.Slot(object, object)
    def _thumbs_ready(self, found, error):
        if error is not None:
            _logger().exception("No se pudieron leer los thumbs")
            self._fail("Could not read the thumbnails: %s" % error)
            return
        rows = []
        for number, shot, status in self._wanted:
            if number in found:
                rows.append({"row": number, "shot": shot, "status": status,
                             "sha1": found[number]["sha1"], "file": found[number]["file"]})
        self._statuses = {r["row"]: r["status"] for r in rows}
        _logger().info("Filas a ubicar: %d (de %d con shot; %d sin thumb)", len(rows),
                       len(self._wanted), len(self._wanted) - len(rows))
        if not rows:
            self._fail("No shot of this sheet has a thumbnail.")
            return
        root = cache_root()
        (root / "jobs").mkdir(parents=True, exist_ok=True)
        job_path = root / "jobs" / "job.json"
        self.result_path = str(root / "jobs" / "result.json")
        job = {"ffmpeg": str(FFMPEG), "ffprobe": str(FFPROBE), "video": self.video,
               "cache_dir": str(root), "rows": rows, "decisions": self.decisions,
               "out": self.result_path, "workers": min(8, os.cpu_count() or 2),
               "edl": self.edl}
        with open(str(job_path), "w", encoding="utf-8", newline="\n") as handle:
            json.dump(job, handle)
        self.process = QtCore.QProcess(self)
        self.process.setProcessChannelMode(QtCore.QProcess.SeparateChannels)
        self.process.readyReadStandardOutput.connect(self._read_stdout)
        self.process.finished.connect(self._finished)
        self._t0 = time.time()
        _logger().info("Motor: %s %s %s | EDL: %s", PYTHON, ENGINE, job_path, self.edl or "-")
        self.process.start(str(PYTHON), ["-I", str(ENGINE), str(job_path)])
        self._set_status("Starting...")

    def _read_stdout(self):
        self._stdout += bytes(self.process.readAllStandardOutput())
        while b"\n" in self._stdout:
            line, self._stdout = self._stdout.split(b"\n", 1)
            try:
                event = json.loads(line.decode("utf-8", "replace"))
            except ValueError:
                continue
            if event.get("event") == "progress":
                total = max(1, int(event.get("total") or 1))
                done = int(event.get("done") or 0)
                self.progress.setMaximum(total)
                self.progress.setValue(done)
                label = STAGE_LABELS.get(event.get("stage"), event.get("stage"))
                text = "%s: %d %%" % (label, 100 * done // total)
                if event.get("stage") == "index" and event.get("elapsed") and done:
                    left = event["elapsed"] * (total - done) / float(done)
                    text += " &middot; about %s left" % _duration(left)
                self._set_status(text)
            elif event.get("event") == "error":
                self._error_message = event.get("message")

    def _finished(self, code, _status=None):
        if code != 0 or not os.path.isfile(self.result_path):
            message = getattr(self, "_error_message", "") or bytes(
                self.process.readAllStandardError()).decode("utf-8", "replace")[-400:]
            _logger().error("El motor fallo (%s): %s", code, message)
            self._fail("Locating failed: %s" % message)
            return
        with open(self.result_path, encoding="utf-8") as handle:
            self.result = json.load(handle)
        self.fps = int(round(float(self.result["fps"])))
        # Los TC ubicados se miden contra el TC del clip segun NKS, que es el
        # que resta el plan de Shot Marks. El del archivo (ffprobe) puede ser
        # otro: un MP4 con TC 00:59:50:00 que NKS lee como 00:00:00:00.
        file_tc = _sheet_module().parse_timecode(self.result.get("timecode") or "", self.fps) or 0
        nks_tc = getattr(self.timeline, "media_tc", None)
        self.tc0 = nks_tc if nks_tc is not None else file_tc
        if nks_tc is not None and nks_tc != file_tc:
            _logger().warning("TC del archivo %s distinto del de NKS %s: se usa el de NKS",
                              self.result.get("timecode"), _sheet_module().format_timecode(nks_tc, self.fps))
        self.cuts = self.result.get("cuts") or []
        edl = self.result.get("edl") or {}
        if edl.get("used"):
            self.segments = self.result.get("segments") or []
            self._seg_starts = [seg["in"] for seg in self.segments]
        self.rows = self.result["rows"]
        for r in self.rows:
            r["status"] = self._statuses.get(r["row"], "")
        _logger().info("Motor listo en %.1f s: %s | EDL %s", time.time() - self._t0,
                       self.result["levels"], {k: v for k, v in edl.items() if k != "cuts"})
        self.progress.setValue(self.progress.maximum())
        self.progress.hide()
        self._set_status("Done in %s. Review the doubtful ones: select a row, step frames with "
                         "the arrows, Enter to use the frame, N if it is not in the cut. Then "
                         "Use Timecodes adds the marks.%s"
                         % (_duration(time.time() - self._t0), _edl_status(edl)))
        self._connect_viewer()
        self._refresh_filters()
        self._set_review_enabled(True)
        self.apply_button.setEnabled(True)
        self._update_summary()

    def _fail(self, text):
        self.progress.hide()
        self._set_status(_colored(text, Color.ERROR_TEXT))

    # lista
    def _refresh_filters(self):
        counts = {}
        for r in self.rows:
            counts[r["level"]] = counts.get(r["level"], 0) + 1
        current = self.filter_combo.currentData()
        self.filter_combo.blockSignals(True)
        self.filter_combo.clear()
        self.filter_combo.addItem("To review (%d)" % counts.get("review", 0), "review")
        self.filter_combo.addItem("Not found (%d)" % (counts.get("not_found", 0)
                                                      + counts.get("not_in_cut", 0)), "missing")
        self.filter_combo.addItem("Accepted (%d)" % (counts.get("auto", 0)
                                                     + counts.get("confirmed", 0)), "ok")
        self.filter_combo.addItem("All (%d)" % len(self.rows), "all")
        index = self.filter_combo.findData(current) if current else 0
        self.filter_combo.setCurrentIndex(max(index, 0))
        self.filter_combo.blockSignals(False)
        self._fill_list()

    def _visible_rows(self):
        mode = self.filter_combo.currentData()
        if mode == "review":
            rows = [r for r in self.rows if r["level"] == "review"]
        elif mode == "missing":
            rows = [r for r in self.rows if r["level"] in ("not_found", "not_in_cut")]
        elif mode == "ok":
            rows = [r for r in self.rows if r["level"] in ("auto", "confirmed")]
        else:
            rows = sorted(self.rows, key=lambda r: (LEVEL_ORDER.get(r["level"], 9), r["row"]))
        return rows

    def _fill_list(self, *_args):
        if not self.rows:
            return
        keep = self.current["row"] if self.current else None
        self._shown = self._visible_rows()
        self.list.blockSignals(True)
        self.list.setRowCount(len(self._shown))
        select = 0
        for index, r in enumerate(self._shown):
            level_color = {"auto": Color.OK_TEXT, "confirmed": Color.OK_TEXT,
                           "review": Color.WARNING_TEXT}.get(r["level"], Color.ERROR_TEXT)
            values = (str(r["row"]), r["shot"], r.get("status", ""), LEVEL_LABELS.get(r["level"], r["level"]),
                      "%.2f" % r["score"] if r.get("score") else "")
            for col, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(value)
                if col == 3:
                    item.setForeground(QtGui.QBrush(QtGui.QColor(level_color)))
                self.list.setItem(index, col, item)
            self.list.setRowHeight(index, Metric.ROW_HEIGHT)
            if r["row"] == keep:
                select = index
        self.list.blockSignals(False)
        if self._shown:
            self.list.selectRow(select)
            self._row_selected()

    def _move_row(self, delta):
        if not getattr(self, "_shown", None):
            return
        rows = self.list.selectionModel().selectedRows()
        index = rows[0].row() if rows else 0
        self.list.selectRow(min(max(index + delta, 0), len(self._shown) - 1))

    def _row_selected(self):
        rows = self.list.selectionModel().selectedRows()
        if not rows or not getattr(self, "_shown", None):
            return
        self.current = self._shown[rows[0].row()]
        r = self.current
        note = (" &middot; " + _colored(r["note"], Color.WARNING_TEXT)) if r.get("note") else ""
        shot = r.get("edl") or {}
        clip = (" &middot; " + _colored("%s (EDL event %s)" % (shot["clip"], shot["event"]),
                                        Color.TEXT_DIM)) if shot else ""
        self.detail_title.setText("%s &nbsp;row %d &middot; %s%s%s" % (
            emphasis(r["shot"]), r["row"], LEVEL_LABELS.get(r["level"], r["level"]), clip, note))
        for k, button in enumerate(self.candidate_buttons):
            cands = r.get("candidates") or []
            if k < len(cands):
                button.setText("%d &middot; %.2f".replace("&middot;", "·") % (k + 1, cands[k][1]))
                button.setEnabled(True)
            else:
                button.setText(str(k + 1))
                button.setEnabled(False)
        self._fill_strip()
        self._show_thumb()
        if r.get("frame") is not None:
            self._go_media_frame(int(r["frame"]))

    # visor
    def _connect_viewer(self):
        viewer = hiero.ui.currentViewer()
        if viewer is None:
            return
        try:
            viewer.timeChanged.connect(self._time_changed)
            self._viewer = viewer
        except Exception as exc:
            _logger().warning("No se pudo seguir el visor: %s", exc)

    def _time_changed(self, *_args):
        self._frame_timer.start()

    def _timeline_frame(self, media_frame):
        reference = self.timeline.media_start if self.timeline.media_start is not None else self.timeline.start
        return self.tc0 + media_frame - reference

    def _media_frame(self, timeline_frame):
        reference = self.timeline.media_start if self.timeline.media_start is not None else self.timeline.start
        return timeline_frame + reference - self.tc0

    def _go_media_frame(self, frame):
        viewer = self._viewer or hiero.ui.currentViewer()
        if viewer is None:
            return
        try:
            if viewer.player().sequence() is not self.sequence and \
                    viewer.player().sequence().name() != self.sequence.name():
                viewer.setSequence(self.sequence, 0)
        except Exception:
            pass
        viewer.setTime(int(self._timeline_frame(frame)))
        self._frame_timer.start()

    def _current_media_frame(self):
        viewer = self._viewer or hiero.ui.currentViewer()
        if viewer is None:
            return None
        return self._media_frame(int(viewer.time()))

    def _step(self, step):
        frame = self._current_media_frame()
        if frame is None or not self.rows:
            return
        if step == "cut+":
            import bisect
            k = bisect.bisect_right(self.cuts, frame)
            target = self.cuts[k] if k < len(self.cuts) else frame
        elif step == "cut-":
            import bisect
            k = bisect.bisect_left(self.cuts, frame)
            target = self.cuts[k - 1] if k > 0 else 0
        else:
            target = frame + step
        self._go_media_frame(max(0, min(int(self.result["frames"]) - 1, target)))

    def _go_candidate(self, index):
        if not self.current:
            return
        cands = self.current.get("candidates") or []
        if index < len(cands):
            self._go_media_frame(int(cands[index][0]))

    def _grab_frame(self):
        """Decodifica del MOV el cuadro donde esta el playhead, en otro hilo.

        No se usa viewer.image(): llamada mientras el visor todavia decodifica
        el cuadro nuevo (90 ms despues de setTime) tiro abajo NKS 16 con un
        access violation. Medido en una instancia aparte con un MOV ProRes.
        """
        frame = self._current_media_frame()
        if frame is None or not self.result:
            return
        self._frame_request += 1
        request = self._frame_request
        width, height = int(self.result.get("width") or 16), int(self.result.get("height") or 9)
        out_h = max(2, 2 * int(round(FRAME_W * height / float(width) / 2)))
        args = [str(FFMPEG), "-v", "error", "-ss", "%.6f" % (frame / float(self.result["fps"])),
                "-i", self.video, "-frames:v", "1", "-an",
                "-vf", "scale=%d:%d:flags=area,format=rgb24" % (FRAME_W, out_h),
                "-f", "rawvideo", "-"]

        def decode():
            data = subprocess.run(args, capture_output=True, check=True,
                                  creationflags=CREATE_NO_WINDOW).stdout
            return request, frame, data, out_h

        QtCore.QThreadPool.globalInstance().start(_Job(decode, self._frame_signals))

    @QtCore.Slot(object, object)
    def _frame_ready(self, result, error):
        if error is not None:
            _logger().warning("No se pudo leer el cuadro del video: %s", error)
            return
        request, frame, data, out_h = result
        if request != self._frame_request or len(data) < FRAME_W * out_h * 3:
            return
        image = QtGui.QImage(data, FRAME_W, out_h, FRAME_W * 3, QtGui.QImage.Format_RGB888).copy()
        self._frame_image = image
        self._mark_strip(frame)
        if frame is not None:
            self.frame_caption.setText("Viewer &middot; %s" % _sheet_module().format_timecode(
                self.tc0 + frame, self.fps))
        self._render()

    # tira de planos entre vecinas
    def _strip_aspect(self):
        width, height = int(self.result.get("width") or 16), int(self.result.get("height") or 9)
        return height / float(width)

    def _strip_size(self):
        """Ancho y alto de cada cuadro: los mas grandes que dejan ver toda la tira."""
        count = max(1, len(self._strip_tiles))
        room = self.strip_row.width()
        # 6 px de margen interno, hasta 6 de borde y 2 de redondeo por cuadro.
        width = (room - STRIP_SPACING * (count - 1)) // count - 14 if room > 50 else STRIP_TILE_W
        width = max(STRIP_TILE_MIN_W, min(STRIP_TILE_W, width))
        return width, max(2, int(round(width * self._strip_aspect())))

    def _relayout_strip(self):
        if not self._strip_tiles:
            self.strip_row.setFixedHeight(0)
            return
        width, height = self._strip_size()
        for tile in self._strip_tiles:
            tile.set_image(self._strip_cache.get(tile.frame), width, height)
        bar = self.strip_area.horizontalScrollBar().sizeHint().height()
        self.strip_row.setFixedHeight(self._strip_tiles[0].sizeHint().height() + bar + 6)

    def _fill_strip(self):
        """Arma la tira de la fila elegida: vecinas, planos del medio, rotulos."""
        for tile in self._strip_tiles:
            tile.setParent(None)
            tile.deleteLater()
        self._strip_tiles = []
        r = self.current
        if not r or not self.result:
            self.strip_title.setText("")
            self._relayout_strip()
            return
        sheet = _sheet_module()
        strip = sheet.strip_shots(self.rows, self.cuts, int(self.result["frames"]), r["row"],
                                  STRIP_LIMIT)
        if not strip["shots"]:
            self.strip_title.setText("")
            self._relayout_strip()
            return
        between = sum(1 for shot in strip["shots"] if shot["role"] == "between") + strip["hidden"]
        if strip["prev"] and strip["next"]:
            text = "%d %s between %s and %s" % (
                between, "shot" if between == 1 else "shots",
                _colored("row %d" % strip["prev"], STRIP_COLORS["prev"]),
                _colored("row %d" % strip["next"], STRIP_COLORS["next"]))
        elif strip["prev"]:
            text = "Shots after %s" % _colored("row %d" % strip["prev"], STRIP_COLORS["prev"])
        elif strip["next"]:
            text = "Shots before %s" % _colored("row %d" % strip["next"], STRIP_COLORS["next"])
        else:
            text = "Shots around this row"
        if strip["hidden"]:
            text += _colored(" &middot; %d in the middle not shown" % strip["hidden"], Color.TEXT_DIM)
        text += _colored(" &middot; click one to see it in the viewer", Color.TEXT_DIM)
        self.strip_title.setText(text)
        candidates = [int(c[0]) for c in r.get("candidates") or []]
        viewer = self._current_media_frame()
        insert_at = 0
        for shot in strip["shots"]:
            # El cuadro del plano: el candidato de la fila que cae ahi, o el medio.
            inside = [c for c in candidates if shot["start"] <= c <= shot["end"]]
            frame = inside[0] if inside else (shot["start"] + shot["end"]) // 2
            tile = _StripTile(frame)
            tile.clicked.connect(self._go_media_frame)
            tile.shot = shot
            tile.caption.setText(self._strip_caption(shot, r))
            role = "current" if shot["current"] else shot["role"]
            tile.set_state(border=STRIP_COLORS.get(role, Color.BORDER),
                           viewer_here=viewer is not None and shot["start"] <= viewer <= shot["end"])
            if shot["role"] == "prev":
                self.strip_prev_box.addWidget(tile)
            elif shot["role"] == "next":
                self.strip_next_box.addWidget(tile)
            else:
                self.strip_layout.insertWidget(insert_at, tile)
                insert_at += 1
            self._strip_tiles.append(tile)
        apply_ui_font(self.strip_row)
        self._relayout_strip()
        for tile in self._strip_tiles:
            if tile.frame not in self._strip_cache:
                self._decode_strip_frame(tile.frame)

    def _strip_caption(self, shot, r):
        fmt = _sheet_module().format_timecode
        labels = []
        if shot["role"] == "prev":
            labels.append(_colored("row %d" % shot["rows"][0] if shot["rows"] else "before",
                                   STRIP_COLORS["prev"]))
        elif shot["role"] == "next":
            labels.append(_colored("row %d" % shot["rows"][0] if shot["rows"] else "after",
                                   STRIP_COLORS["next"]))
        if shot["current"]:
            labels.append(_colored("row %d now" % r["row"], STRIP_COLORS["current"]))
        others = [n for n in shot["rows"] if shot["role"] == "between" or n != shot["rows"][0]]
        if others:
            labels.append(_colored("row %s" % ", ".join(str(n) for n in others[:2]), Color.TEXT_DIM))
        seconds = (shot["end"] - shot["start"] + 1) / float(self.fps)
        first = " &middot; ".join(labels) if labels else "&nbsp;"
        return "%s<br>%s" % (first, _colored("%s &middot; %.1f s" % (
            fmt(self.tc0 + shot["start"], self.fps)[:8], seconds), Color.TEXT_DIM))

    def _decode_strip_frame(self, frame):
        if frame in self._strip_pending:
            return
        self._strip_pending.add(frame)
        out_h = max(2, 2 * int(round(STRIP_DECODE_W * self._strip_aspect() / 2)))
        args = [str(FFMPEG), "-v", "error", "-ss", "%.6f" % (frame / float(self.result["fps"])),
                "-i", self.video, "-frames:v", "1", "-an",
                "-vf", "scale=%d:%d:flags=area,format=rgb24" % (STRIP_DECODE_W, out_h),
                "-f", "rawvideo", "-"]

        def decode():
            data = subprocess.run(args, capture_output=True, check=True,
                                  creationflags=CREATE_NO_WINDOW).stdout
            return frame, data, out_h

        QtCore.QThreadPool.globalInstance().start(_Job(decode, self._strip_signals))

    @QtCore.Slot(object, object)
    def _strip_ready(self, result, error):
        if error is not None:
            _logger().warning("No se pudo leer un cuadro de la tira: %s", error)
            return
        frame, data, out_h = result
        self._strip_pending.discard(frame)
        if len(data) < STRIP_DECODE_W * out_h * 3:
            return
        image = QtGui.QImage(data, STRIP_DECODE_W, out_h, STRIP_DECODE_W * 3,
                             QtGui.QImage.Format_RGB888).copy()
        self._strip_cache[frame] = image
        width, height = self._strip_size()
        for tile in self._strip_tiles:
            if tile.frame == frame:
                tile.set_image(image, width, height)

    def _mark_strip(self, frame):
        """Resalta el plano de la tira donde quedo el visor."""
        for tile in self._strip_tiles:
            here = frame is not None and tile.shot["start"] <= frame <= tile.shot["end"]
            if here != tile.viewer_here:
                tile.set_state(viewer_here=here)
                if here and tile.shot["role"] == "between":
                    self.strip_area.ensureWidgetVisible(tile)

    # imagenes
    def _thumb_image(self):
        r = self.current
        if not r:
            return None
        path = r.get("thumb")
        if path not in self._thumb_cache:
            image = QtGui.QImage(path) if path else QtGui.QImage()
            self._thumb_cache[path] = image
        return self._thumb_cache[path]

    def _thumb_rect(self, image):
        """Area de imagen del thumb en la escala del JPG chico."""
        r = self.current
        rect, size = r.get("rect"), r.get("size")
        if not rect or not size or image.isNull():
            return None
        k = image.width() / float(size[0])
        return [int(round(v * k)) for v in rect]

    def _show_thumb(self):
        image = self._thumb_image()
        if image is None or image.isNull():
            self.thumb_view.setText("No thumbnail")
            return
        self._render()

    def _set_mode(self, mode):
        self._mode = mode
        for key, button in self.mode_buttons.items():
            button.setChecked(key == mode)
            button.setStyleSheet(Style.PILL_ACTIVE if key == mode else Style.PILL_INACTIVE)
        self._render()

    def _render(self):
        thumb = self._thumb_image()
        frame = self._frame_image
        if thumb is not None and not thumb.isNull():
            self.thumb_view.setPixmap(QtGui.QPixmap.fromImage(thumb).scaled(
                self.thumb_view.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        if frame is None:
            return
        shown = frame
        rect = self._thumb_rect(thumb) if thumb is not None else None
        if self._mode != "side" and rect is not None:
            picture = thumb.copy(QtCore.QRect(*rect)).scaled(frame.size(), Qt.IgnoreAspectRatio,
                                                             Qt.SmoothTransformation)
            shown = frame.convertToFormat(QtGui.QImage.Format_RGB32)
            painter = QtGui.QPainter(shown)
            if self._mode == "blend":
                painter.setOpacity(0.5)
            else:
                painter.setCompositionMode(QtGui.QPainter.CompositionMode_Difference)
            painter.drawImage(0, 0, picture)
            painter.end()
        self.frame_view.setPixmap(QtGui.QPixmap.fromImage(shown).scaled(
            self.frame_view.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        if rect is not None:
            key = (self.current["sha1"], tuple(rect))
            if key not in self._thumb_prints:
                self._thumb_prints[key] = _gray_print(thumb, rect)
            score = similarity(self._thumb_prints[key], _gray_print(frame))
            color = Color.OK_TEXT if score >= 0.9 else (Color.WARNING_TEXT if score >= 0.7 else Color.ERROR_TEXT)
            self.score_label.setText("Similarity %s" % _colored("%.2f" % score, color))

    # decisiones
    def _use_frame(self):
        r = self.current
        frame = self._current_media_frame()
        if r is None or frame is None or not self.result:
            return
        self._set_row(r, frame, "confirmed")
        self._advance()

    def _not_in_cut(self):
        r = self.current
        if r is None or not self.result:
            return
        r["level"] = "not_in_cut"
        _sheet_module().store_decision(self.decisions, r["sha1"], r["shot"],
                                       {"state": "not_in_cut", "video": self.result["video_key"]})
        save_decisions(self.project_name, self.decisions)
        _logger().info("Fila %s %s: no esta en el corte", r["row"], r["shot"])
        self._advance()

    def _set_row(self, r, frame, level):
        edl = _edl_module()
        seg = edl.segment_at(self.segments, frame, self._seg_starts) if self.segments else None
        if seg is not None:
            # Plano del EDL: exacto, sin el tope de 60 s.
            start, end = seg["in"], seg["out"]
            r["edl"] = edl.source_info(seg, frame, self.fps)
        else:
            start, end = self._cut_range(frame)
            if end - start + 1 > 60 * self.fps:
                start = end = frame
            r.pop("edl", None)
        r.update({"frame": frame, "in": start, "out": end, "level": level})
        d8, g32 = frame_prints(self.result["index_folder"], frame)
        _sheet_module().store_decision(self.decisions, r["sha1"], r["shot"], {
            "state": "confirmed", "frame": frame, "video": self.result["video_key"],
            "d8": d8, "g32": g32})
        save_decisions(self.project_name, self.decisions)
        _logger().info("Fila %s %s: cuadro %d confirmado (plano %d-%d)", r["row"], r["shot"],
                       frame, start, end)

    def _advance(self):
        index = self.list.selectionModel().selectedRows()
        position = index[0].row() if index else 0
        self._refresh_filters()
        if self._shown:
            self.list.selectRow(min(position, len(self._shown) - 1))
        self._update_summary()

    def _update_summary(self):
        marked = [r for r in self.rows if r["level"] in ("auto", "confirmed", "review")]
        review = sum(1 for r in self.rows if r["level"] == "review")
        text = "%s shots will be marked" % emphasis(str(len(marked)))
        if review:
            text += " &middot; " + _colored(
                "%d to review are marked as unconfirmed" % review, Color.WARNING_TEXT)
        else:
            # Revisar no escribe nada en el timeline: sin este aviso, terminar
            # la revision parecia el final.
            text += " &middot; " + _colored(
                "Nothing left to review: press Use Timecodes to add the marks", Color.OK_TEXT)
        self.summary.setText(text)

    def _apply(self):
        if not self.result:
            return
        sheet = _sheet_module()
        fmt = sheet.format_timecode
        marks = [{"row": r["row"], "shot": r["shot"], "frame": int(r["frame"]),
                  "in": int(r["in"]), "out": int(r["out"])}
                 for r in self.rows
                 if r["level"] in ("auto", "confirmed", "review") and r.get("in") is not None
                 and r.get("frame") is not None]
        scores = self._cut_scores()
        with_edl = {r["row"] for r in self.rows if r.get("edl")}
        for mark in marks:
            # Marca de un cuadro por un "plano" de mas de 60 s (scdet no vio
            # los cortes): se le da el tramo entre los cortes debiles.
            if mark["in"] != mark["out"] or mark["row"] in with_edl:
                continue
            start, end = self._cut_range(mark["frame"])
            if end - start + 1 > 60 * self.fps:
                mark["in"], mark["out"] = sheet.soft_shot_range(scores, mark["frame"], start, end)
                _logger().info("Fila %s: plano de %d cuadros sin corte claro, marca %d-%d",
                               mark["row"], end - start + 1, mark["in"], mark["out"])
        for row_a, row_b, cut in sheet.split_shared_ranges(marks, scores):
            _logger().info("Plano compartido: filas %s y %s partidas en el cuadro %d", row_a, row_b, cut)
        ranges = {m["row"]: m for m in marks}
        located = {}
        for r in self.rows:
            if r["row"] not in ranges:
                continue
            span = ranges[r["row"]]
            located[r["row"]] = {
                "tc_in": fmt(self.tc0 + span["in"], self.fps),
                # Exclusivo, como el REC TC OUT de una planilla de montaje.
                "tc_out": fmt(self.tc0 + span["out"] + 1, self.fps),
                "thumb": r.get("thumb") or "",
                "level": "%s %.2f" % (r["level"], r.get("score") or 0.0),
                "clip": _sheet_module().clip_text(r.get("edl")),
            }
        _logger().info("Pasando %d filas ubicadas a Shot Marks", len(located))
        callback = self.on_done
        self.on_done = None
        self.close()
        if callback is not None:
            callback(located)

    def _cut_range(self, frame):
        """(in, out) del plano de scdet que contiene `frame`."""
        import bisect
        k = bisect.bisect_right(self.cuts, frame)
        start = self.cuts[k - 1] if k > 0 else 0
        end = (self.cuts[k] - 1) if k < len(self.cuts) else int(self.result["frames"]) - 1
        return start, end

    def _cut_scores(self):
        """Puntajes de scdet por cuadro (scd.bin del indice), o [] si no estan."""
        import array
        path = os.path.join(self.result.get("index_folder") or "", "scd.bin")
        scores = array.array("f")
        try:
            with open(path, "rb") as handle:
                scores.frombytes(handle.read())
        except OSError:
            _logger().warning("Sin puntajes de cortes (%s): los planos compartidos se parten al medio",
                              path)
        return scores

    def closeEvent(self, event):
        if self.process is not None and self.process.state() != QtCore.QProcess.NotRunning:
            self.process.kill()
            self.process.waitForFinished(2000)
        if self._viewer is not None:
            try:
                self._viewer.timeChanged.disconnect(self._time_changed)
            except Exception:
                pass
        super(LocateWindow, self).closeEvent(event)

    def resizeEvent(self, event):
        super(LocateWindow, self).resizeEvent(event)
        self._render()

    def _set_status(self, text):
        self.status.setText(text)


def _colored(text, color):
    return '<span style="color:%s">%s</span>' % (color, text)


def _edl_status(edl):
    """Una linea sobre el EDL para el estado de la ventana ('' sin EDL)."""
    if not edl.get("path"):
        return ""
    name = os.path.basename(edl["path"])
    if edl.get("used"):
        return "<br>Cuts from %s: %d of %d match the picture to the frame%s." % (
            emphasis(name), edl.get("matched", 0), edl.get("edl_cuts", 0),
            "" if not edl.get("offset") else " (EDL shifted %+d frames)" % edl["offset"])
    return "<br>" + _colored("%s not used: %s. Cuts were detected in the picture." % (
        name, edl.get("reason", "it does not match the movie")), Color.WARNING_TEXT)


def _duration(seconds):
    seconds = int(round(seconds))
    if seconds < 60:
        return "%d s" % seconds
    return "%d min %02d s" % (seconds // 60, seconds % 60)


def open_window(sequence, timeline, table, columns, skip_omit, on_done, edl=""):
    """Abre la ventana (una sola) y arranca el motor."""
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if widget.objectName() == WINDOW_NAME:
            widget.close()
    _logger()
    window = LocateWindow(sequence, timeline, table, columns, skip_omit, on_done,
                          hiero.ui.mainWindow(), edl=edl)
    window.show()
    window.start()
    return window
