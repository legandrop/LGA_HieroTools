"""
____________________________________________________________________

  LGA_NKS_Flow_UpdateThumb v1.06 | Lega

  Reemplaza una imagen de un shot existente en Flow (ShotGrid) con un snapshot
  del viewer actual de Hiero. Dos destinos (TARGETS):
  - "thumbnail": el thumbnail del shot. Click normal del boton "Thumbnail" del
    panel Flow | S3.
  - "slate_frame": el campo File/Link sg_slate_frame del shot, con el frame del
    aPlate que va en el slate de entrega. Boton "Slate Frame" del mismo panel.
    Es otra imagen a proposito: el thumbnail se pisa seguido y el slate frame
    lo elige el coordinador una vez.

  v1.06: Destino nuevo "slate_frame" (sg_slate_frame, solo sitio studio): misma
         captura y misma ventana de comparacion, sube con sg.upload al campo y
         baja el actual con download_attachment. JPG calidad 95. Los textos
         visibles de la ventana pasan a ingles, como pide la regla de UI.

  v1.05: Apaga el VideoTrack BurnIn, espera el refresco del viewer durante la
         captura y restaura el estado original aunque viewer.image() falle.
  v1.04: La ventana lleva la fuente del pack (apply_ui_font); sin
         eso salia con la fuente del host.
  v1.03: ThumbReplaceDialog migra al modulo de estilo LGA_UI_Style_HieroTools:
         Style.WINDOW, Replace en BTN_PRIMARY, Cancel en BTN_SECONDARY y
         tokens en el HTML y en los pozos de imagen.
  v1.02: Los carteles de aviso pasan al helper LGA_NKS_MessageBox con el
         estilo del pack.
  v1.01: La ventana se auto-cierra tras un reemplazo exitoso, con cuenta regresiva
         en el boton Close. Configurable con AUTO_CLOSE_SECONDS (arriba); 0 lo
         desactiva.
  v1.00: Version inicial. Captura el viewer, compara contra el thumbnail actual
         del shot en Flow y lo reemplaza (upload en hilo separado).

  Flujo:
  1. Toma el clip bajo el playhead (fallback a la seleccion).
  2. Captura un snapshot del viewer (zoom to fill, BurnIn deshabilitado, crop al
     aspecto de la secuencia) a un archivo temporal.
  3. project_name y shot_code se extraen del path del clip (segmento VFX-NOMBRE),
     con fallback al nombre del archivo.
  4. Abre una ventana (estetica Create Shot) que muestra el thumbnail actual del
     shot en Flow vs el nuevo snapshot, con botones Replace / Cancel.
  5. Al confirmar, sube el nuevo thumbnail a Flow en un hilo separado.

  Si el shot no existe en Flow, muestra un error y no hace nada.
  El archivo es temporal: se sube a Flow y se borra (no deja copia en disco).
____________________________________________________________________
"""

import os
import sys
import tempfile
import time
import urllib.request
from datetime import datetime
from pathlib import Path

import hiero.core
import hiero.ui

from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui, QtCore, Qt
from LGA_NKS_Shared.LGA_NKS_MessageBox import show_warning
from LGA_NKS_Shared.LGA_UI_Style_HieroTools import Style, Color, apply_ui_font

QApplication = QtWidgets.QApplication
QDialog = QtWidgets.QDialog
QVBoxLayout = QtWidgets.QVBoxLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QLabel = QtWidgets.QLabel
QPushButton = QtWidgets.QPushButton
QFrame = QtWidgets.QFrame
QSizePolicy = QtWidgets.QSizePolicy
QFont = QtGui.QFont
QPixmap = QtGui.QPixmap
QObject = QtCore.QObject
QRunnable = QtCore.QRunnable
QThreadPool = QtCore.QThreadPool
QTimer = QtCore.QTimer
Signal = QtCore.Signal
Slot = QtCore.Slot

# Segundos para el auto-cierre de la ventana tras un reemplazo exitoso.
# Poner 0 (o menos) para desactivar el auto-cierre.
AUTO_CLOSE_SECONDS = 4

