# -*- coding: utf-8 -*-
"""
____________________________________________________________________

  LGA_NKS_Projects_Panel v2.45 | Lega

  Panel de Proyectos LGA integrado para Hiero con recarga inteligente.
  - Escanea proyectos en AltTPath (PipeSync) o T:\ como fallback.
  - Permite abrir proyectos y secuencias (cross-project) sin perder ajustes de viewer.
  - Incluye botón de reimport/redock para aplicar cambios al vuelo.
  - Toggle pill Studio/Client (arriba de la lista, a la izquierda) visible para lega@wanka.tv.

  v2.45: El preview usa un eje continuo, selector de track en su tabla y clip
         nuevo rojo con nombre real para representar cada placement sin huecos.
  v2.44: El preview dibuja color real, playhead y proyeccion por opcion; el
         modal conserva la secuencia capturada sin consultar activeSequence.
  v2.43: El ripple del drop reutiliza push_clips_right de Import Shot, que abre
         espacio desde el clip real, y el preview muestra clips por track.
  v2.42: El drop analiza el hueco real desde el playhead. Si no cabe, abre un
         preview para elegir track y colocar en el hueco, insertar con ripple
         global o importar al final; el ripple excluye BurnIn y lo extiende.
  v2.41: El drop acepta MOV, MXF, JPG, PNG y EXR ademas de MP4. Para las
         imagenes, Hiero detecta automaticamente si el archivo representa una
         secuencia; el log deja el rango detectado para diagnosticarlo.
  v2.40: El panel acepta un unico MP4 local arrastrado. Si hay una secuencia,
         track y playhead validos y el track esta libre desde ese frame, lo
         importa al bin raiz y lo coloca desde el playhead. Los demas casos
         quedan bloqueados hasta que exista el preview de resolucion.

  v2.39: Organize Project y Clean Project pasan del Edit Panel a la barra
         lateral de este panel. Los scripts se cargan desde Projects_Panel_py
         y conservan sus tooltips en castellano.
  v2.38: Colapsar y cerrar proyectos. collapsed_projects recuerda los
         colapsados a traves del rearmado de la lista. close_project() pregunta
         con modifiedSinceLastSave() antes de cerrar (project.close() descarta
         en silencio), y si era el proyecto activo va al ultimo timeline de otro
         abierto. El panel escucha kAfterProjectClose para refrescarse aunque
         el cierre venga de File > Close.
  v2.37: La ventana principal no repinta desde el click en el proyecto hasta el
         final de la post-apertura (FREEZE_DURING_PROJECT_OPEN): antes se veia
         el timeline que abre Hiero y los restos del proyecto anterior.
  v2.36: Post-apertura de proyecto (after_project_open). Al abrir un proyecto
         desde el panel se espera a que Hiero restaure su timeline y se corre el
         switch completo hacia el ultimo timeline usado en ese proyecto (en
         cualquier version), o al que abrio Hiero. Antes quedaban timelines de
         mas, sin top track ni LUT.
  v2.35: El toggle larga un solo escaneo. El segundo, a los 150 ms, era trabajo
         doble: con los escaneos numerados solo se aplicaba el ultimo.
  v2.34: El toggle vuelve a largar el escaneo ANTES del switch, en paralelo, y
         ScanManager difiere el display si termina con la UI congelada. En
         v2.33 el escaneo esperaba al switch y la lista llegaba ~0.2s tarde.
         El aviso a los paneles sigue yendo despues del switch.
  v2.33: El toggle Studio/Client hace el switch de timeline ANTES del rescan y
         del aviso a los paneles. El switch congela el repintado de la ventana
         principal, y el rescan terminaba en ese lapso: el panel y el timeline
         quedaban sin dibujar hasta que NKS perdia y recuperaba el foco.
  v2.32: El toggle Studio/Client vuelve al ultimo timeline usado en el contexto
         de destino. Antes de cambiar guarda el timeline activo como el ultimo
         del contexto que se deja (LGA_NKS_TimelineMemory); despues, si el de
         destino tiene uno guardado y su proyecto sigue abierto, cambia a esa
         secuencia con su zoom, scroll y playhead. Si no, el timeline queda
         donde estaba.
  v2.31: La seccion Track names se repuebla en cada apertura de Settings,
         igual que los colores. La vista se arma una sola vez y el toggle
         Studio/Client cambia el scope de tasks en caliente, asi que despues
         de un switch mostraba las tasks del contexto viejo.
  v2.30: La vista de Settings suma la seccion read-only "Track names", con
         los nombres de track que el pack espera para cada task del
         contexto activo. Es informativa: la convencion vive en el codigo
         (LGA_NKS_TaskScope) y no se edita desde la UI. Sirve para que un
         artista al que una tool no le encuentra el clip vea con que
         nombres se lo busca. Vive en LGA_NKS_TrackNames_Section, que no
         importa hiero -asi el harness la captura sin levantar NKS-, usa el
         modulo de estilo del pack, y esta blindada: si falla, la vista de
         Settings sigue andando.

  v2.29: Los carteles de aviso pasan al helper LGA_NKS_MessageBox con el
         estilo del pack.

  v2.28: ensure_min_luminance() se movio a LGA_NKS_StyleUtils, porque el
         Assignee y el Flow Rev Panel necesitan la operacion inversa (techo) sobre
         los mismos colores de Flow. Aca queda solo la constante del piso.

  v2.27: Piso de luminancia para los colores de proyecto (ensure_min_luminance).
         Los colores de Flow son identitarios, no de texto, y los oscuros no se
         leian contra el panel. Se aclaran solo lo necesario, respetando el tono.

  v2.26: Los colores de proyecto salen de la DB de PipeSync del contexto activo.
         Se elimino la seccion [Colors] del .ini y la edicion de colores del panel
         de settings, que ahora los muestra read-only.

  v2.25: El switch de contexto avisa a los demas paneles por LGA_NKS_ContextSwitch
         y el login de PipeSync normal pasa a leerse memoizado (se resolvia dos
         veces en el arranque: el panel y el UIManager).

  v2.24: Reemplazado el botón de switch por un toggle pill Client/Studio alineado a la derecha
         de la línea de proyectos encontrados. Nuevos métodos set_context_mode() (cambio directo
         sin popup) y _refresh_context_toggle() (estilo activo/inactivo). Se eliminó el botón viejo.
  v2.23: Agregado botón de switch Studio/Client: lee login de PipeSync normal y muestra botón
         debajo de refresh solo para lega@wanka.tv, permitiendo cambiar entre contextos studio/client
         con persistencia en INI y ENV. Se migró lógica de UIManager para inicializar dependencias
         correctamente. Se agregó debug logging detallado en _get_normal_pipesync_login().
  v2.22: Migrado al sistema de logging a archivo con flags de debug compartidas para Projects Panel
  v2.21: Mejorada lógica de versiones: búsqueda en anteúltimo bloque y priorización de sufijos (_Mac)
         Las versiones ahora se detectan correctamente cuando están en bloques anteriores
         Ejemplo: v40_Mac > v40 (prioriza sufijos), v040_Mac detecta v040 correctamente
  v2.20: Display formateado: PROYECTO (vXXX), emojis ▼▶, sin _SUP_
____________________________________________________________________
"""

import hiero.ui
import hiero.core
import os
import importlib
import importlib.util
import sys
import configparser
import time
from pathlib import Path
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui, QtCore, Qt, is_widget_alive
from LGA_NKS_Shared.LGA_UI_Style_HieroTools import Color, Style
from LGA_NKS_Shared.LGA_NKS_ContextProfile import get_context_mode, find_context_ini
from LGA_NKS_Shared.LGA_NKS_ContextSwitch import (
    SWITCH_USER_LOGIN,
    get_normal_login,
    notify as notify_context_change,
)
from LGA_NKS_Shared.LGA_NKS_Project_Colors_Config import (
    get_project_colors_db_path,
    load_project_colors as load_project_colors_from_db,
)
from LGA_NKS_Shared.LGA_NKS_MessageBox import show_warning, ask_save_discard_cancel
from LGA_NKS_Projects_Panel_py import LGA_NKS_TimelineMemory as timeline_memory
from LGA_NKS_Edit_Panel_py import LGA_import_shots_timeline as timeline_mod
from LGA_NKS_Projects_Panel_py.LGA_NKS_ProjectMediaPreview import (
    ProjectMediaPreviewDialog,
)
from LGA_NKS_Projects_Panel_py.LGA_NKS_ProjectsPanel_Logging import (
    DEBUG,
    DEBUG_CONSOLE,
    DEBUG_LOG,
    debug_print,
    print_debug_messages,
)
try:
    from LGA_NKS_Projects_Panel_py.LGA_NKS_TrackNames_Section import (
        build_track_names_section,
        populate_track_names_section,
    )
except Exception:  # pragma: no cover - la seccion es informativa
    build_track_names_section = None
    populate_track_names_section = None

# Importar funciones de utilidad de estilos
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "LGA_NKS_Shared"))
from LGA_NKS_Shared.LGA_NKS_StyleUtils import (
    calculate_dynamic_border,
    calculate_dynamic_hover,
    ensure_min_luminance,
)

# Variable global para controlar si se debe crear panel automáticamente
# Se usa en smart reload para evitar creación duplicada
AUTO_CREATE_PANEL = True

