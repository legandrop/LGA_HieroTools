"""
____________________________________________________________________

  LGA_NKS_UIManager v1.09 | Lega

  Gestor de interfaz de usuario para el panel de proyectos LGA.
  Centraliza creación de widgets, conexión de señales, y manejo de eventos.

  v1.09: El toggle Studio/Client usa el estilo compartido PILL y fuerza el
         fondo del contenedor para que la capsula se pinte en cualquier host.
  v1.08: Reordenado el rail a Refresh, Reload Panel y Settings; Refresh usa
         la variante bold de PipeSync, Reload Panel una silueta llena de
         reinicio y todos los tooltips usan la hoja compartida del pack. Sus
         encuadres SVG quedan normalizados opticamente con los otros iconos.
  v1.07: Agregados Organize Project y Clean Project como botones de icono
         separados de Refresh, Settings y Reimport; conservan sus tooltips.
  v1.06: El toggle de contexto arranca alineado con los nombres de proyecto
         (antes quedaba mas a la izquierda) y la separacion entre el toggle y
         el primer proyecto es un 35% menor. Los dos valores se calculan con
         los margenes reales de la lista, que dependen del estilo del host.
  v1.05: El toggle de contexto pasa a una fila propia ARRIBA de la lista de
         proyectos, alineado a la izquierda. Antes compartia la fila del
         contador, debajo de la lista. La fila solo se crea si el toggle existe.
  v1.04: El toggle de contexto invierte el orden visual: studio a la izquierda
         y client a la derecha. Solo posicion en el layout; el estado activo
         se sigue pintando por identidad del boton.
  v1.03: Corregida la inicializacion para usuarios sin acceso al toggle Studio/Client:
         setup_connections() ahora conecta sus señales solo cuando ambos botones fueron creados.
  v1.02: El switch Studio/Client pasa a ser un toggle pill (_build_context_toggle) ubicado a la
         derecha del info_label, en vez del botón en la columna derecha. Conecta ctx_client_btn /
         ctx_studio_btn a panel.set_context_mode() en setup_connections().
  v1.01: Agregado botón de switch Studio/Client en setup_ui() cuando el usuario es lega@wanka.tv.
         Se inicializa con dependencias de funciones (get_normal_pipesync_flow_login, etc.) y se
         conecta en setup_connections(). Incluye debug logging para diagnosticar visibilidad del botón.
  v1.00: Versión inicial - UI manager central
____________________________________________________________________

"""

import os
import configparser
from pathlib import Path
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui, QtCore, Qt
from LGA_NKS_Shared.LGA_UI_Style_HieroTools import Color, Style

# Importar variable global
# Esta será importada desde el archivo principal cuando se importe este módulo
REIMPORT_BUTTON = None
SWITCH_ALLOWED_LOGIN = None
GET_CONTEXT_MODE = None
FIND_CONTEXT_INI = None
GET_NORMAL_PIPESYNC_LOGIN = None

# Margenes de LGA_NKS_ProjectItem (setContentsMargins(5, 2, 5, 2)). Se repiten
# aca para alinear el toggle con el texto de los proyectos; si cambian alla,
# cambiarlos tambien aca.
PROJECT_ITEM_LEFT_MARGIN = 5
PROJECT_ITEM_TOP_MARGIN = 2

# Margen inferior original de la fila del toggle, y cuanto se achica la
# separacion entre el toggle y el primer proyecto.
TOGGLE_ROW_BOTTOM_MARGIN = 4
TOGGLE_GAP_REDUCTION = 0.35

TOOLTIPS = {
    "refresh": "Re-escanear proyectos",
    "reload": "Recargar panel",
    "settings": "Configuración",
    "organize": "Organiza los clips en bins basándose en su ruta de archivo",
    "clean": "Elimina clips no usados del proyecto",
}


def initialize_ui_dependencies(reimport_flag, switch_login=None, get_context_fn=None, find_ini_fn=None, get_login_fn=None):
    """Inicializar las dependencias globales necesarias para el UI manager"""
    global REIMPORT_BUTTON, SWITCH_ALLOWED_LOGIN, GET_CONTEXT_MODE, FIND_CONTEXT_INI, GET_NORMAL_PIPESYNC_LOGIN
    REIMPORT_BUTTON = reimport_flag
    SWITCH_ALLOWED_LOGIN = switch_login or "lega@wanka.tv"
    GET_CONTEXT_MODE = get_context_fn
    FIND_CONTEXT_INI = find_ini_fn
    GET_NORMAL_PIPESYNC_LOGIN = get_login_fn


