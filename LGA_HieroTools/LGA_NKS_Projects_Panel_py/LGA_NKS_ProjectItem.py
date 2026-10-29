# -*- coding: utf-8 -*-

"""
____________________________________________________________________

  LGA_NKS_ProjectItem v1.06 | Lega

  Widget personalizado para mostrar proyectos y secuencias en el panel de proyectos LGA.

  v1.06: Clic derecho sobre un timeline abre un menu con Delete Timeline, que
         delega en delete_sequence() del panel. El switch de timeline queda
         solo en el boton izquierdo.
  v1.05: Iconos Save incremental (disquete con +) y Upload to Wasabi (nube con
         flecha) antes de la x, con el mismo trazo. RowIconButton los dibuja
         con QPainter y tokens de Color: hover gris, y en upload spinner,
         check o error. El estado de la subida vive en el panel y sobrevive
         al rearmado de la lista. Tras guardar, el nombre se ilumina un momento.
  v1.04: El triangulo pasa a ser un label propio con hover compartido con el
         nombre (los dos hacen lo mismo y se iluminan juntos). Un proyecto
         abierto se colapsa y expande sin cerrarlo, y el estado sobrevive al
         rearmado de la lista. Boton x para cerrar el proyecto, pegado al
         nombre y visible solo con el mouse sobre la fila de un proyecto abierto.
  v1.03: Las secuencias se limpian con takeAt + hide + deleteLater en vez de
         setParent(None), que podia dejar un widget huerfano abierto como ventana.
  v1.02: El nombre visible conserva lo que va despues del bloque _SUP
  v1.01: El color sale de 'project_key' (carpeta VFX-) y no del nombre del archivo
____________________________________________________________________

"""

# Forzar recarga del módulo para evitar problemas de cache en Nuke
import os
import sys
if 'LGA_NKS_ProjectItem' in sys.modules:
    import importlib
    importlib.reload(sys.modules['LGA_NKS_ProjectItem'])

from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui, QtCore, Qt, horizontal_advance
from LGA_NKS_Shared.LGA_UI_Style_HieroTools import Style, Color

# Lado del triangulo de expandir/colapsar, en px. Se dibuja en vez de usar los
# caracteres de texto: la fuente dibuja el que apunta a la derecha mucho mas
# chico que el que apunta hacia abajo.
TRIANGLE_SIZE = 9


def _triangle_pixmap(color, pointing_down, dpr=1.0, size=TRIANGLE_SIZE):
    """Triangulo lleno del color pedido; los dos sentidos ocupan el mismo cuadrado."""
    pixmap = QtGui.QPixmap(int(round(size * dpr)), int(round(size * dpr)))
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.setPen(QtCore.Qt.NoPen)
    painter.setBrush(QtGui.QColor(color))
    inset = size * 0.12
    if pointing_down:
        points = [(0, inset), (size, inset), (size / 2.0, size - inset)]
    else:
        points = [(inset, 0), (size - inset, size / 2.0), (inset, size)]
    painter.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(x, y) for x, y in points]))
    painter.end()
    return pixmap


# Boton de cerrar proyecto: caja chica (el rojo del hover de BTN_CLOSE ocupa toda
# la caja) y la x dibujada, mas grande y clara que el glifo de la hoja.
CLOSE_BUTTON_SIZE = 16
CLOSE_ICON_SIZE = 12


def _close_icon(color, dpr=1.0, size=CLOSE_ICON_SIZE):
    """Cruz dibujada con trazo redondeado, del color pedido."""
    pixmap = QtGui.QPixmap(int(round(size * dpr)), int(round(size * dpr)))
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    pen = QtGui.QPen(QtGui.QColor(color))
    pen.setWidthF(1.6)
    pen.setCapStyle(QtCore.Qt.RoundCap)
    painter.setPen(pen)
    margin = 1.5
    painter.drawLine(QtCore.QPointF(margin, margin), QtCore.QPointF(size - margin, size - margin))
    painter.drawLine(QtCore.QPointF(size - margin, margin), QtCore.QPointF(margin, size - margin))
    painter.end()
    return QtGui.QIcon(pixmap)


