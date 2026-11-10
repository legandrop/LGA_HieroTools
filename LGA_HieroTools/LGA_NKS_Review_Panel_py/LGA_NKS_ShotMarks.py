"""
____________________________________________________________________

  LGA_NKS_ShotMarks v1.13 | Lega

  Shot Marks: lee una planilla de breakdown (xlsx, csv o un link de
  Google Sheets) y pone un tag
  de rango por shot en el timeline activo, en el REC TC de la planilla,
  con el nombre del shot. Viewer > Next Tag / Previous Tag
  (Alt+Shift+Right / Left) salta de shot en shot.

  Existe para cruzar planilla contra corte cada vez que llega un update:
  re-correrla reemplaza solo los tags que puso ella (metadata
  tag.lga_shotmarks), los pinta segun lo que cambio en la planilla y deja
  intactos los tags hechos a mano.

  Timecode: si el timeline es un solo clip de referencia (el MOV del
  episodio), el REC TC se mide contra el TC de esa media, que es el que
  se ve quemado en la imagen; el TC de la secuencia puede venir distinto
  (01:00:00:00 contra 00:59:50:00 de la media). Opcionalmente alinea el
  TC de inicio de la secuencia al de la media. Todo en un solo undo.

  Nucleo sin host (lectura y plan): LGA_NKS_ShotMarks_Sheet.py.
  Descarga desde Google Sheets: LGA_NKS_ShotMarks_Google.py.
  Filas y filtro de la vista previa: LGA_NKS_ShotMarks_Preview.py.
  Log de cada corrida: logs/DebugPy_LGA_NKS_ShotMarks.log.

  v1.13: Una marca por clip. Con un timeline de clips sueltos (edit refs,
         un clip por shot) la seccion Marks ofrece One per clip / From
         timecode: por clip, cada marca toma el largo del clip cuyo nombre
         empieza con el shot, y la planilla no necesita TC. Se sugiere sola
         si la mitad de los clips tiene su shot en la planilla; la linea de
         abajo dice cuantos cruzaron. Las filas sin clip y los clips sin fila
         van a Problems. Columna Group (Grupo) en Mark window columns. El
         mensaje final explica que la ventana de la marca sigue al playhead.
  v1.12: La columna Notes 2 pasa a llamarse Alternative en el dialogo (Budget
         Alternative en la ventana de la marca: el nombre entero no entra en
         el ancho de rotulo de la columna de ajustes).
  v1.11: Dialogo rediseniado: ajustes en una columna a la izquierda y la
         vista previa a la derecha. Switch Google Sheet / File, nombre de
         la planilla (link en el tooltip) y Reload. Solo Shot, TC In y TC
         Out a la vista; las columnas de datos (con Difficulty, nueva)
         plegadas detras de "Mark window: N columns..." y aviso si una
         imprescindible no se encontro por nombre. Numero de marcas,
         leyenda de cambios y filtro All / Changes / Problems. En modo
         thumbnails, grilla con las fotos de la planilla, leidas en un
         hilo. Tooltips propios en vez de los nativos de Qt.
         Columna de ajustes pulida: una grilla de rotulos grises del mismo
         ancho, secciones separadas por una linea, la planilla en una
         tarjeta (nombre, punto de estado, boton de recargar dibujado),
         Mark window columns como fila plegable con su cuenta, y el
         timecode elegido con su inicio y clip en una linea aparte.
         Combos vacios apagados hasta que hay planilla.
  v1.10: El campo de la planilla acepta un link de Google Sheets: se baja
         como xlsx en un hilo (con login de Google la primera vez) a una
         cache local y se lee igual que un Excel. Si no cambio desde la
         ultima vez, no se vuelve a bajar. La marca guarda el titulo de
         Google como origen y los thumbs van a una carpeta con ese titulo.
  v1.09: Las marcas ubicadas desde thumbnails guardan el thumb junto al
         proyecto: se copia a una subcarpeta del .hrox con el nombre de la
         planilla (en un hilo) y el tag lleva la ruta relativa. Antes
         apuntaba a la cache de Locate de esta maquina.
  v1.08: Una roja (shot que ya no esta) que caeria encima de una marca
         nueva no se crea: con una planilla renumerada quedaban cientos de
         tags uno arriba del otro, el nombre viejo sobre el nuevo.
  v1.07: La columna de shot se elige mirando las filas: con "SHOT NAME" y
         "VFX SHOT NAME", la que tiene mas nombres completos, y le gana a
         la columna recordada de la corrida anterior si esa tiene menos.
         Una planilla renumerada dejaba 290 shots sin marcar.
  v1.06: El resumen dice cuantos comentarios de la planilla van a la
         ventana de sus shots y cuantos quedan en otras filas.
  v1.05: Columnas Notes y Notes 2 (se sugieren "Notas" y "Alternativa"):
         van a la ventana de la marca, resaltadas. Los encabezados con
         salto de linea se ven en una linea en los combos. TimelineInfo
         expone media_tc (TC del clip segun NKS) para Locate.
  v1.04: Re-correr compara contra la corrida anterior: cada tag toma el
         color de su cambio (verde igual, amarillo cambio un dato de la
         planilla, naranja nuevo) y los shots que ya no estan o no se
         ubican quedan en rojo en su lugar de antes, hasta la corrida
         siguiente. Columna Change en la vista previa y confirmacion con la
         cuenta antes de borrar. Las keys propias que la corrida no escribe
         se vacian: hiero.core.Tag(nombre) hereda la metadata de un tag que
         ya existio con ese nombre.
  v1.03: Modo thumbnails: campo EDL opcional (se recuerda). El motor lo
         cruza con la imagen y, si coincide, toma de ahi los cortes y el
         clip de camara y SRC TC de cada shot (columna LGA Clip, que
         viaja a la metadata del tag).
  v1.02: Planillas sin timecode: si la hoja no tiene columna de TC pero
         sus filas tienen thumbnail, el boton pasa a "Locate from
         Thumbnails...", que abre LGA_NKS_ShotMarks_Locate (ubica cada
         thumb en el video del timeline y deja revisar). Al volver, el
         dialogo se reabre con los TC ubicados como columnas y sigue igual
         que con una planilla con TC. Los tags guardan el thumb y el nivel
         de confianza.
  v1.01: Columnas de descripcion, escena, vendor y categoria; cada tag
         guarda la info de su fila para Previous/Next Mark
         (LGA_NKS_ShotMarks_Nav).
  v1.00: Version inicial.
____________________________________________________________________
"""

import configparser
import html
import importlib.util
import logging
import math
import os
import re
import sys
import threading
import time
from pathlib import Path

import hiero.core
import hiero.ui

from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtCore, QtGui, QtWidgets, Qt
from LGA_NKS_Shared.LGA_UI_Style_HieroTools import (
    Color,
    Metric,
    Style,
    apply_ui_font,
    emphasis,
    semibold_css,
)
from LGA_NKS_Shared.LGA_NKS_ArrowComboBox import ArrowComboBox
from LGA_NKS_Shared.LGA_UI_CustomTooltip_HieroTools import set_custom_tooltip
from LGA_NKS_Shared.LGA_NKS_MessageBox import (
    ask_question,
    show_error,
    show_info,
    show_warning,
)

DEBUG = False

TAG_KEY = "tag.lga_shotmarks"
TAG_ICON = "icons:Tag.png"
# Al re-correr, cada marca toma el color de su cambio contra la corrida
# anterior. Son los iconos del bin Markers de los Tag Presets de NKS.
CHANGE_ICONS = {
    "unchanged": "icons:TagGreen.png",
    "changed": "icons:TagYellow.png",
    "new": "icons:TagOrange.png",
    "removed": "icons:TagRed.png",
}
# Mismo color que el icono, para el resumen y la tabla: es dato, no estilo.
CHANGE_COLORS = {
    "unchanged": Color.OK_TEXT,
    "changed": Color.WARNING_TEXT,
    "new": "#FFA24D",
    "removed": Color.ERROR_TEXT,
}
CHANGE_LABELS = {
    "unchanged": "unchanged",
    "changed": "changed",
    "new": "new",
    "removed": "no longer in the sheet",
}
# Leyenda de la vista previa: cortos, entran al lado del numero grande.
LEGEND_LABELS = {
    "unchanged": "unchanged",
    "changed": "changed",
    "new": "new",
    "removed": "removed",
}
# Color del resultado de cada fila (result_kind de LGA_NKS_ShotMarks_Preview).
RESULT_COLORS = {
    "ok": Color.OK_TEXT,
    "warning": Color.WARNING_TEXT,
    "error": Color.ERROR_TEXT,
    "dim": Color.TEXT_DIM,
}
FILTER_TEXTS = {"all": "All", "changes": "Changes", "problems": "Problems"}
UNDO_NAME = "Shot Marks from Sheet"
NONE_LABEL = "(none)"
ALL_EPISODES = "All"

# Columnas a la vista (sin shot y TC In no hay plan) y las de datos, plegadas.
REQUIRED_COLUMNS = (("shot", "Shot"), ("tc_in", "TC In"), ("tc_out", "TC Out"))
DATA_COLUMNS = (("episode", "Episode"), ("status", "Status"), ("note", "Brief"),
                ("notes", "Notes"), ("notes2", "Alternative"), ("description", "Description"),
                ("scene", "Scene"), ("vendor", "Vendor"), ("category", "Category"),
                ("group", "Group"), ("difficulty", "Difficulty"))
# Donde va cada marca: en el rango de su clip (timeline de edit refs, un clip
# por shot) o en el REC TC de la planilla (un MOV del corte entero).
PLACE_CLIP, PLACE_TIMECODE = "clip", "timecode"
SIDE_WIDTH = 340
# Columna de ajustes: un solo ancho de rotulo y un solo ritmo vertical para
# todas las secciones, asi los campos arrancan en la misma vertical.
COLUMN_LABEL_WIDTH = 74
ROW_GAP = 8  # entre filas de una seccion
SECTION_GAP = 14  # antes y despues de la linea que separa secciones
# Paginas de la vista previa.
PAGE_MESSAGE, PAGE_PLAN, PAGE_THUMBS = 0, 1, 2
# Grilla de fotos del modo thumbnails: 3 filas de 5; la ultima celda dice
# cuantas quedan afuera.
GRID_COLUMNS = 5
GRID_CELLS = 15
THUMB_SIZE = (128, 72)

CONFIG_FILE_NAME = "ShotMarks.ini"
CONFIG_SECTION = "Settings"