class UIManager:
    """Clase para manejar la configuración y gestión de la interfaz de usuario"""

    @staticmethod
    def _new_toolbar_button(tooltip):
        """Crea un boton compacto del rail sin rehacer el estilo con QSS."""
        button = QtWidgets.QToolButton()
        button.setAutoRaise(True)
        button.setFixedSize(30, 30)
        button.setIconSize(QtCore.QSize(20, 20))
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        return button

    @staticmethod
    def setup_ui(panel):
        """Configurar la interfaz de usuario del panel"""
        # QToolTip es un popup separado: si el panel no instala la hoja
        # compartida, Qt cae al tooltip nativo del host. Se concatena para no
        # pisar una hoja que el contenedor pudiera traer en el futuro.
        panel.setStyleSheet("\n".join(filter(None, (panel.styleSheet(), Style.TOOLTIP))))

        # Layout principal horizontal para dividir en dos columnas
        panel.main_layout = QtWidgets.QHBoxLayout(panel)

        # Columna izquierda: proyectos y settings (stack)
        left_column = QtWidgets.QVBoxLayout()

        panel.content_stack = QtWidgets.QStackedWidget()

        # Contenedor de proyectos
        panel.projects_container = QtWidgets.QWidget()
        projects_container_layout = QtWidgets.QVBoxLayout(panel.projects_container)
        projects_container_layout.setContentsMargins(0, 0, 0, 0)

        # Área de scroll para la lista de proyectos
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        panel.projects_widget = QtWidgets.QWidget()
        panel.projects_layout = QtWidgets.QVBoxLayout(panel.projects_widget)
        panel.projects_layout.setAlignment(QtCore.Qt.AlignTop)

        scroll_area.setWidget(panel.projects_widget)

        # Toggle de contexto: fila propia ARRIBA de la lista, alineado a la izquierda.
        # Solo existe para el login habilitado; si no aplica, no se agrega la fila
        # y la lista queda pegada al borde superior como antes.
        context_toggle = UIManager._build_context_toggle(panel)
        if context_toggle is not None:
            left_margin, bottom_margin = UIManager._fit_toggle_to_list(
                projects_container_layout, scroll_area, panel.projects_layout
            )
            toggle_row = QtWidgets.QHBoxLayout()
            toggle_row.setContentsMargins(left_margin, 0, 0, bottom_margin)
            toggle_row.setSpacing(6)
            toggle_row.addWidget(context_toggle, 0, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            toggle_row.addStretch(1)
            projects_container_layout.addLayout(toggle_row)

        projects_container_layout.addWidget(scroll_area)

        # Información de estado (contador), debajo de la lista
        info_row = QtWidgets.QHBoxLayout()
        info_row.setContentsMargins(0, 0, 0, 0)
        info_row.setSpacing(6)

        panel.info_label = QtWidgets.QLabel("")
        panel.info_label.setStyleSheet(
            "color: %s; margin-top: 6px;" % Color.TEXT_DIM
        )
        panel.info_label.setAlignment(QtCore.Qt.AlignCenter)
        info_row.addWidget(panel.info_label, 1)

        projects_container_layout.addLayout(info_row)

        panel.content_stack.addWidget(panel.projects_container)
        left_column.addWidget(panel.content_stack)

        # Añadir columna izquierda al layout principal (con stretch para que tome el espacio disponible)
        panel.main_layout.addLayout(left_column, 1)  # stretch factor 1

        # Columna derecha: botones
        right_column = QtWidgets.QVBoxLayout()
        right_column.setAlignment(QtCore.Qt.AlignTop)
        right_column.setSpacing(2)  # Espacio pequeño entre botones

        # Configurar iconos para el botón refresh
        refresh_icon_path = os.path.join(os.path.dirname(__file__), "..", "LGA_NKS_Projects_Panel_py", "refresh.svg")
        refresh_hover_icon_path = os.path.join(os.path.dirname(__file__), "..", "LGA_NKS_Projects_Panel_py", "refresh_white.svg")

        panel.refresh_button = UIManager._new_toolbar_button(TOOLTIPS["refresh"])

        # Cargar iconos SVG si existen
        if os.path.exists(refresh_icon_path) and os.path.exists(refresh_hover_icon_path):
            panel.refresh_icon_normal = QtGui.QIcon(refresh_icon_path)
            panel.refresh_icon_hover = QtGui.QIcon(refresh_hover_icon_path)
            panel.refresh_button.setIcon(panel.refresh_icon_normal)
            panel.refresh_button.setIconSize(QtCore.QSize(20, 20))  # Tamaño aproximado al botón original

            # Instalar event filter para manejar hover
            panel.refresh_button.installEventFilter(panel)
        else:
            # Fallback si no se encuentran los iconos
            panel.refresh_button.setText("🔄 Refresh")

        # Añadir botón refresh a la columna derecha
        right_column.addWidget(panel.refresh_button)

        # Configurar iconos para Reload Panel
        reimport_icon_path = os.path.join(os.path.dirname(__file__), "..", "LGA_NKS_Projects_Panel_py", "reload_panel.svg")
        reimport_hover_icon_path = os.path.join(os.path.dirname(__file__), "..", "LGA_NKS_Projects_Panel_py", "reload_panel_white.svg")

        # Botón de reimport con iconos SVG (solo si la flag está activada)
        if REIMPORT_BUTTON:
            panel.reimport_button = UIManager._new_toolbar_button(TOOLTIPS["reload"])

            # Cargar iconos SVG si existen
            if os.path.exists(reimport_icon_path) and os.path.exists(reimport_hover_icon_path):
                panel.reimport_icon_normal = QtGui.QIcon(reimport_icon_path)
                panel.reimport_icon_hover = QtGui.QIcon(reimport_hover_icon_path)
                panel.reimport_button.setIcon(panel.reimport_icon_normal)
                panel.reimport_button.setIconSize(QtCore.QSize(20, 20))  # Tamaño aproximado al botón original

                # Instalar event filter para manejar hover
                panel.reimport_button.installEventFilter(panel)
            else:
                # Fallback si no se encuentran los iconos
                panel.reimport_button.setText("Reload")

            right_column.addWidget(panel.reimport_button)

        # Settings va despues de Reload Panel para que el orden del rail siga
        # el recorrido: actualizar datos, reconstruir panel, configurar.
        settings_icon_path = os.path.join(os.path.dirname(__file__), "..", "LGA_NKS_Projects_Panel_py", "settings.svg")
        settings_hover_icon_path = os.path.join(os.path.dirname(__file__), "..", "LGA_NKS_Projects_Panel_py", "settings_white.svg")

        panel.settings_button = UIManager._new_toolbar_button(TOOLTIPS["settings"])

        if os.path.exists(settings_icon_path) and os.path.exists(settings_hover_icon_path):
            panel.settings_icon_normal = QtGui.QIcon(settings_icon_path)
            panel.settings_icon_hover = QtGui.QIcon(settings_hover_icon_path)
            panel.settings_button.setIcon(panel.settings_icon_normal)
            panel.settings_button.setIconSize(QtCore.QSize(20, 20))
            panel.settings_button.installEventFilter(panel)
        else:
            panel.settings_button.setText("Settings")

        right_column.addWidget(panel.settings_button)

        # Las acciones que afectan al proyecto completo viven separadas de los
        # controles propios del panel. Reutilizan el mismo constructor de
        # QToolButton que Refresh para conservar la misma huella visual.
        project_actions_separator = QtWidgets.QFrame()
        project_actions_separator.setFrameShape(QtWidgets.QFrame.HLine)
        project_actions_separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        project_actions_separator.setFixedWidth(20)
        right_column.addSpacing(4)
        right_column.addWidget(
            project_actions_separator, 0, QtCore.Qt.AlignHCenter
        )
        right_column.addSpacing(4)

        icons_dir = os.path.dirname(__file__)
        shared_icons_dir = os.path.normpath(
            os.path.join(icons_dir, "..", "LGA_NKS_Shared", "icons")
        )
        UIManager._add_project_action_button(
            panel,
            right_column,
            "organize",
            TOOLTIPS["organize"],
            os.path.join(icons_dir, "organize_project.svg"),
            os.path.join(icons_dir, "organize_project_white.svg"),
            "Organize",
        )
        UIManager._add_project_action_button(
            panel,
            right_column,
            "clean",
            TOOLTIPS["clean"],
            os.path.join(shared_icons_dir, "trash.svg"),
            os.path.join(shared_icons_dir, "trash_hover.svg"),
            "Clean",
        )

        # Añadir columna derecha al layout principal (sin stretch para mantener tamaño pequeño)
        panel.main_layout.addLayout(right_column, 0)  # stretch factor 0

    @staticmethod
    def _add_project_action_button(
        panel, layout, name, tooltip, normal_icon_path, hover_icon_path, fallback_text
    ):
        """Agrega una accion de proyecto con el mismo estilo del rail existente."""
        button = UIManager._new_toolbar_button(tooltip)

        if os.path.exists(normal_icon_path) and os.path.exists(hover_icon_path):
            normal_icon = QtGui.QIcon(normal_icon_path)
            hover_icon = QtGui.QIcon(hover_icon_path)
            button.setIcon(normal_icon)
            button.setIconSize(QtCore.QSize(20, 20))
            button.installEventFilter(panel)
            setattr(panel, f"{name}_icon_normal", normal_icon)
            setattr(panel, f"{name}_icon_hover", hover_icon)
        else:
            button.setText(fallback_text)

        setattr(panel, f"{name}_button", button)
        layout.addWidget(button)

    @staticmethod
    def _fit_toggle_to_list(container_layout, scroll_area, list_layout):
        """
        Calcula (margen_izquierdo, margen_inferior) de la fila del toggle.

        Izquierda: el texto de un proyecto arranca despues del marco del scroll,
        el margen de la lista y el margen del ProjectItem. Abajo: la separacion
        original sumaba el margen de la fila, el spacing del contenedor, el marco,
        el margen superior de la lista y el del item; el recorte se saca primero
        del margen superior de la lista y el resto del margen de la fila.
        """
        frame = scroll_area.frameWidth()
        margins = list_layout.contentsMargins()
        left_margin = frame + margins.left() + PROJECT_ITEM_LEFT_MARGIN

        gap = (
            TOGGLE_ROW_BOTTOM_MARGIN
            + max(container_layout.spacing(), 0)
            + frame
            + margins.top()
            + PROJECT_ITEM_TOP_MARGIN
        )
        cut = int(round(gap * TOGGLE_GAP_REDUCTION))
        cut_from_list = min(cut, margins.top())
        cut_from_row = min(cut - cut_from_list, TOGGLE_ROW_BOTTOM_MARGIN)
        list_layout.setContentsMargins(
            margins.left(), margins.top() - cut_from_list, margins.right(), margins.bottom()
        )
        return left_margin, TOGGLE_ROW_BOTTOM_MARGIN - cut_from_row

    @staticmethod
    def _build_context_toggle(panel):
        """Construye el toggle pill Client/Studio. Devuelve el widget o None si no aplica."""
        if not GET_NORMAL_PIPESYNC_LOGIN:
            return None
        try:
            normal_login = str(GET_NORMAL_PIPESYNC_LOGIN() or "").strip().lower()
            can_show = normal_login == SWITCH_ALLOWED_LOGIN
            if hasattr(panel, "debug_print"):
                panel.debug_print(f"Context toggle visible={can_show} login='{normal_login}' allowed='{SWITCH_ALLOWED_LOGIN}'")
            if not can_show:
                return None
        except Exception as e:
            if hasattr(panel, "debug_print"):
                import traceback
                panel.debug_print(f"Error evaluando login para toggle: {e}")
                panel.debug_print(f"Traceback: {traceback.format_exc()}")
            return None

        container = QtWidgets.QWidget()
        container.setObjectName("ctxToggle")
        container.setAttribute(Qt.WA_StyledBackground, True)
        container.setStyleSheet(Style.PILL_CONTAINER)
        h = QtWidgets.QHBoxLayout(container)
        h.setContentsMargins(2, 2, 2, 2)
        h.setSpacing(2)

        # El orden de creacion sigue al orden VISUAL: studio a la izquierda,
        # client a la derecha. Es solo posicion; el estado activo lo pinta
        # _refresh_context_toggle() por identidad del boton, no por su lugar
        # en el layout, asi que mover estas lineas no toca el comportamiento.
        panel.ctx_studio_btn = QtWidgets.QPushButton("studio")
        panel.ctx_client_btn = QtWidgets.QPushButton("client")
        for btn in (panel.ctx_studio_btn, panel.ctx_client_btn):
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            btn.setFlat(True)
            btn.setMinimumHeight(22)
        h.addWidget(panel.ctx_studio_btn)
        h.addWidget(panel.ctx_client_btn)

        panel.context_toggle_widget = container
        if hasattr(panel, "_refresh_context_toggle"):
            panel._refresh_context_toggle()
        return container

    @staticmethod
    def setup_connections(panel):
        """Configurar las conexiones de señales del panel"""
        panel.refresh_button.clicked.connect(panel.start_scan)
        if hasattr(panel, 'settings_button'):
            panel.settings_button.clicked.connect(panel.show_settings_view)
        if REIMPORT_BUTTON and hasattr(panel, 'reimport_button'):
            panel.reimport_button.clicked.connect(panel.reimport_panel)
        panel.organize_button.clicked.connect(panel.organize_project)
        panel.clean_button.clicked.connect(panel.clean_project)
        ctx_client_btn = getattr(panel, "ctx_client_btn", None)
        ctx_studio_btn = getattr(panel, "ctx_studio_btn", None)
        if ctx_client_btn is not None and ctx_studio_btn is not None:
            ctx_client_btn.clicked.connect(lambda: panel.set_context_mode("client"))
            ctx_studio_btn.clicked.connect(lambda: panel.set_context_mode("studio"))

    @staticmethod
    def eventFilter(panel, obj, event):
        """Manejar eventos de hover para botones y labels"""
        # Manejar hover del botón refresh
        if obj == panel.refresh_button:
            if event.type() == QtCore.QEvent.Enter:
                if hasattr(panel, 'refresh_icon_hover'):
                    panel.refresh_button.setIcon(panel.refresh_icon_hover)
            elif event.type() == QtCore.QEvent.Leave:
                if hasattr(panel, 'refresh_icon_normal'):
                    panel.refresh_button.setIcon(panel.refresh_icon_normal)

        # Hover botón settings
        elif obj == getattr(panel, "settings_button", None):
            if event.type() == QtCore.QEvent.Enter:
                if hasattr(panel, 'settings_icon_hover'):
                    panel.settings_button.setIcon(panel.settings_icon_hover)
            elif event.type() == QtCore.QEvent.Leave:
                if hasattr(panel, 'settings_icon_normal'):
                    panel.settings_button.setIcon(panel.settings_icon_normal)

        # Manejar hover del botón reimport
        elif obj == getattr(panel, "reimport_button", None):
            if event.type() == QtCore.QEvent.Enter:
                if hasattr(panel, 'reimport_icon_hover'):
                    panel.reimport_button.setIcon(panel.reimport_icon_hover)
            elif event.type() == QtCore.QEvent.Leave:
                if hasattr(panel, 'reimport_icon_normal'):
                    panel.reimport_button.setIcon(panel.reimport_icon_normal)

        # Hover de las acciones de proyecto
        elif obj == getattr(panel, "organize_button", None):
            if event.type() == QtCore.QEvent.Enter:
                if hasattr(panel, "organize_icon_hover"):
                    panel.organize_button.setIcon(panel.organize_icon_hover)
            elif event.type() == QtCore.QEvent.Leave:
                if hasattr(panel, "organize_icon_normal"):
                    panel.organize_button.setIcon(panel.organize_icon_normal)

        elif obj == getattr(panel, "clean_button", None):
            if event.type() == QtCore.QEvent.Enter:
                if hasattr(panel, "clean_icon_hover"):
                    panel.clean_button.setIcon(panel.clean_icon_hover)
            elif event.type() == QtCore.QEvent.Leave:
                if hasattr(panel, "clean_icon_normal"):
                    panel.clean_button.setIcon(panel.clean_icon_normal)

        # Manejar hover del botón update (buscar en todos los project items)
        elif hasattr(obj, 'toolTip') and obj.toolTip() == "Actualizar a versión más nueva":
            # Es un botón de update
            if event.type() == QtCore.QEvent.Enter:
                # Cambiar a ícono hover
                if hasattr(obj, 'update_icon_hover'):
                    obj.setIcon(obj.update_icon_hover)
            elif event.type() == QtCore.QEvent.Leave:
                # Cambiar a ícono normal
                if hasattr(obj, 'update_icon_normal'):
                    obj.setIcon(obj.update_icon_normal)

        # Manejar hover de los project labels y sequence labels
        elif hasattr(obj, 'setStyleSheet') and obj != panel.refresh_button:
            # Verificar si es un label con cursor de pointing hand
            if obj.cursor().shape() == QtCore.Qt.PointingHandCursor:
                if event.type() == QtCore.QEvent.Enter:
                    # Cambiar a color hover usando las propiedades guardadas
                    hover_color = obj.property("hover_color")
                    if hover_color:
                        obj.setStyleSheet(f"color: {hover_color};")
                elif event.type() == QtCore.QEvent.Leave:
                    # Volver a color base usando las propiedades guardadas
                    base_color = obj.property("base_color")
                    if base_color:
                        obj.setStyleSheet(f"color: {base_color};")

        return super(panel.__class__, panel).eventFilter(obj, event)