# Destinos posibles de la imagen capturada. Los textos son los visibles de la
# ventana (en ingles); jpeg_quality -1 es el default de Qt.
TARGET_THUMBNAIL = "thumbnail"
TARGET_SLATE_FRAME = "slate_frame"
TARGETS = {
    TARGET_THUMBNAIL: {
        "window_title": "Flow | Update Thumbnail",
        "title": "Replace the shot thumbnail in Flow",
        "current_header": "Current in Flow",
        "empty": "No thumbnail",
        "ready": "The current thumbnail will be replaced with the new snapshot.",
        "uploading": "Uploading thumbnail to Flow...",
        "done": "Thumbnail updated in Flow.",
        "upload_failed": "Could not upload the thumbnail to Flow.",
        "jpeg_quality": -1,
        "temp_prefix": "LGA_FlowThumb_",
    },
    TARGET_SLATE_FRAME: {
        "window_title": "Flow | Slate Frame",
        "title": "Replace the delivery slate frame in Flow",
        "current_header": "Current slate frame",
        "empty": "No slate frame",
        "ready": "This frame will be used in the delivery slate of the shot.",
        "uploading": "Uploading slate frame to Flow...",
        "done": "Slate frame updated in Flow.",
        "upload_failed": "Could not upload the slate frame to Flow.",
        # El slate lo muestra grande (38 % del frame): calidad alta.
        "jpeg_quality": 95,
        "temp_prefix": "LGA_FlowSlateFrame_",
        # En un slate de 1920 el thumbnail ocupa el 38 % del ancho (~730 px).
        # Una captura mas chica se ve blanda: se avisa, no se bloquea.
        "min_width": 730,
    },
}

# shotgun_api3 + utilidades compartidas
shared_dir = Path(__file__).parent.parent / "LGA_NKS_Shared"
sys.path.insert(0, str(shared_dir))
# El directorio propio del script: necesario porque el panel lo carga via
# importlib (spec_from_file_location), que no agrega su carpeta a sys.path.
panel_dir = Path(__file__).parent
sys.path.insert(0, str(panel_dir))
import shotgun_api3  # noqa: E402
from SecureConfig_Reader import get_flow_credentials  # noqa: E402
from LGA_NKS_Flow_NamingUtils import (  # noqa: E402
    extract_shot_code,
    extract_project_name,
    extract_project_name_from_path,
    clean_base_name,
)
from LGA_NKS_Shared.LGA_NKS_GetClip import get_clip_to_process  # noqa: E402
from LGA_NKS_Slate_Config import FIELD_SLATE_FRAME  # noqa: E402
from LGA_NKS_Shared.LGA_NKS_ThumbnailCapture import (  # noqa: E402
    BurnInTrackError,
    capture_viewer_image_without_burnin,
)

# Reutilizar los helpers de captura del snapshot del viewer (mismo comportamiento
# que el click normal del boton Thumbnail).
from LGA_NKS_Flow_Thumbs import (  # noqa: E402
    zoom_to_fill_simple,
    crop_to_aspect_ratio,
)


DEBUG = False
LOG_DIR = Path(__file__).parent / "logs"
LOG_PATH = LOG_DIR / "DebugPy_LGA_NKS_Flow_UpdateThumb.log"
_LOG_STARTED_AT = None


def _reset_log():
    global _LOG_STARTED_AT
    _LOG_STARTED_AT = time.monotonic()
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        LOG_PATH.write_text(
            f"Fecha: {datetime.now():%Y-%m-%d %H:%M:%S}\n",
            encoding="utf-8",
        )
    except Exception:
        pass


def debug_print(*message):
    text = " ".join(str(part) for part in message)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        elapsed = time.monotonic() - (_LOG_STARTED_AT or time.monotonic())
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(f"[{elapsed:.3f}s] {text}\n")
    except Exception:
        pass
    if DEBUG:
        print("[UpdateThumb]", text, file=sys.stderr)