# Flag para controlar si mostrar el botón de reimport
REIMPORT_BUTTON = True
# El login habilitado para el switch vive en LGA_NKS_ContextSwitch, que es lo que
# consultan los demas paneles para decidir si conectarse al bus de contexto.
SWITCH_ALLOWED_LOGIN = SWITCH_USER_LOGIN

# Post-apertura de proyecto. Medido con explore_project_open_timelines: Hiero
# abre el timeline guardado ~0.16s despues de kAfterProjectLoad y despues no
# cambia nada. Se espera a que la secuencia activa sea del proyecto nuevo y se
# mantenga POST_OPEN_STABLE_MS; si no llega en POST_OPEN_TIMEOUT_MS, se sigue igual.
POST_OPEN_POLL_MS = 50
POST_OPEN_STABLE_MS = 150
POST_OPEN_TIMEOUT_MS = 3000

# Congela el repintado de la ventana principal desde el click en el proyecto
# hasta el final de la post-apertura. Sin esto se ve el timeline que abre Hiero
# y los restos del proyecto anterior antes de que arranque el switch.
FREEZE_DURING_PROJECT_OPEN = True

# Primer grupo de formatos para el drop de media. Las secuencias JPG/PNG/EXR
# no se arman a mano: hiero.core.Clip reconoce la secuencia desde cualquiera
# de sus frames, igual que Import Shot.
_DROP_MEDIA_EXTENSIONS = {".mp4", ".mov", ".mxf", ".jpg", ".png", ".exr"}
_DROP_IMAGE_EXTENSIONS = {".jpg", ".png", ".exr"}

# Opciones de intervalo de auto-refresh (minutos)
AUTO_REFRESH_OPTIONS = {
    "never": 0,
    "5min": 5,
    "10min": 10,
    "15min": 15,
    "30min": 30,
    "1h": 60,
    "2h": 120,
}

# Colores de proyecto, tomados de la DB de PipeSync del contexto activo.
# No hay copia local: si PipeSync no sincronizo, el panel usa el color por defecto.
PROJECT_COLORS = {}


def load_project_colors():
    """Carga los colores de proyectos desde la pipesync_stats.db del contexto activo"""
    global PROJECT_COLORS
    PROJECT_COLORS.clear()
    debug_print("🔧 Iniciando carga de colores desde PipeSync...")

    try:
        db_path = get_project_colors_db_path()
        debug_print(f"📁 DB de PipeSync: {db_path}")
        debug_print(f"📁 DB existe: {os.path.exists(db_path)}")

        PROJECT_COLORS.update(load_project_colors_from_db())

        debug_print(f"📊 Total colores cargados: {len(PROJECT_COLORS)}")
        debug_print(f"📋 Colores cargados: {sorted(PROJECT_COLORS.keys())}")
        if not PROJECT_COLORS:
            debug_print(
                "⚠️ Sin colores: PipeSync no sincronizo este contexto o la DB no tiene "
                "project_settings_cache. Los proyectos se muestran con el color por defecto."
            )

    except Exception as e:
        debug_print(f"💥 Error al cargar colores desde PipeSync: {e}")
        import traceback
        debug_print(f"Traceback: {traceback.format_exc()}")


# Piso de luminancia para que el color del proyecto se lea como texto sobre el
# panel oscuro. Los colores salen de Flow pensados como color identitario del
# proyecto, no como color de texto, asi que los oscuros quedaban ilegibles.
# La funcion vive en StyleUtils porque el Assignee y el Flow Rev Panel usan la
# operacion inversa (techo) sobre los colores de usuario.
MIN_TEXT_LUMINANCE = 150


def get_brighter_color(base_color):
    """Devuelve un color más brillante para hover basado en el color base"""
    if not base_color.startswith('#') or len(base_color) != 7:
        return "#FFFFFF"  # Color por defecto si el formato es inválido

    try:
        # Convertir de hex a RGB
        r = int(base_color[1:3], 16)
        g = int(base_color[3:5], 16)
        b = int(base_color[5:7], 16)

        # Aumentar el brillo (mezclar con blanco)
        factor = 0.4  # Cuánto brillo añadir (0.0 = sin cambio, 1.0 = blanco puro)
        r = min(255, int(r + (255 - r) * factor))
        g = min(255, int(g + (255 - g) * factor))
        b = min(255, int(b + (255 - b) * factor))

        # Convertir de vuelta a hex
        return f"#{r:02X}{g:02X}{b:02X}"

    except ValueError:
        return "#FFFFFF"  # Color por defecto si hay error


def get_project_colors(project_name):
    """Devuelve los colores (base, hover) para un proyecto específico"""
    project_name_upper = project_name.upper()  # Buscar en mayúsculas
    debug_print(f"🎨 get_project_colors() llamado para: '{project_name}' (buscando como: '{project_name_upper}')")
    debug_print(f"📋 PROJECT_COLORS disponibles: {sorted(PROJECT_COLORS.keys())}")

    if project_name_upper in PROJECT_COLORS:
        color_flow = PROJECT_COLORS[project_name_upper]
        # El color de Flow es el color identitario del proyecto, no un color de
        # texto: si es muy oscuro no se lee contra el panel. Se aclara solo lo
        # necesario y respetando el tono.
        base_color = ensure_min_luminance(color_flow, MIN_TEXT_LUMINANCE)
        if base_color != color_flow:
            debug_print(
                f"🎨 '{project_name}' aclarado por legibilidad: {color_flow} -> {base_color}"
            )
        hover_color = get_brighter_color(base_color)
        debug_print(f"✅ Proyecto '{project_name}' encontrado - Base: {base_color}, Hover: {hover_color}")
        return base_color, hover_color
    else:
        # Color por defecto: el proyecto no esta en la DB de PipeSync o no tiene color
        debug_print(f"⚪ Proyecto '{project_name}' sin color en PipeSync - Usando color por defecto")
        return "#cccccc", "#ffffff"


# Buscar y añadir la ruta del módulo de escaneo al sys.path
projects_panel_path = None

# Método 1: carpeta LGA_NKS_Projects_Panel_py junto a este script
try:
    script_dir = Path(__file__).resolve().parent
    candidate = script_dir / "LGA_NKS_Projects_Panel_py"
    if (candidate / "LGA_Projects_Panel_ScanProjects.py").exists():
        projects_panel_path = candidate
except Exception:
    pass

# Método 2: Buscar en sys.path y subcarpetas LGA_*
if projects_panel_path is None:
    for path_str in sys.path:
        try:
            path = Path(path_str)
            if (path / "LGA_Projects_Panel_ScanProjects.py").exists():
                projects_panel_path = path
                break
            if path.exists():
                for subdir in path.iterdir():
                    if subdir.is_dir() and subdir.name.startswith("LGA_"):
                        if (subdir / "LGA_Projects_Panel_ScanProjects.py").exists():
                            projects_panel_path = subdir
                            break
                if projects_panel_path:
                    break
        except Exception:
            continue

# Método 3: rutas estándar en .nuke
if projects_panel_path is None:
    standard_paths = [
        Path.home() / ".nuke" / "Python" / "Startup" / "LGA_NKS_Projects_Panel_py",
        Path(os.path.expanduser("~")) / ".nuke" / "Python" / "Startup" / "LGA_NKS_Projects_Panel_py",
    ]
    for test_path in standard_paths:
        if (test_path / "LGA_Projects_Panel_ScanProjects.py").exists():
            projects_panel_path = test_path
            break

# Añadir al sys.path si se encontró
if projects_panel_path and projects_panel_path.exists():
    if str(projects_panel_path) not in sys.path:
        sys.path.insert(0, str(projects_panel_path))

# Importar funciones del módulo de escaneo
try:
    from LGA_Projects_Panel_ScanProjects import (
        scan_projects_on_disk,
        get_open_projects_info,
        is_project_open,
        get_project_sequences,
        get_projects_with_newer_versions,
    )
except ImportError as e:
    raise ImportError(
        f"No se pudo importar LGA_Projects_Panel_ScanProjects: {e}. Buscado en: {projects_panel_path}"
    )

# Importar función de cambio de secuencia V3 híbrida
try:
    import importlib

    import LGA_Projects_Panel_SwitchSequence

    importlib.reload(LGA_Projects_Panel_SwitchSequence)
    from LGA_Projects_Panel_SwitchSequence import switch_to_sequence_hybrid as switch_to_sequence

    debug_print("✅ Módulo LGA_Projects_Panel_SwitchSequence recargado exitosamente")
except ImportError as e:
    raise ImportError(f"No se pudo importar LGA_Projects_Panel_SwitchSequence: {e}")

# Importar módulo ProjectItem
try:
    from LGA_NKS_Projects_Panel_py.LGA_NKS_ProjectItem import ProjectItem, initialize_dependencies
    # Inicializar dependencias del módulo ProjectItem
    initialize_dependencies(get_project_colors, debug_print, switch_to_sequence)
    debug_print("✅ Módulo LGA_NKS_ProjectItem importado exitosamente")
except ImportError as e:
    debug_print(f"❌ Error importando LGA_NKS_ProjectItem: {e}")
    raise

