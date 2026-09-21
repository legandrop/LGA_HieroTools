# -*- coding: utf-8 -*-
"""
____________________________________________________________________

  LGA_NKS_ProjectMediaPreview v1.00 | Lega

  Dialogo de decision para insertar media arrastrada desde el Projects Panel.
  Expone el track y la estrategia antes de modificar el timeline; la logica
  viva queda en el panel para revalidarla contra la secuencia al confirmar.

  v1.00: Version inicial.
____________________________________________________________________
"""

from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtCore
from LGA_NKS_Shared.LGA_UI_Style_HieroTools import Style, apply_ui_font


class ProjectMediaPreviewDialog(QtWidgets.QDialog):
    """Preview interactivo de una insercion; no toca el timeline por si solo."""

    _PLACEMENT_LABELS = (
        ("gap", "At playhead — use available gap"),
        ("ripple", "At playhead — split and shift timeline"),
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
        parent=None,
    ):
        super(ProjectMediaPreviewDialog, self).__init__(parent)
        self._tracks = list(tracks)
        self._analyze_callback = analyze_callback
        self.result_data = None
        self._current_plan = None

        self.setWindowTitle("Import media")
        self.setModal(True)
        self.setMinimumWidth(700)
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
        form.addRow("Placement", self._placement_combo)
        layout.addLayout(form)

        self._status = QtWidgets.QLabel()
        self._status.setWordWrap(True)
        self._status.setStyleSheet(Style.DETAIL)
        layout.addWidget(self._status)

        self._timeline_table = QtWidgets.QTableWidget(0, 4)
        self._timeline_table.setHorizontalHeaderLabels(
            ["Track", "Before playhead", "At playhead", "After playhead"]
        )
        self._timeline_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self._timeline_table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self._timeline_table.setFocusPolicy(QtCore.Qt.NoFocus)
        self._timeline_table.verticalHeader().setVisible(False)
        self._timeline_table.horizontalHeader().setStretchLastSection(True)
        self._timeline_table.setMinimumHeight(105)
        self._timeline_table.setMaximumHeight(150)
        self._timeline_table.setStyleSheet(Style.TABLE)
        layout.addWidget(self._timeline_table)

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
        if track is None:
            self._current_plan = None
            self._status.setText("Choose a video track to preview the insertion.")
            self._timeline_table.setRowCount(0)
            self._import_button.setEnabled(False)
            return

        self._current_plan = self._analyze_callback(track, mode)
        plan = self._current_plan or {}
        self._status.setText(plan.get("message", "Couldn't analyze the timeline."))
        self._import_button.setEnabled(bool(plan.get("valid")))
        self._import_button.setText(plan.get("action_label", "Import media"))
        self._populate_timeline(plan.get("rows", []))

    def _populate_timeline(self, rows):
        self._timeline_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = (
                row.get("track", ""),
                row.get("before", ""),
                row.get("at_playhead", ""),
                row.get("after", ""),
            )
            for column, value in enumerate(values):
                self._timeline_table.setItem(
                    row_index, column, QtWidgets.QTableWidgetItem(str(value))
                )
        self._timeline_table.resizeColumnsToContents()
        self._timeline_table.resizeRowsToContents()

    def _accept_plan(self):
        if not self._current_plan or not self._current_plan.get("valid"):
            return
        self.result_data = {
            "track": self._selected_track(),
            "mode": self._selected_mode(),
        }
        self.accept()
