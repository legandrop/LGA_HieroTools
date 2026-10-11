"""
____________________________________________________________________

  LGA_NKS_MediaSpreadsheetColumns v1.05 | Lega

  Ajusta las columnas del Media Spreadsheet abierto de Hiero/Nuke Studio.
  La API de SpreadsheetView no expone este control, pero su tabla interna
  usa un QHeaderView; se identifica por clase y cabeceras para no tocar
  otras tablas del host. Solo modifica la vista, nunca los clips.

  v1.05: Módulo compartido de TL Refresh y Projects Panel. Cierra los tabs
         anteriores antes de reconstruir el timeline; ajusta también tabs ocultos.
  v1.04: Clip Media queda segunda a 99 px; filas ordenadas por Clip ascendente.
         Se ocultan también Reel y Version cuando existen.
  v1.03: Color queda cuarta a 33 px y Shot Name quinta con ancho automático.
         Se agrupa el repintado y se evitan cambios Qt redundantes.
  v1.02: Status y Clip Media fijan los anchos medidos; Clip Media queda
         tercera y se ocultan Event, Action, Num Versions y Link Status.
  v1.01: Clip se ajusta al contenido como con doble click en el header.
  v1.00: Orden, anchos y visibilidad configurables por nombre de columna.
____________________________________________________________________
"""

import os
import time
import traceback

import hiero.ui
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import (
    QtCore, QtWidgets, is_widget_alive, iter_live_widgets,
)


DEBUG = False
_LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
_LOG_PATH = os.path.join(_LOG_DIR, "DebugPy_LGA_NKS_MediaSpreadsheetColumns.log")
_DEFAULT_ORDER = ("Status", "Clip Media", "Clip", "Color", "Shot Name")
_DEFAULT_WIDTHS = {"Status": 51, "Clip": "auto", "Clip Media": 99,
                   "Color": 33, "Shot Name": "auto"}
_DEFAULT_HIDDEN = ("Event", "Action", "Num Versions", "Link Status", "Reel", "Version")