# Importar módulo Workers
try:
    from LGA_NKS_Projects_Panel_py.LGA_NKS_Workers import WorkerSignals, ScanWorker, initialize_dependencies as initialize_workers_dependencies
    # Inicializar dependencias del módulo Workers
    initialize_workers_dependencies(scan_projects_on_disk, get_open_projects_info, debug_print)
    debug_print("✅ Módulo LGA_NKS_Workers importado exitosamente")
except ImportError as e:
    debug_print(f"❌ Error importando LGA_NKS_Workers: {e}")
    raise

# Importar módulo UIManager
try:
    from LGA_NKS_Projects_Panel_py.LGA_NKS_UIManager import UIManager, initialize_ui_dependencies
    # Inicializar dependencias del módulo UI
    initialize_ui_dependencies(
        REIMPORT_BUTTON,
        switch_login=SWITCH_ALLOWED_LOGIN,
        get_context_fn=get_context_mode,
        find_ini_fn=find_context_ini,
        get_login_fn=get_normal_login
    )
    debug_print("✅ Módulo LGA_NKS_UIManager importado exitosamente")
except ImportError as e:
    debug_print(f"❌ Error importando LGA_NKS_UIManager: {e}")
    raise

# Importar módulo ScanManager
try:
    from LGA_NKS_Projects_Panel_py.LGA_NKS_ScanManager import ScanManager, initialize_scan_dependencies
    # Inicializar dependencias del módulo ScanManager
    initialize_scan_dependencies(ScanWorker, debug_print, print_debug_messages)
    debug_print("✅ Módulo LGA_NKS_ScanManager importado exitosamente")
except ImportError as e:
    debug_print(f"❌ Error importando LGA_NKS_ScanManager: {e}")
    raise

# Importar módulo ProjectHandler
try:
    from LGA_NKS_Projects_Panel_py.LGA_NKS_ProjectHandler import ProjectHandler, initialize_project_dependencies
    # Inicializar dependencias del módulo ProjectHandler
    initialize_project_dependencies(ProjectItem, is_project_open, get_project_sequences, debug_print)
    debug_print("✅ Módulo LGA_NKS_ProjectHandler importado exitosamente")
except ImportError as e:
    debug_print(f"❌ Error importando LGA_NKS_ProjectHandler: {e}")
    raise


def _install_project_close_listener(panel):
    """
    Refresca el panel cuando se cierra un proyecto por CUALQUIER via (la x del
    panel, File > Close, un script). Antes el panel no se enteraba y seguia
    mostrando el proyecto abierto con sus secuencias.

    Se registra una sola vez por proceso: el handler anterior queda guardado en
    hiero.core y se desregistra antes, porque el reimport del panel recarga este
    modulo y sin eso se acumularian handlers apuntando a paneles destruidos.
    """
    import weakref

    from hiero.core import events

    panel_ref = weakref.ref(panel)

    def _on_project_close(event):
        target = panel_ref()
        if target is None or not is_widget_alive(target):
            return
        if QtCore.QCoreApplication.closingDown():
            return  # NKS cerrando: no largar escaneos en hilos
        QtCore.QTimer.singleShot(0, target.start_scan)

    previous = getattr(hiero.core, "_lga_projects_panel_close_handler", None)
    if previous is not None:
        try:
            events.unregisterInterest(events.EventType.kAfterProjectClose, previous)
        except Exception:
            pass
    events.registerInterest(events.EventType.kAfterProjectClose, _on_project_close)
    hiero.core._lga_projects_panel_close_handler = _on_project_close