# Tooltips en castellano, separados del widget para que pasar a bilingue sea
# un cambio de datos.
TOOLTIPS = {
    "help": "Pone un tag de rango por cada shot de la planilla en el timeline: en el REC TC "
            "de la planilla, o en el rango de su clip si el timeline tiene un clip por shot.<br>"
            "Viewer &gt; Next Tag (Alt+Shift+Right) salta de shot en shot.<br>"
            "Al volver a correrla reemplaza solo sus tags y los pinta contra la corrida "
            "anterior: verde igual, amarillo cambio, naranja nuevo, rojo ya no esta.",
    "mode_google": "Pegar el link de una planilla de Google Sheets y apretar Enter.<br>"
                   "Se baja con tu cuenta de Google y solo de nuevo si cambio.",
    "mode_file": "Elegir un .xlsx o .csv del disco (Browse) o escribir su ruta.",
    "source_name": "Planilla en uso:<br>%s",
    "reload_google": "Volver a consultar Google: la baja de nuevo solo si cambio.",
    "reload_file": "Volver a leer el archivo.",
    "data": "Columnas que van a la ventana de cada marca: episodio, status, brief, notas, "
            "descripcion, escena, vendor, categoria y dificultad.<br>"
            "Casi siempre se detectan solas.",
    "filter_all": "Todas las filas del plan.",
    "filter_changes": "Solo lo que cambio contra la corrida anterior: amarillas, naranjas y "
                      "rojas.",
    "filter_problems": "Solo las filas que no se escriben, las que se escriben con aviso y "
                       "las rojas que siguen en la planilla pero no se ubicaron.",
    "browse": "Elegir la planilla (.xlsx o .csv).",
    "source": "Planilla: un .xlsx o .csv (Browse), o pegar el link de una planilla de Google "
              "Sheets y apretar Enter. La de Google se baja con tu cuenta y solo de nuevo si "
              "cambio.",
    "sheet": "Hoja de la planilla. Se sugiere la que tiene columnas de shot y REC TC.",
    "shot": "Columna con el nombre del shot: es el nombre del tag.",
    "tc_in": "Timecode de entrada del shot en el montaje (REC TC IN, no el TC de camara).",
    "tc_out": "Timecode de salida. Es exclusivo: el tag termina un cuadro antes.",
    "episode": "Columna de episodio, para filtrar los shots de este timeline.",
    "status": "Columna de status, para saltear los Omit.",
    "note": "Columna del brief: va a la nota del tag y a la ventana de Next Mark.",
    "description": "Descripcion del shot, para la ventana de Next Mark.",
    "scene": "Escena, para la ventana de Next Mark.",
    "vendor": "Vendor, para la ventana de Next Mark.",
    "category": "Categoria del shot, para la ventana de Next Mark. Se sugiere Category o VFX Type.",
    "group": "Grupo del shot (bloque, set o personaje), para la ventana de Next Mark.<br>"
             "Se sugiere la columna Grupo.",
    "place_clip": "Una marca por clip, con el largo del clip.<br>"
                  "El clip es del shot si su nombre (o el de su archivo) empieza con el shot: "
                  "PROJA_010_0100_EditRef.",
    "place_timecode": "Las marcas van en el REC TC de la planilla, como con el MOV del corte "
                      "entero.",
    "notes": "Notas del shot: la ventana de Next Mark las resalta. Se sugiere la columna Notas.",
    "notes2": "Alternativa para bajar el presupuesto del shot (que dejar de hacer o como\n"
              "hacerlo de otra forma). Se sugiere la columna Alternativa.",
    "episode_filter": "Solo los shots de este episodio. Se sugiere el que aparece en el nombre del timeline.",
    "skip_omit": "No marcar los shots con status Omit.",
    "reference": "Contra que timecode se mide el REC TC de la planilla.",
    "difficulty": "Dificultad del shot: la ventana de la marca la muestra con su color. Se "
                  "sugiere la columna Dificultad.",
    "align": "Cambia el TC de inicio del timeline al de la media, para que el timeline muestre "
             "el mismo TC que la imagen.<br>Ahora empieza en %s. Se puede deshacer.",
    "locate": "Buscar el thumbnail de cada shot en el video del timeline y revisar los dudosos.",
    "edl": "EDL del mismo armado que el video. Opcional: da los cortes exactos (la deteccion por "
           "imagen pierde cortes entre planos parecidos) y el clip de camara y SRC TC de cada shot.",
    "edl_browse": "Elegir el EDL del armado (.edl).",
    "edl_clear": "No usar EDL: los cortes se detectan en la imagen.",
}

_sheet = None
_locate = None
_thumbs = None
_google = None
_preview = None


def _preview_module():
    global _preview
    if _preview is None:
        _preview = _module("LGA_NKS_ShotMarks_Preview")
    return _preview


def _escape(text):
    """Texto de datos (nombres, rutas, links, errores) dentro de rich text."""
    return html.escape(str(text or ""), quote=False)


_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _short_stamp(stamp):
    """'Nov 3, 10:42': entra en una linea de la tarjeta de la fuente. Los
    meses van escritos aca y no con %b, que sale en el idioma del sistema."""
    return "%s %d, %s" % (_MONTHS[stamp.month - 1], stamp.day, stamp.strftime("%H:%M"))


def _file_changed(path):
    """' · Changed Nov 3, 10:42' de un archivo local, o '' si no se puede leer."""
    import datetime
    try:
        stamp = datetime.datetime.fromtimestamp(os.path.getmtime(path))
    except Exception:
        return ""
    return " &middot; Changed %s" % _short_stamp(stamp)


def _module(name):
    path = Path(__file__).resolve().parent / (name + ".py")
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _locate_module():
    global _locate
    if _locate is None:
        _locate = _module("LGA_NKS_ShotMarks_Locate")
    return _locate


def _thumbs_module():
    global _thumbs
    if _thumbs is None:
        _thumbs = _module("LGA_NKS_ShotMarks_Thumbs")
    return _thumbs


def _google_module():
    global _google
    if _google is None:
        _google = _module("LGA_NKS_ShotMarks_Google")
    return _google


def _local_time(iso_utc):
    """'2026-11-04T00:02:41.414Z' -> 'Nov 3, 21:02' en la hora local."""
    import datetime
    try:
        stamp = datetime.datetime.strptime(iso_utc[:19], "%Y-%m-%dT%H:%M:%S")
        stamp = stamp.replace(tzinfo=datetime.timezone.utc).astimezone()
        return _short_stamp(stamp)
    except Exception:
        return iso_utc or "?"


def _sheet_module():
    """Carga LGA_NKS_ShotMarks_Sheet desde la carpeta de este script."""
    global _sheet
    if _sheet is None:
        path = Path(__file__).resolve().parent / "LGA_NKS_ShotMarks_Sheet.py"
        spec = importlib.util.spec_from_file_location("LGA_NKS_ShotMarks_Sheet", str(path))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _sheet = module
    return _sheet


# -- log y preferencias ----------------------------------------------------

def _logger():
    log_dir = Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(exist_ok=True)
    logger = logging.getLogger("LGA_NKS_ShotMarks")
    logger.setLevel(logging.DEBUG)
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
    logger.propagate = False
    handler = logging.FileHandler(str(log_dir / "DebugPy_LGA_NKS_ShotMarks.log"),
                                  mode="w", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    if DEBUG:
        logger.addHandler(logging.StreamHandler())
    return logger


def log_path():
    return str(Path(__file__).resolve().parent / "logs" / "DebugPy_LGA_NKS_ShotMarks.log")


def _config_path():
    if sys.platform == "win32":
        root = os.getenv("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        root = str(Path.home() / "Library" / "Application Support")
    else:
        root = str(Path.home() / ".config")
    return Path(root) / "LGA" / "HieroTools" / CONFIG_FILE_NAME


def _read_settings():
    config = configparser.ConfigParser()
    try:
        config.read(str(_config_path()), encoding="utf-8")
    except Exception:
        return {}
    return dict(config[CONFIG_SECTION]) if config.has_section(CONFIG_SECTION) else {}


def _write_settings(values):
    path = _config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        config = configparser.ConfigParser()
        config[CONFIG_SECTION] = {k: str(v) for k, v in values.items()}
        with open(str(path), "w", encoding="utf-8", newline="\n") as handle:
            config.write(handle)
    except Exception as exc:
        _logger_ref().warning("No se pudieron guardar las preferencias: %s", exc)


_log = None


def _logger_ref():
    global _log
    if _log is None:
        _log = _logger()
    return _log


# -- timeline --------------------------------------------------------------

class TimelineInfo(object):
    """Lo que hace falta del timeline para ubicar los timecodes."""

    def __init__(self, sequence):
        self.sequence = sequence
        rate = sequence.framerate()
        self.fps_float = float(rate.toFloat())
        self.fps = int(round(self.fps_float))
        self.start = int(sequence.timecodeStart())
        self.duration = int(sequence.duration())
        self.media_start = None
        # TC del cuadro 0 del archivo segun NKS (no segun ffprobe).
        self.media_tc = None
        self.media_clip = ""
        self.media_reason = ""
        # Clips habilitados del timeline, para marcar uno por clip.
        self.clips = []
        self._detect_reference()
        self._collect_clips()

    def _collect_clips(self):
        """[{name, file, frame_in, frame_out, src_in, src_out, event}] en orden de
        timeline. frame_out es inclusivo (timelineOut de Hiero); el SRC TC OUT va
        exclusivo, como en un EDL."""
        fmt = _sheet_module().format_timecode
        clips = []
        for track in self.sequence.videoTracks():
            if not track.isEnabled():
                continue
            for item in track.items():
                try:
                    if not item.isEnabled():
                        continue
                    clip = item.source()
                    try:
                        path = clip.mediaSource().fileinfos()[0].filename()
                    except Exception:
                        path = ""
                    tc = int(clip.timecodeStart())
                    clips.append({
                        "name": item.name(), "file": path,
                        "frame_in": int(item.timelineIn()), "frame_out": int(item.timelineOut()),
                        "src_in": fmt(tc + int(round(item.sourceIn())), self.fps),
                        "src_out": fmt(tc + int(round(item.sourceOut())) + 1, self.fps),
                        "event": "%s %s" % (_sheet_module().CLIP_EVENT_PREFIX, track.name()),
                    })
                except Exception as exc:
                    _logger_ref().warning("Clip del timeline ilegible: %s", exc)
        clips.sort(key=lambda c: (c["frame_in"], c["frame_out"]))
        self.clips = clips

    def _detect_reference(self):
        items = []
        for track in self.sequence.videoTracks():
            if track.isEnabled():
                items.extend(track.items())
        if len(items) != 1:
            self.media_reason = "%d video clips: timeline timecode is used" % len(items)
            return
        item = items[0]
        try:
            speed = float(item.playbackSpeed())
        except Exception:
            speed = 1.0
        if abs(speed - 1.0) > 1e-6:
            self.media_reason = "The clip is retimed: timeline timecode is used"
            return
        clip = item.source()
        # TC de la media en el cuadro 0 del timeline.
        self.media_tc = int(clip.timecodeStart())
        self.media_start = (self.media_tc + int(round(item.sourceIn()))
                            - int(item.timelineIn()))
        self.media_clip = clip.name()

    def timecode(self, frames):
        return _sheet_module().format_timecode(frames, self.fps)


def own_tags(sequence):
    tags = []
    for tag in sequence.tags():
        try:
            if tag.metadata().hasKey(TAG_KEY):
                tags.append(tag)
        except Exception:
            continue
    return tags


def previous_marks(sequence):
    """Los tags propios de la corrida anterior, listos para compare_marks.

    Cada uno lleva ademas su metadata de Shot Marks y su nota: si el shot ya
    no esta en la planilla, la marca se vuelve a crear igual, en rojo.
    """
    module = _sheet_module()
    marks = []
    for tag in own_tags(sequence):
        data = tag.metadata()

        def get(key, data=data):
            return data.value(key) if data.hasKey(key) else None

        mark = module.previous_mark(tag.name(), tag.inTime(), tag.outTime(), get, tag.note())
        mark["note"] = tag.note()
        mark["metadata"] = {}
        for field in (None,) + module.META_FIELDS:
            key = module.META_KEY if field is None else module.meta_key(field)
            if data.hasKey(key):
                mark["metadata"][key] = str(data.value(key))
        marks.append(mark)
    return marks


def _add_tag(sequence, name, note, icon, metadata, frame_in, frame_out):
    tag = hiero.core.Tag(name, icon)
    tag.setNote(note)
    data = tag.metadata()
    # hiero.core.Tag(nombre) nace con la metadata de un tag que ya existio con
    # ese nombre (medido en NKS 16: la marca recreada traia el prev_brief de
    # dos corridas antes). DataCollection no tiene removeKey: lo propio que
    # esta corrida no escribe se vacia, o un status borrado en la planilla
    # seguiria apareciendo.
    for key in data.keys():
        if key.startswith(TAG_KEY) and key not in metadata:
            data.setValue(key, "")
    for key, value in metadata.items():
        data.setValue(key, value)
    sequence.addTagToRange(tag, int(frame_in), int(frame_out))


def apply_plan(sequence, plan, align_start=None, source_label="", removed=()):
    """Reemplaza los tags propios por los del plan, en un solo undo.

    Cada marca va con el icono de su cambio contra la corrida anterior
    (mark.change; sin corrida anterior, el icono comun). `removed` son las
    marcas anteriores cuyo shot ya no esta: se vuelven a crear en rojo en su
    lugar de antes, para que se vea que se fueron.
    """
    log = _logger_ref()
    project = sequence.project()
    replaced = 0
    module = _sheet_module()
    with project.beginUndo(UNDO_NAME):
        for tag in own_tags(sequence):
            sequence.removeTag(tag)
            replaced += 1
        if align_start is not None and align_start != sequence.timecodeStart():
            log.info("TC de inicio del timeline: %s -> %s", sequence.timecodeStart(), align_start)
            sequence.setTimecodeStart(int(align_start))
        for mark in plan.marks:
            _add_tag(sequence, mark.shot, mark.note, CHANGE_ICONS.get(mark.change, TAG_ICON),
                     module.mark_metadata(mark, source_label), mark.frame_in, mark.frame_out)
        for old in removed:
            metadata = dict(old["metadata"])
            metadata[module.META_KEY] = "1"
            metadata[module.meta_key("change")] = module.CHANGE_REMOVED
            if old.get("reason"):
                metadata[module.meta_key("change_reason")] = old["reason"]
            _add_tag(sequence, old["shot"], old["note"], CHANGE_ICONS["removed"], metadata,
                     old["frame_in"], old["frame_out"])
    log.info("Aplicado: %d tags nuevos, %d en rojo (ya no estan), %d tags propios anteriores "
             "reemplazados", len(plan.marks), len(removed), replaced)
    for mark in plan.marks:
        changed = ", ".join(sorted(mark.changed))
        log.info("  %-28s %6d-%-6d  TC %s  fila %d  %s%s", mark.shot, mark.frame_in,
                 mark.frame_out, mark.tc_in, mark.row, mark.change or "-",
                 " (%s)" % changed if changed else "")
    for old in removed:
        log.info("  %-28s %6d-%-6d  removed%s", old["shot"], old["frame_in"], old["frame_out"],
                 " (%s)" % old["reason"] if old.get("reason") else "")
    return replaced


def _copy_thumbs_later(project_dir, copies):
    """Copia los thumbs fuera del hilo de UI: a una unidad de red son segundos.
    Mientras tanto la ventana de la marca los encuentra en la cache de Locate."""
    module = _sheet_module()
    log = _logger_ref()

    def run():
        copied, errors = module.copy_thumbs(copies, project_dir)
        log.info("Thumbs en %s: %d copiados, %d ya estaban, %d errores", project_dir, copied,
                 len(copies) - copied - len(errors), len(errors))
        for error in errors[:20]:
            log.warning("  No se copio %s", error)

    threading.Thread(target=run, name="LGA_ShotMarks_Thumbs", daemon=True).start()


def guess_episode(sequence_name, episodes):
    """El episodio que aparece como numero suelto en el nombre del timeline."""
    found = [ep for ep in episodes
             if ep and re.search(r"(?<![0-9])%s(?![0-9])" % re.escape(ep), sequence_name)]
    return found[0] if len(found) == 1 else None


# -- hilo de lectura -------------------------------------------------------

class _Signals(QtCore.QObject):
    done = QtCore.Signal(object, object, object)  # (token, resultado, error)


class _Job(QtCore.QRunnable):
    """Corre una funcion de lectura fuera del hilo de UI."""

    def __init__(self, func, signals, token):
        super(_Job, self).__init__()
        self.func = func
        self.signals = signals
        self.token = token

    def run(self):
        try:
            result = self.func()
        except Exception as exc:
            self.signals.done.emit(self.token, None, exc)
            return
        self.signals.done.emit(self.token, result, None)


# -- dialogo ---------------------------------------------------------------

def _section_label(text):
    """Rotulo de seccion de la columna de ajustes: como las pestanas del pack."""
    label = QtWidgets.QLabel(text.upper())
    label.setStyleSheet("QLabel { color: %s; %s letter-spacing: 1px; }"
                        % (Color.TEXT_DIM, semibold_css()))
    label.setProperty("lgaSection", True)
    return label


def _field_label(text):
    """Rotulo de un campo de la columna de ajustes: gris, para que el valor
    del campo sea lo que se lee primero."""
    label = QtWidgets.QLabel(text)
    label.setFixedWidth(COLUMN_LABEL_WIDTH)
    label.setStyleSheet("QLabel { color: %s; }" % Color.TEXT_DIM)
    return label


def _form_grid():
    grid = QtWidgets.QGridLayout()
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(Metric.SPACING)
    grid.setVerticalSpacing(ROW_GAP)
    grid.setColumnStretch(1, 1)
    return grid


def _hline():
    line = QtWidgets.QFrame()
    line.setObjectName("shotMarksRule")
    line.setAttribute(Qt.WA_StyledBackground, True)
    line.setFixedHeight(1)
    line.setStyleSheet("#shotMarksRule { background-color: %s; }" % Color.BORDER)
    return line


class _ElidedLabel(QtWidgets.QLabel):
    """Texto de una linea que se corta con ... en el medio si no entra: el
    nombre de un clip de 60 caracteres en una columna de 340 px."""

    def __init__(self, parent=None):
        super(_ElidedLabel, self).__init__(parent)
        self._full = ""
        self.setMinimumWidth(1)
        self.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)

    def set_full_text(self, text):
        self._full = text
        self._elide()

    def resizeEvent(self, event):
        super(_ElidedLabel, self).resizeEvent(event)
        self._elide()

    def _elide(self):
        metrics = QtGui.QFontMetrics(self.font())
        self.setText(metrics.elidedText(self._full, Qt.ElideRight, max(self.width(), 1)))


class _ReloadButton(QtWidgets.QAbstractButton):
    """Boton cuadrado con la flecha circular de recargar, dibujada a mano:
    el pack no trae iconos y un 'Reload' de texto pesaba mas que el nombre
    de la planilla al lado."""

    SIZE = 26

    def __init__(self, parent=None):
        super(_ReloadButton, self).__init__(parent)
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)

    def enterEvent(self, event):
        super(_ReloadButton, self).enterEvent(event)
        self.update()

    def leaveEvent(self, event):
        super(_ReloadButton, self).leaveEvent(event)
        self.update()

    def paintEvent(self, _event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        hover = self.isEnabled() and self.underMouse()
        if hover:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QtGui.QColor(Color.SURFACE_HOVER))
            painter.drawRoundedRect(QtCore.QRectF(self.rect()), Metric.RADIUS_SMALL,
                                    Metric.RADIUS_SMALL)
        color = (Color.TEXT_STRONG if hover else Color.TEXT_HEADER) if self.isEnabled() \
            else Color.BORDER_HOVER
        pen = QtGui.QPen(QtGui.QColor(color), 1.5)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        center = QtCore.QPointF(self.width() / 2.0, self.height() / 2.0)
        radius = 5.5
        box = QtCore.QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2)
        # Arco en sentido horario de 100 a -200 grados; la punta va al final.
        start, span = 100.0, -300.0
        path = QtGui.QPainterPath()
        path.arcMoveTo(box, start)
        path.arcTo(box, start, span)
        painter.drawPath(path)
        end = math.radians(start + span)
        tip = QtCore.QPointF(center.x() + radius * math.cos(end),
                             center.y() - radius * math.sin(end))
        # Direccion de avance horario en pantalla: (sen, cos) del angulo.
        heading = math.atan2(math.cos(end), math.sin(end))
        for turn in (math.radians(150), math.radians(-150)):
            angle = heading + turn
            painter.drawLine(tip, QtCore.QPointF(tip.x() + 3.4 * math.cos(angle),
                                                 tip.y() + 3.4 * math.sin(angle)))
        painter.end()


