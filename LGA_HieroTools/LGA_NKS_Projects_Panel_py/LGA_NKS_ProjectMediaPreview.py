# -*- coding: utf-8 -*-
"""
____________________________________________________________________

  LGA_NKS_ProjectMediaPreview v1.02 | Lega

  Dialogo de decision para insertar media arrastrada desde el Projects Panel.
  Reproduce la lectura visual de Import Shot: cada track se ve alrededor del
  punto de insercion antes de modificar el timeline.

  v1.02: Chips con color real, playhead visible y proyeccion de cada opcion.
  v1.01: Preview grafico por track y seleccion inicial de ripple cuando falta
         espacio; el plan sigue siendo propiedad del Projects Panel.
  v1.00: Version inicial.
____________________________________________________________________
"""

from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui, QtCore, Qt
from LGA_NKS_Shared.LGA_UI_Style_HieroTools import (
    Color,
    Style,
    apply_ui_font,
    semibold,
)


class _TimelineCell(QtWidgets.QWidget):
    """Dibuja clips reales de una zona del timeline, como el preview de Import Shot."""

    _MARGIN = 3
    _MIN_WIDTH = 1

    def __init__(self, clips, time_range=None, playhead=None, parent=None):
        super(_TimelineCell, self).__init__(parent)
        self._clips = list(clips or [])
        self._time_range = time_range
        self._playhead = playhead
        self.setMinimumHeight(30)

    def paintEvent(self, event):
        super(_TimelineCell, self).paintEvent(event)
        if not self._clips and self._playhead is None:
            return

        if self._time_range is None:
            if self._clips:
                starts = [clip["preview_in"] for clip in self._clips]
                ends = [clip["preview_out"] for clip in self._clips]
                first = min(starts)
                last = max(ends)
            else:
                first = last = self._playhead
        else:
            first, last = self._time_range
        span = max(1, last - first + 1)
        rect = self.rect().adjusted(self._MARGIN, self._MARGIN, -self._MARGIN, -self._MARGIN)
        if rect.width() <= 0 or rect.height() <= 0:
            return

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        for clip in self._clips:
            start_ratio = float(clip["preview_in"] - first) / span
            width_ratio = float(clip["preview_out"] - clip["preview_in"] + 1) / span
            left = rect.left() + int(rect.width() * start_ratio)
            width = max(self._MIN_WIDTH, int(rect.width() * width_ratio))
            width = min(width, rect.right() - left + 1)
            clip_rect = QtCore.QRect(left, rect.top(), width, rect.height())
            is_new = bool(clip.get("is_new"))
            fill = QtGui.QColor(
                clip.get("color") or (Color.ACCENT if is_new else Color.SURFACE_RAISED)
            )
            painter.setPen(QtGui.QPen(QtGui.QColor(Color.ACCENT if is_new else Color.BORDER_STRONG)))
            painter.setBrush(QtGui.QBrush(fill))
            painter.drawRoundedRect(clip_rect, 3, 3)

            font = self.font()
            if is_new:
                semibold(font)
            painter.setFont(font)
            luminance = 0.299 * fill.red() + 0.587 * fill.green() + 0.114 * fill.blue()
            text_color = Color.TEXT_ON_ACCENT if luminance < 145 else Color.WINDOW
            painter.setPen(QtGui.QColor(text_color))
            label = str(clip.get("name") or "Untitled media")
            if clip.get("shift_frames"):
                label += "  +%df" % int(clip["shift_frames"])
            label_rect = clip_rect.adjusted(5, 0, -5, 0)
            painter.drawText(
                label_rect,
                Qt.AlignVCenter | Qt.AlignLeft,
                painter.fontMetrics().elidedText(label, Qt.ElideRight, max(0, label_rect.width())),
            )
        if self._playhead is not None:
            if self._playhead <= first:
                playhead_x = rect.left()
            elif self._playhead >= last:
                playhead_x = rect.right()
            else:
                playhead_ratio = float(self._playhead - first) / span
                playhead_x = rect.left() + int(rect.width() * playhead_ratio)
            painter.setPen(QtGui.QPen(QtGui.QColor(Color.ERROR_TEXT), 2))
            painter.drawLine(playhead_x, rect.top(), playhead_x, rect.bottom())
        painter.end()


