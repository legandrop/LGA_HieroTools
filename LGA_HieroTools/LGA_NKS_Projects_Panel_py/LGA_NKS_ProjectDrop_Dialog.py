"""
____________________________________________________________________

  LGA_NKS_ProjectDrop_Dialog v1.00 | Lega

  Ofrece guardar una copia compatible con Nuke 16 de un proyecto arrastrado.
  El original se conserva y las operaciones de disco van fuera del hilo UI.

  v1.00: Dialogo compacto con nombre, carpeta y descarte explicito de annotations.
____________________________________________________________________
"""

import logging
import os
from pathlib import Path
import re

from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtCore, QtWidgets
from LGA_NKS_Shared.LGA_UI_Style_HieroTools import (
    Color, Metric, Style, apply_ui_font, mono_family, semibold,
)

DEBUG = False
TOOLTIPS = {
    'filename': 'Nombre de la copia compatible. Se propone la siguiente version.',
    'folder': 'Carpeta donde se guardara la copia; por defecto, la del original.',
    'browse': 'Elegir otra carpeta para la copia compatible.',
    'annotations': 'Acepta descartar solo en la copia las annotations incompatibles.',
    'save': 'Crear un archivo nuevo compatible con Nuke Studio / Hiero 16.0.',
}
_RUNNING_TASKS = set()


class _TaskSignals(QtCore.QObject):
    succeeded = QtCore.Signal(object)
    failed = QtCore.Signal(object)
    finished = QtCore.Signal(object)


class _TaskCleanup(QtCore.QObject):
    @QtCore.Slot(object)
    def release(self, task):
        _RUNNING_TASKS.discard(task)


_cleanup = None


class _ProjectTask(QtCore.QRunnable):
    def __init__(self, operation, source, destination=None, drop_annotations=False):
        super().__init__()
        self.operation = operation
        self.source = source
        self.destination = destination
        self.drop_annotations = drop_annotations
        self.signals = _TaskSignals()

    def run(self):
        logger = logging.Logger('ProjectDrop_Dialog')
        handler = None
        try:
            log_dir = Path(__file__).resolve().parent / 'logs'
            log_dir.mkdir(exist_ok=True)
            handler = logging.FileHandler(
                log_dir / 'DebugPy_ProjectDrop_Dialog.log',
                mode='w' if self.operation == 'inspect' else 'a', encoding='utf-8')
            handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
            logger.addHandler(handler)
            if DEBUG:
                logger.addHandler(logging.StreamHandler())
            logger.info('Operacion: %s; origen: %s; destino: %s; descartar annotations: %s',
                        self.operation, self.source, self.destination, self.drop_annotations)
            from LGA_NKS_Project_Downgrade import (
                inspect_project, suggest_project_name, convert_project,
            )
            if self.operation == 'inspect':
                result = inspect_project(self.source)
                result['suggested_name'] = suggest_project_name(self.source)
                logger.info('Lectura: version %s; release %s; annotations %s',
                            result['version'], result['release'], result['annotations'])
            else:
                result = str(convert_project(self.source, self.destination,
                                            drop_annotations=self.drop_annotations))
                logger.info('Copia guardada: %s', result)
            self.signals.succeeded.emit(result)
        except Exception as error:
            logger.exception('No se pudo completar la operacion.')
            self.signals.failed.emit(error)
        finally:
            if handler is not None:
                handler.close()
            self.signals.finished.emit(self)


def _label(text, strong=False):
    widget = QtWidgets.QLabel(text)
    widget.setTextFormat(QtCore.Qt.PlainText)
    widget.setWordWrap(True)
    widget.setStyleSheet('color: %s;' % (Color.TEXT_STRONG if strong else Color.TEXT))
    widget.setProperty('lgaStrong', strong)
    return widget


def _filename_error(name):
    if not name or name != name.strip():
        return 'Enter a file name without leading or trailing spaces.'
    if name in ('.', '..') or re.search(r'[<>:"/\\|?*\x00-\x1f]', name):
        return 'Enter a file name without folders or special characters.'
    if name.endswith('.') or name.endswith(' '):
        return 'The file name cannot end with a dot or a space.'
    if not name.lower().endswith('.hrox') or name.lower() == '.hrox':
        return 'The file name must end with .hrox.'
    if re.match(r'^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)', name, re.I):
        return 'Choose a different file name; this name is reserved.'
    return ''