def _log(message):
    os.makedirs(_LOG_DIR, exist_ok=True)
    with open(_LOG_PATH, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(str(message) + "\n")
    if DEBUG:
        print(message)


def _start_log(message):
    os.makedirs(_LOG_DIR, exist_ok=True)
    with open(_LOG_PATH, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(message + "\n")


def _panels():
    # Las raíces incluyen docks flotantes; solo se buscan tablas del Spreadsheet.
    panels = []
    roots = [hiero.ui.mainWindow()]
    roots.extend(root for root in iter_live_widgets(only_top_level=True) if root not in roots)
    for root in roots:
        for tree in root.findChildren(QtWidgets.QTreeView):
            if not is_widget_alive(tree):
                continue
            panel = tree.parentWidget()
            if (is_widget_alive(panel)
                    and panel.metaObject().className() == "Foundry::Storm::UI::SpreadsheetView"
                    and panel not in panels):
                panels.append(panel)
    return panels


def tab_count():
    """Incluye tabs detrás de otros y spreadsheets flotantes."""
    return len(_panels())


def close_for_refresh():
    """Cierra solo las vistas de media antes de openInTimeline; no toca clips."""
    _start_log("Media Spreadsheet: cierre previo al refresh")
    panels = _panels()
    for panel in panels:
        if is_widget_alive(panel) and not panel.close():
            _log("ERROR: no se pudo cerrar un tab de Media Spreadsheet")
            raise RuntimeError("No se pudo cerrar un tab de Media Spreadsheet")
    if panels:
        # close() difiere la destrucción: sin este paso Foundry puede reciclar
        # un tab obsoleto en vez de crear el del timeline nuevo.
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    _log("Tabs anteriores cerrados: %s" % len(panels))
    return len(panels)


def refresh(sequence=None):
    """Al final del refresh, repone la vista si Hiero no la creó y aplica reglas."""
    sequence = sequence if sequence is not None else hiero.ui.activeSequence()
    window = None
    if not _panels() and sequence is not None:
        spreadsheet = hiero.ui.openInSpreadsheet(sequence)
        # Retener el padre mientras se ajustan sus hijos Qt.
        window = spreadsheet.window()
    return apply()


def _spreadsheets():
    matches = []
    for panel in _panels():
        for view in panel.findChildren(QtWidgets.QTreeView):
            if not is_widget_alive(view) or not view.metaObject().className().endswith("SpreadsheetTreeView"):
                continue
            model = view.model()
            if not is_widget_alive(model):
                continue
            names = [str(model.headerData(i, QtCore.Qt.Horizontal) or "")
                     for i in range(model.columnCount())]
            if {"Status", "Clip", "Clip Media"}.issubset(names):
                # Al liberar el wrapper del padre, PySide invalida los wrappers
                # de sus hijos. Retener ambos durante todo el ajuste.
                matches.append((view, names, panel))
    return matches


def apply(order=_DEFAULT_ORDER, widths=None, hide=None, show=_DEFAULT_ORDER):
    """Aplica preferencias a los Media Spreadsheets abiertos; no toca el proyecto.

    order coloca esos nombres primero; el resto conserva su orden relativo.
    widths es un dict de nombre a pixeles o "auto"; None usa los sugeridos.
    hide/show cambian solo las columnas nombradas; hide=None usa las ocultas
    por defecto si existen. hide=() no oculta ninguna columna.
    Las filas se ordenan siempre por Clip ascendente, con el criterio del host.
    """
    started = time.perf_counter()
    _start_log("Media Spreadsheet: inicio")
    widths = _DEFAULT_WIDTHS if widths is None else widths
    hide_defaults = hide is None
    order = tuple(order)
    hide = _DEFAULT_HIDDEN if hide_defaults else tuple(hide)
    show = tuple(show)
    try:
        if len(order) != len(set(order)) or set(hide) & set(show):
            raise ValueError("Hay columnas duplicadas o presentes tanto en hide como en show")
        if any(size != "auto" and (not isinstance(size, int) or size <= 0)
               for size in widths.values()):
            raise ValueError('Los anchos deben ser enteros positivos o "auto"')
        matches = _spreadsheets()
        if not matches:
            _log("Sin Media Spreadsheet abierto: no hay columnas que ajustar")
            return 0
        requested = set(order) | set(widths) | set(show)
        if not hide_defaults:
            requested |= set(hide)
        prepared = [(view, {name: logical for logical, name in enumerate(names)})
                    for view, names, _panel in matches]
        for _view, columns in prepared:
            missing = requested - columns.keys()
            if missing:
                raise ValueError("Columnas no encontradas: %s" % ", ".join(sorted(missing)))
        states = [(view, view.header().saveState(), view.updatesEnabled(),
                   view.header().resizeContentsPrecision(), view.isSortingEnabled())
                  for view, _columns in prepared]
        try:
            for view, _state, was_enabled, _precision, _sorting in states:
                if was_enabled:
                    view.setUpdatesEnabled(False)
            for view, columns in prepared:
                header = view.header()
                for name in show:
                    logical = columns[name]
                    if view.isColumnHidden(logical):
                        view.setColumnHidden(logical, False)
                for visual, name in enumerate(order):
                    current = header.visualIndex(columns[name])
                    if current != visual:
                        header.moveSection(current, visual)
                hidden_present = tuple(name for name in hide if name in columns)
                for name in hidden_present:
                    logical = columns[name]
                    if not view.isColumnHidden(logical):
                        view.setColumnHidden(logical, True)
                # Qt mide todas las filas para no omitir un nombre largo fuera de pantalla.
                if "auto" in widths.values() and header.resizeContentsPrecision() != -1:
                    header.setResizeContentsPrecision(-1)
                for name, size in widths.items():
                    logical = columns[name]
                    if size == "auto":
                        view.resizeColumnToContents(logical)
                    elif header.sectionSize(logical) != size:
                        header.resizeSection(logical, size)
                if not view.isSortingEnabled():
                    view.setSortingEnabled(True)
                view.sortByColumn(columns["Clip"], QtCore.Qt.AscendingOrder)
                view.horizontalScrollBar().setValue(view.horizontalScrollBar().minimum())
                _log("Vista ajustada: filas=Clip ascendente orden=%s anchos=%s ocultas=%s visibles=%s"
                     % (order, widths, hidden_present, show))
        except Exception:
            for view, state, _was_enabled, _precision, sorting in states:
                view.header().restoreState(state)
                if view.isSortingEnabled() != sorting:
                    view.setSortingEnabled(sorting)
            raise
        finally:
            for view, _state, was_enabled, precision, _sorting in states:
                if view.header().resizeContentsPrecision() != precision:
                    view.header().setResizeContentsPrecision(precision)
                if was_enabled:
                    view.setUpdatesEnabled(True)
        _log("Duración total: %.3f ms" % ((time.perf_counter() - started) * 1000))
        return len(matches)
    except Exception:
        _log("ERROR:\n" + traceback.format_exc())
        raise