# ----------------------------------------------------------------------------
# Captura del snapshot del viewer
# ----------------------------------------------------------------------------
def capture_viewer_snapshot_to_temp(target=TARGET_THUMBNAIL):
    """Captura el viewer actual a un JPG temporal (zoom to fill + crop al aspecto
    de la secuencia, con el track BurnIn deshabilitado temporalmente).

    Returns:
        str | None: ruta del JPG temporal, o None si fallo la captura.
    """
    try:
        viewer = hiero.ui.currentViewer()
        if not viewer:
            debug_print("No hay viewer activo")
            return None

        sequence = hiero.ui.activeSequence()

        def capture_after_track_settles():
            if not zoom_to_fill_simple():
                debug_print("No se pudo aplicar zoom to fill; se captura igualmente")
            debug_print("Esperando 0.5 s con el track BurnIn apagado")
            QApplication.processEvents()
            time.sleep(0.5)
            QApplication.processEvents()
            return viewer.image()

        qimage = capture_viewer_image_without_burnin(
            sequence,
            capture_after_track_settles,
            process_events=QApplication.processEvents,
            logger=debug_print,
        )
        if qimage is None or qimage.isNull():
            debug_print("viewer.image() devolvio None o imagen nula")
            return None

        # Crop al aspecto de la secuencia
        if sequence is None:
            target_aspect = 16 / 9
        else:
            fmt = sequence.format()
            target_aspect = fmt.width() / fmt.height()
        qimage_cropped = crop_to_aspect_ratio(qimage, target_aspect)

        # Guardar a archivo temporal
        config = TARGETS[target]
        fd, temp_path = tempfile.mkstemp(prefix=config["temp_prefix"], suffix=".jpg")
        os.close(fd)
        ok = qimage_cropped.save(temp_path, "JPEG", config["jpeg_quality"])
        if not ok or not os.path.exists(temp_path):
            debug_print("No se pudo guardar el JPG temporal")
            return None
        debug_print(
            f"Snapshot temporal guardado: {temp_path} "
            f"({qimage_cropped.width()}x{qimage_cropped.height()})"
        )
        return temp_path

    except BurnInTrackError as e:
        debug_print(f"Captura cancelada para evitar un thumbnail con burn-in: {e}")
        return None
    except Exception as e:
        debug_print(f"Error capturando snapshot: {e}")
        return None


def get_playhead_clip_info():
    """Obtiene info del clip bajo el playhead (fallback a seleccion).

    Returns:
        dict | None: {file_path, project_name, shot_code} o None.
    """
    sequence = hiero.ui.activeSequence()
    if not sequence:
        debug_print("No hay secuencia activa")
        return None

    clip = get_clip_to_process(track_name=None, prioritize_multiple_selection=False)
    if not clip:
        debug_print("No hay clip en playhead ni seleccionado")
        return None

    try:
        file_path = clip.source().mediaSource().fileinfos()[0].filename()
    except Exception as e:
        debug_print(f"No se pudo obtener file_path del clip: {e}")
        return None

    base_name = clean_base_name(os.path.basename(file_path))
    project_name = extract_project_name_from_path(file_path)
    if not project_name:
        project_name = extract_project_name(base_name)
    shot_code = extract_shot_code(base_name)

    return {
        "file_path": file_path,
        "project_name": project_name,
        "shot_code": shot_code,
    }


# ----------------------------------------------------------------------------
# Flow / ShotGrid
# ----------------------------------------------------------------------------
class FlowThumbManager:
    """Operaciones de ShotGrid necesarias para reemplazar el thumbnail de un shot."""

    def __init__(self, url, login, password):
        try:
            self.sg = shotgun_api3.Shotgun(url, login=login, password=password)
        except Exception as e:
            debug_print(f"Error inicializando conexion a ShotGrid: {e}")
            self.sg = None

    def get_project_id(self, project_name):
        if not self.sg or not project_name:
            return None
        projects = self.sg.find("Project", [["name", "is", project_name]], ["id"])
        return projects[0]["id"] if projects else None

    def find_shot(self, project_name, shot_code, extra_fields=()):
        """Devuelve el shot {id, code, image, *extra_fields} o None si no existe."""
        if not self.sg:
            return None
        project_id = self.get_project_id(project_name)
        if not project_id:
            debug_print(f"Proyecto no encontrado en Flow: {project_name}")
            return None
        filters = [
            ["project", "is", {"type": "Project", "id": project_id}],
            ["code", "is", shot_code],
        ]
        shots = self.sg.find(
            "Shot", filters, ["id", "code", "image"] + list(extra_fields)
        )
        return shots[0] if shots else None

    def upload_thumbnail(self, shot_id, thumbnail_path):
        if not self.sg or not shot_id or not thumbnail_path:
            return False
        if not os.path.exists(thumbnail_path):
            debug_print(f"No existe el archivo a subir: {thumbnail_path}")
            return False
        try:
            self.sg.upload_thumbnail("Shot", shot_id, thumbnail_path)
            return True
        except Exception as e:
            debug_print(f"Error subiendo thumbnail: {e}")
            return False

    def upload_slate_frame(self, shot_id, image_path, shot_code=""):
        """Sube la imagen al campo File/Link del slate frame del shot."""
        if not self.sg or not shot_id or not image_path:
            return False
        if not os.path.exists(image_path):
            debug_print(f"No existe el archivo a subir: {image_path}")
            return False
        try:
            self.sg.upload(
                "Shot",
                shot_id,
                image_path,
                field_name=FIELD_SLATE_FRAME,
                display_name=f"{shot_code or shot_id}_slate_frame.jpg",
            )
            return True
        except Exception as e:
            debug_print(f"Error subiendo slate frame: {e}")
            return False

    def download_slate_frame(self, field_value):
        """Baja el adjunto del campo slate frame a un JPG temporal, o None."""
        if not self.sg or not isinstance(field_value, dict) or not field_value.get("id"):
            return None
        try:
            fd, temp_path = tempfile.mkstemp(prefix="LGA_FlowSlateFrameCur_", suffix=".jpg")
            os.close(fd)
            self.sg.download_attachment(attachment=field_value, file_path=temp_path)
            if os.path.getsize(temp_path) > 0:
                return temp_path
            _safe_remove(temp_path)
            return None
        except Exception as e:
            debug_print(f"No se pudo descargar el slate frame actual: {e}")
            return None