class ProjectsPanel(QtWidgets.QWidget):
    """Panel final integrado: escaneo, apertura y cambio de secuencias"""

    def __init__(self):
        super(ProjectsPanel, self).__init__()

        self.setObjectName("com.lega.ProjectsPanel")
        self.setWindowTitle("Projects")
        self.setAttribute(Qt.WA_DeleteOnClose, False)

        # Cargar configuración de colores
        debug_print("🏗️ Inicializando ProjectsPanel - cargando colores...")
        load_project_colors()
        debug_print("✅ Carga de colores completada")

        # Estado
        self.proyectos_encontrados = []
        self.proyectos_abiertos = {}
        self.project_items = {}
        self.content_stack = None
        self.projects_container = None
        self.settings_widget = None
        self.track_names_container = None
        self.settings_list_layout = None
        self.settings_rows = []
        self.settings_timer_dropdown = None
        self.auto_refresh_timer = QtCore.QTimer(self)
        self.auto_refresh_timer.timeout.connect(self._on_auto_refresh_timeout)
        self.ctx_client_btn = None
        self.ctx_studio_btn = None
        self.normal_pipesync_login = self._get_normal_pipesync_login()
        # Proyectos abiertos que el usuario colapso (por nombre_base). Estado del
        # panel: sobrevive al rearmado de la lista, no a reabrir NKS.
        self.collapsed_projects = set()
        self._drop_has_supported_media = False
        self._drop_overlay = None

        UIManager.setup_ui(self)
        UIManager.setup_connections(self)
        self.setAcceptDrops(True)
        self._create_media_drop_overlay()
        try:
            _install_project_close_listener(self)
        except Exception as e:
            debug_print(f"No se pudo registrar el aviso de cierre de proyecto: {e}")

        # Aplicar intervalo de auto-refresh desde .ini
        interval_key = self._load_auto_refresh_interval()
        self._apply_auto_refresh_interval(interval_key)

        # Delay antes de iniciar escaneo para que Qt esté completamente inicializado
        QtCore.QTimer.singleShot(500, self.start_scan)  # 500ms delay

    # =========================
    #       DROP DE MEDIA
    # =========================
    def _create_media_drop_overlay(self):
        """Crea el cartel de drop que se muestra solo para media valida."""
        overlay = QtWidgets.QWidget(self)
        overlay.setObjectName("ProjectMediaDropOverlay")
        overlay.setAttribute(Qt.WA_StyledBackground, True)
        overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        overlay.setStyleSheet(
            "\n".join(
                (
                    Style.WINDOW,
                    "QWidget#ProjectMediaDropOverlay {"
                    " background-color: %s; border: 2px dashed %s; border-radius: 8px;"
                    "} QLabel#ProjectMediaDropOverlayLabel {"
                    " background: transparent; border: none; color: %s;"
                    "}"
                    % (Color.ACCENT_DISABLED, Color.ACCENT, Color.TEXT_STRONG),
                )
            )
        )

        layout = QtWidgets.QVBoxLayout(overlay)
        label = QtWidgets.QLabel("Drop media to import at the playhead", overlay)
        label.setObjectName("ProjectMediaDropOverlayLabel")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        overlay.setGeometry(self.rect())
        overlay.hide()
        self._drop_overlay = overlay

    def _set_media_drop_overlay_visible(self, visible):
        if self._drop_overlay is None:
            return
        if visible:
            self._drop_overlay.setGeometry(self.rect())
            self._drop_overlay.raise_()
            self._drop_overlay.show()
        else:
            self._drop_overlay.hide()

    @staticmethod
    def _single_media_from_mime(mime_data):
        """Devuelve un único archivo local con una extensión soportada."""
        if mime_data is None or not mime_data.hasUrls():
            return None

        paths = []
        for url in mime_data.urls():
            if not url.isLocalFile():
                continue
            path = url.toLocalFile()
            if (
                os.path.isfile(path)
                and os.path.splitext(path)[1].lower() in _DROP_MEDIA_EXTENSIONS
            ):
                paths.append(path)

        return paths[0] if len(paths) == 1 and len(mime_data.urls()) == 1 else None

    def dragEnterEvent(self, event):
        media_path = self._single_media_from_mime(event.mimeData())
        self._drop_has_supported_media = media_path is not None
        if self._drop_has_supported_media:
            event.acceptProposedAction()
            self._set_media_drop_overlay_visible(True)
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if self._drop_has_supported_media:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._drop_has_supported_media = False
        self._set_media_drop_overlay_visible(False)
        event.accept()

    def dropEvent(self, event):
        self._drop_has_supported_media = False
        self._set_media_drop_overlay_visible(False)
        media_path = self._single_media_from_mime(event.mimeData())
        if media_path is None:
            debug_print("[Drop media] Drop ignorado: se espera un unico archivo de media local soportado.")
            event.ignore()
            return

        event.acceptProposedAction()
        # Un modal dentro de dropEvent puede dejar el loop nativo de Windows
        # abierto. Se difiere toda la operacion al siguiente ciclo de Qt.
        QtCore.QTimer.singleShot(
            0,
            lambda path=media_path: (
                self._import_dropped_media(path) if is_widget_alive(self) else None
            ),
        )

    def resizeEvent(self, event):
        super(ProjectsPanel, self).resizeEvent(event)
        if self._drop_overlay is not None:
            self._drop_overlay.setGeometry(self.rect())

    @staticmethod
    def _current_playhead_time():
        """Lee el playhead del viewer actual, con el fallback del player."""
        viewer = hiero.ui.currentViewer()
        if viewer is None:
            return None
        try:
            return int(viewer.time())
        except Exception:
            try:
                return int(viewer.player().time())
            except Exception:
                return None

    @staticmethod
    def _selected_video_track(sequence, timeline_editor):
        """Resuelve el track seleccionado desde selección directa de track o clip."""
        tracks = list(sequence.videoTracks())
        try:
            selection = list(timeline_editor.selection() or [])
        except Exception:
            selection = []

        for item in selection:
            if isinstance(item, hiero.core.TrackBase) and item in tracks:
                return item
            try:
                parent_track = item.parentTrack()
            except Exception:
                parent_track = None
            if parent_track in tracks:
                return parent_track

        # No usar selectedRow() como indice de videoTracks(): la vista puede
        # incluir tracks de audio y no se midio aun una correspondencia 1:1.
        # Es preferible pedir al usuario una seleccion explicita que colocar
        # media en otro track. La sonda de esta feature deja el dato para una
        # ampliacion posterior.
        debug_print("[Drop media] No hay un track de video seleccionado explicitamente.")
        return None

    @staticmethod
    def _is_burnin_track(track):
        """Identifica BurnIn sin depender de la instancia concreta del track."""
        try:
            return track.name().lower().strip().replace(" ", "").replace("_", "") == "burnin"
        except Exception:
            return False

    @staticmethod
    def _real_track_items(track):
        """TrackItems reales; los EffectTrackItems se leen por subtrack aparte."""
        try:
            return [
                item
                for item in list(track.items() or [])
                if not isinstance(item, hiero.core.EffectTrackItem)
            ]
        except Exception:
            return []

    @classmethod
    def _all_edit_tracks(cls, sequence):
        """Video y audio editables, excluyendo el overlay de BurnIn."""
        tracks = []
        for collection in (sequence.videoTracks(), sequence.audioTracks()):
            for track in list(collection or []):
                if not cls._is_burnin_track(track):
                    tracks.append(track)
        return tracks

    @classmethod
    def _track_entries_for_preview(cls, sequence):
        """Tracks de video con etiqueta unica aunque Hiero repita nombres."""
        entries = []
        video_tracks = list(sequence.videoTracks() or [])
        occurrences = {}
        for index, track in enumerate(video_tracks):
            if cls._is_burnin_track(track):
                continue
            try:
                name = track.name()
            except Exception:
                name = "Video track"
            occurrences[name] = occurrences.get(name, 0) + 1
            entries.append({"track": track, "name": name, "index": index})

        totals = {}
        for entry in entries:
            totals[entry["name"]] = totals.get(entry["name"], 0) + 1
        seen = {}
        for entry in entries:
            name = entry["name"]
            seen[name] = seen.get(name, 0) + 1
            suffix = " (%d)" % seen[name] if totals[name] > 1 else ""
            entry["label"] = "%s%s" % (name, suffix)
        return list(reversed(entries))

    @classmethod
    def _audio_entries_for_preview(cls, sequence):
        """Tracks de audio solo para explicar el alcance del ripple."""
        entries = []
        audio_tracks = list(sequence.audioTracks() or [])
        totals = {}
        for track in audio_tracks:
            if cls._is_burnin_track(track):
                continue
            try:
                name = track.name()
            except Exception:
                name = "Audio track"
            totals[name] = totals.get(name, 0) + 1
            entries.append({"track": track, "name": name})
        seen = {}
        for entry in entries:
            name = entry["name"]
            seen[name] = seen.get(name, 0) + 1
            suffix = " (%d)" % seen[name] if totals[name] > 1 else ""
            entry["label"] = "Audio · %s%s" % (name, suffix)
        return list(reversed(entries))

    @classmethod
    def _track_has_free_interval(cls, track, first_frame, duration):
        """True si [first_frame, first_frame + duration - 1] no pisa un clip."""
        last_frame = first_frame + duration - 1
        for item in cls._real_track_items(track):
            try:
                if int(item.timelineIn()) <= last_frame and int(item.timelineOut()) >= first_frame:
                    return False
            except Exception:
                return False
        return True

    @classmethod
    def _last_timeline_frame(cls, sequence):
        """Ultimo frame de clips reales de video y audio, sin contar BurnIn."""
        last_frame = None
        for track in cls._all_edit_tracks(sequence):
            for item in cls._real_track_items(track):
                try:
                    value = int(item.timelineOut())
                except Exception:
                    continue
                last_frame = value if last_frame is None else max(last_frame, value)
        return last_frame

    @classmethod
    def _import_shot_ripple_items(cls, sequence, playhead):
        """Replica la seleccion de push_clips_right antes de alterar el timeline."""
        items = []
        for track in list(sequence.videoTracks() or []):
            if cls._is_burnin_track(track):
                continue
            for item in cls._real_track_items(track):
                try:
                    if int(item.timelineOut()) >= playhead:
                        items.append(item)
                except Exception:
                    continue
        return items

    @staticmethod
    def _timeline_item_color(item):
        """Lee el color de BinItem que Hiero muestra en el timeline."""
        try:
            color = item.source().binItem().color()
            if color is not None and color.isValid():
                return color.name()
        except Exception:
            pass
        return Color.SURFACE_RAISED

    @classmethod
    def _preview_item(cls, item, shift_frames=0, is_new=False, name=None, duration=None):
        """Normaliza un clip para la tabla grafica sin tocar la API de Hiero."""
        if is_new:
            timeline_in = 0
            timeline_out = max(0, int(duration or 1) - 1)
        else:
            timeline_in = int(item.timelineIn())
            timeline_out = int(item.timelineOut())
        return {
            "name": name if name is not None else item.name(),
            "preview_in": timeline_in + shift_frames,
            "preview_out": timeline_out + shift_frames,
            "shift_frames": shift_frames,
            "is_new": is_new,
            "color": Color.ACCENT if is_new else cls._timeline_item_color(item),
        }

    @classmethod
    def _preview_timeline_rows(
        cls, sequence, target_track, playhead, duration, mode, media_name="New media"
    ):
        """Construye el timeline proyectado continuo con el mismo ripple de Import Shot."""
        rows = []
        ripple_items = cls._import_shot_ripple_items(sequence, playhead)
        ripple_ids = {id(item) for item in ripple_items}
        effective_insert_frame = min(
            (int(item.timelineIn()) for item in ripple_items), default=playhead
        )
        end_frame = cls._last_timeline_frame(sequence)
        end_insert_frame = 0 if end_frame is None else end_frame + 1
        preview_entries = [
            dict(entry, selectable=True)
            for entry in cls._track_entries_for_preview(sequence)
        ]
        preview_entries.extend(
            dict(entry, selectable=False)
            for entry in cls._audio_entries_for_preview(sequence)
        )
        visual_ripple = mode == "ripple" and target_track is not None
        insert_frame = effective_insert_frame if visual_ripple else playhead
        for entry in preview_entries:
            track = entry["track"]
            clips = []
            for item in cls._real_track_items(track):
                try:
                    int(item.timelineOut())
                except Exception:
                    continue
                shift = duration if visual_ripple and id(item) in ripple_ids else 0
                clips.append(cls._preview_item(item, shift))
            if track is target_track:
                new_item = cls._preview_item(
                    None,
                    is_new=True,
                    name="%s · %df" % (media_name, duration),
                    duration=duration,
                )
                new_item["color"] = Color.ERROR_TEXT
                if mode == "end":
                    new_item["preview_in"] = end_insert_frame
                    new_item["preview_out"] = end_insert_frame + duration - 1
                else:
                    new_item["preview_in"] = insert_frame
                    new_item["preview_out"] = insert_frame + duration - 1
                clips.append(new_item)
            clips.sort(key=lambda clip: (clip["preview_in"], clip["preview_out"]))
            rows.append(
                {
                    "track": entry["label"],
                    "track_ref": track,
                    "selectable": entry["selectable"],
                    "color": Color.ACCENT_TRACK if track is target_track else Color.SURFACE_RAISED,
                    "clips": clips,
                }
            )
        return rows

    def _analyze_media_insert(
        self, sequence, target_track, playhead, duration, mode, media_name="New media"
    ):
        """Plan puro de UI; se vuelve a calcular inmediatamente antes del Undo."""
        rows = self._preview_timeline_rows(
            sequence, target_track, playhead, duration, mode, media_name
        )
        if target_track is None:
            return {
                "valid": False,
                "message": "Choose a video track to preview the insertion.",
                "action_label": "Import media",
                "rows": rows,
                "playhead": playhead,
            }
        if mode == "gap":
            if self._track_has_free_interval(target_track, playhead, duration):
                return {
                    "valid": True,
                    "message": "The media fits in the selected gap. No clips will move.",
                    "action_label": "Import media",
                    "rows": rows,
                    "playhead": playhead,
                }
            return {
                "valid": False,
                "message": "The selected gap is too short. Choose ripple, another track, or timeline end.",
                "action_label": "Import media",
                "rows": rows,
                "playhead": playhead,
            }

        if mode == "end":
            end_frame = self._last_timeline_frame(sequence)
            insert_frame = 0 if end_frame is None else end_frame + 1
            return {
                "valid": True,
                "message": "The media will start at frame %d. No clips will move." % insert_frame,
                "action_label": "Import at timeline end",
                "rows": rows,
                "playhead": playhead,
            }

        ripple_items = self._import_shot_ripple_items(sequence, playhead)
        effective_insert_frame = min(
            (int(item.timelineIn()) for item in ripple_items), default=playhead
        )
        return {
            "valid": True,
            "message": "The media will open %d frames of space at the playhead. %d video clip(s) will shift right and the media will start at frame %d."
            % (duration, len(ripple_items), effective_insert_frame),
            "action_label": "Import and shift timeline",
            "rows": rows,
            "playhead": playhead,
        }

    def _warn_drop_import(self, text):
        debug_print("[Drop media] %s" % text, level="warning")
        show_warning(self, "Import media", text)

    @staticmethod
    def _detected_drop_media_kind(clip, extension):
        """Describe la media que Hiero detectó al crear el Clip."""
        if extension not in _DROP_IMAGE_EXTENSIONS:
            return "video"

        try:
            media_source = clip.mediaSource()
            duration = int(media_source.duration())
            file_infos = list(media_source.fileinfos() or [])
            frame_ranges = [
                (int(info.startFrame()), int(info.endFrame())) for info in file_infos
            ]
            if duration > 1 or any(first != last for first, last in frame_ranges):
                return "image sequence"
        except Exception as exc:
            debug_print(
                "[Drop media] No se pudo clasificar la imagen detectada: %s" % exc,
                level="warning",
            )
        return "single image"

    @staticmethod
    def _log_detected_drop_media(clip, extension, media_path):
        """Registra el rango que Hiero detectó; no vuelve a escanear el disco."""
        kind = ProjectsPanel._detected_drop_media_kind(clip, extension)
        try:
            media_source = clip.mediaSource()
            duration = int(media_source.duration())
            file_infos = list(media_source.fileinfos() or [])
            ranges = [
                "%s-%s" % (int(info.startFrame()), int(info.endFrame()))
                for info in file_infos
            ]
            range_text = ", ".join(ranges) if ranges else "sin FileInfo"
            debug_print(
                "[Drop media] Detectado %s | '%s' | duracion=%d | rango=%s"
                % (kind, media_path, duration, range_text)
            )
        except Exception as exc:
            debug_print(
                "[Drop media] No se pudo leer el rango detectado para '%s': %s"
                % (media_path, exc),
                level="warning",
            )
        return kind

    def _import_media_at(self, sequence, timeline_editor, target_track, media_path, playhead, duration, mode):
        """Ejecuta un plan ya revalidado dentro de un unico Undo de proyecto."""
        extension = os.path.splitext(media_path)[1].lower()
        clip_name = os.path.splitext(os.path.basename(media_path))[0]
        project = sequence.project()
        if project is None:
            raise RuntimeError("Couldn't resolve the project for the active timeline.")

        if mode == "end":
            end_frame = self._last_timeline_frame(sequence)
            insert_frame = 0 if end_frame is None else end_frame + 1
        else:
            insert_frame = playhead

        # Crear y validar la media ANTES de tocar el timeline. Si esto falla,
        # no hay movimiento ni BinItem que cancelar.
        clip = hiero.core.Clip(str(media_path))
        clip.setName(clip_name)
        actual_duration = int(clip.mediaSource().duration())
        if actual_duration != duration or actual_duration <= 0:
            raise RuntimeError("The media duration changed before it was imported.")
        project.beginUndo("Import media: %s" % clip_name)
        try:
            project.clipsBin().addItem(hiero.core.BinItem(clip))
            if mode == "ripple":
                # Mismo helper, orden y punto efectivo que Import Shot. El helper
                # desplaza desde el borde real del clip y devuelve donde encaja.
                timeline_mod.set_debug_print(debug_print)
                _moved, insert_frame = timeline_mod.push_clips_right(
                    sequence, playhead, duration
                )

            # No llamar clip.rescan(): crea otra entrada Undo aunque este dentro
            # de beginUndo. Clip() detecta secuencias desde cualquier frame.
            media_kind = self._log_detected_drop_media(clip, extension, media_path)

            track_item = target_track.addTrackItem(clip, insert_frame)
            track_item.setName(clip_name)
            track_item.setTimes(
                insert_frame,
                insert_frame + duration - 1,
                0,
                duration - 1,
            )
            track_item.setVersionLinkedToBin(True)

            if mode == "ripple":
                timeline_mod.stretch_burnin(sequence)
        except Exception:
            # cancelUndo revierte el grupo abierto; endUndo solamente lo cierra
            # y dejaria un ripple parcial si falla una operacion posterior.
            try:
                project.cancelUndo()
            except Exception as cancel_exc:
                debug_print(
                    "[Drop media] No se pudo cancelar el Undo tras un fallo: %s"
                    % cancel_exc,
                    level="error",
                )
            raise
        else:
            project.endUndo()

        timeline_editor.setSelection([track_item])
        debug_print(
            "[Drop media] %s importado '%s' | modo=%s | track='%s' | tl=%d-%d"
            % (
                media_kind,
                media_path,
                mode,
                target_track.name(),
                insert_frame,
                insert_frame + duration - 1,
            )
        )

    def _show_media_insert_preview(
        self, sequence, timeline_editor, media_path, playhead, duration, selected_track
    ):
        """Muestra las opciones y revalida el plan antes de modificar el proyecto."""
        dialog = ProjectMediaPreviewDialog(
            os.path.basename(media_path),
            duration,
            playhead,
            self._track_entries_for_preview(sequence),
            lambda track, mode: self._analyze_media_insert(
                sequence,
                track,
                playhead,
                duration,
                mode,
                os.path.splitext(os.path.basename(media_path))[0],
            ),
            selected_track=selected_track,
            initial_mode="ripple",
            parent=self,
        )
        if dialog.exec() != QtWidgets.QDialog.Accepted or not dialog.result_data:
            debug_print("[Drop media] Preview cancelado.")
            return
        target_track = dialog.result_data["track"]
        mode = dialog.result_data["mode"]
        # Un QDialog modal deja activeSequence() en None aunque el mismo
        # timeline siga abierto. Import Shot opera sobre la secuencia capturada;
        # hacemos lo mismo y revalidamos el plan contra ese objeto vivo.
        debug_print(
            "[Drop media] Preview confirmado | modo=%s | track='%s' | playhead=%d | duracion=%d"
            % (mode, target_track.name(), playhead, duration)
        )
        plan = self._analyze_media_insert(
            sequence,
            target_track,
            playhead,
            duration,
            mode,
            os.path.splitext(os.path.basename(media_path))[0],
        )
        if not plan.get("valid"):
            self._warn_drop_import("The timeline changed. Review the updated preview.")
            return
        self._import_media_at(
            sequence,
            timeline_editor,
            target_track,
            media_path,
            playhead,
            duration,
            mode,
        )

    def _import_dropped_media(self, media_path):
        """Analiza el drop y usa import directo o preview segun el riesgo."""
        if not os.path.isfile(media_path):
            self._warn_drop_import("The dropped media is no longer available.")
            return

        extension = os.path.splitext(media_path)[1].lower()
        if extension not in _DROP_MEDIA_EXTENSIONS:
            self._warn_drop_import("This media format is not supported yet.")
            return

        sequence = hiero.ui.activeSequence()
        if sequence is None:
            self._warn_drop_import("Open a timeline before dropping media.")
            return

        timeline_editor = hiero.ui.getTimelineEditor(sequence)
        if timeline_editor is None:
            self._warn_drop_import("Couldn't access the active timeline editor.")
            return

        playhead = self._current_playhead_time()
        if playhead is None:
            self._warn_drop_import("Couldn't read the active playhead.")
            return

        try:
            probe_clip = hiero.core.Clip(str(media_path))
            duration = int(probe_clip.mediaSource().duration())
            if duration <= 0:
                raise RuntimeError("Hiero reported an invalid media duration.")
            self._log_detected_drop_media(probe_clip, extension, media_path)
            target_track = self._selected_video_track(sequence, timeline_editor)
            debug_print(
                "[Drop media] Contexto | playhead=%d | duracion=%d | track=%s"
                % (
                    playhead,
                    duration,
                    target_track.name() if target_track is not None else "<sin seleccionar>",
                )
            )
            if target_track is not None and self._track_has_free_interval(
                target_track, playhead, duration
            ):
                debug_print("[Drop media] Insercion directa: hueco suficiente.")
                self._import_media_at(
                    sequence,
                    timeline_editor,
                    target_track,
                    media_path,
                    playhead,
                    duration,
                    "gap",
                )
                return
            debug_print("[Drop media] Abriendo preview: falta track o el hueco no alcanza.")
            self._show_media_insert_preview(
                sequence,
                timeline_editor,
                media_path,
                playhead,
                duration,
                target_track,
            )
        except Exception as exc:
            self._warn_drop_import("Couldn't import the media.\n\n%s" % exc)


    def _get_normal_pipesync_login(self):
        # Memoizado en LGA_NKS_ContextSwitch: leerlo implica desencriptar
        # config.secure y antes se hacia una vez aca y otra en el UIManager.
        result = get_normal_login()
        debug_print(f"Login de PipeSync normal: '{result}'")
        return result

    def _get_context_ini_path(self):
        ini_path = find_context_ini()
        if ini_path:
            return Path(ini_path)
        return Path(__file__).resolve().parent.parent / "LGA_HieroTools_context.ini"

    def _refresh_context_toggle(self):
        """Actualiza el estilo del toggle pill segun el contexto activo."""
        if not hasattr(self, "ctx_client_btn") or self.ctx_client_btn is None:
            return
        current_mode = get_context_mode()
        active_style = (
            "QPushButton { background: #443a91; color: #cccccc; border: none;"
            " border-radius: 11px; padding: 3px 14px; font-size: 12px; }"
        )
        inactive_style = (
            "QPushButton { background: transparent; color: #8a8a8a; border: none;"
            " border-radius: 11px; padding: 3px 14px; font-size: 12px; }"
            " QPushButton:hover { color: #c8c8c8; }"
        )
        if current_mode == "client":
            self.ctx_client_btn.setStyleSheet(active_style)
            self.ctx_studio_btn.setStyleSheet(inactive_style)
        else:
            self.ctx_studio_btn.setStyleSheet(active_style)
            self.ctx_client_btn.setStyleSheet(inactive_style)
        self.ctx_client_btn.setToolTip("Contexto Client (PipeSyncClient)")
        self.ctx_studio_btn.setToolTip("Contexto Studio (PipeSync normal)")

    def _write_context_mode(self, mode):
        ini_path = self._get_context_ini_path()
        ini_path.parent.mkdir(parents=True, exist_ok=True)

        parser = configparser.ConfigParser()
        if ini_path.exists():
            parser.read(str(ini_path), encoding="utf-8")
        if not parser.has_section("Context"):
            parser.add_section("Context")
        parser.set("Context", "mode", mode)

        with open(ini_path, "w", encoding="utf-8") as ini_file:
            parser.write(ini_file)

        os.environ["LGA_HIEROTOOLS_CONTEXT_INI"] = str(ini_path)
        os.environ["PIPESYNC_CONTEXT"] = mode
        debug_print(f"Contexto actualizado a '{mode}' en {ini_path}")
        return ini_path

    def _reload_after_context_switch(self):
        # Un solo escaneo. Hasta v2.34 se largaba un segundo a los 150 ms; con
        # los escaneos numerados solo contaba el ultimo, asi que era trabajo doble.
        self.start_scan()

    def set_context_mode(self, mode):
        """Cambia el contexto al modo indicado (studio|client) si difiere del actual."""
        new_mode = "client" if mode == "client" else "studio"
        current_mode = get_context_mode()
        if new_mode == current_mode:
            return
        # Antes de tocar nada: el timeline activo es el ultimo del contexto que se deja.
        try:
            timeline_memory.remember_context(current_mode)
        except Exception as e:
            debug_print(f"Error guardando el timeline del contexto '{current_mode}': {e}")
        try:
            self._write_context_mode(new_mode)
            # El escaneo corre en otro hilo y arranca ya, en paralelo con el switch.
            # Si termina con la UI congelada, ScanManager difiere el display.
            self._reload_after_context_switch()
            self._refresh_context_toggle()
            debug_print(f"Contexto cambiado a '{new_mode}' desde toggle")
            # Diferido: el toggle se repinta antes del switch, que tarda medio segundo.
            QtCore.QTimer.singleShot(0, lambda: self._finish_context_switch(new_mode))
        except Exception as e:
            debug_print(f"Error al cambiar contexto: {e}")
            self._refresh_context_toggle()
            show_warning(
                self, "Error al cambiar contexto", f"No se pudo cambiar el contexto:\n{e}"
            )

    # =========================
    #     POST-APERTURA
    # =========================
    def begin_project_open(self):
        """Congela el repintado antes de openProject. Lo levanta end_project_open()."""
        if not FREEZE_DURING_PROJECT_OPEN:
            return
        try:
            hiero.ui.mainWindow().setUpdatesEnabled(False)
            debug_print("[Post-apertura] Repintado congelado desde el click")
        except Exception as e:
            debug_print(f"[Post-apertura] No se pudo congelar el repintado: {e}")

    def end_project_open(self):
        """Levanta el congelado de begin_project_open(). Idempotente."""
        try:
            window = hiero.ui.mainWindow()
            if not window.updatesEnabled():
                window.setUpdatesEnabled(True)
                window.update()
                debug_print("[Post-apertura] Repintado reactivado")
        except Exception as e:
            debug_print(f"[Post-apertura] Error reactivando el repintado: {e}")

    def after_project_open(self, project):
        """
        Deja un proyecto recien abierto como si se hubiera llegado con el switch:
        su ultimo timeline (o el que abrio Hiero), top track, LUT y sin restos
        del proyecto anterior. Espera a que Hiero termine de restaurar su
        timeline, porque limpiar antes lo haria reaparecer encima.
        """
        if project is None:
            self.end_project_open()
            return
        self._post_open = {"project": project, "start": time.time(), "last": None, "since": None}
        QtCore.QTimer.singleShot(POST_OPEN_POLL_MS, self._poll_post_open)

    def _poll_post_open(self):
        state = getattr(self, "_post_open", None)
        if not state:
            return
        project = state["project"]
        now = time.time()
        try:
            seq = hiero.ui.activeSequence()
            current = seq.name() if seq and seq.project() == project else None
        except Exception:
            current = None
        if current != state["last"]:
            state["last"], state["since"] = current, now
        elapsed_ms = (now - state["start"]) * 1000
        stable = current is not None and (now - state["since"]) * 1000 >= POST_OPEN_STABLE_MS
        if not stable and elapsed_ms < POST_OPEN_TIMEOUT_MS:
            QtCore.QTimer.singleShot(POST_OPEN_POLL_MS, self._poll_post_open)
            return
        self._post_open = None
        self._finish_project_open(project, current, elapsed_ms)

    def _finish_project_open(self, project, active_name, elapsed_ms):
        """Elige el timeline de destino y corre el switch completo."""
        try:
            target, origin = timeline_memory.recall_last_sequence(project), "ultimo usado"
            if not target:
                target, origin = active_name, "el que abrio Hiero"
            if not target:
                sequences = project.sequences()
                target, origin = (sequences[0].name(), "primera secuencia") if sequences else (None, "")
            if not target:
                debug_print(f"[Post-apertura] {project.name()} no tiene secuencias")
                return
            switch_to_sequence(target, target_project=project, force_cleanup=True)
            # El switch reinicia el log: esta linea queda como primera traza visible.
            debug_print(
                f"[Post-apertura] {project.name()}: '{target}' ({origin}) | "
                f"Hiero listo en {elapsed_ms:.0f} ms (activa al terminar la espera: {active_name})"
            )
        except Exception as e:
            debug_print(f"[Post-apertura] Error: {e}")
        finally:
            # El switch ya reactiva el repintado al terminar; esto cubre los
            # caminos sin switch (sin secuencias, error) para no dejar NKS congelado.
            self.end_project_open()

    # =========================
    #   COLAPSAR Y CERRAR
    # =========================
    def set_project_collapsed(self, nombre_base, collapsed):
        if collapsed:
            self.collapsed_projects.add(nombre_base)
        else:
            self.collapsed_projects.discard(nombre_base)

    def close_project(self, project):
        """
        Cierra un proyecto desde la x del panel.

        project.close() desde Python NO pregunta ni guarda: descarta los cambios
        en silencio (medido con explore_project_close). Por eso se pregunta aca,
        con modifiedSinceLastSave(); si esa llamada falla, se pregunta igual.
        """
        try:
            name, path = project.name(), project.path()
        except Exception as e:
            debug_print(f"[Cerrar] Proyecto invalido: {e}")
            return

        modified = None
        try:
            modified = bool(project.modifiedSinceLastSave())
        except Exception as e:
            debug_print(f"[Cerrar] modifiedSinceLastSave() fallo: {e}")
        debug_print(f"[Cerrar] {name}: modifiedSinceLastSave={modified}")

        if modified is not False:
            text = (
                f"{name} has unsaved changes. Save them before closing?"
                if modified
                else f"Couldn't check if {name} has unsaved changes. Save before closing?"
            )
            answer = ask_save_discard_cancel(self, "Close project", text)
            debug_print(f"[Cerrar] Respuesta: {answer}")
            if answer == "cancel":
                return
            if answer == "save":
                try:
                    project.save()
                except Exception as e:
                    show_warning(self, "Close project", f"Couldn't save {name}:\n{e}")
                    return

        try:
            active = hiero.ui.activeSequence()
            was_active = bool(active and active.project() == project)
        except Exception:
            was_active = False

        try:
            project.close()
        except Exception as e:
            show_warning(self, "Close project", f"Couldn't close {name}:\n{e}")
            return
        debug_print(f"[Cerrar] {name} cerrado | era el del timeline activo: {was_active}")

        if was_active:
            self._go_to_other_open_project(path)
        self.start_scan()

    def _go_to_other_open_project(self, closed_path):
        """Tras cerrar el proyecto activo, va al ultimo timeline de otro abierto del panel."""
        for item in self.project_items.values():
            project = item.project_info.get("proyecto_abierto")
            if not item.is_open or project is None:
                continue
            try:
                if project.path() == closed_path:
                    continue
                target = timeline_memory.recall_last_sequence(project)
                if not target:
                    sequences = project.sequences()
                    target = sequences[0].name() if sequences else None
            except Exception:
                continue  # el objeto puede ser del proyecto recien cerrado
            if target:
                switch_to_sequence(target, target_project=project, force_cleanup=True)
                debug_print(f"[Cerrar] Vuelta a '{target}' de {project.name()}")
                return
        debug_print("[Cerrar] No hay otro proyecto abierto en el panel: sin timeline")

    def _finish_context_switch(self, mode):
        """
        Segunda mitad del toggle: el switch de timeline y, despues, el aviso.

        El switch congela el repintado de la ventana principal y procesa eventos
        adentro. Todo lo que rearme UI en ese lapso queda sin dibujar hasta que
        NKS pierde y recupera el foco. Por eso el aviso a los paneles suscriptos
        va despues, y el escaneo propio (ya largado) difiere su display.
        """
        self._return_to_context_timeline(mode)
        try:
            # Recien despues de que el INI quedo escrito: los paneles suscriptos
            # releen el contexto y tienen que ver el valor nuevo, no el viejo.
            notify_context_change(mode)
        except Exception as e:
            debug_print(f"Error avisando el cambio a '{mode}': {e}")

    def _return_to_context_timeline(self, mode):
        """Vuelve al ultimo timeline usado en `mode`, si hay uno y su proyecto sigue abierto."""
        try:
            target = timeline_memory.recall_context(mode)
            if not target:
                return
            project, seq_name = target
            switch_to_sequence(seq_name, target_project=project)
            # El switch reinicia el log: esta linea queda como primera traza visible.
            debug_print(f"[Memoria] Toggle a '{mode}': vuelta a '{seq_name}' de {project.name()}")
        except Exception as e:
            debug_print(f"Error volviendo al timeline del contexto '{mode}': {e}")

    def eventFilter(self, obj, event):
        """Manejar eventos de hover para botones y labels"""
        return UIManager.eventFilter(self, obj, event)

    def start_scan(self):
        ScanManager.start_scan(self)
        self._restart_auto_refresh_timer()

    def on_scan_finished(self, proyectos_encontrados, proyectos_abiertos):
        ScanManager.on_scan_finished(self, proyectos_encontrados, proyectos_abiertos)

    def on_scan_error(self, error_msg):
        ScanManager.on_scan_error(self, error_msg)

    def update_projects_display(self):
        # Diagnostico: si esto sale False, la lista se esta rearmando mientras un
        # switch de secuencia tiene congelado el repintado.
        try:
            debug_print(
                f"[Freeze] Display de proyectos con repintado de la ventana principal="
                f"{hiero.ui.mainWindow().updatesEnabled()}"
            )
        except Exception:
            pass
        # Se releen los colores en cada display para que un cambio hecho en PipeSync
        # se vea con un Refresh, sin reiniciar Hiero.
        load_project_colors()
        ProjectHandler.update_projects_display(self)
        # Siempre volver a la vista principal después de actualizar
        self.show_projects_view()

    def on_project_click(self, proyecto_info):
        ProjectHandler.on_project_click(self, proyecto_info)

    def reimport_panel(self):
        """Recarga el panel usando el script externo de smart reload"""
        debug_print("🔄 BOTÓN REIMPORT PRESIONADO - Iniciando recarga del panel...")
        try:
            # 🔄 RECARGAR COLORES DESDE PIPESYNC ANTES DEL RELOAD
            debug_print("🔄 Recargando colores desde PipeSync antes del reimport...")
            load_project_colors()
            debug_print("✅ Colores recargados desde PipeSync")

            script_path = os.path.join(
                os.path.dirname(__file__), "LGA_NKS_Projects_Panel_py", "LGA_NKS_Projects_Panel_Smart_Reload.py"
            )
            if os.path.exists(script_path):
                import importlib.util

                spec = importlib.util.spec_from_file_location(
                    "LGA_NKS_Projects_Panel_Smart_Reload", script_path
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                module.main()
                debug_print("Ejecutado LGA_NKS_Projects_Panel_Smart_Reload script.")
            else:
                debug_print(f"Script not found at path: {script_path}")
        except Exception as e:
            debug_print(f"Error durante reimportación: {e}")
            show_warning(self, "Error", f"Error durante reimportación:\n{str(e)}")

    def _run_project_tool(self, script_name, action_label):
        """Carga una accion de proyecto desde su script y ejecuta main()."""
        script_path = os.path.join(
            os.path.dirname(__file__), "LGA_NKS_Projects_Panel_py", script_name
        )
        debug_print(f"Ejecutando {action_label}: {script_path}")

        try:
            if not os.path.isfile(script_path):
                raise FileNotFoundError(script_path)

            module_name = f"lga_projects_panel_{os.path.splitext(script_name)[0]}"
            spec = importlib.util.spec_from_file_location(module_name, script_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"No se pudo crear el loader para {script_name}")

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            entry_point = getattr(module, "main", None)
            if not callable(entry_point):
                raise AttributeError(f"{script_name} no expone main()")

            entry_point()
            debug_print(f"{action_label} completado")
            return True
        except Exception as e:
            debug_print(f"Error ejecutando {action_label}: {e}")
            show_warning(
                self,
                action_label,
                f"Couldn't run {action_label}.\n\n{e}",
            )
            return False

    def organize_project(self):
        """Organiza los clips del proyecto activo en bins segun su ruta."""
        return self._run_project_tool(
            "LGA_NKS_OrganizeProject.py", "Organize Project"
        )

    def clean_project(self):
        """Elimina del proyecto activo los clips que no estan en uso."""
        return self._run_project_tool("LGA_NKS_CleanProject.py", "Clean Project")

    def on_update_project_click(self, newer_version_info):
        """Manejar el click en el botón de update para actualizar proyecto a versión más nueva"""
        ProjectHandler.on_update_project_click(self, newer_version_info)

    # =========================
    #       SETTINGS VIEW
    # =========================
    def show_settings_view(self):
        if not self.settings_widget:
            self._build_settings_view()
        else:
            # La vista se construye una sola vez, pero los colores viven en la DB de
            # PipeSync y pueden haber cambiado desde la ultima apertura.
            self._populate_settings_colors()
            # Y las tasks dependen del contexto, que el toggle cambia en caliente.
            self._refresh_track_names()
        if self.content_stack and self.settings_widget:
            self.content_stack.setCurrentWidget(self.settings_widget)
            # Actualizar la etiqueta de cuenta regresiva cada vez que se muestra settings
            self._update_next_refresh_label()

    def _refresh_track_names(self):
        """Rehace la seccion Track names con las tasks del contexto activo."""
        if populate_track_names_section is None:
            return
        try:
            populate_track_names_section(getattr(self, "track_names_container", None))
        except Exception as exc:
            debug_print(f"No se pudo refrescar la seccion Track names: {exc}")

    def show_projects_view(self):
        if self.content_stack and self.projects_container:
            self.content_stack.setCurrentWidget(self.projects_container)

    def _build_settings_view(self):
        self.settings_widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(self.settings_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)  # Espaciado más pequeño entre items

        # IMPORTANTE: Configurar para que NO expanda espacios automáticamente
        self.settings_widget.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)

        # Auto-refresh interval (label + dropdown en fila horizontal)
        interval_row = QtWidgets.QHBoxLayout()
        interval_row.setContentsMargins(0, 0, 0, 0)
        interval_row.setSpacing(8)

        interval_label = QtWidgets.QLabel("Auto-refresh")

        # Ruta para icono SVG de flecha (triángulo sólido)
        arrow_icon_path = os.path.join(os.path.dirname(__file__), "LGA_NKS_Projects_Panel_py", "down_arrow.svg")
        arrow_icon_url = QtCore.QUrl.fromLocalFile(arrow_icon_path).toString()

        # Aplicar estilo elegante al dropdown con flecha y separador DENTRO del botón
        dropdown_stylesheet = f"""
            QComboBox {{
                background-color: #2d2d2d;
                border: 1px solid #555555;
                border-radius: 3px;
                color: #d8d8d8;
                padding: 2px 24px 2px 8px;  /* espacio derecho para separador + flecha */
                min-height: 24px;
            }}
            QComboBox:hover {{
                background-color: #3d3d3d;
                border: 1px solid #777777;
            }}
            QComboBox::drop-down {{
                border-left: 1px solid #555555; /* separador vertical interno */
                background: transparent;
                width: 20px;
                subcontrol-origin: padding;
                subcontrol-position: right center;
            }}
            QComboBox::down-arrow {{
                image: url("{arrow_icon_url}");
                width: 10px;
                height: 6px;
                margin-right: 4px;
                margin-top: 3px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #2d2d2d;
                border: 1px solid #555555;
                border-radius: 3px;
                color: #d8d8d8;
                selection-background-color: #443a91;
                selection-color: #ffffff;
            }}
        """

        self.settings_timer_dropdown = QtWidgets.QComboBox()
        self.settings_timer_dropdown.setFixedWidth(95)  # Ancho suficiente para texto + flecha integrada
        self.settings_timer_dropdown.setStyleSheet(dropdown_stylesheet)
        for key in ["never", "5min", "10min", "15min", "30min", "1h", "2h"]:
            self.settings_timer_dropdown.addItem(key, key)

        # Orden correcto: label primero, luego dropdown
        interval_row.addWidget(interval_label)
        interval_row.addWidget(self.settings_timer_dropdown)
        interval_row.addStretch(1)  # Empujar elementos a la izquierda

        current_interval_key = self._load_auto_refresh_interval()
        idx = self.settings_timer_dropdown.findData(current_interval_key)
        if idx >= 0:
            self.settings_timer_dropdown.setCurrentIndex(idx)

        layout.addLayout(interval_row)

        # Línea de próximo auto-refresh
        self.next_refresh_label = QtWidgets.QLabel("Next in: --")
        self.next_refresh_label.setStyleSheet("color: #888888; font-size: 13px; margin: 0px;")
        self.next_refresh_label.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.next_refresh_label.setMinimumHeight(20)
        layout.addWidget(self.next_refresh_label, alignment=QtCore.Qt.AlignLeft)

        # Actualizar la etiqueta con el estado actual del timer
        self._update_next_refresh_label()

        # Línea en blanco antes del título de projects colors
        layout.addWidget(QtWidgets.QLabel(""))

        # Projects colors list. Es SOLO VISIBILIDAD: los colores salen de la DB de
        # PipeSync y se editan en su Project Settings tab, para que sean los mismos
        # en todas las maquinas.
        colors_label = QtWidgets.QLabel("Project colors")
        colors_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #d8d8d8;")
        layout.addWidget(colors_label)

        colors_hint = QtWidgets.QLabel("Read-only. Se editan en PipeSync > Project Settings.")
        colors_hint.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(colors_hint)

        self.settings_rows = []
        self.settings_list_container = QtWidgets.QWidget()
        self.settings_list_layout = QtWidgets.QVBoxLayout(self.settings_list_container)
        self.settings_list_layout.setContentsMargins(0, 0, 0, 0)
        self.settings_list_layout.setSpacing(4)  # Reducir espacios entre filas de colores
        layout.addWidget(self.settings_list_container)

        self._populate_settings_colors()

        # Línea en blanco antes de los nombres de track
        layout.addWidget(QtWidgets.QLabel(""))

        # Seccion informativa: si falla, la vista de Settings sigue andando.
        if build_track_names_section is not None:
            try:
                self.track_names_container = build_track_names_section()
                layout.addWidget(self.track_names_container)
            except Exception as exc:
                debug_print(f"No se pudo armar la seccion Track names: {exc}")

        # Línea en blanco antes de los botones Cancel y Save
        layout.addWidget(QtWidgets.QLabel(""))

        # Save / Cancel buttons - alineados con los botones X de las filas
        # El layout padre ya tiene 10px de margen izquierdo, así que ajustamos
        # ancho real necesario: 140 + 4 + 40 + 4 + 30 - 10 = 208px
        buttons_container = QtWidgets.QHBoxLayout()
        buttons_container.setContentsMargins(40, 0, 0, 0)  # ✅✅ Margen izquierdo para alinear con botones X
        buttons_container.setSpacing(10)

        # Aplicar estilo dinámico a los botones Cancel y Save
        button_style = "#443a91"
        border_color = calculate_dynamic_border(button_style)
        hover_color = calculate_dynamic_hover(button_style)

        button_stylesheet = f"""
            QPushButton {{
                background-color: {button_style};
                border: 1px solid {border_color};
                border-radius: 3px;
                color: #d8d8d8;
                padding: 0px 0px;
                min-height: 24px;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:pressed {{
                background-color: {button_style}aa;
            }}
        """

        cancel_btn = QtWidgets.QPushButton("Cancel")
        save_btn = QtWidgets.QPushButton("Save")
        cancel_btn.setFixedWidth(70)
        save_btn.setFixedWidth(70)
        cancel_btn.setStyleSheet(button_stylesheet)
        save_btn.setStyleSheet(button_stylesheet)
        cancel_btn.clicked.connect(self._on_settings_cancel)
        save_btn.clicked.connect(self._on_settings_save)

        buttons_container.addWidget(cancel_btn)
        buttons_container.addWidget(save_btn)
        buttons_container.addStretch(1)  # Empujar botones a la izquierda dentro del margen

        layout.addLayout(buttons_container)

        # AÑADIR STRETCH AL FINAL PARA EVITAR ESPACIOS FLEX ENTRE ELEMENTOS
        layout.addStretch(1)

        # Insert settings widget into stack
        if self.content_stack:
            self.content_stack.addWidget(self.settings_widget)

    def _populate_settings_colors(self):
        """Rellena la lista read-only de colores con lo que hay ahora en PipeSync."""
        if not self.settings_list_layout:
            return

        for i in reversed(range(self.settings_list_layout.count())):
            item = self.settings_list_layout.itemAt(i)
            if item.widget():
                item.widget().setParent(None)
        self.settings_rows = []

        load_project_colors()

        if PROJECT_COLORS:
            for name, color in sorted(PROJECT_COLORS.items()):
                self._add_settings_row(name, color)
            return

        # Sin esto el vacio se leeria como "no hay proyectos con color asignado",
        # cuando en realidad lo que falta es el sync de PipeSync de este contexto.
        empty_label = QtWidgets.QLabel("Sin colores: PipeSync todavía no sincronizó este contexto.")
        empty_label.setStyleSheet("color: #888888; font-style: italic; font-size: 12px;")
        empty_label.setWordWrap(True)
        self.settings_list_layout.addWidget(empty_label)

    def _add_settings_row(self, name, color):
        """Fila read-only: nombre del proyecto y su swatch de color, tal como vienen de PipeSync."""
        row_widget = QtWidgets.QWidget()
        row_layout = QtWidgets.QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        name_label = QtWidgets.QLabel(name)
        name_label.setFixedWidth(140)
        name_label.setStyleSheet("color: #d8d8d8; font-size: 12px;")

        swatch_border_color = calculate_dynamic_border(color)
        swatch = QtWidgets.QLabel()
        swatch.setFixedSize(16, 16)
        swatch.setStyleSheet(
            f"background-color: {color}; border: 1px solid {swatch_border_color}; border-radius: 3px;"
        )
        swatch.setToolTip(f"Color de {name} en PipeSync: {color}")

        hex_label = QtWidgets.QLabel(color)
        hex_label.setStyleSheet("color: #888888; font-size: 11px;")

        row_layout.addWidget(name_label)
        row_layout.addWidget(swatch)
        row_layout.addWidget(hex_label)
        row_layout.addStretch(1)

        self.settings_list_layout.addWidget(row_widget)
        self.settings_rows.append({"widget": row_widget, "name": name, "color": color})

    def _on_settings_cancel(self):
        self.show_projects_view()

    def _on_settings_save(self):
        # Lo unico editable del panel de settings es el intervalo: los colores son
        # read-only y se editan en PipeSync.
        interval_key = self.settings_timer_dropdown.currentData()
        self._save_auto_refresh_interval(interval_key)

        self._apply_auto_refresh_interval(interval_key)
        self.show_projects_view()
        self.start_scan()

    # --- Auto refresh helpers ---
    def _load_auto_refresh_interval(self):
        ini_path = Path(__file__).parent / "LGA_NKS_Projects_Panel.ini"
        if not ini_path.exists():
            return "never"
        config = configparser.ConfigParser()
        config.read(ini_path, encoding="utf-8")
        return config.get("General", "AutoRefreshInterval", fallback="never")

    def _save_auto_refresh_interval(self, key):
        ini_path = Path(__file__).parent / "LGA_NKS_Projects_Panel.ini"
        config = configparser.ConfigParser()
        if ini_path.exists():
            config.read(ini_path, encoding="utf-8")
        if "General" not in config:
            config["General"] = {}
        config["General"]["AutoRefreshInterval"] = key
        with open(ini_path, "w", encoding="utf-8") as f:
            config.write(f)

    def _apply_auto_refresh_interval(self, key):
        minutes = AUTO_REFRESH_OPTIONS.get(key, 0)
        if minutes <= 0:
            self.auto_refresh_timer.stop()
            self._update_next_refresh_label()
            return
        self.auto_refresh_timer.start(minutes * 60 * 1000)
        self._update_next_refresh_label()

    def _restart_auto_refresh_timer(self):
        if self.auto_refresh_timer.isActive():
            self.auto_refresh_timer.start(self.auto_refresh_timer.interval())
        self._update_next_refresh_label()

    def _on_auto_refresh_timeout(self):
        if self.refresh_button.isEnabled():
            self.start_scan()
        self._update_next_refresh_label()

    def _update_next_refresh_label(self):
        """Actualiza la etiqueta de cuenta regresiva del auto-refresh."""
        if not hasattr(self, "next_refresh_label") or self.next_refresh_label is None:
            return
        if not self.auto_refresh_timer.isActive():
            self.next_refresh_label.setText("Next in: --")
            return
        remaining_ms = self.auto_refresh_timer.remainingTime()
        if remaining_ms < 0:
            self.next_refresh_label.setText("Next in: --")
            return
        minutes = max(1, int(round(remaining_ms / 60000.0)))
        self.next_refresh_label.setText(f"Next in: {minutes} min")


# Crear la instancia del widget y añadirlo al gestor de ventanas de Hiero
# SOLO si AUTO_CREATE_PANEL está activado (controlado por smart reload)
if AUTO_CREATE_PANEL:
    projectsPanel = ProjectsPanel()
    wm = hiero.ui.windowManager()
    wm.addWindow(projectsPanel)