class ProjectConversionDialog(QtWidgets.QDialog):
    saved = QtCore.Signal(str)

    def __init__(self, source, parent=None):
        super().__init__(parent)
        self.source = os.path.abspath(os.fspath(source))
        self._info = None
        self._busy = False
        self.setWindowTitle('Project conversion')
        self.setStyleSheet(Style.FORM)
        self.setMinimumWidth(Metric.DIALOG_MIN_WIDTH + Metric.DIALOG_MARGIN * 4)
        self.resize(self.minimumWidth(), self.sizeHint().height())
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(Metric.DIALOG_MARGIN, Metric.DIALOG_MARGIN,
                                  Metric.DIALOG_MARGIN, Metric.DIALOG_MARGIN)
        layout.setSpacing(Metric.SPACING)
        layout.addWidget(_label('Save a Nuke 16 copy', strong=True))
        self.subtitle = _label('Reading project...')
        layout.addWidget(self.subtitle)
        layout.addSpacing(Metric.SPACING)
        form = QtWidgets.QFormLayout()
        form.setHorizontalSpacing(Metric.DIALOG_MARGIN)
        form.setVerticalSpacing(Metric.SPACING)
        form.addRow('Original', _label(os.path.basename(self.source), strong=True))
        self.filename = QtWidgets.QLineEdit()
        self.filename.setObjectName('outputName')
        self.filename.setStyleSheet(Style.LINE_EDIT)
        self.filename.setMinimumHeight(Metric.BUTTON_HEIGHT)
        self.filename.setToolTip(TOOLTIPS['filename'])
        self.filename.setEnabled(False)
        form.addRow('Save as', self.filename)
        folder_row = QtWidgets.QHBoxLayout()
        folder_row.setSpacing(Metric.SPACING)
        self.folder = QtWidgets.QLineEdit(os.path.dirname(self.source))
        self.folder.setObjectName('outputFolder')
        self.folder.setReadOnly(True)
        self.folder.setStyleSheet(Style.LINE_EDIT)
        self.folder.setMinimumHeight(Metric.BUTTON_HEIGHT)
        self.folder.setToolTip(TOOLTIPS['folder'])
        self.browse = QtWidgets.QPushButton('Browse...')
        self.browse.setAutoDefault(False)
        self.browse.setStyleSheet(Style.BTN_SECONDARY)
        self.browse.setFixedHeight(Metric.BUTTON_HEIGHT)
        self.browse.setToolTip(TOOLTIPS['browse'])
        self.browse.setEnabled(False)
        folder_row.addWidget(self.folder, 1)
        folder_row.addWidget(self.browse)
        form.addRow('Folder', folder_row)
        layout.addLayout(form)
        self.annotation_warning = _label('')
        self.annotation_warning.setStyleSheet('color: %s;' % Color.WARNING_TEXT)
        self.annotation_warning.hide()
        layout.addWidget(self.annotation_warning)
        self.discard_annotations = QtWidgets.QCheckBox('Discard annotations in the copy')
        self.discard_annotations.setProperty('lgaLabeled', True)
        self.discard_annotations.setStyleSheet(Style.CHECKBOX)
        self.discard_annotations.setToolTip(TOOLTIPS['annotations'])
        self.discard_annotations.hide()
        layout.addWidget(self.discard_annotations)
        layout.addWidget(_label('The original project will stay unchanged.'))
        self.status = _label('')
        self.status.hide()
        layout.addWidget(self.status)
        actions = QtWidgets.QHBoxLayout()
        actions.setSpacing(Metric.SPACING)
        actions.addStretch()
        self.cancel = QtWidgets.QPushButton('Cancel')
        self.cancel.setAutoDefault(False)
        self.cancel.setStyleSheet(Style.BTN_SECONDARY)
        self.cancel.setFixedHeight(Metric.BUTTON_HEIGHT)
        self.save_button = QtWidgets.QPushButton('Save Nuke 16 Copy')
        self.save_button.setDefault(True)
        self.save_button.setStyleSheet(Style.BTN_PRIMARY)
        self.save_button.setFixedHeight(Metric.BUTTON_HEIGHT)
        self.save_button.setToolTip(TOOLTIPS['save'])
        self.save_button.setEnabled(False)
        actions.addWidget(self.cancel)
        actions.addWidget(self.save_button)
        layout.addSpacing(Metric.SPACING)
        layout.addLayout(actions)
        apply_ui_font(self, Metric.FORM_FONT_SIZE)
        for label in self.findChildren(QtWidgets.QLabel):
            if label.property('lgaStrong'):
                font = label.font()
                semibold(font)
                label.setFont(font)
        font = self.folder.font()
        font.setFamily(mono_family())
        self.folder.setFont(font)
        self.cancel.clicked.connect(self.reject)
        self.browse.clicked.connect(self._browse)
        self.filename.textChanged.connect(self._name_changed)
        self.discard_annotations.toggled.connect(self._update_save)
        self.save_button.clicked.connect(self._save)
        self.adjustSize()
        self._start_task(_ProjectTask('inspect', self.source), self._inspected, self._inspect_failed)

    def _start_task(self, task, success, failure):
        global _cleanup
        if _cleanup is None:
            _cleanup = _TaskCleanup(QtWidgets.QApplication.instance())
        _RUNNING_TASKS.add(task)
        task.signals.succeeded.connect(success, QtCore.Qt.QueuedConnection)
        task.signals.failed.connect(failure, QtCore.Qt.QueuedConnection)
        task.signals.finished.connect(_cleanup.release, QtCore.Qt.QueuedConnection)
        QtCore.QThreadPool.globalInstance().start(task)

    @QtCore.Slot(object)
    def _inspected(self, info):
        if info['version'] == 11:
            self.subtitle.setText('This project is already compatible with Nuke 16.0.')
            return
        if info['version'] != 12 or not re.fullmatch(r'(?:16\.1|17\.0)v\d+', info['release']):
            self.subtitle.setText('This project version is not supported for conversion to Nuke 16.0.')
            return
        self._info = info
        self.subtitle.setText('Create a compatible copy of this Nuke %s project.' % info['release'])
        self.filename.setText(info['suggested_name'])
        self.filename.setEnabled(True)
        self.browse.setEnabled(True)
        if info['annotations']:
            noun = 'annotation' if info['annotations'] == 1 else 'annotations'
            self.annotation_warning.setText(
                '%d %s cannot be kept in Nuke 16.0. Accept removal to save the copy.'
                % (info['annotations'], noun))
            self.annotation_warning.show()
            self.discard_annotations.show()
        self._update_save()
        self.adjustSize()

    @QtCore.Slot(object)
    def _inspect_failed(self, error):
        self.subtitle.setText('This project could not be read or is not supported for conversion.')
        self._show_status('See DebugPy_ProjectDrop_Dialog.log for details.', error=True)

    def _show_status(self, text, error=False):
        self.status.setStyleSheet('color: %s;' % (Color.ERROR_TEXT if error else Color.TEXT))
        self.status.setText(text)
        self.status.setVisible(bool(text))

    def _update_save(self):
        valid = self._info is not None and not _filename_error(self.filename.text())
        accepted = self._info is not None and (
            not self._info['annotations'] or self.discard_annotations.isChecked())
        self.save_button.setEnabled(bool(valid and accepted and not self._busy))

    def _name_changed(self):
        if self._info is not None and not self._busy:
            error = _filename_error(self.filename.text())
            self._show_status(error, error=bool(error))
        self._update_save()

    def _browse(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, 'Choose save folder', self.folder.text())
        if folder:
            self.folder.setText(folder)
            self._show_status('')

    def _save(self):
        if self._busy or self._info is None:
            return
        error = _filename_error(self.filename.text())
        if error:
            self._show_status(error, error=True)
            return
        if self._info['annotations'] and not self.discard_annotations.isChecked():
            self._show_status('Accept discarding annotations before saving the copy.', error=True)
            return
        destination = os.path.join(self.folder.text(), self.filename.text())
        if os.path.normcase(os.path.abspath(destination)) == os.path.normcase(self.source):
            self._show_status('Choose a new file name. The original cannot be replaced.', error=True)
            return
        self._busy = True
        self.filename.setEnabled(False)
        self.browse.setEnabled(False)
        self.discard_annotations.setEnabled(False)
        self.cancel.setEnabled(False)
        self.save_button.setEnabled(False)
        self._show_status('Saving Nuke 16 copy...')
        self._start_task(_ProjectTask('convert', self.source, destination,
                                     self.discard_annotations.isChecked()),
                         self._saved, self._save_failed)

    @QtCore.Slot(object)
    def _saved(self, destination):
        self._busy = False
        self.saved.emit(destination)
        self.accept()

    @QtCore.Slot(object)
    def _save_failed(self, error):
        self._busy = False
        self.filename.setEnabled(True)
        self.browse.setEnabled(True)
        self.discard_annotations.setEnabled(True)
        self.cancel.setEnabled(True)
        if isinstance(error, FileExistsError):
            message = 'A file already exists at this location. Choose a different name or folder.'
        elif isinstance(error, PermissionError):
            message = 'Could not save the copy. Choose a folder you can write to.'
        else:
            message = 'Could not save the copy. See DebugPy_ProjectDrop_Dialog.log for details.'
        self._show_status(message, error=True)
        self._update_save()

    def reject(self):
        if not self._busy:
            super().reject()

    def closeEvent(self, event):
        if self._busy:
            event.ignore()
        else:
            super().closeEvent(event)
