"""
____________________________________________________________________

  LGA_NKS_ShotMarks v1.01 | Lega

  Shot Marks: lee una planilla de breakdown (xlsx o csv) y pone un tag
  de rango por shot en el timeline activo, en el REC TC de la planilla,
  con el nombre del shot. Viewer > Next Tag / Previous Tag
  (Alt+Shift+Right / Left) salta de shot en shot.

  Existe para cruzar planilla contra corte cada vez que llega un update:
  re-correrla reemplaza solo los tags que puso ella (metadata
  tag.lga_shotmarks) y deja intactos los tags hechos a mano.

  Timecode: si el timeline es un solo clip de referencia (el MOV del
  episodio), el REC TC se mide contra el TC de esa media, que es el que
  se ve quemado en la imagen; el TC de la secuencia puede venir distinto
  (01:00:00:00 contra 00:59:50:00 de la media). Opcionalmente alinea el
  TC de inicio de la secuencia al de la media. Todo en un solo undo.

  Nucleo sin host (lectura y plan): LGA_NKS_ShotMarks_Sheet.py.
  Log de cada corrida: logs/DebugPy_LGA_NKS_ShotMarks.log.

  v1.01: Columnas de descripcion, escena, vendor y categoria; cada tag
         guarda la info de su fila para Previous/Next Mark
         (LGA_NKS_ShotMarks_Nav).
  v1.00: Version inicial.
____________________________________________________________________
"""

import configparser
import importlib.util
import logging
import os
import re
import sys
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
from LGA_NKS_Shared.LGA_NKS_ArrowComboBox import ArrowComboBox
from LGA_NKS_Shared.LGA_NKS_MessageBox import show_error, show_info, show_warning

DEBUG = False

TAG_KEY = "tag.lga_shotmarks"
TAG_ICON = "icons:Tag.png"
UNDO_NAME = "Shot Marks from Sheet"
NONE_LABEL = "(none)"
ALL_EPISODES = "All"
PREVIEW_ROWS = 10

CONFIG_FILE_NAME = "ShotMarks.ini"
CONFIG_SECTION = "Settings"

# Tooltips en castellano, separados del widget para que pasar a bilingue sea
# un cambio de datos.
TOOLTIPS = {
    "browse": "Elegir la planilla (.xlsx o .csv).",
    "sheet": "Hoja de la planilla. Se sugiere la que tiene columnas de shot y REC TC.",
    "shot": "Columna con el nombre del shot: es el nombre del tag.",
    "tc_in": "Timecode de entrada del shot en el montaje (REC TC IN, no el TC de camara).",
    "tc_out": "Timecode de salida. Es exclusivo: el tag termina un cuadro antes.",
    "episode": "Columna de episodio, para filtrar los shots de este timeline.",
    "status": "Columna de status, para saltear los Omit.",
    "note": "Columna del brief: va a la nota del tag y a la ventana de Next Mark.",
    "description": "Descripcion del shot, para la ventana de Next Mark.",
    "scene": "Escena, para la ventana de Next Mark.",
    "vendor": "Vendor, para la ventana de Next Mark.",
    "category": "Categoria del shot, para la ventana de Next Mark.",
    "episode_filter": "Solo los shots de este episodio. Se sugiere el que aparece en el nombre del timeline.",
    "skip_omit": "No marcar los shots con status Omit.",
    "reference": "Contra que timecode se mide el REC TC de la planilla.",
    "align": "Cambia el TC de inicio del timeline al de la media, para que el timeline muestre el mismo TC que la imagen. Se puede deshacer.",
}

_sheet = None


def _sheet_module():
    """Carga LGA_NKS_ShotMarks_Sheet desde la carpeta de este script."""
    global _sheet
    if _sheet is None:
        path = Path(__file__).resolve().parent / "LGA_NKS_ShotMarks_Sheet.py"
        spec = importlib.util.spec_from_file_location("LGA_NKS_ShotMarks_Sheet", str(path))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _sheet = module
    return _sheet


# -- log y preferencias ----------------------------------------------------