def download_thumbnail(image_url):
    """Descarga la URL del thumbnail actual a un JPG temporal.

    Returns:
        str | None: ruta temporal o None si no hay URL o falla la descarga.
    """
    if not image_url:
        return None
    try:
        fd, temp_path = tempfile.mkstemp(prefix="LGA_FlowThumbCur_", suffix=".jpg")
        os.close(fd)
        with urllib.request.urlopen(image_url, timeout=15) as resp:
            data = resp.read()
        with open(temp_path, "wb") as f:
            f.write(data)
        if os.path.getsize(temp_path) > 0:
            return temp_path
        return None
    except Exception as e:
        debug_print(f"No se pudo descargar el thumbnail actual: {e}")
        return None


def _safe_remove(path):
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except Exception as e:
            debug_print(f"No se pudo borrar temp {path}: {e}")


# ----------------------------------------------------------------------------
# Workers (hilos)
# ----------------------------------------------------------------------------
class LoadSignals(QObject):
    loaded = Signal(object)  # dict: {shot_id, code, current_thumb_path}
    failed = Signal(str)
    debug_output = Signal()


class LoadShotWorker(QRunnable):
    """Conecta a Flow, busca el shot y baja su thumbnail actual (si tiene)."""

    def __init__(self, project_name, shot_code, target=TARGET_THUMBNAIL):
        super(LoadShotWorker, self).__init__()
        self.project_name = project_name
        self.shot_code = shot_code
        self.target = target
        self.signals = LoadSignals()

    @Slot()
    def run(self):
        try:
            url, login, password = get_flow_credentials()
            if not url or not login or not password:
                self.signals.failed.emit("Could not read the Flow credentials.")
                return
            manager = FlowThumbManager(url, login, password)
            if not manager.sg:
                self.signals.failed.emit("Could not connect to Flow.")
                return
            is_slate = self.target == TARGET_SLATE_FRAME
            try:
                shot = manager.find_shot(
                    self.project_name,
                    self.shot_code,
                    extra_fields=(FIELD_SLATE_FRAME,) if is_slate else (),
                )
            except Exception as e:
                debug_print(f"Error buscando el shot: {e}")
                if is_slate and FIELD_SLATE_FRAME in str(e):
                    self.signals.failed.emit(
                        "This Flow site has no Slate Frame field "
                        "(it only exists on the studio site)."
                    )
                else:
                    self.signals.failed.emit(f"Error searching the shot in Flow: {e}")
                return
            if not shot:
                self.signals.failed.emit(
                    f"Shot '{self.shot_code}' does not exist in project "
                    f"'{self.project_name}' in Flow."
                )
                return
            if is_slate:
                current_thumb_path = manager.download_slate_frame(
                    shot.get(FIELD_SLATE_FRAME)
                )
            else:
                current_thumb_path = download_thumbnail(shot.get("image"))
            self.signals.loaded.emit(
                {
                    "shot_id": shot["id"],
                    "code": shot.get("code", self.shot_code),
                    "current_thumb_path": current_thumb_path,
                }
            )
        except Exception as e:
            self.signals.failed.emit(f"Error searching the shot in Flow: {e}")


