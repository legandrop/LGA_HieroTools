# -*- coding: utf-8 -*-
"""
____________________________________________________________________

  LGA_NKS_ProjectMediaPreview v1.04 | Lega

  Dialogo de decision para insertar media arrastrada desde el Projects Panel.
  Reproduce la lectura visual de Import Shot: cada track se ve alrededor del
  punto de insercion antes de modificar el timeline.

  v1.04: El preview ajusta su alto sin scrollbar vertical, deja solo el
         resumen de media y usa un switch compacto debajo del timeline.
  v1.03: El track se elige en la tabla, placement usa tres botones y cada fila
         comparte un eje temporal continuo con la media nueva en rojo.
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
    """Dibuja un tramo continuo del timeline, sin cortar el playhead en celdas."""

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
            # La media nueva es roja: el playhead usa blanco para seguir
            # leyendose cuando cae dentro de ese chip.
            painter.setPen(QtGui.QPen(QtGui.QColor(Color.TEXT_STRONG), 2))
            painter.drawLine(playhead_x, rect.top(), playhead_x, rect.bottom())
        painter.end()


class ProjectMediaPreviewDialog(QtWidgets.QDialog):
    """Preview interactivo de una insercion; no toca el timeline por si solo."""

    _PLACEMENT_LABELS = (
        ("ripple", "Open space"),
        ("gap", "Use available gap"),
        ("end", "Timeline end"),
    )

    def __init__(
        self,
        media_name,
        duration,
        playhead,
        tracks,
        analyze_callback,
        selected_track=None,
        initial_mode="ripple",
        parent=None,
    ):
        super(ProjectMediaPreviewDialog, self).__init__(parent)
        self._tracks = list(tracks)
        self._analyze_callback = analyze_callback
        self.result_data = None
        self._current_plan = None
        self._selected_track_value = self._normalize_track(selected_track)
        self._selected_mode_value = initial_mode
        self._row_tracks = []

        self.setWindowTitle("Import Media into Timeline")
        self.setModal(True)
        self.setMinimumWidth(1040)
        self.setStyleSheet(Style.FORM)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self._summary = QtWidgets.QLabel(
            "<b>%s</b> <span style='color:%s'>· %d frames</span>"
            % (self._escape_html(media_name), Color.TEXT_DIM, duration)
        )
        self._summary.setWordWrap(True)
        self._summary.setStyleSheet(Style.DETAIL)
        layout.addWidget(self._summary)

        instruction = QtWidgets.QLabel(
            "Click a track name to choose a destination track."
        )
        instruction.setStyleSheet(Style.DETAIL)
        layout.addWidget(instruction)

        self._timeline_table = QtWidgets.QTableWidget(0, 3)
        self._timeline_table.setHorizontalHeaderLabels(
            ["", "Track", "Timeline preview"]
        )
        self._timeline_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self._timeline_table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self._timeline_table.setFocusPolicy(Qt.NoFocus)
        self._timeline_table.verticalHeader().setVisible(False)
        self._timeline_table.setShowGrid(False)
        self._timeline_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._timeline_table.setStyleSheet(Style.TABLE)
        header = self._timeline_table.horizontalHeader()
        header.setMinimumSectionSize(1)
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Fixed)
        self._timeline_table.setColumnWidth(0, 5)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        layout.addWidget(self._timeline_table)

        footer_row = QtWidgets.QHBoxLayout()
        footer_row.setSpacing(6)
        placement_label = QtWidgets.QLabel("Placement")
        footer_row.addWidget(placement_label)

        placement_switch = QtWidgets.QWidget()
        placement_switch.setStyleSheet(Style.PANEL)
        placement_layout = QtWidgets.QHBoxLayout(placement_switch)
        placement_layout.setContentsMargins(2, 2, 2, 2)
        placement_layout.setSpacing(2)
        self._placement_buttons = {}
        self._placement_button_labels = {}
        self._placement_group = QtWidgets.QButtonGroup(self)
        self._placement_group.setExclusive(True)
        for mode, label in self._PLACEMENT_LABELS:
            button = QtWidgets.QPushButton(label)
            button.setCheckable(True)
            button.clicked.connect(
                lambda _checked=False, placement_mode=mode: self._set_placement(
                    placement_mode
                )
            )
            self._placement_group.addButton(button)
            button.setStyleSheet(Style.BTN_SMALL)
            self._placement_buttons[mode] = button
            self._placement_button_labels[mode] = label
            placement_layout.addWidget(button)
        footer_row.addWidget(placement_switch)

        self._status = QtWidgets.QLabel()
        self._status.setWordWrap(True)
        self._status.setStyleSheet(
            "QLabel { color: %s; }" % Color.ERROR_TEXT
        )
        self._status.hide()
        footer_row.addWidget(self._status, 1)
        footer_row.addStretch(1)
        layout.addLayout(footer_row)

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

        self._timeline_table.cellClicked.connect(self._on_timeline_cell_clicked)
        self._set_placement(initial_mode, refresh=False)
        apply_ui_font(self)
        self._refresh()

    def _selected_track(self):
        return self._selected_track_value

    def _normalize_track(self, track):
        """Devuelve el wrapper de la tabla aunque Hiero haya creado otro wrapper."""
        for entry in self._tracks:
            candidate = entry["track"]
            if self._tracks_match(candidate, track):
                return candidate
        return None

    @staticmethod
    def _tracks_match(first, second):
        """Compara wrappers de Hiero que pueden no conservar identidad Python."""
        if first is second:
            return True
        if first is None or second is None:
            return False
        try:
            return bool(first == second)
        except Exception:
            return False

    def _selected_mode(self):
        return self._selected_mode_value

    def _set_placement(self, mode, refresh=True):
        """Actualiza el switch de placement y la proyeccion que controla."""
        self._selected_mode_value = mode
        for button_mode, button in self._placement_buttons.items():
            selected = button_mode == mode
            button.setChecked(selected)
            button.setText(
                ("✓ " if selected else "") + self._placement_button_labels[button_mode]
            )
            button.setStyleSheet(Style.BTN_SMALL)
        if refresh:
            self._refresh()

    def _on_timeline_cell_clicked(self, row_index, column):
        """El nombre del track es el control de destino, no un dropdown aparte."""
        if column != 1 or row_index >= len(self._row_tracks):
            return
        track, selectable = self._row_tracks[row_index]
        if not selectable:
            return
        self._selected_track_value = self._normalize_track(track)
        self._refresh()

    def _refresh(self):
        track = self._selected_track()
        mode = self._selected_mode()
        self._current_plan = self._analyze_callback(track, mode)
        plan = self._current_plan or {}
        valid = bool(plan.get("valid"))
        self._import_button.setEnabled(valid)
        self._import_button.setText(plan.get("action_label", "Import media"))
        if valid:
            self._status.clear()
            self._status.hide()
        else:
            self._status.setText(
                plan.get("message", "Couldn't analyze the timeline.")
            )
            self._status.show()
        self._populate_timeline(plan.get("rows", []), plan.get("playhead"))
        self._fit_timeline_table_height()
        self.adjustSize()

    def _populate_timeline(self, rows, playhead=None):
        self._timeline_table.clearContents()
        self._timeline_table.setRowCount(len(rows))
        time_range = self._timeline_range(rows, playhead)
        self._row_tracks = []
        for row_index, row in enumerate(rows):
            color_item = QtWidgets.QTableWidgetItem()
            color_item.setBackground(QtGui.QColor(row.get("color", Color.ACCENT_TRACK)))
            color_item.setFlags(Qt.NoItemFlags)
            self._timeline_table.setItem(row_index, 0, color_item)
            track = row.get("track_ref")
            selectable = bool(row.get("selectable"))
            selected = self._tracks_match(track, self._selected_track_value)
            track_text = str(row.get("track", ""))
            if selected:
                track_text = "✓ " + track_text
            track_item = QtWidgets.QTableWidgetItem(track_text)
            track_item.setFlags(Qt.ItemIsEnabled if not selectable else Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            if selected:
                track_item.setBackground(QtGui.QColor(Color.ACCENT_TRACK))
                track_item.setForeground(QtGui.QBrush(QtGui.QColor(Color.TEXT_STRONG)))
                track_font = track_item.font()
                semibold(track_font)
                track_item.setFont(track_font)
            self._timeline_table.setItem(row_index, 1, track_item)
            self._timeline_table.setCellWidget(
                row_index,
                2,
                _TimelineCell(
                    row.get("clips", []),
                    time_range,
                    playhead,
                    self._timeline_table,
                ),
            )
            self._row_tracks.append((track, selectable))
            self._timeline_table.setRowHeight(row_index, 38)

    def _fit_timeline_table_height(self):
        """Reserva exactamente cabecera y filas para que no aparezca scroll."""
        header = self._timeline_table.horizontalHeader()
        header_height = max(header.height(), header.sizeHint().height())
        rows_height = sum(
            self._timeline_table.rowHeight(index)
            for index in range(self._timeline_table.rowCount())
        )
        frame = self._timeline_table.frameWidth() * 2
        table_height = header_height + rows_height + frame
        self._timeline_table.setFixedHeight(table_height)

    @staticmethod
    def _escape_html(value):
        """Evita que caracteres del nombre de archivo modifiquen el resumen."""
        return (
            str(value or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    @staticmethod
    def _timeline_range(rows, playhead=None):
        """Un solo eje real evita huecos falsos alrededor del playhead."""
        clips = [clip for row in rows for clip in row.get("clips", [])]
        points = [playhead] if playhead is not None else []
        if clips:
            points.extend(clip["preview_in"] for clip in clips)
            points.extend(clip["preview_out"] for clip in clips)
        if not points:
            return (0, 0)
        return min(points), max(points)

    def _accept_plan(self):
        if not self._current_plan or not self._current_plan.get("valid"):
            return
        self.result_data = {
            "track": self._selected_track(),
            "mode": self._selected_mode(),
        }
        self.accept()