class _Disclosure(QtWidgets.QAbstractButton):
    """Fila plegable: chevron, texto y una cuenta a la derecha. Abre las
    columnas de datos sin sumar otro boton con caja a la columna."""

    HEIGHT = 28

    def __init__(self, text, parent=None):
        super(_Disclosure, self).__init__(parent)
        self.setText(text)
        self.setCheckable(True)
        self.setFixedHeight(self.HEIGHT)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.count_text = ""

    def set_count(self, text):
        self.count_text = text
        self.update()

    def sizeHint(self):
        return QtCore.QSize(200, self.HEIGHT)

    def enterEvent(self, event):
        super(_Disclosure, self).enterEvent(event)
        self.update()

    def leaveEvent(self, event):
        super(_Disclosure, self).leaveEvent(event)
        self.update()

    def paintEvent(self, _event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = QtCore.QRectF(self.rect())
        hover = self.underMouse()
        if hover:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QtGui.QColor(Color.SURFACE_HOVER))
            painter.drawRoundedRect(rect, Metric.RADIUS_SMALL, Metric.RADIUS_SMALL)
        pen = QtGui.QPen(QtGui.QColor(Color.TEXT_STRONG if hover else Color.TEXT_HEADER), 1.5)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        cx, cy = 7.0, rect.center().y() + 0.5
        if self.isChecked():
            points = [(cx - 4, cy - 2), (cx, cy + 2), (cx + 4, cy - 2)]
        else:
            points = [(cx - 2, cy - 4), (cx + 2, cy), (cx - 2, cy + 4)]
        painter.drawPolyline(QtGui.QPolygonF([QtCore.QPointF(x, y) for x, y in points]))
        text_rect = rect.adjusted(20, 0, -8, 0)
        painter.setFont(self.font())
        painter.setPen(QtGui.QColor(Color.TEXT_STRONG if hover else Color.TEXT))
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.text())
        painter.setPen(QtGui.QColor(Color.TEXT_DIM))
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignRight, self.count_text)
        painter.end()


class _PillSwitch(QtWidgets.QWidget):
    """Switch segmentado del pack (Style.PILL_*): una sola eleccion visible."""

    def __init__(self, options, on_pick, parent=None):
        super(_PillSwitch, self).__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(Style.PILL_CONTAINER_SUNKEN)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)
        self.buttons = {}
        self.current = None
        for key, text, tip in options:
            button = QtWidgets.QPushButton(text)
            button.setFixedHeight(22)
            button.setFocusPolicy(Qt.NoFocus)
            set_custom_tooltip(button, tip)
            button.clicked.connect(lambda _checked=False, key=key: on_pick(key))
            layout.addWidget(button)
            self.buttons[key] = button

    def select(self, key):
        self.current = key
        for name, button in self.buttons.items():
            button.setStyleSheet(Style.PILL_ACTIVE if name == key else Style.PILL_INACTIVE)