class UploadSignals(QObject):
    finished = Signal(bool, str)
    debug_output = Signal()


class UploadThumbWorker(QRunnable):
    """Sube el nuevo thumbnail al shot en Flow."""

    def __init__(self, shot_id, thumbnail_path, target=TARGET_THUMBNAIL, shot_code=""):
        super(UploadThumbWorker, self).__init__()
        self.shot_id = shot_id
        self.thumbnail_path = thumbnail_path
        self.target = target
        self.shot_code = shot_code
        self.signals = UploadSignals()

    @Slot()
    def run(self):
        try:
            url, login, password = get_flow_credentials()
            if not url or not login or not password:
                self.signals.finished.emit(False, "Could not read the Flow credentials.")
                return
            manager = FlowThumbManager(url, login, password)
            if not manager.sg:
                self.signals.finished.emit(False, "Could not connect to Flow.")
                return
            config = TARGETS[self.target]
            if self.target == TARGET_SLATE_FRAME:
                ok = manager.upload_slate_frame(
                    self.shot_id, self.thumbnail_path, self.shot_code
                )
            else:
                ok = manager.upload_thumbnail(self.shot_id, self.thumbnail_path)
            debug_print(f"Upload {self.target} shot_id={self.shot_id}: ok={ok}")
            if ok:
                self.signals.finished.emit(True, config["done"])
            else:
                self.signals.finished.emit(False, config["upload_failed"])
        except Exception as e:
            self.signals.finished.emit(False, f"Upload error: {e}")


# ----------------------------------------------------------------------------
# Ventana de comparacion / confirmacion
# ----------------------------------------------------------------------------
THUMB_W = 280