def _logger():
    log_dir = Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(exist_ok=True)
    logger = logging.getLogger("LGA_NKS_ShotMarks")
    logger.setLevel(logging.DEBUG)
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
    logger.propagate = False
    handler = logging.FileHandler(str(log_dir / "DebugPy_LGA_NKS_ShotMarks.log"),
                                  mode="w", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    if DEBUG:
        logger.addHandler(logging.StreamHandler())
    return logger


def log_path():
    return str(Path(__file__).resolve().parent / "logs" / "DebugPy_LGA_NKS_ShotMarks.log")


def _config_path():
    if sys.platform == "win32":
        root = os.getenv("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        root = str(Path.home() / "Library" / "Application Support")
    else:
        root = str(Path.home() / ".config")
    return Path(root) / "LGA" / "HieroTools" / CONFIG_FILE_NAME


def _read_settings():
    config = configparser.ConfigParser()
    try:
        config.read(str(_config_path()), encoding="utf-8")
    except Exception:
        return {}
    return dict(config[CONFIG_SECTION]) if config.has_section(CONFIG_SECTION) else {}


def _write_settings(values):
    path = _config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        config = configparser.ConfigParser()
        config[CONFIG_SECTION] = {k: str(v) for k, v in values.items()}
        with open(str(path), "w", encoding="utf-8", newline="\n") as handle:
            config.write(handle)
    except Exception as exc:
        _logger_ref().warning("No se pudieron guardar las preferencias: %s", exc)


_log = None


def _logger_ref():
    global _log
    if _log is None:
        _log = _logger()
    return _log


# -- timeline --------------------------------------------------------------

class TimelineInfo(object):
    """Lo que hace falta del timeline para ubicar los timecodes."""

    def __init__(self, sequence):
        self.sequence = sequence
        rate = sequence.framerate()
        self.fps_float = float(rate.toFloat())
        self.fps = int(round(self.fps_float))
        self.start = int(sequence.timecodeStart())
        self.duration = int(sequence.duration())
        self.media_start = None
        self.media_clip = ""
        self.media_reason = ""
        self._detect_reference()

    def _detect_reference(self):
        items = []
        for track in self.sequence.videoTracks():
            if track.isEnabled():
                items.extend(track.items())
        if len(items) != 1:
            self.media_reason = "%d video clips: timeline timecode is used" % len(items)
            return
        item = items[0]
        try:
            speed = float(item.playbackSpeed())
        except Exception:
            speed = 1.0
        if abs(speed - 1.0) > 1e-6:
            self.media_reason = "The clip is retimed: timeline timecode is used"
            return
        clip = item.source()
        # TC de la media en el cuadro 0 del timeline.
        self.media_start = (int(clip.timecodeStart()) + int(round(item.sourceIn()))
                            - int(item.timelineIn()))
        self.media_clip = clip.name()

    def timecode(self, frames):
        return _sheet_module().format_timecode(frames, self.fps)


def own_tags(sequence):
    tags = []
    for tag in sequence.tags():
        try:
            if tag.metadata().hasKey(TAG_KEY):
                tags.append(tag)
        except Exception:
            continue
    return tags


def apply_plan(sequence, plan, align_start=None, source_label=""):
    """Reemplaza los tags propios por los del plan, en un solo undo."""
    log = _logger_ref()
    project = sequence.project()
    removed = 0
    with project.beginUndo(UNDO_NAME):
        for tag in own_tags(sequence):
            sequence.removeTag(tag)
            removed += 1
        if align_start is not None and align_start != sequence.timecodeStart():
            log.info("TC de inicio del timeline: %s -> %s", sequence.timecodeStart(), align_start)
            sequence.setTimecodeStart(int(align_start))
        module = _sheet_module()
        for mark in plan.marks:
            tag = hiero.core.Tag(mark.shot, TAG_ICON)
            tag.setNote(mark.note)
            data = tag.metadata()
            for key, value in module.mark_metadata(mark, source_label).items():
                data.setValue(key, value)
            sequence.addTagToRange(tag, int(mark.frame_in), int(mark.frame_out))
    log.info("Aplicado: %d tags nuevos, %d tags propios anteriores reemplazados",
             len(plan.marks), removed)
    for mark in plan.marks:
        log.info("  %-28s %6d-%-6d  TC %s  fila %d", mark.shot, mark.frame_in,
                 mark.frame_out, mark.tc_in, mark.row)
    return removed


def guess_episode(sequence_name, episodes):
    """El episodio que aparece como numero suelto en el nombre del timeline."""
    found = [ep for ep in episodes
             if ep and re.search(r"(?<![0-9])%s(?![0-9])" % re.escape(ep), sequence_name)]
    return found[0] if len(found) == 1 else None


# -- hilo de lectura -------------------------------------------------------

class _Signals(QtCore.QObject):
    done = QtCore.Signal(object, object, object)  # (token, resultado, error)


class _Job(QtCore.QRunnable):
    """Corre una funcion de lectura fuera del hilo de UI."""

    def __init__(self, func, signals, token):
        super(_Job, self).__init__()
        self.func = func
        self.signals = signals
        self.token = token

    def run(self):
        try:
            result = self.func()
        except Exception as exc:
            self.signals.done.emit(self.token, None, exc)
            return
        self.signals.done.emit(self.token, result, None)


# -- dialogo ---------------------------------------------------------------

class ShotMarksDialog(QtWidgets.QDialog):
    def __init__(self, sequence, parent=None):
        super(ShotMarksDialog, self).__init__(parent)
        self.sequence = sequence
        self.timeline = TimelineInfo(sequence)
        self.settings = _read_settings()
        self.table = None
        self.plan = None
        self._jobs = {}
        self._token = 0
        self._loading = False
        self.setWindowTitle("Shot Marks from Sheet")
        self.setStyleSheet(Style.FORM)
        self.setMinimumWidth(720)
        self._build()
        apply_ui_font(self)
        self._restore()

    # armado
    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        margin = Metric.WINDOW_MARGIN
        layout.setContentsMargins(margin, margin, margin, margin)
        layout.setSpacing(Metric.SPACING)

        title = QtWidgets.QLabel("Shot Marks from Sheet")
        title.setProperty("lgaTitle", True)
        layout.addWidget(title)

        intro = QtWidgets.QLabel(
            "Adds a range tag for each shot of the sheet to %s. Jump between them "
            "with Viewer &gt; Next Tag (Alt+Shift+Right). Running it again replaces "
            "only the tags it added." % emphasis(self.sequence.name()))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(Metric.SPACING)
        grid.setVerticalSpacing(6)
        row = 0

        self.path_edit = QtWidgets.QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("Choose a .xlsx or .csv file")
        browse = QtWidgets.QPushButton("Browse")
        browse.setStyleSheet(Style.BTN_SECONDARY)
        browse.setFixedHeight(Metric.BUTTON_HEIGHT)
        browse.setToolTip(TOOLTIPS["browse"])
        browse.clicked.connect(self._browse)
        file_row = QtWidgets.QHBoxLayout()
        file_row.addWidget(self.path_edit, 1)
        file_row.addWidget(browse)
        grid.addWidget(QtWidgets.QLabel("Sheet file"), row, 0)
        grid.addLayout(file_row, row, 1, 1, 3)
        row += 1

        self.sheet_combo = self._combo("sheet")
        self.sheet_combo.currentIndexChanged.connect(self._sheet_changed)
        grid.addWidget(QtWidgets.QLabel("Sheet"), row, 0)
        grid.addWidget(self.sheet_combo, row, 1, 1, 3)
        row += 1

        self.column_combos = {}
        labels = (("shot", "Shot"), ("tc_in", "TC In"), ("tc_out", "TC Out"),
                  ("episode", "Episode"), ("status", "Status"), ("note", "Brief"),
                  ("description", "Description"), ("scene", "Scene"),
                  ("vendor", "Vendor"), ("category", "Category"))
        for index, (role, label) in enumerate(labels):
            combo = self._combo(role)
            combo.currentIndexChanged.connect(self._columns_changed)
            self.column_combos[role] = combo
            grid_row = row + index // 2
            grid_col = (index % 2) * 2
            grid.addWidget(QtWidgets.QLabel(label + " column"), grid_row, grid_col)
            grid.addWidget(combo, grid_row, grid_col + 1)
        row += (len(labels) + 1) // 2

        self.episode_combo = self._combo("episode_filter")
        self.episode_combo.currentIndexChanged.connect(self._refresh_plan)
        grid.addWidget(QtWidgets.QLabel("Episode"), row, 0)
        grid.addWidget(self.episode_combo, row, 1)
        self.skip_omit = QtWidgets.QCheckBox("Skip omitted shots")
        self.skip_omit.setProperty("lgaLabeled", True)
        self.skip_omit.setChecked(True)
        self.skip_omit.setToolTip(TOOLTIPS["skip_omit"])
        self.skip_omit.toggled.connect(self._refresh_plan)
        grid.addWidget(self.skip_omit, row, 2, 1, 2)
        row += 1

        self.reference_combo = self._combo("reference")
        timeline_label = "Timeline timecode (%s)" % self.timeline.timecode(self.timeline.start)
        if self.timeline.media_start is not None:
            self.reference_combo.addItem(
                "Media timecode of %s (%s)" % (self.timeline.media_clip,
                                               self.timeline.timecode(self.timeline.media_start)),
                "media")
        self.reference_combo.addItem(timeline_label, "timeline")
        self.reference_combo.currentIndexChanged.connect(self._reference_changed)
        grid.addWidget(QtWidgets.QLabel("Timecode"), row, 0)
        grid.addWidget(self.reference_combo, row, 1, 1, 3)
        row += 1

        self.align_check = QtWidgets.QCheckBox("")
        self.align_check.setProperty("lgaLabeled", True)
        self.align_check.setToolTip(TOOLTIPS["align"])
        self.align_check.toggled.connect(self._refresh_plan)
        grid.addWidget(self.align_check, row, 1, 1, 3)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        layout.addLayout(grid)

        self.summary = QtWidgets.QLabel("")
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.RichText)
        layout.addWidget(self.summary)

        self.preview = QtWidgets.QTableWidget(0, 5, self)
        self.preview.setHorizontalHeaderLabels(["Row", "Shot", "TC In", "Frames", "Result"])
        self.preview.verticalHeader().setVisible(False)
        self.preview.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.preview.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.preview.setFocusPolicy(Qt.NoFocus)
        self.preview.setStyleSheet(Style.TABLE)
        self.preview.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.preview, 1)

        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch(1)
        cancel = QtWidgets.QPushButton("Cancel")
        cancel.setStyleSheet(Style.BTN_SECONDARY)
        cancel.setFixedHeight(Metric.BUTTON_HEIGHT)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        self.apply_button = QtWidgets.QPushButton("Add Marks")
        self.apply_button.setStyleSheet(Style.BTN_PRIMARY)
        self.apply_button.setFixedHeight(Metric.BUTTON_HEIGHT)
        self.apply_button.setDefault(True)
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self._apply)
        buttons.addWidget(self.apply_button)
        layout.addLayout(buttons)
        self._reference_changed()

    def _combo(self, key):
        combo = ArrowComboBox(self)
        combo.setStyleSheet(Style.COMBO)
        combo.setToolTip(TOOLTIPS[key])
        combo.setFixedHeight(Metric.BUTTON_HEIGHT)
        return combo

    # estado inicial
    def _restore(self):
        index = self.reference_combo.findData(self.settings.get("reference", "media"))
        if index >= 0:
            self.reference_combo.setCurrentIndex(index)
        self.skip_omit.setChecked(self.settings.get("skip_omit", "true") != "false")
        self.align_check.setChecked(self.settings.get("align", "false") == "true")
        last = self.settings.get("last_file", "")
        if last and os.path.isfile(last):
            self._open_file(last)
        else:
            self._set_summary("Choose the breakdown sheet to start.")

    # archivo y hoja
    def _browse(self):
        start = os.path.dirname(self.path_edit.text()) or str(Path.home())
        path, _filter = QtWidgets.QFileDialog.getOpenFileName(
            self, "Choose sheet", start, "Sheets (*.xlsx *.csv)")
        if path:
            self._open_file(path)

    def _run(self, func, callback):
        # El receptor es un metodo del dialogo (un QObject del hilo de UI):
        # asi la conexion es encolada y el callback corre en el hilo de UI.
        # Solo vale el ultimo pedido: si el usuario cambia de hoja mientras se
        # lee la anterior, el resultado viejo se descarta.
        self._token += 1
        token = self._token
        signals = _Signals()
        self._jobs[token] = (signals, callback)
        signals.done.connect(self._job_done)
        QtCore.QThreadPool.globalInstance().start(_Job(func, signals, token))

    @QtCore.Slot(object, object, object)
    def _job_done(self, token, result, error):
        _signals, callback = self._jobs.pop(token, (None, None))
        if callback is not None and token == self._token:
            callback(result, error)

    def _open_file(self, path):
        self.path_edit.setText(path)
        self.table = None
        self._set_busy("Reading sheets...")
        saved = self.settings.get("last_sheet", "") if path == self.settings.get("last_file") else ""
        module = _sheet_module()

        def read():
            sheets = module.list_sheets(path)
            choice = saved if saved in sheets else module.suggest_sheet(path, sheets)
            return sheets, choice

        self._run(read, self._sheets_ready)

    def _sheets_ready(self, result, error):
        if error is not None:
            _logger_ref().error("No se pudo leer el archivo: %s", error)
            self._set_summary("Could not read the file: %s" % error, Color.ERROR_TEXT)
            return
        sheets, choice = result
        self._loading = True
        self.sheet_combo.clear()
        for name in sheets:
            self.sheet_combo.addItem(name or "(CSV)", name)
        index = self.sheet_combo.findData(choice) if choice is not None else -1
        self.sheet_combo.setCurrentIndex(max(index, 0))
        self._loading = False
        self._sheet_changed()

    def _sheet_changed(self, *_args):
        if self._loading or self.sheet_combo.count() == 0:
            return
        path = self.path_edit.text()
        sheet = self.sheet_combo.currentData()
        self._set_busy("Reading %s..." % (sheet or "file"))
        module = _sheet_module()
        self._run(lambda: module.load_table(path, sheet), self._table_ready)

    def _table_ready(self, table, error):
        if error is not None:
            self.table = None
            _logger_ref().warning("Hoja no utilizable: %s", error)
            self._fill_columns([])
            self._set_summary("This sheet cannot be used: %s" % error, Color.WARNING_TEXT)
            self._clear_preview()
            return
        self.table = table
        self._fill_columns(table.headers)
        _logger_ref().info("Planilla: %s | hoja %s | encabezado en fila %d | %d filas",
                           table.path, table.sheet, table.header_row, len(table.rows))
        self._columns_changed()

    def _fill_columns(self, headers):
        module = _sheet_module()
        detected = module.detect_columns(headers) if headers else {}
        self._loading = True
        for role, combo in self.column_combos.items():
            combo.clear()
            if role not in ("shot", "tc_in"):
                combo.addItem(NONE_LABEL, None)
            for index, header in enumerate(headers):
                combo.addItem(header, index)
            saved = self.settings.get("col_" + role, "")
            pick = headers.index(saved) if saved in headers else detected.get(role)
            if pick is not None:
                combo.setCurrentIndex(combo.findData(pick))
        self._loading = False

    def _columns(self):
        return {role: combo.currentData() for role, combo in self.column_combos.items()}

    def _columns_changed(self, *_args):
        if self._loading or self.table is None:
            return
        module = _sheet_module()
        episodes = module.episode_values(self.table, self._columns().get("episode"))
        current = self.episode_combo.currentText()
        self._loading = True
        self.episode_combo.clear()
        self.episode_combo.addItem(ALL_EPISODES, None)
        for episode in episodes:
            self.episode_combo.addItem(episode, episode)
        guess = current if current in episodes else guess_episode(self.sequence.name(), episodes)
        if guess:
            self.episode_combo.setCurrentIndex(self.episode_combo.findData(guess))
        self._loading = False
        self._refresh_plan()

    def _reference_changed(self, *_args):
        media = self.reference_combo.currentData() == "media"
        start = self.timeline.media_start
        show = media and start is not None and start != self.timeline.start
        self.align_check.setVisible(show)
        if start is not None:
            self.align_check.setText(
                "Set the timeline start timecode to %s, the media timecode (now %s)"
                % (self.timeline.timecode(start), self.timeline.timecode(self.timeline.start)))
        self._refresh_plan()

    def _reference_start(self):
        if self.reference_combo.currentData() == "media" and self.timeline.media_start is not None:
            return self.timeline.media_start
        return self.timeline.start

    # plan
    def _refresh_plan(self, *_args):
        if self._loading or self.table is None:
            return
        module = _sheet_module()
        columns = self._columns()
        try:
            self.plan = module.build_plan(
                self.table, columns, self.timeline.fps, self._reference_start(),
                self.timeline.duration, episode=self.episode_combo.currentData(),
                skip_omit=self.skip_omit.isChecked())
        except ValueError as exc:
            self.plan = None
            self._set_summary(str(exc), Color.WARNING_TEXT)
            self._clear_preview()
            return
        self._show_plan()

    def _show_plan(self):
        plan = self.plan
        marks, errors, warnings = len(plan.marks), len(plan.errors()), len(plan.warnings())
        previous = len(own_tags(self.sequence))
        parts = ["%s %s ready" % (emphasis(str(marks)), _plural(marks, "mark"))]
        if plan.skipped_omit:
            parts.append("%d omitted skipped" % plan.skipped_omit)
        if plan.skipped_episode:
            parts.append("%d from other episodes" % plan.skipped_episode)
        parts.append(_colored("%d not written" % errors, Color.ERROR_TEXT) if errors else "0 not written")
        if warnings:
            parts.append(_colored("%d %s" % (warnings, _plural(warnings, "warning")),
                                  Color.WARNING_TEXT))
        text = " &middot; ".join(parts)
        if previous:
            text += "<br>Replaces %d %s added before." % (previous, _plural(previous, "mark"))
        if self.timeline.media_reason:
            text += "<br>%s." % self.timeline.media_reason
        self._set_summary(text)
        self.apply_button.setEnabled(marks > 0)
        self.apply_button.setText(
            "Add %d %s" % (marks, _plural(marks, "Mark")) if marks else "Add Marks")
        self._fill_preview()
        log = _logger_ref()
        log.info("Prueba en seco: columnas %s | episodio %s | omit %s | fps %d | referencia %s "
                 "(%d) | duracion %d | %d marcas, %d no escritas, %d avisos",
                 self._columns(), self.episode_combo.currentData(), self.skip_omit.isChecked(),
                 self.timeline.fps, self.reference_combo.currentData(), self._reference_start(),
                 self.timeline.duration, marks, errors, warnings)
        for issue in plan.issues:
            log.info("  fila %d %s (%s): %s%s", issue.row, issue.shot, issue.tc_in,
                     issue.message, "" if issue.written else " [no se escribe]")

    def _fill_preview(self):
        plan = self.plan
        notes = {}
        for issue in plan.issues:
            notes.setdefault((issue.row, issue.shot), []).append(issue)
        rows = []
        for mark in plan.marks:
            issues = notes.pop((mark.row, mark.shot), [])
            text = "; ".join(i.message for i in issues) or "Mark"
            color = Color.WARNING_TEXT if issues else Color.OK_TEXT
            rows.append((mark.row, mark.shot, mark.tc_in,
                         "%d-%d" % (mark.frame_in, mark.frame_out), text, color))
        for (row, shot), issues in notes.items():
            rows.append((row, shot, issues[0].tc_in, "",
                         "; ".join(i.message for i in issues), Color.ERROR_TEXT))
        # Lo que no se escribe arriba: es lo que hay que revisar.
        rows.sort(key=lambda r: (r[5] != Color.ERROR_TEXT, r[5] != Color.WARNING_TEXT, r[0]))
        self.preview.setRowCount(len(rows))
        for index, (row, shot, tc_in, frames, text, color) in enumerate(rows):
            values = (str(row), shot, tc_in, frames, text)
            for col, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(value)
                if col == 4:
                    item.setForeground(QtGui.QBrush(QtGui.QColor(color)))
                self.preview.setItem(index, col, item)
            self.preview.setRowHeight(index, Metric.ROW_HEIGHT)
        self.preview.resizeColumnsToContents()
        visible = min(max(len(rows), 1), PREVIEW_ROWS)
        height = (self.preview.horizontalHeader().sizeHint().height()
                  + self.preview.frameWidth() * 2 + Metric.ROW_HEIGHT * visible)
        self.preview.setMinimumHeight(height)

    def _clear_preview(self):
        self.preview.setRowCount(0)
        self.apply_button.setEnabled(False)
        self.apply_button.setText("Add Marks")

    def _set_busy(self, text):
        self.apply_button.setEnabled(False)
        self._set_summary(text, Color.TEXT_DIM)

    def _set_summary(self, text, color=None):
        self.summary.setText(_colored(text, color) if color else text)

    # aplicar
    def _apply(self):
        if not self.plan or not self.plan.marks:
            return
        align = None
        # isHidden y no isVisible: isVisible depende tambien del dialogo.
        if not self.align_check.isHidden() and self.align_check.isChecked():
            align = self.timeline.media_start
        source = "%s | %s" % (os.path.basename(self.path_edit.text()),
                              self.sheet_combo.currentData() or "")
        try:
            removed = apply_plan(self.sequence, self.plan, align, source)
        except Exception as exc:
            _logger_ref().exception("No se pudieron escribir los tags")
            show_error(self, "Shot Marks", "Could not add the marks:\n%s" % exc)
            return
        self._save_settings()
        message = "Added %d marks to %s." % (len(self.plan.marks), self.sequence.name())
        if removed:
            message += "\nReplaced %d marks from a previous run." % removed
        if align is not None:
            message += "\nTimeline start timecode is now %s." % self.timeline.timecode(align)
        message += "\n\nJump between them with Viewer > Next Tag (Alt+Shift+Right).\nUndo: Edit > Undo."
        self.accept()
        show_info(hiero.ui.mainWindow(), "Shot Marks", message)

    def _save_settings(self):
        values = {
            "last_file": self.path_edit.text(),
            "last_sheet": self.sheet_combo.currentData() or "",
            "skip_omit": "true" if self.skip_omit.isChecked() else "false",
            "align": "true" if self.align_check.isChecked() else "false",
            "reference": self.reference_combo.currentData() or "media",
        }
        headers = self.table.headers if self.table else []
        for role, index in self._columns().items():
            values["col_" + role] = headers[index] if index is not None else ""
        _write_settings(values)