# Iconos de accion de la fila (Save incremental, Upload to Wasabi): caja de 18 px
# y glifo de 16 px con el mismo trazo de 1.6 px que la x, para que los
# tres se lean como familia. Diseno elegido en
# +Building_Blocks/Mockups/ProjectsPanel_RowIcons_Mockup.html (S1 y U1).
ACTION_BUTTON_SIZE = 18
ACTION_GLYPH_SIZE = 16
# Aire entre icono e icono (save, upload y la x)
ACTION_SPACING = 2
ACTION_PEN_WIDTH = 1.6
SPINNER_INTERVAL_MS = 50
# Tras una subida correcta el check queda este tiempo y vuelve al icono.
UPLOAD_OK_HOLD_MS = 2500
# Tras un Save incremental el nombre queda iluminado este tiempo.
SAVE_FLASH_MS = 1200

# Estados del boton de upload. El error queda hasta el proximo click: su
# motivo tiene que poder leerse en el tooltip.
STATE_IDLE = "idle"
STATE_BUSY = "busy"
STATE_OK = "ok"
STATE_ERROR = "error"

# Tooltips en un solo lugar: van a pasar a ser bilingues y asi la migracion es
# un cambio de datos, no de widgets.
TOOLTIPS = {
    "toggle": "Colapsar / expandir las secuencias (no cierra el proyecto)",
    "close": "Cerrar el proyecto. Si tiene cambios sin guardar, pregunta antes",
    "save": "Guardar versión incremental: {current} → {next}",
    "save_unknown": "Guardar versión incremental (sube un número de versión)",
    "upload": "Subir {name} a Wasabi con FileManager S3",
    "upload_busy": "Subiendo {name} a Wasabi… El progreso está en la pestaña Activity de FileManager S3",
    "upload_ok": "{name} subido a Wasabi",
    "upload_error": "No se pudo subir {name}: {message}\nClick para reintentar",
    "delete_timeline": "Borrar este timeline del proyecto. Pregunta antes y se deshace con Ctrl+Z",
}


def _save_glyph_path():
    """S1: disquete con un + en la esquina. Devuelve (cuerpo, recorte, plus) en viewBox 16."""
    body = QtGui.QPainterPath()
    body.moveTo(1.5, 1.5)
    body.lineTo(10.2, 1.5)
    body.lineTo(13.2, 4.5)
    body.lineTo(13.2, 13.2)
    body.lineTo(1.5, 13.2)
    body.closeSubpath()
    body.moveTo(4.3, 1.5)
    body.lineTo(4.3, 4.6)
    body.lineTo(9.6, 4.6)
    body.lineTo(9.6, 1.5)
    # El + va recortado del disquete: un circulo de aire alrededor.
    cutout = QtGui.QPainterPath()
    cutout.addEllipse(QtCore.QPointF(12.6, 12.6), 4.3, 4.3)
    plus = QtGui.QPainterPath()
    plus.moveTo(12.6, 10.1)
    plus.lineTo(12.6, 15.1)
    plus.moveTo(10.1, 12.6)
    plus.lineTo(15.1, 12.6)
    return body, cutout, plus


def _upload_glyph_path():
    """
    U1: nube con flecha hacia arriba. Devuelve (nube, recorte, flecha) en viewBox 16.

    La nube llena el ancho y casi todo el alto de la caja: con la proporcion
    del mockup quedaba chata y se veia mas chica que el disquete y la x.
    """
    cloud = QtGui.QPainterPath()
    cloud.addEllipse(QtCore.QPointF(4.2, 9.6), 3.4, 3.4)
    top = QtGui.QPainterPath()
    top.addEllipse(QtCore.QPointF(8.4, 6.6), 4.6, 4.6)
    right = QtGui.QPainterPath()
    right.addEllipse(QtCore.QPointF(11.9, 9.3), 3.7, 3.7)
    base = QtGui.QPainterPath()
    base.addRect(QtCore.QRectF(4.2, 9.0, 7.7, 4.0))
    cloud = cloud.united(top).united(right).united(base).simplified()
    # La flecha sale de la nube por abajo: se abre un hueco en el borde.
    cutout = QtGui.QPainterPath()
    cutout.addRect(QtCore.QRectF(5.4, 12.0, 5.2, 3.0))
    arrow = QtGui.QPainterPath()
    arrow.moveTo(8.0, 15.0)
    arrow.lineTo(8.0, 7.4)
    arrow.moveTo(5.6, 9.8)
    arrow.lineTo(8.0, 7.4)
    arrow.lineTo(10.4, 9.8)
    return cloud, cutout, arrow


def _check_glyph_path():
    path = QtGui.QPainterPath()
    path.moveTo(3.0, 8.4)
    path.lineTo(6.5, 11.8)
    path.lineTo(13.0, 4.6)
    return None, None, path