class ProjectMediaPreviewDialog(QtWidgets.QDialog):
    """Preview interactivo de una insercion; no toca el timeline por si solo."""

    _PLACEMENT_LABELS = (
        ("gap", "At playhead — use available gap"),
        ("ripple", "At playhead — open space and shift timeline"),
        ("end", "At timeline end — do not move clips"),
    )

    def __init__(
        self,
        media_name,
        duration,
        playhead,
        tracks,
        analyze_callback,
        selected_track=None,
        initial_mode="gap",
        parent=None,
    ):
        super(ProjectMediaPreviewDialog, self).__init__(parent)
        self._tracks = list(tracks)
        self._analyze_callback = analyze_callback
        self.result_data = None
        self._current_plan = None

        self.setWindowTitle("Import media")
        self.setModal(True)
        self.setMinimumWidth(1040)
        self.setMinimumHeight(430)
        self.setStyleSheet(Style.FORM)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QtWidgets.QLabel("Import media into timeline")
        title.setProperty("lgaSectionTitle", True)
        layout.addWidget(title)

        self._summary = QtWidgets.QLabel(
            "<b>%s</b> · %d frames · playhead %d"
            % (media_name, duration, playhead)
        )
        self._summary.setWordWrap(True)
        self._summary.setStyleSheet(Style.DETAIL)
        layout.addWidget(self._summary)

        form = QtWidgets.QFormLayout()
        form.setSpacing(8)
        self._track_combo = QtWidgets.QComboBox()
        self._track_combo.setStyleSheet(Style.COMBO)
        self._track_combo.addItem("Select a video track", None)
        selected_index = 0
        for index, track_data in enumerate(self._tracks, start=1):
            self._track_combo.addItem(track_data["label"], track_data["track"])
            if track_data["track"] is selected_track:
                selected_index = index
        self._track_combo.setCurrentIndex(selected_index)
        form.addRow("Destination", self._track_combo)

        self._placement_combo = QtWidgets.QComboBox()
        self._placement_combo.setStyleSheet(Style.COMBO)
        for mode, label in self._PLACEMENT_LABELS:
            self._placement_combo.addItem(label, mode)
        initial_index = self._placement_combo.findData(initial_mode)
        self._placement_combo.setCurrentIndex(max(0, initial_index))
        form.addRow("Placement", self._placement_combo)
        layout.addLayout(form)

        self._status = QtWidgets.QLabel()
        self._status.setWordWrap(True)
        self._status.setStyleSheet(Style.DETAIL)
        layout.addWidget(self._status)

        self._timeline_table = QtWidgets.QTableWidget(0, 5)
        self._timeline_table.setHorizontalHeaderLabels(
            ["", "Track", "Before playhead", "At playhead", "After playhead"]
        )
        self._timeline_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self._timeline_table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self._timeline_table.setFocusPolicy(Qt.NoFocus)
        self._timeline_table.verticalHeader().setVisible(False)
        self._timeline_table.setShowGrid(False)
        self._timeline_table.setStyleSheet(Style.TABLE)
        header = self._timeline_table.horizontalHeader()
        header.setMinimumSectionSize(1)
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Fixed)
        self._timeline_table.setColumnWidth(0, 5)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)
        self._timeline_table.setColumnWidth(1, 150)
        for column in (2, 3, 4):
            header.setSectionResizeMode(column, QtWidgets.QHeaderView.Stretch)
        layout.addWidget(self._timeline_table, 1)

        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch(1)
        cancel_button = QtWidgets.QPushButton("Cancel")
        cancel_button.setStyleSheet(Style.BTN_SECONDARY)
        cancel_button.clicked.connect(self.reject)
        self._import_button = QtWidgets.QPushButton("Import media")
        self._import_button.setStyleSheet(Style.BTN_PRIMARY)
        self._import_button.clicked.connect(self._accept_plan)
        buttons.addWidget(cancel_button)
        buttons.addWidget(self._import_button)
        layout.addLayout(buttons)

        self._track_combo.currentIndexChanged.connect(self._refresh)
        self._placement_combo.currentIndexChanged.connect(self._refresh)
        self._refresh()
        apply_ui_font(self)

    def _selected_track(self):
        return self._track_combo.currentData()

    def _selected_mode(self):
        return self._placement_combo.currentData()

    def _refresh(self):
        track = self._selected_track()
        mode = self._selected_mode()
        self._current_plan = self._analyze_callback(track, mode)
        plan = self._current_plan or {}
        self._status.setText(plan.get("message", "Couldn't analyze the timeline."))
        self._import_button.setEnabled(bool(plan.get("valid")))
        self._import_button.setText(plan.get("action_label", "Import media"))
        self._populate_timeline(plan.get("rows", []), plan.get("playhead"))

    def _populate_timeline(self, rows, playhead=None):
        self._timeline_table.setRowCount(len(rows))
        ranges = self._column_time_ranges(rows)
        if playhead is not None and "at_playhead" not in ranges:
            ranges["at_playhead"] = (playhead, playhead)
        for row_index, row in enumerate(rows):
            color_item = QtWidgets.QTableWidgetItem()
            color_item.setBackground(QtGui.QColor(row.get("color", Color.ACCENT_TRACK)))
            color_item.setFlags(Qt.NoItemFlags)
            self._timeline_table.setItem(row_index, 0, color_item)
            self._timeline_table.setItem(
                row_index, 1, QtWidgets.QTableWidgetItem(str(row.get("track", "")))
            )
            for column, key in enumerate(("before", "at_playhead", "after"), start=2):
                self._timeline_table.setCellWidget(
                    row_index,
                    column,
                    _TimelineCell(
                        row.get(key, []),
                        ranges.get(key),
                        playhead if key == "at_playhead" else None,
                        self._timeline_table,
                    ),
                )
            self._timeline_table.setRowHeight(row_index, 38)

    @staticmethod
    def _column_time_ranges(rows):
        """Comparte el eje temporal de cada columna entre todos los tracks."""
        ranges = {}
        for key in ("before", "at_playhead", "after"):
            clips = [clip for row in rows for clip in row.get(key, [])]
            if clips:
                ranges[key] = (
                    min(clip["preview_in"] for clip in clips),
                    max(clip["preview_out"] for clip in clips),
                )
        return ranges

    def _accept_plan(self):
        if not self._current_plan or not self._current_plan.get("valid"):
            return
        self.result_data = {
            "track": self._selected_track(),
            "mode": self._selected_mode(),
        }
        self.accept()