def _colored(text, color):
    return '<span style="color:%s">%s</span>' % (color, text)


def _plural(count, word):
    return word if count == 1 else word + "s"


def main():
    global _log
    _log = _logger()
    sequence = hiero.ui.activeSequence()
    if sequence is None:
        _log.warning("No hay timeline activo")
        show_warning(hiero.ui.mainWindow(), "Shot Marks", "Open a timeline first.")
        return
    try:
        editable = sequence.project().editable()
    except Exception:
        editable = True
    if not editable:
        _log.warning("Proyecto no editable: %s", sequence.project().name())
        show_warning(hiero.ui.mainWindow(), "Shot Marks",
                     "The project of this timeline is locked and cannot be edited.")
        return
    info = TimelineInfo(sequence)
    _log.info("Timeline %s | fps %.3f | inicio %d (%s) | duracion %d | media %s %s %s",
              sequence.name(), info.fps_float, info.start, info.timecode(info.start),
              info.duration, info.media_clip, info.media_start, info.media_reason)
    if abs(info.fps_float - info.fps) > 0.01:
        _log.info("Frame rate NTSC: se cuentan cuadros a %d nominal, sin drop-frame", info.fps)
    dialog = ShotMarksDialog(sequence, hiero.ui.mainWindow())
    dialog.exec_() if hasattr(dialog, "exec_") else dialog.exec()


if __name__ == "__main__":
    main()