def _warning_glyph_path():
    path = QtGui.QPainterPath()
    path.moveTo(8.0, 2.5)
    path.lineTo(14.0, 13.2)
    path.lineTo(2.0, 13.2)
    path.closeSubpath()
    path.moveTo(8.0, 6.6)
    path.lineTo(8.0, 9.4)
    path.moveTo(8.0, 11.4)
    path.lineTo(8.0, 11.5)
    return None, None, path


_GLYPHS = {
    "save": _save_glyph_path,
    "upload": _upload_glyph_path,
    "check": _check_glyph_path,
    "warning": _warning_glyph_path,
}


class RowIconButton(QtWidgets.QAbstractButton):
    """
    Boton de icono de la fila de proyecto, dibujado a mano.

    No hay hoja de estilo para un boton plano con hover gris: BTN_ICON trae
    caja y borde, y BTN_CLOSE pinta de rojo. Se dibuja con QPainter y los
    tokens de Color, sin QSS propio. Ademas tiene que poder mostrar estados
    (spinner, check, error), que un QPushButton con QSS no resuelve.
    """

    def __init__(self, glyph, parent=None):
        super(RowIconButton, self).__init__(parent)
        self.glyph = glyph
        self.state = STATE_IDLE
        self._angle = 0
        self._spinner = QtCore.QTimer(self)
        self._spinner.setInterval(SPINNER_INTERVAL_MS)
        self._spinner.timeout.connect(self._advance_spinner)
        self.setFixedSize(ACTION_BUTTON_SIZE, ACTION_BUTTON_SIZE)
        self.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.setAttribute(QtCore.Qt.WA_Hover, True)
        policy = self.sizePolicy()
        policy.setRetainSizeWhenHidden(True)
        self.setSizePolicy(policy)

    def set_state(self, state):
        self.state = state
        if state == STATE_BUSY:
            self._spinner.start()
        else:
            self._spinner.stop()
        self.update()

    def _advance_spinner(self):
        self._angle = (self._angle + 30) % 360
        self.update()

    def enterEvent(self, event):
        self.update()
        super(RowIconButton, self).enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super(RowIconButton, self).leaveEvent(event)

    def sizeHint(self):
        return QtCore.QSize(ACTION_BUTTON_SIZE, ACTION_BUTTON_SIZE)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        hovered = self.underMouse() and self.state in (STATE_IDLE, STATE_ERROR)
        if hovered:
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QColor(Color.SURFACE_HOVER))
            painter.drawRoundedRect(QtCore.QRectF(self.rect()), 3, 3)

        if self.state == STATE_BUSY:
            self._paint_spinner(painter)
        elif self.state == STATE_OK:
            self._paint_glyph(painter, "check", Color.OK_TEXT)
        elif self.state == STATE_ERROR:
            self._paint_glyph(painter, "warning", Color.ERROR_TEXT)
        else:
            self._paint_glyph(painter, self.glyph, Color.TEXT_STRONG if hovered else Color.TEXT)
        painter.end()

    def _paint_glyph(self, painter, glyph, color):
        outline, cutout, stroke = _GLYPHS[glyph]()
        scale = ACTION_GLYPH_SIZE / 16.0
        offset = (ACTION_BUTTON_SIZE - ACTION_GLYPH_SIZE) / 2.0
        painter.save()
        painter.translate(offset, offset)
        painter.scale(scale, scale)
        pen = QtGui.QPen(QtGui.QColor(color))
        pen.setWidthF(ACTION_PEN_WIDTH / scale)  # grosor visual igual al de la x
        pen.setCapStyle(QtCore.Qt.RoundCap)
        pen.setJoinStyle(QtCore.Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.NoBrush)
        if outline is not None:
            painter.save()
            if cutout is not None:
                visible = QtGui.QPainterPath()
                visible.addRect(QtCore.QRectF(-4, -4, 24, 24))
                painter.setClipPath(visible.subtracted(cutout))
            painter.drawPath(outline)
            painter.restore()
        painter.drawPath(stroke)
        painter.restore()

    def _paint_spinner(self, painter):
        radius = ACTION_GLYPH_SIZE / 2.0 - 1.0
        center = QtCore.QPointF(self.width() / 2.0, self.height() / 2.0)
        rect = QtCore.QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2)
        track = QtGui.QPen(QtGui.QColor(Color.BORDER_STRONG))
        track.setWidthF(2.0)
        painter.setPen(track)
        painter.drawEllipse(rect)
        arc = QtGui.QPen(QtGui.QColor(Color.INFO))
        arc.setWidthF(2.0)
        arc.setCapStyle(QtCore.Qt.RoundCap)
        painter.setPen(arc)
        # drawArc va en 1/16 de grado, antihorario desde las 3
        painter.drawArc(rect, int((90 - self._angle) * 16), int(-100 * 16))