class ThumbReplaceDialog(QDialog):
    def __init__(
        self, project_name, shot_code, new_thumb_path, parent=None, target=TARGET_THUMBNAIL
    ):
        super(ThumbReplaceDialog, self).__init__(parent)
        self.config = TARGETS[target]
        self.project_name = project_name
        self.shot_code = shot_code
        self.new_thumb_path = new_thumb_path
        self.replace_callback = None
        self._uploading = False
        self._countdown_timer = None
        self._countdown_remaining = 0

        self.setWindowTitle(self.config["window_title"])
        self.setModal(False)
        self.setWindowModality(Qt.NonModal)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setMinimumWidth(640)

        layout = QVBoxLayout()
        self.setLayout(layout)

        # Titulo
        title_label = QLabel(self.config["title"])
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet(f"color: {Color.TEXT_STRONG}; padding: 5px;")
        layout.addWidget(title_label)

        # Subtitulo: proyecto / shot
        subtitle = QLabel(
            f"<span style='color: {Color.INFO};'>{project_name}</span> / "
            f"<span style='color: {Color.ENTITY};'>{shot_code}</span>"
        )
        subtitle.setTextFormat(Qt.RichText)
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("padding: 2px 5px 8px 5px;")
        layout.addWidget(subtitle)

        # Fila de imagenes: actual  ->  nuevo
        images_layout = QHBoxLayout()

        images_layout.addStretch()
        images_layout.addLayout(self._build_image_column(self.config["current_header"], is_current=True))

        arrow = QLabel("→")  # flecha
        arrow_font = QFont()
        arrow_font.setPointSize(22)
        arrow_font.setBold(True)
        arrow.setFont(arrow_font)
        arrow.setStyleSheet(f"color: {Color.TEXT}; padding: 0px 12px;")
        arrow.setAlignment(Qt.AlignCenter)
        images_layout.addWidget(arrow)

        images_layout.addLayout(self._build_image_column("New (snapshot)", is_current=False))
        images_layout.addStretch()

        layout.addLayout(images_layout)

        # Cargar la imagen nueva inmediatamente
        self._set_pixmap(self.new_image_label, self.new_thumb_path)

        # Etiqueta de estado/resultado
        self.status_label = QLabel("Searching the shot in Flow...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setTextFormat(Qt.RichText)
        self.status_label.setStyleSheet(f"color: {Color.TEXT}; padding: 8px;")
        layout.addWidget(self.status_label)

        # Botones alineados a la derecha, con el de accion ultimo y en violeta
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.close)
        self.cancel_button.setStyleSheet(Style.BTN_SECONDARY)
        button_layout.addWidget(self.cancel_button)
        button_layout.addSpacing(10)

        self.replace_button = QPushButton("Replace")
        self.replace_button.setEnabled(False)
        self.replace_button.clicked.connect(self._on_replace_clicked)
        self.replace_button.setStyleSheet(Style.BTN_PRIMARY)
        button_layout.addWidget(self.replace_button)
        layout.addLayout(button_layout)

        # Estilo general: la hoja de ventana del pack
        self.setStyleSheet(Style.WINDOW)
        # Fuente del pack al final del armado: recorre los hijos ya creados.
        apply_ui_font(self)

    def _build_image_column(self, header_text, is_current):
        col = QVBoxLayout()
        header = QLabel(header_text)
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet(
            f"color: {Color.TEXT_STRONG}; font-weight: bold; padding: 2px;"
        )
        col.addWidget(header)

        image_label = QLabel("Loading..." if is_current else "")
        image_label.setAlignment(Qt.AlignCenter)
        image_label.setFixedWidth(THUMB_W)
        image_label.setMinimumHeight(int(THUMB_W * 9 / 16))
        image_label.setStyleSheet(
            "background-color: %s; border: 1px solid %s; color: %s;"
            % (Color.SURFACE_SUNKEN, Color.BORDER_STRONG, Color.TEXT_DIM)
        )
        col.addWidget(image_label)

        if is_current:
            self.current_image_label = image_label
        else:
            self.new_image_label = image_label
        return col

    def _set_pixmap(self, label, path):
        if path and os.path.exists(path):
            pix = QPixmap(path)
            if not pix.isNull():
                label.setPixmap(
                    pix.scaledToWidth(THUMB_W, Qt.SmoothTransformation)
                )
                label.setText("")
                return True
        return False

    # --- API publica usada por el orquestador ---
    def set_current_thumb(self, path):
        if not self._set_pixmap(self.current_image_label, path):
            self.current_image_label.setText(self.config["empty"])

    def set_replace_callback(self, callback):
        self.replace_callback = callback

    def show_ready(self):
        self.replace_button.setEnabled(True)
        text = f"<span style='color: {Color.TEXT};'>{self.config['ready']}</span>"
        min_width = self.config.get("min_width")
        if min_width:
            width = QPixmap(self.new_thumb_path).width()
            if 0 < width < min_width:
                text += (
                    f"<br><span style='color: {Color.WARNING_TEXT};'>Low resolution "
                    f"capture ({width} px wide, {min_width} px recommended). Enlarge "
                    f"the viewer for a sharper slate frame.</span>"
                )
        self.status_label.setText(text)

    def show_step(self, message):
        self.status_label.setText(f"<span style='color: {Color.TEXT};'>{message}</span>")

    def show_success(self, message):
        self._uploading = False
        self.status_label.setText(f"<span style='color: {Color.OK_TEXT};'>{message}</span>")
        self.replace_button.setEnabled(False)
        self.cancel_button.setText("Close")
        self._start_auto_close()

    def _start_auto_close(self):
        """Inicia la cuenta regresiva que auto-cierra la ventana."""
        if AUTO_CLOSE_SECONDS <= 0:
            return  # Auto-cierre desactivado
        self._countdown_remaining = AUTO_CLOSE_SECONDS
        self.cancel_button.setText(f"Close ({self._countdown_remaining})")
        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._on_countdown_tick)
        self._countdown_timer.start()

    def _on_countdown_tick(self):
        self._countdown_remaining -= 1
        if self._countdown_remaining <= 0:
            if self._countdown_timer:
                self._countdown_timer.stop()
            self.close()
        else:
            self.cancel_button.setText(f"Close ({self._countdown_remaining})")

    def show_error(self, message):
        self._uploading = False
        self.status_label.setText(f"<span style='color: {Color.ERROR_TEXT};'>{message}</span>")
        self.replace_button.setEnabled(False)
        self.cancel_button.setText("Close")

    def set_uploading(self):
        self._uploading = True
        self.replace_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        self.show_step(self.config["uploading"])

    def _on_replace_clicked(self):
        if self.replace_callback:
            self.replace_callback()

    def closeEvent(self, event):
        # No permitir cerrar mientras se esta subiendo a Flow
        if self._uploading:
            event.ignore()
            return
        # Detener la cuenta regresiva si el usuario cierra manualmente antes de tiempo
        if self._countdown_timer:
            self._countdown_timer.stop()
            self._countdown_timer = None
        event.accept()


