"""
____________________________________________________________________

  LGA_NKS_ShotMarks_Find v1.00 | Lega

  Find Shot Mark: Shift+Click en Shot Marks del panel Review. Una
  ventanita con un campo de texto que busca entre las marcas de Shot
  Marks del timeline del visor: por nombre de shot o por cualquier
  texto de la planilla (descripcion, brief, status, vendor, escena,
  categoria, episodio, TC, clip). Find salta al shot con ese nombre
  exacto o al primer resultado; Next, al siguiente desde el que se
  mostro (o desde el playhead si se movio), y al final vuelve al
  primero. Cada salto muestra la marca en la ventanita de Previous /
  Next Mark.

  Existe porque con cientos de marcas, Previous / Next no sirve para
  ir a un shot puntual ni a "el del humo de la sopa".

  Queda siempre arriba (Keep this window on top), como la ventana del
  Flow Pull: en Windows con SetWindowPos, sin recrear la ventana.
  Busca en la metadata de los tags, no en el Excel: no lee la
  planilla ni la DB de PipeSync y responde al instante.

  Log: logs/DebugPy_LGA_NKS_ShotMarks_Find.log.

  v1.00: Version inicial.
____________________________________________________________________
"""

import configparser
import importlib.util
import logging
import os
import sys
from pathlib import Path

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

WINDOW_NAME = "LGA_ShotMarkFind"
# Sube cuando cambia la API de la ventana: el panel re-ejecuta este modulo en
# cada click, y una ventana creada por una version vieja se reemplaza.
WINDOW_API = 1
WINDOW_WIDTH = 440
SCREEN_MARGIN = 24

LOGGER_NAME = "LGA_NKS_ShotMarks_Find"

# INI propio: ShotMarks.ini lo reescribe entero el dialogo de Shot Marks y se
# llevaria cualquier seccion ajena.
CONFIG_FILE_NAME = "ShotMarksFind.ini"
CONFIG_SECTION = "FindWindow"

# Tooltips en castellano, separados del widget para que pasar a bilingue sea
# un cambio de datos.
TOOLTIPS = {
    "query": "Nombre de shot o cualquier texto de la planilla: descripcion, brief, status, "
             "vendor, escena, categoria o TC. Sin mayusculas ni acentos.",
    "find": "Salta al shot que se llama exactamente asi o, si no hay, al primer resultado "
            "del timeline (Enter).",
    "next": "Salta al siguiente resultado; despues del ultimo vuelve al primero (Enter "
            "otra vez, con el mismo texto).",
    "keep_on_top": "Deja esta ventana arriba de todas las demas, tambien de Nuke Studio.",
}

FIELD_LABELS = {"shot": "Shot name", "description": "Description", "brief": "Brief",
                "status": "Status", "vendor": "Vendor", "scene": "Scene",
                "category": "Category", "episode": "Episode", "tc_in": "REC TC IN",
                "tc_out": "REC TC OUT", "clip": "Camera clip"}

_modules = {}


def _module(name):
    """Modulo hermano cargado por ruta, como lo carga el panel."""
    if name not in _modules:
        path = Path(__file__).resolve().parent / ("%s.py" % name)
        spec = importlib.util.spec_from_file_location(name, str(path))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _modules[name] = module
    return _modules[name]


def _nav():
    return _module("LGA_NKS_ShotMarks_Nav")


def _sheet():
    return _module("LGA_NKS_ShotMarks_Sheet")