# Importar funciones necesarias del módulo principal
# Estas serán importadas desde el archivo principal cuando se importe este módulo
get_project_colors = None
debug_print = None
switch_to_sequence = None


def initialize_dependencies(colors_func, debug_func, switch_func):
    """Inicializar las dependencias externas necesarias para ProjectItem"""
    global get_project_colors, debug_print, switch_to_sequence
    get_project_colors = colors_func
    debug_print = debug_func
    switch_to_sequence = switch_func


class ProjectItem(QtWidgets.QWidget):
    """Widget personalizado para mostrar un proyecto y sus secuencias"""

    def __init__(self, project_info, panel=None, has_newer_version=False, newer_version_info=None, parent=None):
        super(ProjectItem, self).__init__(parent)
        self.project_info = project_info
        self.panel = panel  # Referencia al ProjectsPanel para el event filter
        self.is_open = False
        self.sequences = []
        self.has_newer_version = has_newer_version
        self.newer_version_info = newer_version_info  # Dict con info de versión más nueva
        # Colapsado es estado del PANEL, no de Hiero: el panel lo recuerda por
        # proyecto para que sobreviva al rearmado de la lista.
        self.collapsed = bool(
            panel and project_info.get("nombre_base", "") in getattr(panel, "collapsed_projects", ())
        )
        self.setup_ui()

    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)

        # Contenedor horizontal para el proyecto (para evitar expansión horizontal)
        project_container = QtWidgets.QWidget()
        project_layout = QtWidgets.QHBoxLayout(project_container)
        project_layout.setContentsMargins(0, 0, 0, 0)
        project_layout.setSpacing(0)

        # Triangulo propio: hueco = cerrado, lleno = abierto (abajo expandido,
        # a la derecha colapsado). Antes era un caracter dentro del nombre y un
        # proyecto abierto colapsado se veia igual que uno cerrado.
        self.toggle_label = QtWidgets.QLabel()
        self.toggle_label.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.toggle_label.setFixedWidth(16)
        self.toggle_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.toggle_label.setToolTip(TOOLTIPS["toggle"])
        # Hover compartido con el nombre: lo maneja eventFilter() de este item,
        # no el del panel, que iluminaba cada label por separado.
        self.toggle_label.installEventFilter(self)
        project_layout.addWidget(self.toggle_label)

        # Nombre del proyecto (clickable)
        self.project_label = QtWidgets.QLabel()
        self.project_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.project_label.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.project_label.setWordWrap(False)  # No word wrap para mantener en una línea
        self.project_label.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        # Asegurar que el texto no se trunque
        self.project_label.setTextFormat(QtCore.Qt.PlainText)
        self.project_label.installEventFilter(self)
        project_layout.addWidget(self.project_label)

        # Botón de update (siempre creado, inicialmente oculto)
        self.update_button = QtWidgets.QPushButton()
        self.update_button.setToolTip("Actualizar a versión más nueva")
        self.update_button.setStyleSheet("""
            QPushButton {
                border: none;
                padding: 2px;
                background: transparent;
            }
        """)
        self.update_button.setVisible(False)  # Inicialmente oculto
        self.update_button.setFixedSize(20, 20)  # Tamaño fijo pequeño

        # Configurar iconos SVG para el botón de update
        import os
        update_icon_path = os.path.join(os.path.dirname(__file__), "update.svg")
        update_hover_icon_path = os.path.join(os.path.dirname(__file__), "update_white.svg")

        if os.path.exists(update_icon_path) and os.path.exists(update_hover_icon_path):
            self.update_icon_normal = QtGui.QIcon(update_icon_path)
            self.update_icon_hover = QtGui.QIcon(update_hover_icon_path)
            self.update_button.setIcon(self.update_icon_normal)
            self.update_button.setIconSize(QtCore.QSize(16, 16))
            # Guardar referencias de iconos en el propio botón para el event filter
            self.update_button.update_icon_normal = self.update_icon_normal
            self.update_button.update_icon_hover = self.update_icon_hover

            # Instalar event filter para manejar hover
            if self.panel:
                self.update_button.installEventFilter(self.panel)

        # Conectar el click del botón
        self.update_button.clicked.connect(self.on_update_click)
        project_layout.addWidget(self.update_button)

        # Save incremental y Upload to Wasabi: antes de la x, que queda ultima
        # para que el mouse no caiga en cerrar al ir a guardar. Igual que la x,
        # solo en proyectos abiertos y con el mouse sobre la fila; el de upload
        # queda visible mientras sube y mientras muestra el resultado.
        self.save_button = RowIconButton("save")
        self.upload_button = RowIconButton("upload")
        project_layout.addSpacing(3)  # aire entre el ")" del nombre y el primer icono
        for button in (self.save_button, self.upload_button):
            button.setVisible(False)
            project_layout.addWidget(button)
            project_layout.addSpacing(ACTION_SPACING)

        # Boton de cerrar: pegado al nombre (despues de la flecha de update, si
        # esta), solo en proyectos abiertos y solo con el mouse sobre la fila.
        # Reserva su lugar oculto para que la fila no salte al aparecer.
        self.close_button = QtWidgets.QPushButton()
        self.close_button.setStyleSheet(Style.BTN_CLOSE)
        try:
            dpr = self.devicePixelRatioF()
        except Exception:
            dpr = 1.0
        self.close_button.setIcon(_close_icon(Color.TEXT, dpr))
        self.close_button.setIconSize(QtCore.QSize(CLOSE_ICON_SIZE, CLOSE_ICON_SIZE))
        self.close_button.setFixedSize(CLOSE_BUTTON_SIZE, CLOSE_BUTTON_SIZE)
        self.close_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.close_button.setToolTip(TOOLTIPS["close"])
        policy = self.close_button.sizePolicy()
        policy.setRetainSizeWhenHidden(True)
        self.close_button.setSizePolicy(policy)
        self.close_button.setVisible(False)
        project_layout.addWidget(self.close_button)

        # Spacer horizontal para empujar los elementos a la izquierda
        spacer = QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        project_layout.addItem(spacer)

        project_container.enterEvent = lambda event: self._set_close_visible(True)
        project_container.leaveEvent = lambda event: self._set_close_visible(False)
        self.project_container = project_container
        self._row_hovered = False
        self._upload_tooltip_name = ""
        self._upload_ok_timer = QtCore.QTimer(self)
        self._upload_ok_timer.setSingleShot(True)
        self._upload_ok_timer.timeout.connect(lambda: self.set_upload_state(STATE_IDLE))

        layout.addWidget(project_container)

        # Contenedor para secuencias
        self.sequences_widget = QtWidgets.QWidget()
        self.sequences_layout = QtWidgets.QVBoxLayout(self.sequences_widget)
        self.sequences_layout.setContentsMargins(20, 0, 0, 0)
        self.sequences_widget.hide()
        layout.addWidget(self.sequences_widget)

        self.update_display()

    def update_display(self):
        nombre = self.project_info.get("nombre_base", "")
        version = self.project_info.get("version", "")

        from LGA_Projects_Panel_ScanProjects import (
            obtener_clave_proyecto,
            obtener_nombre_display_proyecto,
        )

        # Nombre visible: sin el bloque _SUP, pero conservando lo que venga despues
        project_name = obtener_nombre_display_proyecto(nombre)

        # Limpiar versión (quitar 'v' inicial)
        clean_version = version.lstrip('v')

        # Crear texto formateado: "NOMBRE (vXXX)"
        formatted_text = f"{project_name} (v{clean_version})"

        # Obtener colores para este proyecto. El color es del proyecto de trabajo
        # (carpeta VFX-), no del nombre del archivo: PROJB_SUP y PROJB_Breakdown son PROJB.
        # Por eso el fallback recorta en _SUP y no usa el nombre visible.
        color_key = self.project_info.get("project_key") or obtener_clave_proyecto(nombre_base=nombre)
        debug_print(f"🎨 Aplicando colores para proyecto: '{color_key}' (desde nombre_base: '{nombre}')")
        base_color, hover_color = get_project_colors(color_key)
        debug_print(f"🎨 Colores aplicados - Base: {base_color}, Hover: {hover_color}")

        # Triangulo: hacia abajo si esta abierto y expandido; hacia la derecha si
        # esta cerrado o colapsado. Lo que distingue a un abierto colapsado es la
        # x que aparece con el mouse encima.
        self._triangle_down = bool(self.is_open and self.sequences and not self.collapsed)
        display_text = formatted_text
        for label in (self.toggle_label, self.project_label):
            # Guardar colores para el hover compartido
            label.setProperty("base_color", base_color)
            label.setProperty("hover_color", hover_color)
            label.setProperty("is_project_label", True)  # Para distinguir del resto
        self._paint_title("base_color")
        if (
            self.is_open
            and self.panel is not None
            and hasattr(self.panel, "take_flash_after_save")
            and self.panel.take_flash_after_save(self.project_key())
        ):
            # Recien guardado como v+1: el nombre se ilumina un momento. Sin cartel.
            self._paint_title("hover_color")
            QtCore.QTimer.singleShot(SAVE_FLASH_MS, self._end_save_flash)

        if self.is_open and self.sequences and not self.collapsed:
            self.show_sequences()
        else:
            self.sequences_widget.hide()
        if self.panel is not None and hasattr(self.panel, "upload_state_for"):
            # La subida sigue aunque la lista se rearme: el estado vive en el panel
            state, message, file_name = self.panel.upload_state_for(self.project_key())
            self.upload_button.set_state(state)
            self._upload_tooltip_name = file_name or self._upload_tooltip_name
            self._apply_upload_tooltip(message)
        self._set_close_visible(self._row_hovered)

        # Debug: mostrar exactamente qué texto se está configurando
        debug_print(f"UI: Configurando texto para {project_name}: '{display_text}' (longitud: {len(display_text)})")

        self.project_label.setText(display_text)

        # Forzar actualización del tamaño del label para asegurar que muestre todo el texto
        self.project_label.adjustSize()

        # Calcular el tamaño necesario para el texto usando la función compatible del adapter
        font_metrics = self.project_label.fontMetrics()
        text_width = horizontal_advance(font_metrics, display_text)
        text_height = font_metrics.height()

        # Establecer tamaño mínimo basado en el texto
        # Margen chico: la flecha de update y la x van pegadas al nombre
        min_width = text_width + 8
        self.project_label.setMinimumWidth(min_width)

        # Manejar visibilidad del botón de update
        should_show_update = self.has_newer_version and self.is_open
        self.update_button.setVisible(should_show_update)
        debug_print(f"UI: Botón update visible: {should_show_update} (has_newer: {self.has_newer_version}, is_open: {self.is_open})")

        # Debug adicional para entender por qué aparece siempre
        if should_show_update:
            debug_print(f"   🔍 DEBUG: Botón VISIBLE - Proyecto: {self.project_info.get('nombre_base', '')}, versión: {self.project_info.get('version', '')}")
        elif self.has_newer_version:
            debug_print(f"   🔍 DEBUG: Botón OCULTO pero has_newer=True - Proyecto no abierto: {self.project_info.get('nombre_base', '')}")
        elif self.is_open:
            debug_print(f"   🔍 DEBUG: Botón OCULTO pero is_open=True - Proyecto sin versión nueva: {self.project_info.get('nombre_base', '')}")

        # Forzar actualización del layout
        self.project_label.update()
        self.update()

        # Verificar que el texto se aplicó correctamente
        actual_text = self.project_label.text()
        debug_print(f"UI: Texto aplicado al QLabel: '{actual_text}' (longitud: {len(actual_text)})")
        if actual_text != display_text:
            debug_print(f"ERROR: Texto aplicado difiere del esperado!")
            # Debug detallado carácter por carácter
            debug_print(f"Esperado: {[c for c in display_text]}")
            debug_print(f"Actual:   {[c for c in actual_text]}")

        # Información adicional de debug
        size = self.project_label.size()
        debug_print(f"UI: QLabel size: {size.width()}x{size.height()}, texto requiere: {text_width}x{text_height}")

        # Información adicional de debug
        size = self.project_label.size()
        min_size = self.project_label.minimumSize()
        debug_print(f"UI: QLabel size: {size.width()}x{size.height()}, min_size: {min_size.width()}x{min_size.height()}")

    def show_sequences(self):
        # Limpiar secuencias anteriores
        # takeAt + hide + deleteLater, no setParent(None): un widget huerfano con
        # un show() pendiente de Qt se abre como ventana suelta.
        while self.sequences_layout.count():
            layout_item = self.sequences_layout.takeAt(0)
            widget = layout_item.widget() if layout_item else None
            if widget is not None:
                widget.hide()
                widget.deleteLater()

        proyecto_obj = self.project_info.get("proyecto_obj")
        sequences_dict = {}

        if proyecto_obj:
            try:
                for seq in proyecto_obj.sequences():
                    try:
                        sequences_dict[seq.name()] = seq
                    except Exception:
                        continue
            except Exception:
                pass

        # Obtener colores para las secuencias (mismo que el proyecto padre)
        from LGA_Projects_Panel_ScanProjects import obtener_clave_proyecto

        nombre_base = self.project_info.get("nombre_base", "")
        color_key = self.project_info.get("project_key") or obtener_clave_proyecto(nombre_base=nombre_base)
        base_color, hover_color = get_project_colors(color_key)

        for seq_name in sorted(self.sequences):
            # Contenedor horizontal para la secuencia
            seq_container = QtWidgets.QWidget()
            seq_layout = QtWidgets.QHBoxLayout(seq_container)
            seq_layout.setContentsMargins(0, 0, 0, 0)
            seq_layout.setSpacing(0)

            seq_label = QtWidgets.QLabel(f"> {seq_name}")
            seq_label.setStyleSheet(f"color: {base_color};")
            seq_label.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            seq_label.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
            seq_label.adjustSize()  # Ajustar tamaño al contenido del texto
            # Guardar colores para el event filter
            seq_label.setProperty("base_color", base_color)
            seq_label.setProperty("hover_color", hover_color)

            # Instalar event filter para hover (si hay panel disponible)
            if self.panel:
                seq_label.installEventFilter(self.panel)

            seq_obj = sequences_dict.get(seq_name)
            # Solo el boton izquierdo cambia de timeline: el derecho abre el menu
            # contextual, y sin este filtro tambien hacia el switch.
            seq_label.mousePressEvent = (
                lambda e, name=seq_name, so=seq_obj, po=self.project_info.get("proyecto_obj"): (
                    self.on_sequence_click(name, so, po)
                    if e.button() == QtCore.Qt.LeftButton
                    else None
                )
            )
            seq_label.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
            seq_label.customContextMenuRequested.connect(
                lambda pos, lbl=seq_label, name=seq_name, so=seq_obj: self._show_sequence_menu(lbl, pos, name, so)
            )

            seq_layout.addWidget(seq_label)

            # Spacer horizontal para empujar el label a la izquierda
            seq_spacer = QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
            seq_layout.addItem(seq_spacer)

            self.sequences_layout.addWidget(seq_container)

        self.sequences_widget.show()

    def on_sequence_click(self, sequence_name, sequence_obj=None, proyecto_obj=None):
        """Abrir secuencia en timeline preservando ajustes (cross-project)"""
        try:
            success = switch_to_sequence(sequence_name, target_project=proyecto_obj)
            if success:
                debug_print(f"✅ Secuencia '{sequence_name}' cambiada exitosamente")
            else:
                debug_print(f"❌ Error cambiando a secuencia '{sequence_name}'")
        except Exception as e:
            debug_print(f"❌ Error en cambio de secuencia '{sequence_name}': {e}")
            import traceback

            debug_print(traceback.format_exc())

    def _show_sequence_menu(self, label, pos, sequence_name, sequence_obj):
        """Clic derecho sobre un timeline: menu con Delete Timeline."""
        if self.panel is None or not hasattr(self.panel, "delete_sequence"):
            return
        menu = QtWidgets.QMenu(label)
        menu.setToolTipsVisible(True)
        delete_action = menu.addAction("Delete Timeline")
        delete_action.setToolTip(TOOLTIPS["delete_timeline"])
        chosen = menu.exec_(label.mapToGlobal(pos))
        if chosen is not delete_action:
            return
        proyecto = self.project_info.get("proyecto_abierto") or self.project_info.get("proyecto_obj")
        # Diferido: el borrado rearma la lista y destruye este label, que
        # todavia esta despachando el evento del menu.
        panel = self.panel
        QtCore.QTimer.singleShot(
            0, lambda: panel.delete_sequence(proyecto, sequence_name, sequence_obj)
        )

    def eventFilter(self, obj, event):
        """Hover compartido: el triangulo y el nombre hacen lo mismo, se iluminan juntos."""
        # El filtro se instala en setup_ui() y Qt ya le manda eventos mientras
        # arma la fila (ChildAdded, Polish...), antes de que exista el segundo
        # label: primero el tipo de evento, y los labels con getattr.
        event_type = event.type()
        if event_type in (QtCore.QEvent.Enter, QtCore.QEvent.Leave):
            titles = (getattr(self, "toggle_label", None), getattr(self, "project_label", None))
            if obj in titles and None not in titles:
                self._paint_title("hover_color" if event_type == QtCore.QEvent.Enter else "base_color")
        return super(ProjectItem, self).eventFilter(obj, event)

    def _paint_title(self, color_property):
        """Pinta nombre y triangulo del mismo color (base o hover)."""
        color = self.project_label.property(color_property)
        if not color:
            return
        self.project_label.setStyleSheet(f"font-size: 13px; color: {color};")
        try:
            dpr = self.toggle_label.devicePixelRatioF()
        except Exception:
            dpr = 1.0
        self.toggle_label.setPixmap(
            _triangle_pixmap(color, getattr(self, "_triangle_down", False), dpr)
        )

    def _set_close_visible(self, visible):
        """Los iconos aparecen con el mouse sobre la fila, y solo en proyectos abiertos."""
        try:
            self._row_hovered = bool(visible)
            show = bool(visible and self.is_open)
            if show:
                self._refresh_action_tooltips()
            self.close_button.setVisible(show)
            self.save_button.setVisible(show)
            # Mientras sube o muestra el resultado, el de upload no depende del hover
            busy = self.upload_button.state != STATE_IDLE
            self.upload_button.setVisible(bool(self.is_open and (show or busy)))
        except RuntimeError:
            pass  # la fila ya se destruyo (rearmado de la lista)

    def _end_save_flash(self):
        try:
            if not self.project_label.underMouse() and not self.toggle_label.underMouse():
                self._paint_title("base_color")
        except RuntimeError:
            pass  # la fila ya se destruyo

    def project_key(self):
        """Clave estable de la fila: sobrevive al rearmado y al cambio de version."""
        return self.project_info.get("nombre_base", "")

    def open_project_path(self):
        """Ruta del .hrox ABIERTO (puede no ser la mas alta del disco)."""
        proyecto = self.project_info.get("proyecto_abierto") or self.project_info.get("proyecto_obj")
        try:
            if proyecto is not None and proyecto.path():
                return proyecto.path()
        except Exception:
            pass
        return self.project_info.get("ruta_hrox", "")

    def _refresh_action_tooltips(self):
        """Tooltips de save y upload con la version y el archivo reales."""
        from LGA_NKS_Projects_Panel_py.LGA_NKS_ProjectRowActions import split_version

        path = self.open_project_path()
        parts = split_version(path) if path else None
        if parts:
            _folder, _prefix, number, _suffix = parts
            next_number = str(int(number) + 1).zfill(len(number))
            self.save_button.setToolTip(
                TOOLTIPS["save"].format(current="v" + number, next="v" + next_number)
            )
        else:
            self.save_button.setToolTip(TOOLTIPS["save_unknown"])
        self._upload_tooltip_name = os.path.basename(path) if path else self.project_key()
        self._apply_upload_tooltip()

    def _apply_upload_tooltip(self, message=""):
        name = self._upload_tooltip_name or self.project_key()
        state = self.upload_button.state
        if state == STATE_BUSY:
            text = TOOLTIPS["upload_busy"].format(name=name)
        elif state == STATE_OK:
            text = TOOLTIPS["upload_ok"].format(name=name)
        elif state == STATE_ERROR:
            text = TOOLTIPS["upload_error"].format(name=name, message=message or "error")
        else:
            text = TOOLTIPS["upload"].format(name=name)
        self.upload_button.setToolTip(text)

    def set_upload_state(self, state, message="", file_name=""):
        """Lo llama el panel: spinner, check o error en el icono de upload."""
        try:
            if file_name:
                self._upload_tooltip_name = file_name
            self.upload_button.set_state(state)
            self._apply_upload_tooltip(message)
            if state == STATE_OK:
                self._upload_ok_timer.start(UPLOAD_OK_HOLD_MS)
            else:
                self._upload_ok_timer.stop()
            self._set_close_visible(self._row_hovered)
        except RuntimeError:
            pass  # la fila ya se destruyo

    def toggle_collapsed(self):
        """Colapsa o expande las secuencias. Solo el panel: no toca Hiero."""
        self.collapsed = not self.collapsed
        if self.panel and hasattr(self.panel, "set_project_collapsed"):
            self.panel.set_project_collapsed(
                self.project_info.get("nombre_base", ""), self.collapsed
            )
        self.update_display()

    def set_open_state(self, is_open, sequences=None, proyecto_obj=None):
        self.is_open = is_open
        if sequences is not None:
            self.sequences = sequences
        if proyecto_obj:
            self.project_info["proyecto_obj"] = proyecto_obj
        self.update_display()

    def on_update_click(self):
        """Manejar el click en el botón de update para abrir la versión más nueva"""
        if self.panel and self.newer_version_info:
            # Llamar al método del panel para manejar la actualización
            if hasattr(self.panel, 'on_update_project_click'):
                self.panel.on_update_project_click(self.newer_version_info)
