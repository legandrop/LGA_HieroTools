"""
____________________________________________________________________

  LGA_NKS_MediaSpreadsheetColumns v1.00 | Lega

  Ajusta las columnas del Media Spreadsheet abierto de Hiero/Nuke Studio.
  La API de SpreadsheetView no expone este control, pero su tabla interna
  usa un QHeaderView; se identifica por clase y cabeceras para no tocar
  otras tablas del host. Solo modifica la vista, nunca los clips.

  v1.00: Orden, anchos y visibilidad configurables por nombre de columna.
____________________________________________________________________
"""

import os
import traceback

import hiero.ui
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtCore, QtWidgets


DEBUG = False
_LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
_LOG_PATH = os.path.join(_LOG_DIR, "DebugPy_LGA_NKS_MediaSpreadsheetColumns.log")
_DEFAULT_WIDTHS = {"Status": 90, "Clip": 240}


def _log(message):
    os.makedirs(_LOG_DIR, exist_ok=True)
    with open(_LOG_PATH, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(str(message) + "\n")
    if DEBUG:
        print(message)


def _spreadsheets():
    matches = []
    for view in hiero.ui.mainWindow().findChildren(QtWidgets.QTreeView):
        if not view.isVisible() or not view.metaObject().className().endswith("SpreadsheetTreeView"):
            continue
        model = view.model()
        if model is None:
            continue
        names = [str(model.headerData(i, QtCore.Qt.Horizontal) or "")
                 for i in range(model.columnCount())]
        if {"Event", "Status", "Clip"}.issubset(names):
            matches.append((view, names))
    return matches


def apply(order=("Status", "Clip"), widths=None, hide=(), show=("Status", "Clip")):
    """Aplica preferencias a los Media Spreadsheets visibles; no toca el proyecto.

    order coloca esos nombres primero; el resto conserva su orden relativo.
    widths es un dict de nombre a pixeles; None usa los anchos sugeridos.
    hide/show cambian solo las columnas nombradas y dejan las demas como estan.
    """
    os.makedirs(_LOG_DIR, exist_ok=True)
    with open(_LOG_PATH, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("Media Spreadsheet: inicio\n")
    widths = _DEFAULT_WIDTHS if widths is None else widths
    order, hide, show = tuple(order), tuple(hide), tuple(show)
    try:
        if len(order) != len(set(order)) or set(hide) & set(show):
            raise ValueError("Hay columnas duplicadas o presentes tanto en hide como en show")
        if any(not isinstance(size, int) or size <= 0 for size in widths.values()):
            raise ValueError("Los anchos deben ser enteros positivos en pixeles")
        matches = _spreadsheets()
        if not matches:
            raise RuntimeError("No hay un Media Spreadsheet visible")
        requested = set(order) | set(widths) | set(hide) | set(show)
        for _view, names in matches:
            missing = requested - set(names)
            if missing:
                raise ValueError("Columnas no encontradas: %s" % ", ".join(sorted(missing)))
        states = [(view.header(), view.header().saveState()) for view, _names in matches]
        try:
            for view, names in matches:
                header = view.header()
                for name in show:
                    view.setColumnHidden(names.index(name), False)
                for visual, name in enumerate(order):
                    logical = names.index(name)
                    header.moveSection(header.visualIndex(logical), visual)
                for name, size in widths.items():
                    header.resizeSection(names.index(name), size)
                for name in hide:
                    view.setColumnHidden(names.index(name), True)
                _log("Vista ajustada: orden=%s anchos=%s ocultas=%s visibles=%s"
                     % (order, widths, hide, show))
        except Exception:
            for header, state in states:
                header.restoreState(state)
            raise
        return len(matches)
    except Exception:
        _log("ERROR:\n" + traceback.format_exc())
        raise