def _logger():
    log_dir = Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(exist_ok=True)
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG)
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
    logger.propagate = False
    handler = logging.FileHandler(str(log_dir / "DebugPy_LGA_NKS_ShotMarks_Find.log"),
                                  mode="w", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    if DEBUG:
        logger.addHandler(logging.StreamHandler())
    return logger


def _log():
    return logging.getLogger(LOGGER_NAME)


# -- preferencias ----------------------------------------------------------

def _config_path():
    if sys.platform == "win32":
        root = os.getenv("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        root = str(Path.home() / "Library" / "Application Support")
    else:
        root = str(Path.home() / ".config")
    return Path(root) / "LGA" / "HieroTools" / CONFIG_FILE_NAME


def _load_keep_on_top():
    try:
        config = configparser.ConfigParser()
        config.read(str(_config_path()), encoding="utf-8")
        return config.getboolean(CONFIG_SECTION, "keep_on_top", fallback=True)
    except Exception as exc:
        _log().warning("No se pudo leer keep_on_top: %s", exc)
        return True


def _save_keep_on_top(value):
    try:
        path = _config_path()
        config = configparser.ConfigParser()
        config.read(str(path), encoding="utf-8")
        if not config.has_section(CONFIG_SECTION):
            config.add_section(CONFIG_SECTION)
        config.set(CONFIG_SECTION, "keep_on_top", "true" if value else "false")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(path), "w", encoding="utf-8", newline="\n") as handle:
            config.write(handle)
    except Exception as exc:
        _log().warning("No se pudo guardar keep_on_top: %s", exc)


# -- datos -----------------------------------------------------------------

def mark_entries(tags):
    """{campo: texto} de cada marca para buscar, en el orden de `tags`.

    Solo la metadata del tag: mark_info del Nav ademas busca el color del
    vendor en la DB de PipeSync, y hacerlo por cada marca en cada busqueda
    seria lento sin ninguna necesidad.
    """
    sheet = _sheet()
    entries = []
    for tag in tags:
        data = tag.metadata()

        def get(key, data=data):
            return data.value(key) if data.hasKey(key) else None

        entry = sheet.mark_info_from_metadata(get)
        if not entry["brief"]:
            # Tag de la v1.00 de Shot Marks: el brief esta en la nota.
            entry["brief"] = tag.note()
        entry["shot"] = tag.name()
        entries.append(entry)
    return entries


# -- ventana ---------------------------------------------------------------

class ShotMarkFindWindow(QtWidgets.QWidget):
    """Buscador de marcas. Una sola ventana, reutilizada en cada Shift+Click."""

    lga_api = WINDOW_API

    def __init__(self, parent=None):
        super(ShotMarkFindWindow, self).__init__(parent)
        self.setObjectName(WINDOW_NAME)
        self.setWindowTitle("Find Shot Mark")
        self.setStyleSheet(Style.FORM)
        self._keep_on_top = _load_keep_on_top()
        self._apply_window_flags()
        self._placed = False
        # Ultimo resultado mostrado: indice de marca y texto buscado. Next
        # avanza desde ahi mientras el texto no cambie.
        self._current = None
        self._last_query = None
        self._build()
        apply_ui_font(self)
        # Despues de la fuente, que es con la que se mide. El estado reserva
        # dos renglones (resultado + "Back to the first match") para que la
        # ventana no cambie de alto en cada busqueda.
        self.status.setMinimumHeight(self.status.fontMetrics().lineSpacing() * 2)
        self.setFixedWidth(WINDOW_WIDTH)

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        margin = Metric.WINDOW_MARGIN
        layout.setContentsMargins(margin, margin, margin, margin)
        layout.setSpacing(Metric.SPACING)

        self.query = QtWidgets.QLineEdit()
        self.query.setStyleSheet(Style.LINE_EDIT)
        self.query.setPlaceholderText("Shot name or any text from the sheet")
        self.query.setClearButtonEnabled(True)
        self.query.setToolTip(TOOLTIPS["query"])
        self.query.returnPressed.connect(self._on_return)
        self.query.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.query)

        self.status = QtWidgets.QLabel()
        self.status.setTextFormat(Qt.RichText)
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.status)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(Metric.SPACING)
        self.keep_on_top_chk = QtWidgets.QCheckBox("Keep this window on top")
        self.keep_on_top_chk.setProperty("lgaLabeled", True)
        self.keep_on_top_chk.setChecked(self._keep_on_top)
        self.keep_on_top_chk.setToolTip(TOOLTIPS["keep_on_top"])
        self.keep_on_top_chk.toggled.connect(self._set_keep_on_top)
        row.addWidget(self.keep_on_top_chk)
        row.addStretch(1)
        self.next_btn = QtWidgets.QPushButton("Next")
        self.next_btn.setStyleSheet(Style.BTN_SECONDARY)
        self.next_btn.setFixedHeight(Metric.BUTTON_HEIGHT)
        self.next_btn.setToolTip(TOOLTIPS["next"])
        self.next_btn.clicked.connect(lambda: self.search("next"))
        row.addWidget(self.next_btn)
        # La accion va ultima, a la derecha, y es la unica violeta.
        self.find_btn = QtWidgets.QPushButton("Find")
        self.find_btn.setStyleSheet(Style.BTN_PRIMARY)
        self.find_btn.setFixedHeight(Metric.BUTTON_HEIGHT)
        self.find_btn.setToolTip(TOOLTIPS["find"])
        self.find_btn.clicked.connect(lambda: self.search("find"))
        row.addWidget(self.find_btn)
        layout.addLayout(row)

        # Esc cierra: es una ventana, no un QDialog, y no lo trae solo.
        close_shortcut = QtGui.QShortcut(QtGui.QKeySequence(Qt.Key_Escape), self)
        close_shortcut.activated.connect(self.close)
        self._set_status(_dim("Enter jumps to the mark. Enter again goes to the next match."))
        self._update_buttons()

    # -- interaccion -------------------------------------------------------

    def _on_text_changed(self, _text):
        self._update_buttons()

    def _update_buttons(self):
        has_text = bool(self.query.text().strip())
        self.find_btn.setEnabled(has_text)
        self.next_btn.setEnabled(has_text)

    def _on_return(self):
        # Enter otra vez con el mismo texto sigue al siguiente, como un Find
        # de cualquier editor.
        same = self._current is not None and self.query.text() == self._last_query
        self.search("next" if same else "find")

    def search(self, mode):
        query = self.query.text()
        if not query.strip():
            return
        nav, sheet = _nav(), _sheet()
        viewer, sequence = nav._viewer_and_sequence()
        if viewer is None or sequence is None:
            self._set_status(_warning("Open a timeline in the viewer first."))
            return
        tags = nav.mark_tags(sequence)
        if not tags:
            self._set_status(_warning(
                "This timeline has no Shot Marks. Add them with the Shot Marks button."))
            _log().info("%s no tiene marcas", sequence.name())
            return
        entries = mark_entries(tags)
        matches = sheet.search_marks(entries, query)
        if not matches:
            self._current = None
            self._set_status(_warning("No Shot Mark contains %s." % _quoted(query)))
            _log().info("'%s': sin resultados en %d marcas de %s", query, len(tags),
                        sequence.name())
            return
        starts = [int(tag.inTime()) for tag in tags]
        wrapped = False
        if mode == "find":
            position = sheet.find_match(matches, entries, query)
        else:
            current = self._current if query == self._last_query else None
            if current is not None and current >= len(tags):
                current = None  # Shot Marks se volvio a correr: hay menos marcas.
            position, wrapped = sheet.next_match(matches, starts, int(viewer.time()), current)
        index, field = matches[position]
        nav.show_mark_at(viewer, sequence, tags, index)
        self._current, self._last_query = index, query
        self._set_status(_result_html(entries[index]["shot"], field, position, len(matches),
                                      wrapped))
        _log().info("'%s' %s: %s (marca %d, campo %s, resultado %d de %d%s)", query, mode,
                    entries[index]["shot"], index + 1, field, position + 1, len(matches),
                    ", dio la vuelta" if wrapped else "")

    def _set_status(self, text):
        self.status.setText(text)

    # -- presentacion ------------------------------------------------------

    def present(self):
        """Muestra la ventana con el foco en el campo, lista para escribir."""
        if not self._placed:
            self._place()
        self.show()
        self.raise_()
        self.activateWindow()
        self.query.setFocus()
        self.query.selectAll()
        if sys.platform.startswith("win"):
            # Despues de que Qt termine el show: si no, lo reposiciona y pisa
            # el topmost (mismo orden que el Flow Pull).
            QtCore.QTimer.singleShot(0, lambda: self._set_topmost_native(self._keep_on_top))

    def _place(self):
        # Primera vez: a la derecha de la ventanita de info de la marca (arriba
        # a la izquierda), para no taparla. Despues queda donde el usuario la deje.
        screen = None
        main = hiero.ui.mainWindow()
        if main is not None and main.windowHandle() is not None:
            screen = main.windowHandle().screen()
        if screen is None:
            screen = QtWidgets.QApplication.primaryScreen()
        area = screen.availableGeometry()
        self.move(area.left() + SCREEN_MARGIN * 2 + _nav().WINDOW_WIDTH,
                  area.top() + SCREEN_MARGIN * 3)
        self._placed = True

    # -- always on top (mismo mecanismo que el Flow Pull) ------------------

    def _apply_window_flags(self):
        flags = Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint
        # En Windows el topmost lo maneja SetWindowPos; horneado en los flags,
        # cambiarlo despues recrea la ventana nativa (parpadeo).
        if self._keep_on_top and not sys.platform.startswith("win"):
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)

    def _set_topmost_native(self, on):
        """HWND_TOPMOST / NOTOPMOST con SetWindowPos: cambia solo el z-order.

        argtypes declarados: sin ellos ctypes trunca el HWND de 64 bits y la
        llamada apunta a un handle invalido.
        """
        try:
            import ctypes
            import ctypes.wintypes

            set_window_pos = ctypes.windll.user32.SetWindowPos
            set_window_pos.restype = ctypes.wintypes.BOOL
            set_window_pos.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.HWND,
                                       ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                       ctypes.c_int, ctypes.wintypes.UINT]
            swp_nosize, swp_nomove, swp_noactivate = 0x0001, 0x0002, 0x0010
            ok = set_window_pos(int(self.winId()),
                                ctypes.wintypes.HWND(-1 if on else -2), 0, 0, 0, 0,
                                swp_nomove | swp_nosize | swp_noactivate)
            _log().info("SetWindowPos topmost=%s ok=%s", on, bool(ok))
            return bool(ok)
        except Exception as exc:
            _log().warning("SetWindowPos fallo: %s", exc)
            return False

    def _set_keep_on_top(self, value):
        self._keep_on_top = bool(value)
        _save_keep_on_top(self._keep_on_top)
        if sys.platform.startswith("win") and self._set_topmost_native(self._keep_on_top):
            return
        geometry = self.geometry()
        self._apply_window_flags()
        self.setGeometry(geometry)
        self.show()