class ShotMarksDialog(QtWidgets.QDialog):
    """Columna de ajustes a la izquierda y vista previa a la derecha.

    La vista previa es lo que se mira: que marcas se van a escribir y cuales
    cambiaron o tienen problemas. Los ajustes que casi siempre salen bien
    solos (las columnas de datos) quedan plegados.
    """

    def __init__(self, sequence, parent=None, preset=None):
        super(ShotMarksDialog, self).__init__(parent)
        self.sequence = sequence
        self.timeline = TimelineInfo(sequence)
        self.settings = _read_settings()
        # preset: tabla ya ubicada desde los thumbnails {path, sheet, table}.
        self.preset = preset
        # La fuente (ruta o link de Google) se muestra por su nombre; la
        # lectura usa local_path, que para Google es la copia en la cache.
        self.source = ""
        self.local_path = ""
        self.google = None  # {path, title, modified, downloaded, stale}
        self.table = None
        self.plan = None
        # Marcas de la corrida anterior y las que ya no estan en la planilla.
        self.previous = previous_marks(sequence)
        self.removed = []
        # Donde van las marcas: por clip o por timecode. Se sugiere al leer la
        # hoja (por clip si la mitad de los clips tiene su shot en la planilla)
        # hasta que el usuario elige con el switch.
        self.place_mode = PLACE_TIMECODE
        self._place_picked = False
        self.clip_report = None
        self.no_timecode = False
        # Hoja sin TC con thumbnails: el boton principal pasa a ubicarlos.
        self.thumb_mode = False
        self.thumb_rows = 0
        self.thumb_row_list = []
        self._grid_shown = []
        self._grid_more = 0
        # Filas de la vista previa (LGA_NKS_ShotMarks_Preview) y su filtro.
        self.entries = []
        self.filter_mode = _preview_module().FILTER_ALL
        # Columnas imprescindibles que no se encontraron por nombre.
        self._undetected = set()
        self._keep_sheet = None
        self._jobs = {}
        self._token = 0
        self._loading = False
        self._busy_started = None
        self._busy_text = ("", "")
        self._busy_timer = QtCore.QTimer(self)
        self._busy_timer.setInterval(1000)
        self._busy_timer.timeout.connect(self._tick_busy)
        self.setWindowTitle("Shot Marks from Sheet")
        self.setStyleSheet(Style.FORM)
        self.setMinimumSize(980, 600)
        self._build()
        apply_ui_font(self)
        for label in self.findChildren(QtWidgets.QLabel):
            if label.property("lgaSection"):
                apply_ui_font(label, size=Metric.TAB_FONT_SIZE)
        self.resize(1120, 740)
        self._restore()

    # armado
    def _build(self):
        outer = QtWidgets.QVBoxLayout(self)
        margin = Metric.WINDOW_MARGIN
        outer.setContentsMargins(0, 0, 0, margin)
        outer.setSpacing(0)
        body = QtWidgets.QHBoxLayout()
        body.setSpacing(0)
        outer.addLayout(body, 1)
        body.addWidget(self._build_side())
        line = QtWidgets.QFrame()
        line.setObjectName("shotMarksSideLine")
        line.setAttribute(Qt.WA_StyledBackground, True)
        line.setFixedWidth(1)
        line.setStyleSheet("#shotMarksSideLine { background-color: %s; }" % Color.BORDER)
        body.addWidget(line)
        body.addWidget(self._build_preview(), 1)

        buttons = QtWidgets.QHBoxLayout()
        buttons.setContentsMargins(margin + 4, 14, margin + 4, 0)
        buttons.setSpacing(Metric.SPACING)
        buttons.addStretch(1)
        cancel = QtWidgets.QPushButton("Cancel")
        cancel.setStyleSheet(Style.BTN_SECONDARY)
        cancel.setFixedHeight(Metric.BUTTON_HEIGHT)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        self.apply_button = QtWidgets.QPushButton("Add Marks")
        self.apply_button.setStyleSheet(Style.BTN_PRIMARY)
        self.apply_button.setFixedHeight(Metric.BUTTON_HEIGHT)
        self.apply_button.setDefault(True)
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self._apply)
        buttons.addWidget(self.apply_button)
        outer.addLayout(buttons)
        self._reference_changed()

    def _build_side(self):
        """Columna de ajustes: fuente, columnas imprescindibles y timeline.

        Una sola grilla de rotulo + campo por seccion (rotulos grises de un
        mismo ancho), secciones separadas por una linea y el mismo aire
        arriba y abajo de cada una.
        """
        margin = Metric.WINDOW_MARGIN
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFixedWidth(SIDE_WIDTH)
        scroll.setStyleSheet(Style.SCROLLBAR)
        side = QtWidgets.QWidget()
        scroll.setWidget(side)
        lay = QtWidgets.QVBoxLayout(side)
        lay.setContentsMargins(margin + 4, margin + 2, margin + 2, 4)
        lay.setSpacing(0)

        title = QtWidgets.QLabel("Shot Marks from Sheet")
        title.setProperty("lgaTitle", True)
        help_button = QtWidgets.QPushButton("?")
        help_button.setStyleSheet(Style.BTN_ICON)
        help_button.setFixedSize(Metric.CLOSE_BUTTON_SIZE, Metric.CLOSE_BUTTON_SIZE)
        help_button.setFocusPolicy(Qt.NoFocus)
        set_custom_tooltip(help_button, TOOLTIPS["help"])
        head = QtWidgets.QHBoxLayout()
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(help_button)
        lay.addLayout(head)
        lay.addSpacing(4)
        timeline = QtWidgets.QLabel(_colored("Range tags on ", Color.TEXT_DIM)
                                    + emphasis(self.sequence.name()))
        timeline.setTextFormat(Qt.RichText)
        timeline.setWordWrap(True)
        lay.addWidget(timeline)
        self._section(lay, "Source", first=True)

        # --- fuente -----------------------------------------------------------
        self.source_switch = _PillSwitch(
            (("google", "Google Sheet", TOOLTIPS["mode_google"]),
             ("file", "File", TOOLTIPS["mode_file"])), self._set_source_mode)
        self._section_head.addWidget(self.source_switch)

        # Tarjeta de la planilla en uso: nombre (link o ruta en el tooltip),
        # estado con un punto de color y el boton de recargar.
        card = QtWidgets.QFrame()
        card.setObjectName("shotMarksSourceCard")
        card.setAttribute(Qt.WA_StyledBackground, True)
        card.setStyleSheet("#shotMarksSourceCard { background-color: %s; border: 1px solid %s;"
                           " border-radius: %dpx; }"
                           % (Color.SURFACE, Color.BORDER, Metric.RADIUS_FIELD))
        card_lay = QtWidgets.QGridLayout(card)
        card_lay.setContentsMargins(12, 9, 6, 9)
        card_lay.setHorizontalSpacing(6)
        card_lay.setVerticalSpacing(2)
        self.source_name = _ElidedLabel()
        self.source_name.setStyleSheet("QLabel { color: %s; %s }"
                                       % (Color.TEXT_STRONG, semibold_css()))
        card_lay.addWidget(self.source_name, 0, 0)
        self.source_note = QtWidgets.QLabel("")
        self.source_note.setTextFormat(Qt.RichText)
        self.source_note.setVisible(False)
        card_lay.addWidget(self.source_note, 1, 0)
        self.reload_button = _ReloadButton()
        set_custom_tooltip(self.reload_button, TOOLTIPS["reload_file"])
        self.reload_button.clicked.connect(self._reload)
        card_lay.addWidget(self.reload_button, 0, 1, 2, 1, Qt.AlignVCenter)
        card_lay.setColumnStretch(0, 1)
        lay.addWidget(card)
        lay.addSpacing(ROW_GAP)

        self.path_edit = QtWidgets.QLineEdit()
        self.path_edit.setFixedHeight(Metric.BUTTON_HEIGHT)
        set_custom_tooltip(self.path_edit, TOOLTIPS["source"])
        self.path_edit.editingFinished.connect(self._path_entered)
        browse = self.browse_button = QtWidgets.QPushButton("Browse")
        browse.setStyleSheet(Style.BTN_SECONDARY)
        browse.setFixedHeight(Metric.BUTTON_HEIGHT)
        set_custom_tooltip(browse, TOOLTIPS["browse"])
        browse.clicked.connect(self._browse)
        self.input_row = QtWidgets.QWidget()
        input_lay = QtWidgets.QVBoxLayout(self.input_row)
        input_lay.setContentsMargins(0, 0, 0, ROW_GAP)
        input_lay.setSpacing(4)
        field = QtWidgets.QHBoxLayout()
        field.setSpacing(Metric.SPACING)
        field.addWidget(self.path_edit, 1)
        field.addWidget(browse)
        input_lay.addLayout(field)
        # Lo que se escribio y no sirve (no es planilla ni link de Google).
        self.input_note = QtWidgets.QLabel("")
        self.input_note.setWordWrap(True)
        self.input_note.setStyleSheet("QLabel { color: %s; }" % Color.ERROR_TEXT)
        self.input_note.setVisible(False)
        input_lay.addWidget(self.input_note)
        lay.addWidget(self.input_row)

        grid = _form_grid()
        self.sheet_combo = self._combo("sheet")
        self.sheet_combo.currentIndexChanged.connect(self._sheet_changed)
        grid.addWidget(_field_label("Sheet"), 0, 0)
        grid.addWidget(self.sheet_combo, 0, 1)
        lay.addLayout(grid)

        # --- donde van las marcas (solo con dos clips o mas) --------------------
        self.place_box = QtWidgets.QWidget()
        place_lay = QtWidgets.QVBoxLayout(self.place_box)
        place_lay.setContentsMargins(0, 0, 0, 0)
        place_lay.setSpacing(0)
        self._section(place_lay, "Marks")
        self.place_switch = _PillSwitch(
            ((PLACE_CLIP, "One per clip", TOOLTIPS["place_clip"]),
             (PLACE_TIMECODE, "From timecode", TOOLTIPS["place_timecode"])), self._pick_place)
        self._section_head.addWidget(self.place_switch)
        self.place_note = QtWidgets.QLabel("")
        self.place_note.setTextFormat(Qt.RichText)
        self.place_note.setWordWrap(True)
        place_lay.addWidget(self.place_note)
        self.place_switch.select(self.place_mode)
        self.place_box.setVisible(len(self.timeline.clips) > 1 and not self.preset)
        lay.addWidget(self.place_box)
        self._section(lay, "Columns")

        # --- columnas ---------------------------------------------------------
        self.column_combos = {}
        self.column_labels = {}
        required = _form_grid()
        for row, (role, label) in enumerate(REQUIRED_COLUMNS):
            required.addWidget(self._column_label(role, label), row, 0)
            required.addWidget(self._column_combo(role), row, 1)
        lay.addLayout(required)
        # Lo que falta o se adivino de una columna imprescindible.
        self.columns_note = QtWidgets.QLabel("")
        self.columns_note.setTextFormat(Qt.RichText)
        self.columns_note.setWordWrap(True)
        self.columns_note.setContentsMargins(COLUMN_LABEL_WIDTH + Metric.SPACING, 6, 0, 0)
        self.columns_note.setVisible(False)
        lay.addWidget(self.columns_note)
        lay.addSpacing(ROW_GAP)

        # Columnas de datos: van a la ventana de cada marca y casi siempre se
        # detectan bien solas, asi que quedan plegadas.
        self.data_toggle = _Disclosure("Mark window columns")
        set_custom_tooltip(self.data_toggle, TOOLTIPS["data"])
        self.data_toggle.toggled.connect(self._toggle_data_columns)
        lay.addWidget(self.data_toggle)
        self.data_box = QtWidgets.QWidget()
        data = _form_grid()
        data.setContentsMargins(0, 6, 0, 0)
        self.data_box.setLayout(data)
        for row, (role, label) in enumerate(DATA_COLUMNS):
            data.addWidget(self._column_label(role, label), row, 0)
            data.addWidget(self._column_combo(role), row, 1)
        self.data_box.setVisible(False)
        lay.addWidget(self.data_box)
        self._section(lay, "Timeline")

        # --- timeline -----------------------------------------------------------
        grid = _form_grid()
        self.reference_combo = self._combo("reference")
        if self.timeline.media_start is not None:
            self.reference_combo.addItem("Media timecode", "media")
        self.reference_combo.addItem("Timeline timecode", "timeline")
        self.reference_combo.currentIndexChanged.connect(self._reference_changed)
        self.measure_label = _field_label("Measure")
        grid.addWidget(self.measure_label, 0, 0)
        grid.addWidget(self.reference_combo, 0, 1)
        # TC de inicio y clip del timecode elegido: el nombre del clip no
        # entra en el combo.
        self.reference_detail = _ElidedLabel()
        self.reference_detail.setStyleSheet("QLabel { color: %s; }" % Color.TEXT_DIM)
        grid.addWidget(self.reference_detail, 1, 1)
        self.align_check = QtWidgets.QCheckBox("")
        self.align_check.setProperty("lgaLabeled", True)
        self.align_check.toggled.connect(self._refresh_plan)
        grid.addWidget(self.align_check, 2, 1)
        self.episode_combo = self._combo("episode_filter")
        self.episode_combo.currentIndexChanged.connect(self._refresh_plan)
        grid.addWidget(_field_label("Episode"), 3, 0)
        grid.addWidget(self.episode_combo, 3, 1)
        self.skip_omit = QtWidgets.QCheckBox("Skip omitted shots")
        self.skip_omit.setProperty("lgaLabeled", True)
        self.skip_omit.setChecked(True)
        set_custom_tooltip(self.skip_omit, TOOLTIPS["skip_omit"])
        self.skip_omit.toggled.connect(self._refresh_plan)
        grid.addWidget(self.skip_omit, 4, 1)
        lay.addLayout(grid)
        lay.addStretch(1)
        # Sin cliente de Google en esta maquina no se ofrece Google Sheets: el
        # switch no aparece y la fuente es un archivo. Un link pegado igual
        # explica que falta el cliente.
        # Sin planilla los combos estan vacios: apagados hasta que lleguen datos.
        for combo in [self.sheet_combo, self.episode_combo] + list(self.column_combos.values()):
            combo.setEnabled(False)
        self.google_enabled = _google_module().available()
        self.source_switch.setVisible(self.google_enabled)
        self._set_source_mode("google" if self.google_enabled else "file")
        return scroll

    def _section(self, lay, text, first=False):
        """Linea (salvo la primera) y rotulo de una seccion; el rotulo queda
        en self._section_head por si la seccion suma algo a su derecha."""
        if first:
            lay.addSpacing(SECTION_GAP)
        else:
            lay.addSpacing(SECTION_GAP)
            lay.addWidget(_hline())
            lay.addSpacing(SECTION_GAP)
        self._section_head = QtWidgets.QHBoxLayout()
        self._section_head.setContentsMargins(0, 0, 0, 0)
        self._section_head.addWidget(_section_label(text))
        self._section_head.addStretch(1)
        lay.addLayout(self._section_head)
        lay.addSpacing(8)

    def _build_preview(self):
        """Vista previa: mensaje, plan de marcas o grilla de fotos."""
        margin = Metric.WINDOW_MARGIN
        panel = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(panel)
        lay.setContentsMargins(margin + 6, margin + 2, margin + 4, 0)
        lay.setSpacing(0)
        self.pages = QtWidgets.QStackedWidget()
        lay.addWidget(self.pages)

        # 0: sin fuente, leyendo, o un error.
        page = QtWidgets.QWidget()
        page_lay = QtWidgets.QVBoxLayout(page)
        page_lay.setContentsMargins(24, 0, 24, 0)
        page_lay.addStretch(1)
        self.message_title = QtWidgets.QLabel("")
        self.message_title.setProperty("lgaTitle", True)
        self.message_title.setAlignment(Qt.AlignCenter)
        page_lay.addWidget(self.message_title)
        self.message_text = QtWidgets.QLabel("")
        self.message_text.setTextFormat(Qt.RichText)
        self.message_text.setWordWrap(True)
        self.message_text.setAlignment(Qt.AlignCenter)
        page_lay.addWidget(self.message_text)
        page_lay.addStretch(1)
        self.pages.addWidget(page)

        # 1: el plan de marcas.
        page = QtWidgets.QWidget()
        page_lay = QtWidgets.QVBoxLayout(page)
        page_lay.setContentsMargins(0, 0, 0, 0)
        page_lay.setSpacing(Metric.SPACING)
        self.count_label = QtWidgets.QLabel("")
        self.count_label.setProperty("lgaTitle", True)
        self.legend = QtWidgets.QLabel("")
        self.legend.setTextFormat(Qt.RichText)
        self.filter_switch = _PillSwitch(
            [(mode, FILTER_TEXTS[mode], TOOLTIPS["filter_" + mode])
             for mode in _preview_module().FILTERS], self._set_filter)
        self.filter_switch.select(self.filter_mode)
        head = QtWidgets.QHBoxLayout()
        head.addWidget(self.count_label)
        head.addSpacing(12)
        head.addWidget(self.legend)
        head.addStretch(1)
        head.addWidget(self.filter_switch)
        page_lay.addLayout(head)
        self.summary = QtWidgets.QLabel("")
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.RichText)
        page_lay.addWidget(self.summary)
        self.preview = QtWidgets.QTableWidget(0, 6, self)
        self.preview.setHorizontalHeaderLabels(["Row", "Shot", "TC In", "Frames", "Change", "Result"])
        self.preview.verticalHeader().setVisible(False)
        self.preview.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.preview.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.preview.setFocusPolicy(Qt.NoFocus)
        self.preview.setShowGrid(False)
        self.preview.setStyleSheet(Style.TABLE)
        self.preview.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.preview.horizontalHeader().setStretchLastSection(True)
        page_lay.addWidget(self.preview, 1)
        self.pages.addWidget(page)

        # 2: modo thumbnails: las fotos de la planilla que se van a buscar.
        page = QtWidgets.QWidget()
        page_lay = QtWidgets.QVBoxLayout(page)
        page_lay.setContentsMargins(0, 0, 0, 0)
        page_lay.setSpacing(Metric.SPACING)
        self.thumb_title = QtWidgets.QLabel("")
        self.thumb_title.setProperty("lgaTitle", True)
        page_lay.addWidget(self.thumb_title)
        self.thumb_text = QtWidgets.QLabel("")
        self.thumb_text.setTextFormat(Qt.RichText)
        self.thumb_text.setWordWrap(True)
        page_lay.addWidget(self.thumb_text)
        self.thumb_grid_box = QtWidgets.QWidget()
        self.thumb_grid = QtWidgets.QGridLayout(self.thumb_grid_box)
        self.thumb_grid.setContentsMargins(0, 0, 0, 0)
        self.thumb_grid.setSpacing(8)
        self.thumb_grid.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        page_lay.addWidget(self.thumb_grid_box)
        self.grid_status = QtWidgets.QLabel("")
        self.grid_status.setTextFormat(Qt.RichText)
        page_lay.addWidget(self.grid_status)
        page_lay.addStretch(1)

        # EDL del armado: solo en modo thumbnails. Da los cortes exactos y el
        # clip de camara de cada plano.
        self.edl_label = QtWidgets.QLabel("EDL")
        self.edl_edit = QtWidgets.QLineEdit()
        self.edl_edit.setReadOnly(True)
        self.edl_edit.setFixedHeight(Metric.BUTTON_HEIGHT)
        self.edl_edit.setPlaceholderText("Optional: the EDL of this cut, for exact cuts and camera clips")
        set_custom_tooltip(self.edl_edit, TOOLTIPS["edl"])
        self.edl_browse = QtWidgets.QPushButton("Browse")
        self.edl_clear = QtWidgets.QPushButton("Clear")
        for button, key, slot in ((self.edl_clear, "edl_clear", self._clear_edl),
                                  (self.edl_browse, "edl_browse", self._browse_edl)):
            button.setStyleSheet(Style.BTN_SECONDARY)
            button.setFixedHeight(Metric.BUTTON_HEIGHT)
            set_custom_tooltip(button, TOOLTIPS[key])
            button.clicked.connect(slot)
        self.edl_row = QtWidgets.QWidget()
        edl_row = QtWidgets.QHBoxLayout(self.edl_row)
        edl_row.setContentsMargins(0, 0, 0, 0)
        edl_row.addWidget(self.edl_label)
        edl_row.addWidget(self.edl_edit, 1)
        edl_row.addWidget(self.edl_clear)
        edl_row.addWidget(self.edl_browse)
        page_lay.addWidget(self.edl_row)
        self.thumb_note = QtWidgets.QLabel("")
        self.thumb_note.setTextFormat(Qt.RichText)
        self.thumb_note.setWordWrap(True)
        page_lay.addWidget(self.thumb_note)
        self.pages.addWidget(page)
        return panel

    def _combo(self, key):
        combo = ArrowComboBox(self)
        combo.setStyleSheet(Style.COMBO)
        set_custom_tooltip(combo, TOOLTIPS[key])
        combo.setFixedHeight(Metric.BUTTON_HEIGHT)
        # El ancho no sale del item mas largo: en NKS el combo de timecode
        # lleva el nombre del clip del timeline (~60 caracteres) y ensanchaba
        # la columna de ajustes mas alla de su ancho fijo, que quedaba cortada.
        combo.setSizeAdjustPolicy(
            QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        combo.setMinimumContentsLength(6)
        return combo

    def _column_label(self, role, text):
        label = _field_label(text)
        self.column_labels[role] = label
        return label

    def _column_combo(self, role):
        combo = self._combo(role)
        combo.setProperty("lgaRole", role)
        combo.currentIndexChanged.connect(self._columns_changed)
        self.column_combos[role] = combo
        return combo

    # estado inicial
    def _restore(self):
        if self.preset:
            self._restore_common()
            self.source = self.preset["path"]
            self.local_path = self.preset.get("local") or self.preset["path"]
            self.google = self.preset.get("google")
            # Fuente fija: la tabla ya trae los TC ubicados desde las fotos.
            self.input_row.setVisible(False)
            self.source_switch.setEnabled(False)
            self._show_source()
            self._loading = True
            self.sheet_combo.addItem(self.preset["sheet"] or "(CSV)", self.preset["sheet"])
            self.sheet_combo.setEnabled(False)
            self._loading = False
            self._table_ready((self.preset["table"], 0), None)
            return
        self._restore_common()
        last = self.settings.get("last_file", "")
        if last and _google_module().is_link(last):
            self._open_google(last)
        elif last and os.path.isfile(last):
            self._open_file(last)
        else:
            self._show_source()
            self._show_empty()

    def _restore_common(self):
        edl = self.settings.get("last_edl", "")
        self.edl_edit.setText(edl if edl and os.path.isfile(edl) else "")
        index = self.reference_combo.findData(self.settings.get("reference", "media"))
        if index >= 0:
            self.reference_combo.setCurrentIndex(index)
        self.skip_omit.setChecked(self.settings.get("skip_omit", "true") != "false")
        self.align_check.setChecked(self.settings.get("align", "false") == "true")

    # fuente
    def _set_source_mode(self, mode):
        """Google Sheet o File: cambia el campo de entrada, no la planilla cargada."""
        if mode == "google" and not getattr(self, "google_enabled", True) and not (
                self.source and _google_module().is_link(self.source)):
            mode = "file"
        self.source_mode = mode
        self.source_switch.select(mode)
        loaded = bool(self.source)
        if mode == "google":
            self.path_edit.setPlaceholderText(
                "Paste another Google Sheets link + Enter" if loaded
                else "Paste a Google Sheets link + Enter")
        else:
            self.path_edit.setPlaceholderText("Type a path, or Browse")
        self.browse_button.setVisible(mode == "file")

    def _show_source(self):
        """Nombre de la planilla en uso, su tooltip con la fuente completa y el
        estado. El campo de entrada queda libre para pegar otra."""
        is_google = bool(self.source) and _google_module().is_link(self.source)
        if self.source:
            self.source_name.set_full_text(self._source_name())
            set_custom_tooltip(self.source_name, TOOLTIPS["source_name"] % _escape(self.source))
            self._set_source_mode("google" if is_google else "file")
        else:
            self.source_name.set_full_text("No sheet yet")
            set_custom_tooltip(self.source_name, "")
            self._set_source_mode(self.source_mode)
        self.path_edit.clear()
        self.input_note.setVisible(False)
        self.reload_button.setVisible(bool(self.source) and not self.preset)
        set_custom_tooltip(self.reload_button,
                           TOOLTIPS["reload_google" if is_google else "reload_file"])
        self._show_source_note()

    def _reload(self):
        """Vuelve a consultar Google (baja solo si cambio) o relee el archivo,
        conservando la hoja elegida."""
        if self.preset or not self.source:
            return
        self._keep_sheet = self.sheet_combo.currentData()
        _logger_ref().info("Reload de la planilla: %s", self.source)
        if _google_module().is_link(self.source):
            self._open_google(self.source)
        else:
            self._open_file(self.local_path)

    # archivo y hoja
    def _browse(self):
        start = os.path.dirname(self.local_path) if not self.google else ""
        start = start or str(Path.home())
        path, _filter = QtWidgets.QFileDialog.getOpenFileName(
            self, "Choose sheet", start, "Sheets (*.xlsx *.csv)")
        if path:
            self._open_file(path)

    def _browse_edl(self):
        start = os.path.dirname(self.edl_edit.text()
                                or ("" if self.google else self.local_path)) or str(Path.home())
        path, _filter = QtWidgets.QFileDialog.getOpenFileName(
            self, "Choose EDL", start, "EDL (*.edl)")
        if path:
            self.edl_edit.setText(path)
            _logger_ref().info("EDL elegido: %s", path)
            self._refresh_plan()

    def _clear_edl(self):
        self.edl_edit.clear()
        self._refresh_plan()

    def _show_edl_row(self, visible):
        self.edl_row.setVisible(visible)

    def _run(self, func, callback):
        # El receptor es un metodo del dialogo (un QObject del hilo de UI):
        # asi la conexion es encolada y el callback corre en el hilo de UI.
        # Solo vale el ultimo pedido: si el usuario cambia de hoja mientras se
        # lee la anterior, el resultado viejo se descarta.
        self._token += 1
        token = self._token
        signals = _Signals()
        self._jobs[token] = (signals, callback)
        signals.done.connect(self._job_done)
        QtCore.QThreadPool.globalInstance().start(_Job(func, signals, token))

    @QtCore.Slot(object, object, object)
    def _job_done(self, token, result, error):
        _signals, callback = self._jobs.pop(token, (None, None))
        if callback is not None and token == self._token:
            callback(result, error)

    def _path_entered(self):
        """Ruta escrita o link pegado (Enter o al salir del campo)."""
        text = self.path_edit.text().strip()
        if not text or text == self.source:
            return
        if _google_module().is_link(text):
            self._open_google(text)
        elif os.path.isfile(text) and text.lower().endswith((".xlsx", ".csv")):
            self._open_file(text)
        else:
            self.input_note.setText("Not a .xlsx or .csv file, or a Google Sheets link.")
            self.input_note.setVisible(True)

    def _open_google(self, link):
        """Baja (o toma de la cache) la planilla de Google en un hilo y sigue
        como con un archivo. La primera vez abre el navegador para el login."""
        self.source = link
        self.table = None
        self.google = None
        self._show_source()
        self._clear_preview()
        self._set_busy("Getting the sheet from Google",
                       "The first time, sign in with Google in the browser.", timed=True)
        module = _google_module()
        logger = _logger_ref()

        def fetch():
            return module.fetch(link, log=logger.info)

        self._run(fetch, self._google_ready)

    def _google_ready(self, result, error):
        if error is not None:
            _logger_ref().error("Planilla de Google: %s", error)
            message = str(error) if isinstance(error, _google_module().GoogleSheetError) else (
                "Could not get the sheet from Google: %s" % error)
            self._show_message("Could not get the sheet", _escape(message), Color.ERROR_TEXT)
            self.source_note.setText(_status_line(Color.DOT_ERROR, "Could not get it",
                                                  Color.ERROR_TEXT))
            return
        self.google = result
        _logger_ref().info("Planilla de Google '%s': %s, copia en %s", result["title"],
                           "bajada" if result["downloaded"] else "sin cambios", result["path"])
        self._open_file(result["path"], source=self.source)

    def _show_source_note(self):
        # Una linea: punto de color (verde al dia, ambar copia vieja, gris
        # bajando o archivo local) y cuando cambio la planilla.
        info = self.google
        if info:
            if info.get("stale"):
                text = _status_line(Color.DOT_WARNING, "Offline &middot; copy from %s"
                                    % _local_time(info["modified"]), Color.WARNING_TEXT)
            else:
                state = "downloaded now" if info.get("downloaded") else "up to date"
                text = _status_line(Color.DOT_OK, "Changed %s &middot; %s"
                                    % (_local_time(info["modified"]), state))
        elif self.source and _google_module().is_link(self.source):
            text = _status_line(Color.TEXT_DIM, "Getting it from Google...")
        elif self.source:
            text = _status_line(Color.TEXT_DIM, "Local file" + _file_changed(self.local_path))
        else:
            self.source_note.setVisible(False)
            return
        self.source_note.setText(text)
        self.source_note.setVisible(True)

    def _source_name(self):
        """Nombre de la planilla para el origen de la marca y la carpeta de thumbs."""
        if self.google:
            return self.google.get("title") or "Google Sheet"
        if self.source and _google_module().is_link(self.source):
            return "Google Sheet"
        return os.path.basename(self.local_path or self.source)

    def _open_file(self, path, source=None):
        self.source = source or path
        self.local_path = path
        if source is None:
            self.google = None
        self._show_source()
        self.table = None
        self._set_busy("Reading the sheet", "Reading the sheets of %s..." % _escape(self._source_name()))
        keep, self._keep_sheet = self._keep_sheet, None
        saved = keep or (self.settings.get("last_sheet", "")
                         if self.source == self.settings.get("last_file") else "")
        module = _sheet_module()

        def read():
            sheets = module.list_sheets(path)
            choice = saved if saved in sheets else module.suggest_sheet(path, sheets)
            return sheets, choice

        self._run(read, self._sheets_ready)

    def _sheets_ready(self, result, error):
        if error is not None:
            _logger_ref().error("No se pudo leer el archivo: %s", error)
            self._show_message("Could not read the file", _escape(str(error)), Color.ERROR_TEXT)
            return
        sheets, choice = result
        self._loading = True
        self.sheet_combo.clear()
        for name in sheets:
            self.sheet_combo.addItem(name or "(CSV)", name)
        index = self.sheet_combo.findData(choice) if choice is not None else -1
        self.sheet_combo.setCurrentIndex(max(index, 0))
        self.sheet_combo.setEnabled(self.sheet_combo.count() > 0)
        self._loading = False
        self._sheet_changed()

    def _sheet_changed(self, *_args):
        if self._loading or self.sheet_combo.count() == 0:
            return
        path = self.local_path
        sheet = self.sheet_combo.currentData()
        self._set_busy("Reading the sheet", "Reading %s..." % _escape(sheet or "the file"))
        module = _sheet_module()
        thumbs = _thumbs_module()

        def read():
            # require_tc=False: una hoja de shots sin TC puede traer thumbnails.
            table = module.load_table(path, sheet, require_tc=False)
            columns = module.detect_columns(table.headers, table.rows)
            if columns.get("tc_in") is not None or not sheet:
                return table, []
            images = {img["row"] for img in thumbs.sheet_images(path, sheet)}
            shot = columns.get("shot")
            # Solo filas con shot: las de resumen o separadores tambien tienen fotos.
            with_shot = {number for number, values in table.rows
                         if shot is not None and shot < len(values) and module.is_shot_name(values[shot])}
            return table, sorted(images & with_shot)

        self._run(read, self._table_ready)

    def _table_ready(self, result, error):
        table, images = result if result is not None else (None, 0)
        if error is not None:
            self.table = None
            _logger_ref().warning("Hoja no utilizable: %s", error)
            self._fill_columns([])
            self._show_message("This sheet cannot be used", _escape(str(error)), Color.WARNING_TEXT)
            self._clear_preview()
            return
        self.table = table
        self.sheet_combo.setEnabled(self.sheet_combo.count() > 0 and not self.preset)
        self.no_timecode = _sheet_module().detect_columns(table.headers).get("tc_in") is None
        # Filas con foto: la lista (para la grilla) o solo la cuenta (preset).
        self.thumb_row_list = list(images) if isinstance(images, (list, tuple)) else []
        self.thumb_rows = len(images) if isinstance(images, (list, tuple)) else int(images or 0)
        self._fill_columns(table.headers, table.rows)
        _logger_ref().info("Planilla: %s | hoja %s | encabezado en fila %d | %d filas",
                           table.path, table.sheet, table.header_row, len(table.rows))
        self._suggest_place()
        self._apply_place()
        self._columns_changed()

    # donde van las marcas
    def _clip_report(self):
        """Reporte de with_clip_ranges con la columna de shot elegida, o None si el
        timeline no tiene clips sueltos para cruzar."""
        if self.table is None or len(self.timeline.clips) < 2:
            return None
        module = _sheet_module()
        _table, _cols, report = module.with_clip_ranges(
            self.table, self._columns().get("shot"), self.timeline.clips, self.timeline.fps,
            self.timeline.start)
        return report

    def _suggest_place(self):
        """Por clip si al menos la mitad de los clips del timeline tiene su shot en
        la planilla (un timeline de edit refs); si no, por timecode. Una vez que
        el usuario eligio con el switch, se respeta su eleccion."""
        if self._place_picked:
            return
        report = None if self.preset else self._clip_report()
        share = _sheet_module().clip_match_share(report) if report else 0.0
        self.place_mode = (PLACE_CLIP if share >= _sheet_module().CLIP_MATCH_SHARE
                           else PLACE_TIMECODE)
        if report:
            _logger_ref().info("Clips del timeline con su shot en la planilla: %d de %d (%.0f%%): "
                               "se sugiere marcar %s", report["matched"], report["clips"],
                               share * 100, "por clip" if self.place_mode == PLACE_CLIP
                               else "por timecode")

    def _pick_place(self, mode):
        if mode == self.place_mode and self._place_picked:
            return
        self._place_picked = True
        self.place_mode = mode
        _logger_ref().info("Marcas elegidas %s", "por clip" if mode == PLACE_CLIP else "por timecode")
        if self.table is None:
            self.place_switch.select(mode)
            return
        self._apply_place()
        self._refresh_plan()

    def _apply_place(self):
        """Muestra solo lo que usa el modo: por clip no hay columnas de TC ni
        timecode de referencia, y una hoja sin TC no pasa a ubicar thumbnails."""
        clip = self.place_mode == PLACE_CLIP
        self.place_switch.select(self.place_mode)
        self.thumb_mode = bool(self.table is not None and self.no_timecode and not clip)
        for role in ("tc_in", "tc_out"):
            self.column_combos[role].setEnabled(self.table is not None and not self.thumb_mode)
            self.column_combos[role].setVisible(not clip)
            self.column_labels[role].setVisible(not clip)
        for widget in (self.measure_label, self.reference_combo, self.reference_detail):
            widget.setVisible(not clip)
        self._reference_changed(refresh=False)
        self._show_edl_row(self.thumb_mode)
        self._clear_grid()
        if self.thumb_mode and self.thumb_row_list:
            self._start_thumb_grid()

    def _show_place_note(self):
        """Linea debajo del switch: que hace el modo y como cruzaron los clips."""
        report = self.clip_report
        if self.place_mode == PLACE_CLIP:
            if not report:
                self.place_note.setText("")
                return
            text = _colored("Each mark takes the length of its clip.", Color.TEXT_DIM)
            text += "<br>%s of %d clips have their shot in the sheet" % (
                emphasis(str(report["matched"])), report["clips"])
            missing = len(report["unmatched"])
            if missing:
                text += _colored(" &middot; %d %s not" % (missing, "is" if missing == 1 else "are"),
                                 Color.WARNING_TEXT)
            if report["multi"]:
                text += _colored(" &middot; %d %s with two clips or more"
                                 % (len(report["multi"]), _plural(len(report["multi"]), "shot")),
                                 Color.WARNING_TEXT)
            self.place_note.setText(text)
            return
        text = _colored("Each mark goes at the REC TC of its row.", Color.TEXT_DIM)
        if report and _sheet_module().clip_match_share(report) >= _sheet_module().CLIP_MATCH_SHARE:
            text += "<br>" + _colored("%d of %d clips are named after a shot: One per clip fits "
                                      "this timeline." % (report["matched"], report["clips"]),
                                      Color.WARNING_TEXT)
        self.place_note.setText(text)

    def _fill_columns(self, headers, rows=None):
        module = _sheet_module()
        detected = module.detect_columns(headers, rows) if headers else {}
        self._undetected = set()
        self._loading = True
        for role, combo in self.column_combos.items():
            combo.clear()
            combo.setEnabled(bool(headers))
            # Hoja sin columna de TC (modo thumbnails): TC In tambien va en
            # "(none)", no en la primera columna.
            if role not in ("shot", "tc_in") or (role == "tc_in" and detected.get("tc_in") is None):
                combo.addItem(NONE_LABEL, None)
            for index, header in enumerate(headers):
                combo.addItem(header, index)
            saved = self.settings.get("col_" + role, "")
            pick = headers.index(saved) if saved in headers else detected.get(role)
            if role == "shot" and rows and pick != detected.get(role):
                # La columna recordada pierde si tiene menos nombres de shot:
                # una planilla renumerada deja la vieja casi vacia.
                kept, best = (module.shot_name_count(rows, pick),
                              module.shot_name_count(rows, detected.get(role)))
                if best > kept:
                    _logger_ref().info("Columna de shot: %s tiene %d nombres y %s %d; se usa %s",
                                       saved, kept, headers[detected[role]], best,
                                       headers[detected[role]])
                    pick = detected.get(role)
            if pick is not None:
                combo.setCurrentIndex(combo.findData(pick))
            elif headers and role in ("shot", "tc_in"):
                # El combo cae en la primera columna sin que nadie la eligiera:
                # se avisa al lado para que se revise.
                self._undetected.add(role)
        self._loading = False

    def _columns(self):
        columns = {role: combo.currentData() for role, combo in self.column_combos.items()}
        # Thumb, nivel de ubicacion y plano del EDL no tienen combo: son
        # columnas que agrega la ubicacion desde thumbnails y viajan a la
        # metadata de cada tag.
        if self.table is not None:
            detected = _sheet_module().detect_columns(self.table.headers)
            for role in ("thumb", "located", "clip"):
                columns[role] = detected.get(role)
        return columns

    def _columns_changed(self, *_args):
        role = self.sender().property("lgaRole") if self.sender() is not None else None
        if role and not self._loading:
            # Elegida a mano: ya no es una columna adivinada.
            self._undetected.discard(role)
        if self._loading or self.table is None:
            return
        module = _sheet_module()
        episodes = module.episode_values(self.table, self._columns().get("episode"))
        current = self.episode_combo.currentText()
        self._loading = True
        self.episode_combo.clear()
        self.episode_combo.addItem(ALL_EPISODES, None)
        for episode in episodes:
            self.episode_combo.addItem(episode, episode)
        guess = current if current in episodes else guess_episode(self.sequence.name(), episodes)
        if guess:
            self.episode_combo.setCurrentIndex(self.episode_combo.findData(guess))
        self.episode_combo.setEnabled(True)
        self._loading = False
        self._refresh_plan()

    def _update_columns_note(self):
        """Pinta los rotulos de las columnas imprescindibles que faltan (rojo) o
        que se tomaron sin encontrarlas por nombre (amarillo)."""
        preview = _preview_module()
        columns = self._columns() if self.table is not None else {}
        # Por clip, como con thumbnails, el TC no sale de la planilla.
        no_tc = self.thumb_mode or self.place_mode == PLACE_CLIP
        missing = preview.missing_required(columns, no_tc) if self.table is not None else []
        guessed = [r for r in sorted(self._undetected)
                   if r not in missing and not (no_tc and r == "tc_in")]
        for role, label in self.column_labels.items():
            color = (Color.ERROR_TEXT if role in missing
                     else Color.WARNING_TEXT if role in guessed else Color.TEXT_DIM)
            label.setStyleSheet("QLabel { color: %s; }" % color)
        notes = []
        names = dict(REQUIRED_COLUMNS)
        if missing:
            notes.append(_colored("Pick the %s column." % " and ".join(names[r] for r in missing),
                                  Color.ERROR_TEXT))
        elif guessed:
            notes.append(_colored("%s: no column with that name, check the one picked."
                                  % " and ".join(names[r] for r in guessed), Color.WARNING_TEXT))
        if self.thumb_mode and self.table is not None:
            notes.append(_colored("No timecode: found by photo.", Color.TEXT_DIM))
        self.columns_note.setText("<br>".join(notes))
        self.columns_note.setVisible(bool(notes))
        count = preview.data_column_count(columns)
        self.data_toggle.set_count("%d of %d" % (count, len(DATA_COLUMNS)) if self.table is not None
                                   else "")

    def _toggle_data_columns(self, opened=None):
        self.data_box.setVisible(self.data_toggle.isChecked())
        self._update_columns_note()

    def _reference_changed(self, *_args, refresh=True):
        media = self.reference_combo.currentData() == "media"
        start = self.timeline.media_start
        show = (media and start is not None and start != self.timeline.start
                and self.place_mode != PLACE_CLIP)
        self.align_check.setVisible(show)
        if media and start is not None:
            detail = "Starts %s &middot; %s" % (self.timeline.timecode(start), self.timeline.media_clip)
        else:
            detail = "Starts %s" % self.timeline.timecode(self.timeline.start)
        self.reference_detail.set_full_text(html.unescape(detail))
        if start is not None:
            self.align_check.setText("Align timeline start to it")
            set_custom_tooltip(self.align_check, TOOLTIPS["align"] % self.timeline.timecode(
                self.timeline.start))
        if refresh:
            self._refresh_plan()

    def _reference_start(self):
        # Por clip el TC de cada marca sale del timeline mismo.
        if self.place_mode == PLACE_CLIP:
            return self.timeline.start
        if self.reference_combo.currentData() == "media" and self.timeline.media_start is not None:
            return self.timeline.media_start
        return self.timeline.start

    # plan
    def _refresh_plan(self, *_args):
        if self._loading or self.table is None:
            return
        self._update_columns_note()
        module = _sheet_module()
        columns = self._columns()
        clip = self.place_mode == PLACE_CLIP
        table = self.table
        self.clip_report = None
        if len(self.timeline.clips) > 1 and not self.preset:
            # Tambien por timecode: la linea del switch avisa si por clip encaja mejor.
            clip_table, extra, self.clip_report = module.with_clip_ranges(
                self.table, columns.get("shot"), self.timeline.clips, self.timeline.fps,
                self.timeline.start)
            if clip:
                table = clip_table
                columns.update(extra)
        self._show_place_note()
        if self.thumb_mode:
            self._show_thumb_mode()
            return
        try:
            self.plan = module.build_plan(
                table, columns, self.timeline.fps, self._reference_start(),
                self.timeline.duration, episode=self.episode_combo.currentData(),
                skip_omit=self.skip_omit.isChecked())
            if clip and self.clip_report:
                module.finish_clip_plan(self.plan, self.clip_report, self.timeline.fps,
                                        self.timeline.start)
        except ValueError as exc:
            self.plan = None
            missing = _preview_module().missing_required(columns, clip)
            names = dict(REQUIRED_COLUMNS)
            text = ("Pick the %s column on the left." % " and ".join(names[r] for r in missing)
                    if missing else _escape(str(exc)))
            self._clear_preview()
            self._show_message("Columns missing", text, Color.WARNING_TEXT)
            return
        # Sin corrida anterior no hay contra que comparar: icono comun.
        self.removed = (module.compare_marks(self.plan.marks, self.previous, self.plan.issues)
                        if self.previous else [])
        self.removed, covered = module.drop_covered_removed(self.removed, self.plan.marks)
        if covered:
            _logger_ref().info("Rojas que no se crean (caen sobre una marca nueva): %d", len(covered))
            for old in covered:
                _logger_ref().info("  %-28s %6d-%-6d", old["shot"], old["frame_in"], old["frame_out"])
        self._show_plan()

    def _show_plan(self):
        plan = self.plan
        marks, errors, warnings = len(plan.marks), len(plan.errors()), len(plan.warnings())
        previous = len(own_tags(self.sequence))
        self.count_label.setText("%d %s" % (marks, _plural(marks, "mark")) if marks else "No marks")
        parts = []
        if previous:
            counts = _sheet_module().change_counts(plan.marks, self.removed)
            self.legend.setText("&nbsp;&nbsp;&nbsp;".join(
                "%s %s" % (_colored("&#9679;", CHANGE_COLORS[key]),
                           "%d %s" % (counts[key], LEGEND_LABELS[key]))
                for key in ("unchanged", "changed", "new", "removed")))
            self.legend.setVisible(True)
            parts.append("Replaces the %d %s added before" % (previous, _plural(previous, "mark")))
            if counts["removed"]:
                parts.append(_colored(_red_text(counts), CHANGE_COLORS["removed"]))
        else:
            self.legend.setVisible(False)
        if plan.skipped_omit:
            parts.append("%d omitted skipped" % plan.skipped_omit)
        if plan.skipped_episode:
            parts.append("%d from other episodes" % plan.skipped_episode)
        parts.append(_colored("%d not written" % errors, Color.ERROR_TEXT) if errors else "0 not written")
        if warnings:
            parts.append(_colored("%d %s" % (warnings, _plural(warnings, "warning")),
                                  Color.WARNING_TEXT))
        text = _colored(" &middot; ", Color.TEXT_DIM).join(parts)
        comments = _comments_summary(self.table, plan.marks)
        if comments:
            text += "<br>" + comments
        clip = self.place_mode == PLACE_CLIP
        if self.timeline.media_reason and not clip:
            text += "<br>" + _colored("%s." % self.timeline.media_reason, Color.TEXT_DIM)
        self.summary.setText(text)
        self._stop_busy()
        self.pages.setCurrentIndex(PAGE_PLAN)
        self.apply_button.setEnabled(marks > 0)
        set_custom_tooltip(self.apply_button, "")
        verb = "Update" if previous else "Add"
        self.apply_button.setText(
            "%s %d %s" % (verb, marks, _plural(marks, "Mark")) if marks else "Add Marks")
        self._fill_preview()
        log = _logger_ref()
        log.info("Prueba en seco: columnas %s | episodio %s | omit %s | fps %d | referencia %s "
                 "(%d) | duracion %d | %d marcas, %d no escritas, %d avisos",
                 self._columns(), self.episode_combo.currentData(), self.skip_omit.isChecked(),
                 self.timeline.fps, self.reference_combo.currentData(), self._reference_start(),
                 self.timeline.duration, marks, errors, warnings)
        if clip and self.clip_report:
            report = self.clip_report
            log.info("Por clip: %d clips, %d con su shot, %d shots con clip, %d shots con mas de un "
                     "clip, %d filas que no son shots salteadas", report["clips"],
                     report["matched"], report["shots"], len(report["multi"]),
                     plan.skipped_not_shot)
        for issue in plan.issues:
            log.info("  fila %d %s (%s): %s%s", issue.row, issue.shot, issue.tc_in,
                     issue.message, "" if issue.written else " [no se escribe]")

    def _show_thumb_mode(self):
        """Hoja sin columna de TC: ofrecer ubicar los thumbnails en el video."""
        self.plan = None
        self._clear_preview()
        if not self.thumb_rows:
            self._show_message("Nothing to locate",
                               "This sheet has no timecode column and no thumbnails in its rows.",
                               Color.WARNING_TEXT)
            return
        locate = _locate_module()
        movie = locate.media_path(self.sequence)
        missing = locate.missing_tools()
        rows = self.thumb_rows
        self.thumb_title.setText("%d %s to locate" % (rows, _plural(rows, "shot")))
        text = ("This sheet has no timecode. Shot Marks finds each photo in %s and marks the "
                "shot from cut to cut; you review the doubtful ones before any mark is added."
                % emphasis(_escape(os.path.basename(movie or "the timeline movie"))))
        if missing:
            text += "<br>" + _colored("Not available: missing %s." % _escape(", ".join(missing)),
                                      Color.ERROR_TEXT)
        elif not movie:
            text += "<br>" + _colored("The timeline needs a single movie clip to compare with.",
                                      Color.ERROR_TEXT)
        self.thumb_text.setText(text)
        edl = self.edl_edit.text()
        if edl:
            note = "Cuts from %s, checked against the movie before using it." % emphasis(
                _escape(os.path.basename(edl)))
        else:
            note = _colored("Without an EDL, cuts between similar shots may be missed.",
                            Color.TEXT_DIM)
        note += "<br>" + _colored("The first time it indexes the movie: about 1 min per 40 min "
                                  "of movie.", Color.TEXT_DIM)
        self.thumb_note.setText(note)
        self._stop_busy()
        self.pages.setCurrentIndex(PAGE_THUMBS)
        self.apply_button.setText("Locate %d %s..." % (rows, _plural(rows, "Shot")))
        set_custom_tooltip(self.apply_button, TOOLTIPS["locate"])
        self.apply_button.setEnabled(bool(movie) and not missing)

    # grilla de fotos (modo thumbnails)
    def _clear_grid(self):
        while self.thumb_grid.count():
            item = self.thumb_grid.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self._grid_shown, self._grid_more = [], 0
        self.grid_status.setText("")

    def _start_thumb_grid(self):
        """Lee las fotos de las primeras filas fuera del hilo de UI, en la misma
        cache que usa Locate (se extraen una vez por sha1)."""
        self._grid_shown, self._grid_more = _preview_module().grid_rows(self.thumb_row_list,
                                                                         GRID_CELLS)
        self.grid_status.setText(_colored("Reading the photos of the sheet...", Color.TEXT_DIM))
        path, sheet, rows = self.table.path, self.table.sheet, list(self._grid_shown)
        out_dir = str(_locate_module().cache_root() / "thumbs_src")
        thumbs = _thumbs_module()

        def read():
            found = thumbs.extract_thumbs(path, sheet, rows, out_dir)
            images = {}
            for row, info in found.items():
                # QImage (no QPixmap) se puede armar fuera del hilo de UI.
                image = QtGui.QImage(info["file"])
                if not image.isNull():
                    images[row] = image.scaled(THUMB_SIZE[0], THUMB_SIZE[1], Qt.KeepAspectRatio,
                                               Qt.SmoothTransformation)
            return images

        self._run(read, self._grid_ready)

    def _grid_ready(self, images, error):
        if error is not None:
            _logger_ref().warning("No se pudieron leer las fotos para la grilla: %s", error)
            self.grid_status.setText(_colored("Could not read the photos: %s" % _escape(str(error)),
                                              Color.TEXT_DIM))
            return
        self.grid_status.setText("")
        shot_col = self._columns().get("shot")
        shots = {}
        for number, values in self.table.rows if self.table is not None else []:
            if shot_col is not None and shot_col < len(values):
                shots[number] = values[shot_col].strip()
        cells = [self._thumb_card(row, shots.get(row, ""), images.get(row))
                 for row in self._grid_shown]
        if self._grid_more:
            more = QtWidgets.QFrame()
            more.setObjectName("shotMarksMore")
            more.setAttribute(Qt.WA_StyledBackground, True)
            more.setStyleSheet("#shotMarksMore { background-color: %s; border-radius: %dpx; }"
                               % (Color.SURFACE_SUNKEN, Metric.RADIUS))
            label = QtWidgets.QLabel(_colored("+%d more" % self._grid_more, Color.TEXT_DIM))
            label.setAlignment(Qt.AlignCenter)
            QtWidgets.QVBoxLayout(more).addWidget(label)
            cells.append(more)
        for index, cell in enumerate(cells):
            self.thumb_grid.addWidget(cell, index // GRID_COLUMNS, index % GRID_COLUMNS)
        apply_ui_font(self.thumb_grid_box)

    def _thumb_card(self, row, shot, image):
        card = QtWidgets.QFrame()
        card.setObjectName("shotMarksThumb")
        card.setAttribute(Qt.WA_StyledBackground, True)
        card.setStyleSheet("#shotMarksThumb { %s }" % Style.PANEL)
        lay = QtWidgets.QVBoxLayout(card)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(2)
        picture = QtWidgets.QLabel()
        picture.setFixedSize(THUMB_SIZE[0], THUMB_SIZE[1])
        picture.setAlignment(Qt.AlignCenter)
        if image is not None:
            picture.setPixmap(QtGui.QPixmap.fromImage(image))
        else:
            picture.setText(_colored("No photo", Color.TEXT_DIM))
        lay.addWidget(picture)
        name = QtWidgets.QLabel(_escape(shot))
        name.setFixedWidth(THUMB_SIZE[0])
        set_custom_tooltip(name, _escape(shot))
        lay.addWidget(name)
        lay.addWidget(QtWidgets.QLabel(_colored("row %d" % row, Color.TEXT_DIM)))
        return card

    def _locate(self):
        """Cierra el dialogo y abre la ventana de ubicacion (no modal: hay que
        poder mover el visor de NKS mientras se revisa)."""
        self._save_settings()
        sequence, timeline = self.sequence, self.timeline
        path, sheet, table = self.source, self.sheet_combo.currentData(), self.table
        local, google = self.local_path, self.google

        def done(located):
            located_table = _sheet_module().with_located_timecodes(table, located)
            _logger_ref().info("Ubicadas %d filas desde thumbnails", len(located))
            dialog = ShotMarksDialog(sequence, hiero.ui.mainWindow(),
                                     preset={"path": path, "local": local, "google": google,
                                             "sheet": sheet, "table": located_table})
            dialog.exec_() if hasattr(dialog, "exec_") else dialog.exec()

        self.accept()
        _locate_module().open_window(sequence, timeline, table, self._columns(),
                                     self.skip_omit.isChecked(), done, edl=self.edl_edit.text())

    # vista previa
    def _fill_preview(self):
        sheet = _sheet_module()
        self.entries = _preview_module().preview_entries(
            self.plan, self.removed, sheet.CHANGE_FIELDS, sheet.meta_key("tc_in"))
        counts = _preview_module().filter_counts(self.entries)
        for mode, button in self.filter_switch.buttons.items():
            text = FILTER_TEXTS[mode]
            button.setText(text if mode == "all" else "%s %d" % (text, counts[mode]))
        self._render_preview()

    def _set_filter(self, mode):
        self.filter_mode = mode
        self.filter_switch.select(mode)
        self._render_preview()

    def _render_preview(self):
        rows = _preview_module().filter_entries(self.entries, self.filter_mode)
        self.preview.setRowCount(len(rows))
        for index, entry in enumerate(rows):
            values = (str(entry["row"]) if entry["row"] else "", entry["shot"], entry["tc_in"],
                      entry["frames"], entry["change"], entry["result"])
            for col, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(value)
                if col == 0:
                    item.setForeground(QtGui.QBrush(QtGui.QColor(Color.TEXT_DIM)))
                elif col == 4:
                    item.setForeground(QtGui.QBrush(QtGui.QColor(
                        CHANGE_COLORS.get(entry["change_kind"], Color.TEXT_DIM))))
                elif col == 5:
                    item.setForeground(QtGui.QBrush(QtGui.QColor(
                        RESULT_COLORS[entry["result_kind"]])))
                self.preview.setItem(index, col, item)
            self.preview.setRowHeight(index, Metric.ROW_HEIGHT)
        self.preview.resizeColumnsToContents()
        self.preview.horizontalHeader().setStretchLastSection(True)
        # Sin corrida anterior la columna Change estaria vacia.
        self.preview.setColumnHidden(4, not self.previous)

    def _clear_preview(self):
        self.entries = []
        self.preview.setRowCount(0)
        self.apply_button.setEnabled(False)
        self.apply_button.setText("Add Marks")
        set_custom_tooltip(self.apply_button, "")

    # mensajes de la vista previa
    def _show_empty(self):
        self._show_message(
            "Nothing to preview yet",
            "Paste a Google Sheets link or choose a .xlsx / .csv.<br>Every mark shows up here "
            "before anything is written to %s." % emphasis(_escape(self.sequence.name())),
            Color.TEXT_DIM)

    def _show_message(self, title, text, color=None):
        self._stop_busy()
        self.message_title.setText(title)
        self.message_text.setText(_colored(text, color) if color else text)
        self.pages.setCurrentIndex(PAGE_MESSAGE)

    def _set_busy(self, title, text, timed=False):
        """Leyendo o bajando: la vista previa lo dice; con timed, cuenta segundos."""
        self.apply_button.setEnabled(False)
        self._busy_text = (title, text)
        self._busy_started = time.time() if timed else None
        if timed:
            self._busy_timer.start()
        else:
            self._busy_timer.stop()
        self._tick_busy()

    def _tick_busy(self):
        title, text = self._busy_text
        if self._busy_started is not None:
            text += "<br>%d s" % int(time.time() - self._busy_started)
        self.message_title.setText(title + "...")
        self.message_text.setText(_colored(text, Color.TEXT_DIM))
        self.pages.setCurrentIndex(PAGE_MESSAGE)

    def _stop_busy(self):
        self._busy_timer.stop()
        self._busy_started = None


    # aplicar
    def _apply(self):
        if self.thumb_mode:
            self._locate()
            return
        if not self.plan or not self.plan.marks:
            return
        align = None
        # isHidden y no isVisible: isVisible depende tambien del dialogo.
        if not self.align_check.isHidden() and self.align_check.isChecked():
            align = self.timeline.media_start
        source = "%s | %s" % (self._source_name() + (" (Google Sheets)" if self.google else ""),
                              self.sheet_combo.currentData() or "")
        if self.preset:
            source += " | located from thumbnails"
        elif self.place_mode == PLACE_CLIP:
            source += " | one mark per clip"
        counts = _sheet_module().change_counts(self.plan.marks, self.removed)
        if self.previous and not self._confirm_update(counts):
            _logger_ref().info("Actualizacion cancelada por el usuario")
            return
        project_dir, copies = self._thumbs_to_project() if self.preset else ("", [])
        try:
            replaced = apply_plan(self.sequence, self.plan, align, source, self.removed)
        except Exception as exc:
            _logger_ref().exception("No se pudieron escribir los tags")
            show_error(self, "Shot Marks", "Could not add the marks:\n%s" % exc)
            return
        if copies:
            _copy_thumbs_later(project_dir, copies)
        self._save_settings()
        message = "Added %d marks to %s." % (len(self.plan.marks), self.sequence.name())
        if replaced:
            message += "\nReplaced %d marks from a previous run." % replaced
            message += ("\nGreen %d unchanged, yellow %d changed, orange %d new, red %s."
                        % (counts["unchanged"], counts["changed"], counts["new"],
                           _red_text(counts)))
        if align is not None:
            message += "\nTimeline start timecode is now %s." % self.timeline.timecode(align)
        message += ("\n\nPrevious / Next Mark in the Review panel open the mark window with the "
                    "brief; while it is open it follows the playhead.\n"
                    "Viewer > Next Tag (Alt+Shift+Right) also jumps between them.\nUndo: Edit > Undo.")
        self.accept()
        show_info(hiero.ui.mainWindow(), "Shot Marks", message)

    def _thumbs_to_project(self):
        """Thumbs de las marcas a una subcarpeta junto al .hrox, con el nombre
        de la planilla: el tag guarda la ruta relativa y no depende de la cache
        de Locate de esta maquina. Devuelve (carpeta del proyecto, copias)."""
        hrox = self.sequence.project().path()
        if not hrox:
            _logger_ref().info("Proyecto sin guardar: los thumbs quedan en la cache de Locate")
            return "", []
        folder = (_google_module().safe_name(self._source_name()) if self.google
                  else Path(self.local_path).stem)
        copies = _sheet_module().project_thumbs(self.plan.marks, folder)
        return os.path.dirname(hrox), copies

    def _confirm_update(self, counts):
        """Avisa antes de borrar las marcas de la corrida anterior."""
        previous = len(self.previous)
        old_red = sum(1 for old in self.previous if old.get("change") == "removed")
        text = ("This deletes the %d %s added before to %s and adds %d from the sheet:\n\n"
                "   Green: %d unchanged\n   Yellow: %d with changes in the sheet\n"
                "   Orange: %d new\n   Red: %s (kept where they were)"
                % (previous, _plural(previous, "mark"), self.sequence.name(),
                   len(self.plan.marks), counts["unchanged"], counts["changed"], counts["new"],
                   _red_text(counts)))
        if old_red:
            text += "\n\nThe %d red %s from the previous update %s deleted." % (
                old_red, _plural(old_red, "mark"), "is" if old_red == 1 else "are")
        text += "\n\nA shot that only moved in the cut is not a change. Undo: Edit > Undo."
        return ask_question(self, "Update Shot Marks", text, yes_text="Update Marks",
                            no_text="Cancel")

    def _save_settings(self):
        values = {
            "last_file": self.source,
            "last_sheet": self.sheet_combo.currentData() or "",
            "skip_omit": "true" if self.skip_omit.isChecked() else "false",
            "align": "true" if self.align_check.isChecked() else "false",
            "reference": self.reference_combo.currentData() or "media",
            "last_edl": self.edl_edit.text(),
        }
        headers = self.table.headers if self.table else []
        for role, index in self._columns().items():
            values["col_" + role] = headers[index] if index is not None else ""
        _write_settings(values)


def _colored(text, color):
    return '<span style="color:%s">%s</span>' % (color, text)


def _status_line(dot, text, color=None):
    """Estado de la fuente: punto de color y texto (gris salvo que se pida otro)."""
    return "%s&nbsp;&nbsp;%s" % (_colored("&#9679;", dot), _colored(text, color or Color.TEXT_DIM))


def _red_text(counts):
    """'7 no longer in the sheet, 25 not placed in this timeline'."""
    gone = counts["removed"] - counts["unplaced"]
    text = "%d %s" % (gone, CHANGE_LABELS["removed"])
    if counts["unplaced"]:
        text += ", %d in the sheet but not placed in this timeline" % counts["unplaced"]
    return text


def _comments_summary(table, marks):
    """'3 comments from the sheet go to their shots (2 on other rows are not shown).'"""
    comments = getattr(table, "comments", None) or {}
    total = sum(len(threads) for threads in comments.values())
    if not total:
        return ""
    rows = {mark.row for mark in marks}
    on_marks = sum(len(threads) for row, threads in comments.items() if row in rows)
    text = "%d %s from the sheet %s to the mark window of %s" % (
        on_marks, _plural(on_marks, "comment"), "goes" if on_marks == 1 else "go",
        "its shot" if on_marks == 1 else "their shots")
    if total > on_marks:
        text += " (%d on other rows %s not shown)" % (total - on_marks,
                                                      "is" if total - on_marks == 1 else "are")
    return _colored(text + ".", Color.TEXT_DIM)


def _plural(count, word):
    return word if count == 1 else word + "s"


def main():
    global _log
    _log = _logger()
    sequence = hiero.ui.activeSequence()
    if sequence is None:
        _log.warning("No hay timeline activo")
        show_warning(hiero.ui.mainWindow(), "Shot Marks", "Open a timeline first.")
        return
    try:
        editable = sequence.project().editable()
    except Exception:
        editable = True
    if not editable:
        _log.warning("Proyecto no editable: %s", sequence.project().name())
        show_warning(hiero.ui.mainWindow(), "Shot Marks",
                     "The project of this timeline is locked and cannot be edited.")
        return
    info = TimelineInfo(sequence)
    _log.info("Timeline %s | fps %.3f | inicio %d (%s) | duracion %d | media %s %s %s",
              sequence.name(), info.fps_float, info.start, info.timecode(info.start),
              info.duration, info.media_clip, info.media_start, info.media_reason)
    if abs(info.fps_float - info.fps) > 0.01:
        _log.info("Frame rate NTSC: se cuentan cuadros a %d nominal, sin drop-frame", info.fps)
    dialog = ShotMarksDialog(sequence, hiero.ui.mainWindow())
    dialog.exec_() if hasattr(dialog, "exec_") else dialog.exec()


if __name__ == "__main__":
    main()