# ----------------------------------------------------------------------------
# Orquestacion
# ----------------------------------------------------------------------------
# Referencias globales para evitar que el GC cierre la ventana / cancele el worker
_dialog = None
_load_worker = None
_upload_worker = None
_temp_new_thumb = None
_temp_current_thumb = None
_shot_id = None
_target = TARGET_THUMBNAIL
_shot_code = ""


def _warn(message):
    """Muestra un aviso simple cuando no se puede ni abrir la ventana."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    show_warning(None, TARGETS[_target]["window_title"], message)


def _cleanup_temps():
    global _temp_new_thumb, _temp_current_thumb
    _safe_remove(_temp_new_thumb)
    _safe_remove(_temp_current_thumb)
    _temp_new_thumb = None
    _temp_current_thumb = None


def _on_dialog_finished(_result):
    """Al cerrar la ventana: limpiar temporales e invalidar refs para que los
    callbacks tardios de los workers no actuen sobre una ventana cerrada."""
    global _dialog, _shot_id
    _cleanup_temps()
    _dialog = None
    _shot_id = None


def update_thumbnail_in_flow(target=TARGET_THUMBNAIL):
    """Captura el viewer y abre la ventana de reemplazo de la imagen del shot
    en Flow: el thumbnail (click de Thumbnail) o el slate frame (Slate Frame)."""
    _reset_log()
    debug_print(f"=== Iniciando Update {target} ===")

    global _dialog, _load_worker, _upload_worker
    global _temp_new_thumb, _temp_current_thumb, _shot_id, _target, _shot_code
    _target = target

    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    # 1) Info del clip (playhead-first)
    info = get_playhead_clip_info()
    if not info:
        _warn("No clip under the playhead or selected.")
        return
    if not info["project_name"] or not info["shot_code"]:
        _warn("Could not read the project or the shot from the selected clip.")
        return

    # 2) Capturar snapshot a temp
    _shot_code = info["shot_code"]
    debug_print(
        f"Clip: {info['file_path']} | proyecto={info['project_name']} shot={_shot_code}"
    )
    _temp_new_thumb = capture_viewer_snapshot_to_temp(target)
    if not _temp_new_thumb:
        _warn("Could not capture the viewer snapshot.")
        return

    # 3) Abrir ventana de comparacion
    _shot_id = None
    _temp_current_thumb = None
    _dialog = ThumbReplaceDialog(
        info["project_name"], info["shot_code"], _temp_new_thumb, target=target
    )
    _dialog.finished.connect(_on_dialog_finished)
    _dialog.show()

    # 4) Buscar shot + bajar thumbnail actual en hilo
    _load_worker = LoadShotWorker(info["project_name"], info["shot_code"], target)
    _load_worker.signals.loaded.connect(_on_shot_loaded)
    _load_worker.signals.failed.connect(_on_load_failed)
    QThreadPool.globalInstance().start(_load_worker)


def _on_shot_loaded(data):
    global _shot_id, _temp_current_thumb
    if not _dialog:
        return
    _shot_id = data["shot_id"]
    _temp_current_thumb = data.get("current_thumb_path")
    _dialog.set_current_thumb(_temp_current_thumb)
    _dialog.set_replace_callback(_on_replace_confirmed)
    _dialog.show_ready()


def _on_load_failed(message):
    if _dialog:
        _dialog.set_current_thumb(None)
        _dialog.show_error(message)


def _on_replace_confirmed():
    global _upload_worker
    if not _dialog or not _shot_id or not _temp_new_thumb:
        return
    _dialog.set_uploading()
    _upload_worker = UploadThumbWorker(_shot_id, _temp_new_thumb, _target, _shot_code)
    _upload_worker.signals.finished.connect(_on_upload_finished)
    QThreadPool.globalInstance().start(_upload_worker)


def _on_upload_finished(success, message):
    if not _dialog:
        return
    _dialog.cancel_button.setEnabled(True)
    if success:
        _dialog.show_success(message)
    else:
        _dialog.show_error(message)


def main():
    """Compatibilidad: el panel llama main() para el click normal."""
    update_thumbnail_in_flow()


def main_slate_frame():
    """Boton Slate Frame del panel Flow | S3."""
    update_thumbnail_in_flow(TARGET_SLATE_FRAME)


if __name__ == "__main__":
    main()