def _dim(text):
    return '<span style="color:%s">%s</span>' % (Color.TEXT_DIM, text)


def _warning(text):
    return '<span style="color:%s">%s</span>' % (Color.WARNING_TEXT, _escape(text))


def _escape(text):
    return (str(text or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def _quoted(text):
    return "“%s”" % text.strip()


def _result_html(shot, field, position, total, wrapped):
    """'PROJA_010_0100 · match 2 of 5 · found in Brief'."""
    parts = [emphasis(_escape(shot)), _dim("match %d of %d" % (position + 1, total))]
    if field != "shot":
        parts.append(_dim("found in %s" % FIELD_LABELS.get(field, field)))
    text = _dim(" &middot; ").join(parts)
    if wrapped:
        text += "<br>" + _dim("Back to the first match.")
    return text


def find_window(create=True):
    """La ventana existente, o una nueva en el mismo lugar si cambio la API."""
    old = None
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if widget.objectName() == WINDOW_NAME:
            if getattr(widget, "lga_api", None) == WINDOW_API:
                return widget
            old = widget
    if not create:
        return None
    window = ShotMarkFindWindow(hiero.ui.mainWindow())
    if old is not None:
        window.move(old.pos())
        window._placed = True
        old.close()
        old.deleteLater()
    return window


# -- entrada ---------------------------------------------------------------

def main():
    _logger().info("Find Shot Mark abierto")
    find_window().present()


if __name__ == "__main__":
    main()
