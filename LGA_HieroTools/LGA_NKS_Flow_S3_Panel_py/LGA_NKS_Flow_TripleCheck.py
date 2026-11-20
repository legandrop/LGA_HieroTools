"""
____________________________________________________________________

  LGA_NKS_Flow_TripleCheck v1.04 | Lega

  Triple Check del panel Flow | S3: para cada shot y task del timeline
  activo compara la ultima version publicada (EXR) en Flow, en Wasabi y en
  el disco local, y ofrece Download o Upload en cada fila que lo necesita.
  Cruza ademas los shots del timeline con los de Flow en las dos
  direcciones (lo que hacia Check Shots Exist, y los shots de Flow que no
  estan en el timeline).

  La logica (escaneo, reglas de version, estados) vive en
  LGA_NKS_Shared/LGA_NKS_TripleCheck_Core.py, sin hiero ni Qt. Este modulo
  junta los clips del timeline, corre el chequeo fuera del hilo principal
  y muestra la ventana. Detalle: docs/Docu_TripleCheck.md.

  v1.04: Estado Duplicate in Flow para un shot que Flow tiene dos veces
         con el mismo nombre (distinto id), con los ids en Detail; y una
         nota arriba con todos los repetidos del proyecto.
  v1.03: Detail lo dibuja un delegate propio (DetailDelegate): en NKS el
         estilo del host ignoraba el salto de linea y cortaba con puntos.
         Parte por palabra o, si un nombre largo no entra, en cualquier
         punto. Alto de filas automatico (ResizeToContents).
  v1.02: Detail en castellano y multilinea (la fila crece, sin puntos
         suspensivos). El click en una fila ya no lleva al timeline: lo
         hace un boton propio en la columna de al lado del shot. Keep on
         top (prendido, persistido en TripleCheck.ini). Estado Extra
         folder para una carpeta de otro shot que sobra en el publish.
  v1.01: Columna Task Status (estado de la task en Flow, con su color),
         orden por columna con click en la cabecera, filtro por estado y
         Detail que explica los shots de Flow sin nada publicado. La columna
         del chequeo pasa a llamarse Sync. Reload del core robusto.
  v1.00: Version inicial.
____________________________________________________________________
"""

import os
import sys
import time
import logging
import threading
import configparser
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import hiero.core
import hiero.ui

from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui, QtCore, Qt
from LGA_NKS_Shared.LGA_NKS_MessageBox import show_warning, ask_question
from LGA_NKS_Shared.LGA_UI_Style_HieroTools import (
    Style,
    Color,
    Metric,
    apply_ui_font,
    emphasis,
)
from LGA_NKS_Shared.LGA_UI_CustomTooltip_HieroTools import set_custom_tooltip
from LGA_NKS_Shared import LGA_NKS_TripleCheck_Core as core

# El panel carga este script de cero en cada click, pero el core queda
# cacheado en sys.modules: sin el reload, una actualizacion del pack con NKS
# abierto mezclaria la ventana nueva con la logica vieja.
import importlib as _importlib

# Si el modulo salio de sys.modules, el paquete conserva el atributo viejo:
# el import de arriba lo devuelve y reload() falla con ImportError. En ese
# caso se importa de cero.
_CORE_NAME = "LGA_NKS_Shared.LGA_NKS_TripleCheck_Core"
if _CORE_NAME in sys.modules:
    core = _importlib.reload(sys.modules[_CORE_NAME])
else:
    core = _importlib.import_module(_CORE_NAME)
from LGA_NKS_Shared.LGA_NKS_TaskScope import (
    active_track_tasks,
    exr_track_for_task,
    task_folder_name,
    task_display_name,
    CG_TASK_NAME,
)
from LGA_NKS_Shared.LGA_NKS_Flow_Status_Config import get_task_status_dict
from LGA_NKS_Shared.LGA_NKS_Flow_NamingUtils import (
    clean_base_name,
    extract_project_name,
    extract_project_name_from_path,
    extract_sequence_name_from_path,
    extract_shot_code,
    extract_shot_code_from_path,
    normalize_task_name,
)

# FileManagerS3: mismo flag que el resto de los scripts del panel.
Desarrollo = True

WINDOW_TITLE = "Flow | Triple Check"
SCAN_WORKERS = 12

# ── Log: siempre a archivo, consola apagada (regla del repo) ─────────────────
DEBUG_CONSOLE = False
_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_LOG_PATH = _LOG_DIR / "DebugPy_FlowTripleCheck.log"
_logger = logging.getLogger("LGA_FlowTripleCheck")
_logger.propagate = False


def _reset_log():
    for handler in list(_logger.handlers):
        _logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass
    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(str(_LOG_PATH), mode="w", encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(relativeCreated)8.0f ms  %(message)s"))
        _logger.addHandler(handler)
        _logger.setLevel(logging.INFO)
    except Exception:
        pass


def debug_print(*message):
    text = " ".join(str(m) for m in message)
    try:
        _logger.info(text)
    except Exception:
        pass
    if DEBUG_CONSOLE:
        print(text)


# Los reintentos de Wasabi del core quedan en el mismo log que los de Flow.
core.on_retry = debug_print


# ── Textos visibles (ingles) y tooltips (castellano) ─────────────────────────
STATUS_LABELS = {
    core.ST_ERROR: "Error",
    core.ST_DUPLICATE_IN_FLOW: "Duplicate in Flow",
    core.ST_NOT_IN_FLOW: "Not in Flow",
    core.ST_TASK_NOT_IN_FLOW: "Task not in Flow",
    core.ST_NOT_IN_TIMELINE: "Not in timeline",
    core.ST_MISSING_STORAGE: "Missing in Wasabi",
    core.ST_INCOMPLETE: "Incomplete",
    core.ST_MISNAMED: "Wrong folder",
    core.ST_UPLOAD: "Upload",
    core.ST_DOWNLOAD: "Download",
    core.ST_NOT_IN_FLOW_VERSION: "No Flow version",
    core.ST_STRAY: "Extra folder",
    core.ST_OK: "OK",
    core.ST_NO_VERSIONS: "No versions",
}

STATUS_COLORS = {
    core.ST_ERROR: Color.ERROR_TEXT,
    core.ST_DUPLICATE_IN_FLOW: Color.ERROR_TEXT,
    core.ST_NOT_IN_FLOW: Color.ERROR_TEXT,
    core.ST_TASK_NOT_IN_FLOW: Color.ERROR_TEXT,
    core.ST_NOT_IN_TIMELINE: Color.INFO,
    core.ST_MISSING_STORAGE: Color.WARNING_TEXT,
    core.ST_INCOMPLETE: Color.WARNING_TEXT,
    core.ST_MISNAMED: Color.WARNING_TEXT,
    core.ST_UPLOAD: Color.WARNING_TEXT,
    core.ST_DOWNLOAD: Color.WARNING_TEXT,
    core.ST_NOT_IN_FLOW_VERSION: Color.WARNING_TEXT,
    core.ST_STRAY: Color.WARNING_TEXT,
    core.ST_OK: Color.OK_TEXT,
    core.ST_NO_VERSIONS: Color.TEXT_DIM,
}

TOOLTIPS = {
    "download": "Baja de Wasabi la {version} a la carpeta del shot.",
    "upload": "Sube a Wasabi la {version} local.",
    "only_issues": (
        "Oculta los shots donde Flow, Wasabi y Local coinciden<br>"
        "y los que todavia no tienen versiones."
    ),
    "download_all": (
        "Baja de Wasabi las versiones que faltan en local.<br>"
        "Solo los shots del timeline que se ven en la tabla."
    ),
    "upload_all": (
        "Sube a Wasabi las versiones locales que faltan, de las filas que se ven.<br>"
        "Las que son mas nuevas que Flow se suben de a una, desde su fila."
    ),
    "recheck": "Vuelve a leer Flow, Wasabi y el disco.",
    "goto": "Lleva el timeline a este shot.",
    "keep_on_top": "Mantiene esta ventana arriba de NKS.",
    "task_status_filter": (
        "Muestra solo los shots cuya task esta en ese estado de Flow.<br>"
        "Se suma al filtro de Only issues."
    ),
}

(
    COL_SHOT, COL_GOTO, COL_TASK, COL_TASK_STATUS, COL_FLOW, COL_WASABI, COL_LOCAL,
    COL_STATUS, COL_ACTION, COL_DETAIL,
) = range(10)
# "Sync" y no "Status": al lado de "Task Status" (el estado de la task en
# Flow) dos columnas "Status" se confundian.
HEADERS = ["Shot", "", "Task", "Task Status", "Flow", "Wasabi", "Local", "Sync", "", "Detail"]
ALL_TASK_STATUSES = "All task statuses"
ACTION_CELL_WIDTH = 36
GOTO_CELL_WIDTH = 30
# Ancho de Detail al abrir: si la ventana se achica, el texto pasa a dos o mas
# lineas (DetailDelegate) en vez de cortarse.
DETAIL_MIN_WIDTH = 360

# "Keep on top" persiste como en el Flow Pull, en un INI propio.
_SETTINGS_PATH = Path(os.environ.get("APPDATA") or os.path.expanduser("~")) / "LGA" / "HieroTools" / "TripleCheck.ini"
_SETTINGS_SECTION = "TripleCheckWindow"


def _load_keep_on_top():
    try:
        cfg = configparser.ConfigParser()
        if _SETTINGS_PATH.exists():
            cfg.read(str(_SETTINGS_PATH), encoding="utf-8")
        return cfg.getboolean(_SETTINGS_SECTION, "keep_on_top", fallback=True)
    except Exception as exc:
        debug_print("No se pudo leer keep_on_top: %s" % exc)
        return True


def _save_keep_on_top(value):
    try:
        cfg = configparser.ConfigParser()
        if _SETTINGS_PATH.exists():
            cfg.read(str(_SETTINGS_PATH), encoding="utf-8")
        if not cfg.has_section(_SETTINGS_SECTION):
            cfg.add_section(_SETTINGS_SECTION)
        cfg.set(_SETTINGS_SECTION, "keep_on_top", "true" if value else "false")
        _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(str(_SETTINGS_PATH), "w", encoding="utf-8", newline="\n") as fh:
            cfg.write(fh)
    except Exception as exc:
        debug_print("No se pudo guardar keep_on_top: %s" % exc)


def _set_topmost(widget, on):
    """Topmost con SetWindowPos (helper del Shot Info): sin recrear la ventana."""
    try:
        from LGA_NKS_Shared.LGA_NKS_ShotInfoOnReview import _set_topmost_native

        return _set_topmost_native(widget, on)
    except Exception as exc:
        debug_print("Topmost fallo: %s" % exc)
        return False
GLYPH_SIZE = 12


# ── Recoleccion del timeline (hilo principal) ────────────────────────────────
def _clip_file_path(clip):
    try:
        source = clip.source()
        media = source.mediaSource() if source else None
        infos = media.fileinfos() if media else None
        if infos:
            return infos[0].filename()
    except Exception:
        pass
    return ""


def _project_root_from_path(file_path):
    """`N:/vfx-proja/101/SHOT/...` -> `N:/vfx-proja` (la carpeta VFX-*)."""
    if not file_path:
        return ""
    parts = os.path.normpath(file_path).split(os.sep)
    for idx, part in enumerate(parts):
        if part.upper().startswith("VFX-") and len(part) > 4:
            root = os.sep.join(parts[: idx + 1])
            if root.endswith(":"):
                root += os.sep
            return root
    return ""


def collect_timeline(seq, tasks):
    """Clips de los tracks de task: [{project, shot, seq, task, clip, path, root}].

    Recorre TODOS los tracks que coincidan con cada nombre (prendidos o no):
    en client puede haber varios `_cg_`. Un shot con varios clips en el mismo
    track cuenta una vez.
    """
    track_to_task = {}
    for task in tasks:
        track = exr_track_for_task(task)
        if track:
            track_to_task[track.upper()] = task
    entries = []
    unresolved = []
    seen = set()
    for track in seq.videoTracks():
        task = track_to_task.get(track.name().upper())
        if not task:
            continue
        for clip in track.items():
            if isinstance(clip, hiero.core.EffectTrackItem):
                continue
            path = _clip_file_path(clip)
            base = clean_base_name(os.path.basename(path) if path else clip.name())
            project = extract_project_name_from_path(path) or extract_project_name(base)
            shot = extract_shot_code_from_path(path, project) or extract_shot_code(base)
            if not shot or not project:
                unresolved.append(clip.name())
                continue
            key = (project.upper(), shot.lower(), task)
            if key in seen:
                continue
            seen.add(key)
            entries.append(
                {
                    "project": project,
                    "shot": shot,
                    "seq": extract_sequence_name_from_path(path) or "",
                    "task": task,
                    "clip": clip.name(),
                    "path": path,
                    "root": _project_root_from_path(path),
                }
            )
    return entries, unresolved


# ── Conexiones (worker) ──────────────────────────────────────────────────────
def _flow_connection():
    shared = str(Path(__file__).resolve().parent.parent / "LGA_NKS_Shared")
    if shared not in sys.path:
        sys.path.insert(0, shared)
    import shotgun_api3
    from LGA_NKS_Shared.SecureConfig_Reader import get_flow_credentials

    url, login, password = get_flow_credentials()
    if not (url and login and password):
        raise RuntimeError("Flow credentials not found in PipeSync's secure config.")
    return shotgun_api3.Shotgun(url, login=login, password=password)


def _wasabi_client():
    # boto3 viaja vendorizado en la carpeta del Assignee Panel.
    vendor = str(Path(__file__).resolve().parent.parent / "LGA_NKS_Assignee_Panel_py")
    if vendor not in sys.path:
        sys.path.insert(0, vendor)
    import boto3
    from botocore.config import Config
    from LGA_NKS_Shared.SecureConfig_Reader import get_s3_credentials

    access_key, secret_key, endpoint, region = get_s3_credentials()
    if not (access_key and secret_key and endpoint):
        raise RuntimeError("Wasabi credentials not found in PipeSync's secure config.")
    if not endpoint.startswith("http"):
        endpoint = "https://" + endpoint
    return boto3.client(
        "s3",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        endpoint_url=endpoint,
        region_name=region or None,
        config=Config(
            retries={"max_attempts": 2},
            connect_timeout=10,
            read_timeout=30,
            max_pool_connections=SCAN_WORKERS + 4,
        ),
    )


def _project_folder(work_root, project_key):
    """`<raiz>/VFX-<PROY>` con el caso real si ya existe en el disco."""
    target = "VFX-%s" % project_key
    work_root = str(work_root or "")
    # La AltTPath puede venir como `N:` sin barra, y `N:` + `VFX-X` es una
    # ruta RELATIVA a la carpeta actual de esa unidad, no a su raiz.
    if work_root.endswith(":"):
        work_root += os.sep
    try:
        for name in os.listdir(work_root):
            if name.lower() == target.lower():
                return os.path.normpath(os.path.join(work_root, name))
    except OSError:
        pass
    return os.path.normpath(os.path.join(work_root, target))


def _flow_task_key(content, tasks):
    key = normalize_task_name(str(content or "").strip())
    return key if key in tasks else None


def _with_net_retries(func, describe):
    last = None
    for attempt in range(core.NET_ATTEMPTS):
        try:
            return func()
        except Exception as exc:
            last = exc
            debug_print("Reintento %d de %s: %s" % (attempt + 1, describe, exc))
            if attempt < core.NET_ATTEMPTS - 1:
                time.sleep(core.NET_RETRY_DELAY)
    raise last


# ── Worker ───────────────────────────────────────────────────────────────────
class TripleCheckSignals(QtCore.QObject):
    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)
    progress = QtCore.Signal(str)


class TripleCheckWorker(QtCore.QRunnable):
    def __init__(self, entries, tasks, context_mode):
        super(TripleCheckWorker, self).__init__()
        self.entries = entries
        self.tasks = tuple(tasks)
        self.context_mode = context_mode
        self.signals = TripleCheckSignals()

    def run(self):
        try:
            result = self._run()
            self.signals.finished.emit(result)
        except Exception as exc:
            import traceback

            debug_print("Error en el worker:\n" + traceback.format_exc())
            self.signals.failed.emit(str(exc))

    def _run(self):
        t0 = time.time()
        from LGA_NKS_Shared.LGA_NKS_BucketResolver import resolve_bucket_for_project
        from LGA_NKS_Shared.LGA_NKS_PipeSyncPaths import get_alt_work_root

        by_project = {}
        for entry in self.entries:
            by_project.setdefault(entry["project"].upper(), []).append(entry)

        self.signals.progress.emit("Reading Flow...")
        sg = _with_net_retries(_flow_connection, "conexion a Flow")
        s3 = _wasabi_client()
        rows = []
        notes = []

        for project_key, entries in sorted(by_project.items()):
            project = entries[0]["project"]
            found, flow_shots, flow_stats = _with_net_retries(
                lambda: core.fetch_flow_project(
                    sg, project, lambda c: _flow_task_key(c, self.tasks)
                ),
                "Flow %s" % project,
            )
            if not found and project_key != project:
                # Probar con el nombre en mayusculas antes de rendirse.
                found, flow_shots, flow_stats = _with_net_retries(
                    lambda: core.fetch_flow_project(
                        sg, project_key, lambda c: _flow_task_key(c, self.tasks)
                    ),
                    "Flow %s" % project_key,
                )
            if not found:
                notes.append("Project %s not found in Flow." % project)
            for code, ids in flow_stats.get("duplicates") or []:
                # Todo el proyecto, no solo el timeline: es un error de Flow
                # que conviene ver aunque el shot no este en este corte.
                notes.append(
                    "Duplicate shot in Flow: %s (ids %s)."
                    % (code, ", ".join(str(i) for i in ids))
                )
            debug_print(
                "Flow %s: encontrado=%s shots=%d versions=%s"
                % (project, found, len(flow_shots), flow_stats)
            )

            # La raiz local sale del CONTEXTO (T: studio, N: client, o la
            # AltTPath), igual que en FileManagerS3, y no de la ruta del clip:
            # un timeline de client abierto en contexto studio compararia el
            # Wasabi de studio contra el disco de client y ofreceria subidas
            # que no corresponden.
            local_root = _project_folder(get_alt_work_root(), project_key)
            clip_roots = sorted({e["root"] for e in entries if e["root"]})
            foreign_roots = [
                r for r in clip_roots
                if os.path.normcase(os.path.normpath(r)) != os.path.normcase(local_root)
            ]
            if foreign_roots:
                notes.append(
                    "Timeline media is under %s, but this context works on %s: "
                    "comparing against %s."
                    % (", ".join(foreign_roots), local_root, local_root)
                )
            bucket_info = resolve_bucket_for_project(project) or {}
            bucket = bucket_info.get("bucket") if isinstance(bucket_info, dict) else None
            debug_print("Raiz local: %s | bucket: %s" % (local_root, bucket))
            if not bucket:
                notes.append(
                    "No Wasabi bucket for %s: %s"
                    % (project, (bucket_info or {}).get("warning", ""))
                )

            rows.extend(self._rows_for_project(project, entries, flow_shots, found))
            wasabi_lister = core.WasabiLister(s3, bucket) if bucket else None
            self._scan_rows(
                [r for r in rows if r["project"] == project],
                core.LocalLister(local_root),
                wasabi_lister,
            )
            if wasabi_lister is not None and wasabi_lister.dead:
                notes.append(wasabi_lister.dead)
            for row in rows:
                if row["project"] == project:
                    row["local_root"] = local_root

        for row in rows:
            core.classify(row)
        debug_print("Total: %d filas en %.1f s" % (len(rows), time.time() - t0))
        return {"rows": rows, "notes": notes, "seconds": time.time() - t0}

    def _rows_for_project(self, project, entries, flow_shots, found):
        rows = []
        timeline_keys = set()
        scope_sequences = set()
        for entry in entries:
            shot_flow = flow_shots.get(entry["shot"].lower())
            task_flow = (shot_flow or {}).get("tasks", {}).get(entry["task"])
            # La secuencia sale de Flow, como en PipeSync; la de la ruta del
            # clip queda de respaldo para los shots que Flow no tiene.
            seq = (shot_flow or {}).get("sequence", "") or entry["seq"]
            if entry["seq"]:
                scope_sequences.add(entry["seq"].lower())
            if shot_flow and shot_flow.get("sequence"):
                scope_sequences.add(shot_flow["sequence"].lower())
            timeline_keys.add((entry["shot"].lower(), entry["task"]))
            rows.append(
                self._new_row(project, entry["shot"], entry["task"], seq, True,
                              shot_flow, task_flow, entry["clip"])
            )
        if not found:
            # Sin el proyecto en Flow no se sabe que shot falta en el timeline.
            for row in rows:
                row["flow_unknown"] = True
            return rows
        for shot_lower, shot_flow in sorted(flow_shots.items()):
            if (shot_flow.get("sequence") or "").lower() not in scope_sequences:
                continue
            if (shot_flow.get("status") or "").lower() in core.OMITTED_SHOT_STATUSES:
                continue
            for task, task_flow in sorted(shot_flow["tasks"].items()):
                if (shot_lower, task) in timeline_keys:
                    continue
                if (task_flow.get("status") or "").lower() in core.OMITTED_SHOT_STATUSES:
                    continue
                rows.append(
                    self._new_row(project, shot_flow["code"], task,
                                  shot_flow.get("sequence", ""), False,
                                  shot_flow, task_flow, "")
                )
        return rows

    @staticmethod
    def _new_row(project, shot, task, seq, in_timeline, shot_flow, task_flow, clip):
        is_cg = task == CG_TASK_NAME
        versions = (task_flow or {}).get("versions", [])
        flow_number, flow_code = None, ""
        if is_cg:
            latest = core.flow_latest_cg(versions, shot)
            if latest:
                flow_code = latest.get("version_code") or ""
                flow_number = core.version_number(flow_code)
        else:
            flow_number, flow_code = core.flow_highest(versions, shot)
        return {
            "project": project,
            "shot": shot,
            "task": task,
            "seq": seq,
            "clip": clip,
            "in_timeline": in_timeline,
            "shot_in_flow": shot_flow is not None,
            "task_in_flow": task_flow is not None,
            "flow_status": (task_flow or {}).get("status", ""),
            "is_cg": is_cg,
            "flow": flow_number,
            "flow_code": flow_code,
            "flow_versions": len(versions),
            "flow_shot_ids": list((shot_flow or {}).get("ids") or []),
        }

    def _scan_rows(self, rows, local_lister, wasabi_lister):
        cache = {}
        lock = threading.Lock()
        done = [0]
        total = len(rows)

        def _scan(row):
            folder = task_folder_name(row["task"])
            cg_code = row["flow_code"] if row["is_cg"] else None
            for name, lister in (("local", local_lister), ("wasabi", wasabi_lister)):
                if lister is None:
                    scan = core.empty_scan()
                    scan["error"] = "El proyecto no tiene bucket de Wasabi."
                    row[name] = scan
                    continue
                parts, err = core.resolve_shot_parts(cache, lister, row["seq"], row["shot"])
                if err:
                    scan = core.empty_scan()
                    scan["error"] = err
                else:
                    scan = core.scan_task(lister, parts, folder, cg_code)
                row[name] = scan
            if not row["is_cg"]:
                core.compare_content(row, local_lister, wasabi_lister)
            with lock:
                done[0] += 1
                if done[0] % 10 == 0 or done[0] == total:
                    self.signals.progress.emit("Scanning %d / %d..." % (done[0], total))
            debug_print(
                "%s %s | flow=%s wasabi=%s/%s local=%s/%s contenido=%s %s %s"
                % (
                    row["shot"], row["task"], row["flow_code"] or row["flow"],
                    row["wasabi"].get("name"), row["wasabi"].get("number"),
                    row["local"].get("name"), row["local"].get("number"),
                    row.get("content"),
                    row["wasabi"].get("error", ""), row["local"].get("error", ""),
                )
            )

        # La raiz de cada lister se lista una vez antes del pool, para que los
        # 12 hilos no la pidan todos juntos.
        for lister in (local_lister, wasabi_lister):
            if lister is not None and rows:
                core.resolve_shot_parts(cache, lister, rows[0]["seq"], rows[0]["shot"])
        with ThreadPoolExecutor(max_workers=SCAN_WORKERS) as pool:
            list(pool.map(_scan, rows))


# ── Presentacion de una fila ─────────────────────────────────────────────────
def _short_name(name, shot):
    """`PROJA_1005_0500_VND_lighting_v016_SeqRef` -> `lighting_v016_SeqRef`."""
    if name and shot and name.lower().startswith(shot.lower() + "_"):
        return name[len(shot) + 1:]
    return name or "-"


def version_text(row, source):
    if source == "flow":
        if not row["task_in_flow"]:
            return "-"
        if row["is_cg"]:
            return _short_name(row["flow_code"], row["shot"]) if row["flow_code"] else "-"
        return core.format_version(row["flow"]) if row["flow"] is not None else "-"
    scan = row.get(source) or {}
    if scan.get("error"):
        return "?"
    if row["is_cg"] and row["flow_code"]:
        return "Yes" if scan.get("present") else "No"
    if scan.get("number") is None:
        return "-"
    return core.format_version(scan["number"])


def version_color(row, source):
    """Color de la celda: lo que esta atrasado respecto de la mas alta."""
    scan = row.get(source) or {}
    if source != "flow" and scan.get("error"):
        return Color.ERROR_TEXT
    if source != "flow" and scan.get("foreign"):
        return Color.WARNING_TEXT
    if row["is_cg"]:
        if source != "flow" and row["flow_code"] and not scan.get("present"):
            return Color.WARNING_TEXT
        return None
    values = {
        "flow": row.get("flow") or 0,
        "wasabi": (row.get("wasabi") or {}).get("number") or 0,
        "local": (row.get("local") or {}).get("number") or 0,
    }
    if source == "flow" and not row["task_in_flow"]:
        return Color.TEXT_DIM
    top = max(values.values())
    if top and values[source] < top:
        return Color.WARNING_TEXT
    return None


def detail_text(row):
    """Una oracion por estado. En castellano (pedido de Lega, 2026-11-20): es
    la explicacion de la fila, no un rotulo de la UI."""
    parts = []
    w = row.get("wasabi") or {}
    l = row.get("local") or {}
    for status in row.get("statuses", []):
        if status == core.ST_ERROR:
            for label, scan in (("Wasabi", w), ("Local", l)):
                if scan.get("error"):
                    parts.append("%s: %s" % (label, scan["error"]))
        elif status == core.ST_DUPLICATE_IN_FLOW:
            ids = row.get("flow_shot_ids") or []
            parts.append(
                "En Flow hay %d shots con este nombre (ids %s): acá se suman las "
                "tasks y versiones de todos. Borrá o renombrá en Flow el que sobra."
                % (len(ids), ", ".join(str(i) for i in ids))
            )
        elif status == core.ST_NOT_IN_FLOW:
            parts.append("El shot no existe en Flow.")
        elif status == core.ST_TASK_NOT_IN_FLOW:
            parts.append("El shot no tiene la task %s en Flow." % task_display_name(row["task"]))
        elif status == core.ST_NOT_IN_TIMELINE:
            track = exr_track_for_task(row["task"])
            if core.has_no_versions(row):
                # Shot creado y asignado que todavia no se empezo: lo que
                # falta es armarlo en el timeline.
                parts.append(
                    "Está en Flow pero no en el track %s. Todavía no hay nada "
                    "publicado: falta poner el plate y la v000 en el timeline." % track
                )
            else:
                parts.append("Está en Flow pero no en el track %s." % track)
        elif status == core.ST_MISSING_STORAGE:
            version = (
                _short_name(row["flow_code"], row["shot"]) if row["is_cg"]
                else core.format_version(row["flow"])
            )
            parts.append("Flow tiene la %s, que no está ni en Wasabi ni en local." % version)
        elif status == core.ST_DOWNLOAD:
            parts.append("Wasabi tiene la %s, que no está en el disco local." % (w.get("name") or "-"))
        elif status == core.ST_UPLOAD:
            parts.append("En local está la %s, que no está en Wasabi." % (l.get("name") or "-"))
        elif status == core.ST_NOT_IN_FLOW_VERSION:
            top = max((w.get("number") or 0), (l.get("number") or 0))
            parts.append("La %s no tiene Version en Flow." % core.format_version(top))
        elif status == core.ST_INCOMPLETE:
            content = row.get("content") or {}
            l_n, l_b = content.get("local", (0, 0))
            w_n, w_b = content.get("wasabi", (0, 0))
            if row.get("incomplete") == "differs":
                parts.append(
                    "%s tiene los mismos %d archivos en los dos lados, pero el peso "
                    "total difiere en %s." % (l.get("name"), l_n, _human_size(abs(l_b - w_b)))
                )
            else:
                parts.append(
                    "%s está incompleta: %d archivos en local y %d en Wasabi."
                    % (l.get("name"), l_n, w_n)
                )
        elif status == core.ST_MISNAMED:
            for label, scan in (("Wasabi", w), ("local", l)):
                if scan.get("foreign"):
                    parts.append(
                        "En %s, la versión más alta del publish es %s, que lleva el "
                        "nombre de otro shot." % (label, scan.get("name"))
                    )
        elif status == core.ST_STRAY:
            if core.ST_OK in row.get("statuses", []):
                parts.append("Las versiones coinciden.")
            parts.append(_stray_text(w.get("strays") or [], l.get("strays") or []))
    if row.get("upload_blocked") and not l.get("foreign"):
        parts.append(row["upload_blocked"])
    if row.get("upload_needs_confirm"):
        parts.append("Revisá el nombre de la carpeta local antes de subirla.")
    return " ".join(parts)


def _stray_text(wasabi_strays, local_strays):
    """Carpetas de otro shot que sobran en el publish, diciendo de que lado."""
    names = sorted(set(wasabi_strays) | set(local_strays), key=str.lower)
    pieces = []
    for name in names:
        sides = [
            side for side, strays in (("Wasabi", wasabi_strays), ("local", local_strays))
            if name in strays
        ]
        pieces.append("%s (en %s)" % (name, " y en ".join(sides)))
    return (
        "En el publish sobra%s %s de otro shot: %s. Revisá si es una copia de más."
        % (
            "" if len(names) == 1 else "n",
            "una carpeta" if len(names) == 1 else "carpetas",
            ", ".join(pieces),
        )
    )


def _human_size(size):
    size = float(size or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return "%.1f %s" % (size, unit) if unit != "B" else "%d B" % size
        size /= 1024.0
    return "%.1f GB" % size


# ── Glifos de las celdas de accion ───────────────────────────────────────────
# Flecha de descarga: el mismo glifo que el boton de EXR Publish de PipeSync y
# la columna de descarga del Flow Pull (download.svg, viewBox 358). La de
# subida es la misma flecha dada vuelta, con la barra abajo igual.
_GLYPH_VIEWBOX = 358.0
_GLYPH_BAR = (50.5, 306.5, 257.0, 36.7)
_GLYPH_ARROW_DOWN = (
    (307.5, 141.3), (234.1, 141.3), (234.1, 12.8), (124.0, 12.8),
    (124.0, 141.3), (50.5, 141.3), (179.0, 269.8),
)


def _glyph_icon(color_hex, upward=False, size=GLYPH_SIZE):
    screen = QtWidgets.QApplication.primaryScreen()
    dpr = screen.devicePixelRatio() if screen else 1.0
    pixmap = QtGui.QPixmap(int(round(size * dpr)), int(round(size * dpr)))
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(Qt.transparent)
    arrow = _GLYPH_ARROW_DOWN
    if upward:
        # Espejo vertical de la flecha dentro del espacio 12.8-269.8.
        arrow = tuple((x, 282.6 - y) for x, y in arrow)
    path = QtGui.QPainterPath()
    path.addRect(QtCore.QRectF(*_GLYPH_BAR))
    path.addPolygon(QtGui.QPolygonF([QtCore.QPointF(x, y) for x, y in arrow]))
    path.closeSubpath()
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
    painter.scale(size / _GLYPH_VIEWBOX, size / _GLYPH_VIEWBOX)
    painter.fillPath(path, QtGui.QColor(color_hex))
    painter.end()
    return QtGui.QIcon(pixmap)


def _goto_icon(color_hex, size=GLYPH_SIZE):
    """Mira (aro y punto): "ubicar en el timeline"."""
    screen = QtWidgets.QApplication.primaryScreen()
    dpr = screen.devicePixelRatio() if screen else 1.0
    pixmap = QtGui.QPixmap(int(round(size * dpr)), int(round(size * dpr)))
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(Qt.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
    color = QtGui.QColor(color_hex)
    pen = QtGui.QPen(color)
    pen.setWidthF(1.4)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    c = size / 2.0
    painter.drawEllipse(QtCore.QPointF(c, c), c - 1.6, c - 1.6)
    painter.setPen(Qt.NoPen)
    painter.setBrush(color)
    painter.drawEllipse(QtCore.QPointF(c, c), size * 0.17, size * 0.17)
    painter.end()
    return QtGui.QIcon(pixmap)


# ── FileManagerS3 ────────────────────────────────────────────────────────────
def _launch_filemanagers3(cli_args):
    from LGA_NKS_Shared.LGA_NKS_FileManagerS3Launcher import (
        build_filemanagers3_command,
        resolve_context_mode,
    )

    cmd = build_filemanagers3_command(
        cli_args,
        desarrollo=Desarrollo,
        script_dir=Path(__file__).parent,
        context_mode=resolve_context_mode(),
    )
    debug_print("FileManagerS3: %s" % " ".join(cmd))
    subprocess.Popen(cmd, shell=False)


def download_rows(rows):
    paths = []
    for row in rows:
        target = core.download_target(row.get("local_root", ""), row)
        if target and target not in paths:
            paths.append(target)
    if paths:
        _launch_filemanagers3(["--download"] + paths)
    return paths


# --upload acepta UNA carpeta por llamada. Cada llamada extra le pasa el
# comando a la instancia abierta de FileManagerS3 por su canal interno, que
# solo espera 500 ms y no reintenta: con la app cerrada, la primera llamada
# todavia esta arrancando y las siguientes se pierden con un cartel. Por eso la
# primera sale ya y el resto espera a que la app termine de abrir, de a una.
UPLOAD_FIRST_DELAY_MS = 9000
UPLOAD_STEP_MS = 2500


def upload_rows(rows):
    paths = []
    for row in rows:
        source = core.upload_source(
            row.get("local_root", ""), row, task_folder_name(row["task"])
        )
        if source and source not in paths:
            paths.append(source)
    if not paths:
        return paths
    _launch_filemanagers3(["--upload", paths[0]])
    for index, path in enumerate(paths[1:]):
        delay = UPLOAD_FIRST_DELAY_MS + index * UPLOAD_STEP_MS
        QtCore.QTimer.singleShot(
            delay, lambda p=path: _launch_upload_later(p)
        )
    return paths


def _launch_upload_later(path):
    try:
        _launch_filemanagers3(["--upload", path])
    except Exception as exc:
        debug_print("Upload diferido fallido %s: %s" % (path, exc))


def bulk_download_rows(rows):
    """Filas que entran en Download all.

    Solo las del timeline: un shot que no esta en el timeline se baja de a uno,
    si se quiere. Sin esto, en client Download all bajaria las entregas de
    todos los shots de la secuencia.
    """
    return [r for r in rows if r["can_download"] and not r["can_upload"] and r["in_timeline"]]


def bulk_upload_rows(rows):
    """Filas que entran en Upload all: las que no piden confirmacion.

    Una local mas nueva que Flow se sube de a una, con pregunta: en client
    suele ser una carpeta mal nombrada.
    """
    return [r for r in rows if r["can_upload"] and not r.get("upload_needs_confirm")]


# ── Columna Detail ───────────────────────────────────────────────────────────
class OneLineDelegate(QtWidgets.QStyledItemDelegate):
    """Las demas columnas piden una sola fila de ROW_HEIGHT.

    El alto de fila es automatico (ResizeToContents toma el maximo de todas
    las columnas): con el padding de la hoja, una celda comun pedia 28 px y
    las filas de una linea quedaban mas altas que en el resto de las tablas.
    """

    def sizeHint(self, option, index):
        hint = super(OneLineDelegate, self).sizeHint(option, index)
        return QtCore.QSize(hint.width(), Metric.ROW_HEIGHT)


class CellButton(QtWidgets.QPushButton):
    """Boton de celda (ir al timeline, Download/Upload) que pide una fila.

    Su sizeHint con la hoja da 28 px y el alto automatico de la fila lo
    toma en cuenta. No se limita con setMaximumHeight: en una fila alta
    (Detail en varias lineas) el boton tiene que seguir llenando la celda.
    """

    def sizeHint(self):
        hint = super(CellButton, self).sizeHint()
        return QtCore.QSize(hint.width(), Metric.ROW_HEIGHT)


class DetailDelegate(QtWidgets.QStyledItemDelegate):
    """Dibuja Detail con salto de linea propio, sin depender del estilo.

    En NKS el estilo del host (un QProxyStyle de Foundry) ignora el wordWrap
    de la tabla y corta el texto con puntos suspensivos; en el harness, con el
    estilo por defecto, si partia. Por eso el texto se arma con QTextLayout:
    parte por palabra y, si un nombre largo (`SHOT_comp_v005`) no entra en el
    ancho, en cualquier punto. sizeHint() devuelve el alto que necesita, y el
    header vertical en ResizeToContents lo recalcula al cambiar el ancho.
    """

    PAD_X = 6  # el padding de ::item de Style.TABLE
    PAD_Y = 2  # una linea da 24 px, el ROW_HEIGHT del resto de las tablas

    def _layout(self, text, font, width):
        layout = QtGui.QTextLayout(text or "", font)
        option = QtGui.QTextOption()
        option.setWrapMode(QtGui.QTextOption.WrapAtWordBoundaryOrAnywhere)
        layout.setTextOption(option)
        layout.beginLayout()
        height = 0.0
        while True:
            line = layout.createLine()
            if not line.isValid():
                break
            line.setLineWidth(max(10.0, float(width)))
            line.setPosition(QtCore.QPointF(0.0, height))
            height += line.height()
        layout.endLayout()
        return layout, height

    def _text_width(self, index):
        view = self.parent()
        return view.columnWidth(index.column()) - 2 * self.PAD_X

    def sizeHint(self, option, index):
        _layout, height = self._layout(index.data() or "", option.font, self._text_width(index))
        return QtCore.QSize(
            self.parent().columnWidth(index.column()),
            max(Metric.ROW_HEIGHT, int(height + 0.999) + 2 * self.PAD_Y),
        )

    def paint(self, painter, option, index):
        opt = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        text = opt.text
        opt.text = ""
        # Fondo y seleccion los pinta el estilo (con la hoja de la tabla).
        widget = opt.widget
        style = widget.style() if widget else QtWidgets.QApplication.style()
        style.drawControl(QtWidgets.QStyle.CE_ItemViewItem, opt, painter, widget)
        rect = opt.rect.adjusted(self.PAD_X, self.PAD_Y, -self.PAD_X, -self.PAD_Y)
        layout, height = self._layout(text, opt.font, rect.width())
        if opt.state & QtWidgets.QStyle.State_Selected:
            color = QtGui.QColor(Color.TEXT_STRONG)
        else:
            brush = index.data(Qt.ForegroundRole)
            color = brush.color() if isinstance(brush, QtGui.QBrush) else QtGui.QColor(Color.TEXT)
        painter.save()
        painter.setClipRect(opt.rect)
        painter.setPen(color)
        top = rect.top() + max(0.0, (rect.height() - height) / 2.0)
        layout.draw(painter, QtCore.QPointF(rect.left(), top))
        painter.restore()


# ── Ventana ──────────────────────────────────────────────────────────────────
class TripleCheckDialog(QtWidgets.QDialog):
    def __init__(self, result, sequence_name, rerun, parent=None):
        super(TripleCheckDialog, self).__init__(parent)
        self.setWindowTitle(WINDOW_TITLE)
        self.setModal(False)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setStyleSheet(Style.FORM)
        self.setMinimumWidth(980)
        # Primero los shots del timeline, por importancia; despues los de Flow
        # que no estan en el timeline, que suelen ser muchos y menos urgentes.
        self.default_rows = sorted(
            result["rows"],
            key=lambda r: (
                not r["in_timeline"],
                core.STATUS_PRIORITY.index(r["status"]),
                r["shot"].lower(),
                r["task"],
            ),
        )
        self.rows = list(self.default_rows)
        self.catalog = get_task_status_dict()
        self.sort_column = None
        self.sort_order = Qt.AscendingOrder
        self.keep_on_top = _load_keep_on_top()
        self.rerun = rerun
        self._build(result, sequence_name)
        apply_ui_font(self)
        self._apply_filter()
        self._fit_columns()

    # -- armado
    def _build(self, result, sequence_name):
        layout = QtWidgets.QVBoxLayout(self)
        m = Metric.WINDOW_MARGIN
        layout.setContentsMargins(m, m, m, m)
        layout.setSpacing(Metric.SPACING)

        title = QtWidgets.QLabel("Triple Check  ·  %s" % sequence_name)
        title.setProperty("lgaTitle", True)
        layout.addWidget(title)

        summary = QtWidgets.QLabel(self._summary_text(result))
        summary.setTextFormat(Qt.RichText)
        summary.setWordWrap(True)
        layout.addWidget(summary)

        options = QtWidgets.QHBoxLayout()
        self.only_issues = QtWidgets.QCheckBox("Only issues")
        self.only_issues.setProperty("lgaLabeled", True)
        self.only_issues.setChecked(True)
        self.only_issues.toggled.connect(self._apply_filter)
        set_custom_tooltip(self.only_issues, TOOLTIPS["only_issues"])
        options.addWidget(self.only_issues)
        self.status_filter = QtWidgets.QComboBox()
        self.status_filter.setStyleSheet(Style.COMBO)
        self._fill_status_filter()
        self.status_filter.currentIndexChanged.connect(self._apply_filter)
        set_custom_tooltip(self.status_filter, TOOLTIPS["task_status_filter"])
        options.addWidget(self.status_filter)
        options.addStretch(1)
        self.keep_on_top_chk = QtWidgets.QCheckBox("Keep on top")
        self.keep_on_top_chk.setProperty("lgaLabeled", True)
        self.keep_on_top_chk.setChecked(self.keep_on_top)
        self.keep_on_top_chk.toggled.connect(self._set_keep_on_top)
        set_custom_tooltip(self.keep_on_top_chk, TOOLTIPS["keep_on_top"])
        options.addWidget(self.keep_on_top_chk)
        layout.addLayout(options)

        self.table = QtWidgets.QTableWidget(len(self.rows), len(HEADERS), self)
        self.table.setHorizontalHeaderLabels(HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setStyleSheet(Style.TABLE)
        # Detail se lee entero: lo dibuja DetailDelegate con salto de linea y
        # cada fila toma el alto que necesita (ResizeToContents se recalcula
        # solo al cambiar el ancho de Detail o de la ventana).
        self.table.setWordWrap(False)
        self.table.setItemDelegate(OneLineDelegate(self.table))
        self.table.setItemDelegateForColumn(COL_DETAIL, DetailDelegate(self.table))
        rows_header = self.table.verticalHeader()
        rows_header.setMinimumSectionSize(Metric.ROW_HEIGHT)
        # El header vertical esta oculto, pero en ResizeToContents igual
        # aporta su propio alto (el numero de fila con el padding de la hoja,
        # 28 px). Sin padding, una fila de una linea queda en ROW_HEIGHT.
        rows_header.setStyleSheet("QHeaderView::section { padding: 0px; border: none; }")
        rows_header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        # Orden propio (no el de QTableWidget): la fila de la tabla sigue
        # siendo el indice en self.rows, los numeros de version ordenan como
        # numeros y el estado de la task sigue el orden del flujo de trabajo.
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(False)
        header.sectionClicked.connect(self._on_header_clicked)
        self._fill_table()
        layout.addWidget(self.table, 1)

        self.empty_label = QtWidgets.QLabel(
            "Everything matches: Flow, Wasabi and local have the same versions."
        )
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setVisible(False)
        layout.addWidget(self.empty_label, 1)

        buttons = QtWidgets.QHBoxLayout()
        self.recheck_btn = self._secondary("Recheck", self._recheck, TOOLTIPS["recheck"])
        buttons.addWidget(self.recheck_btn)
        buttons.addStretch(1)
        self.download_all_btn = self._secondary("", self._download_all, TOOLTIPS["download_all"])
        self.upload_all_btn = self._secondary("", self._upload_all, TOOLTIPS["upload_all"])
        buttons.addWidget(self.download_all_btn)
        buttons.addWidget(self.upload_all_btn)
        close = self._secondary("Close", self.close, None)
        buttons.addWidget(close)
        layout.addLayout(buttons)

    def _secondary(self, text, slot, tip):
        button = QtWidgets.QPushButton(text)
        button.setStyleSheet(Style.BTN_SECONDARY)
        button.setFixedHeight(Metric.BUTTON_HEIGHT)
        button.setAutoDefault(False)
        button.clicked.connect(slot)
        if tip:
            set_custom_tooltip(button, tip)
        return button

    def _summary_text(self, result):
        counts = {}
        for row in result["rows"]:
            for status in row["statuses"]:
                counts[status] = counts.get(status, 0) + 1
        shots = len({(r["project"], r["shot"].lower()) for r in result["rows"] if r["in_timeline"]})
        pieces = ["%s shots in the timeline" % emphasis(str(shots))]
        for status in core.STATUS_PRIORITY:
            if status in counts and status not in core.QUIET_STATUSES:
                pieces.append(
                    "<span style='color:%s'>%d %s</span>"
                    % (STATUS_COLORS[status], counts[status], STATUS_LABELS[status])
                )
        ok = counts.get(core.ST_OK, 0)
        pieces.append("%d OK" % ok)
        text = "  ·  ".join(pieces)
        text += "<br><span style='color:%s'>Checked in %.1f s.</span>" % (
            Color.TEXT_DIM, result.get("seconds", 0)
        )
        for note in result.get("notes", []):
            text += "<br><span style='color:%s'>%s</span>" % (Color.ERROR_TEXT, note)
        return text

    def _item(self, text, color=None, align=None):
        item = QtWidgets.QTableWidgetItem(text)
        if color:
            item.setForeground(QtGui.QBrush(QtGui.QColor(color)))
        if align is not None:
            item.setTextAlignment(align)
        return item

    def _status_info(self, row):
        return core.task_status_info(row.get("flow_status") or "", self.catalog)

    def _task_status_item(self, row):
        name, color, _order = self._status_info(row)
        if not name:
            return self._item("-", Color.TEXT_DIM, int(Qt.AlignCenter))
        item = self._item(name, align=int(Qt.AlignCenter))
        if color:
            # Como la columna de estado del Flow Pull: el color del estado de
            # Flow de fondo (es dato) y el texto claro u oscuro segun el fondo.
            background = QtGui.QColor(color)
            luminance = (
                0.299 * background.red() + 0.587 * background.green() + 0.114 * background.blue()
            )
            item.setBackground(QtGui.QBrush(background))
            item.setForeground(QtGui.QBrush(QtGui.QColor(
                Color.TEXT_ON_COLOR if luminance < 128 else Color.WINDOW
            )))
        return item

    def _fill_status_filter(self):
        counts = {}
        for row in self.rows:
            code = row.get("flow_status") or ""
            counts[code] = counts.get(code, 0) + 1
        self.status_filter.addItem(ALL_TASK_STATUSES, None)
        for code in sorted(counts, key=lambda c: core.task_status_info(c, self.catalog)[2]):
            name = core.task_status_info(code, self.catalog)[0] or "No task in Flow"
            self.status_filter.addItem("%s (%d)" % (name, counts[code]), code)

    def _fill_table(self):
        self.table.setRowCount(0)
        self.table.setRowCount(len(self.rows))
        for index, row in enumerate(self.rows):
            self._fill_row(index, row)

    def _fill_row(self, index, row):
        center = int(Qt.AlignCenter)
        self.table.setItem(index, COL_SHOT, self._item(row["shot"]))
        self.table.setItem(index, COL_TASK, self._item(task_display_name(row["task"])))
        self.table.setItem(index, COL_TASK_STATUS, self._task_status_item(row))
        for col, source in ((COL_FLOW, "flow"), (COL_WASABI, "wasabi"), (COL_LOCAL, "local")):
            self.table.setItem(
                index, col,
                self._item(version_text(row, source), version_color(row, source), center),
            )
        label = STATUS_LABELS[row["status"]]
        if row["status"] == core.ST_INCOMPLETE and row.get("incomplete") == "differs":
            label = "Size differs"
        self.table.setItem(
            index, COL_STATUS, self._item(label, STATUS_COLORS[row["status"]])
        )
        self.table.setItem(
            index, COL_DETAIL,
            self._item(detail_text(row), Color.TEXT_DIM, int(Qt.AlignLeft | Qt.AlignVCenter)),
        )
        self._set_goto_cell(index, row)
        self._set_action_cell(index, row)

    def _set_goto_cell(self, index, row):
        item = QtWidgets.QTableWidgetItem("")
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        self.table.setItem(index, COL_GOTO, item)
        if not row["in_timeline"]:
            return
        button = CellButton()
        button.setMinimumWidth(GOTO_CELL_WIDTH)
        button.setCursor(Qt.PointingHandCursor)
        button.setAutoDefault(False)
        button.setFocusPolicy(Qt.NoFocus)
        # Sin caja, como la celda de accion pero sin el violeta: navegar no es
        # la accion de la fila.
        button.setStyleSheet(
            Style.BTN_ICON
            + "QPushButton { background-color: transparent; border: none;"
            " border-radius: 0px; padding: 0px; }"
            + " QPushButton:hover { background-color: %s; }" % Color.SURFACE_HOVER
        )
        button.setIcon(_goto_icon(Color.TEXT))
        button.setIconSize(QtCore.QSize(GLYPH_SIZE, GLYPH_SIZE))
        set_custom_tooltip(button, TOOLTIPS["goto"])
        button.clicked.connect(lambda _c=False, r=row: self._goto_row(r))
        self.table.setCellWidget(index, COL_GOTO, button)

    def _set_action_cell(self, index, row):
        item = QtWidgets.QTableWidgetItem("")
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        self.table.setItem(index, COL_ACTION, item)
        # Upload primero: si la local es mas nueva que Wasabi no hay nada que
        # bajar (las dos condiciones no pueden darse juntas).
        if row["can_upload"]:
            upward, version, handler = True, (row["local"].get("name") or ""), self._upload_row
        elif row["can_download"]:
            upward, version, handler = False, (row["wasabi"].get("name") or ""), self._download_row
        else:
            return
        item.setBackground(QtGui.QBrush(QtGui.QColor(Color.ACCENT)))
        button = CellButton()
        button.setMinimumWidth(ACTION_CELL_WIDTH)
        button.setCursor(Qt.PointingHandCursor)
        button.setAutoDefault(False)
        button.setFocusPolicy(Qt.NoFocus)
        # Como la celda de descarga del Flow Pull: BTN_ICON sin caja, el fondo
        # violeta lo pone el item y el hover el violeta claro.
        button.setStyleSheet(
            Style.BTN_ICON
            + "QPushButton { background-color: transparent; border: none;"
            " border-radius: 0px; padding: 0px; }"
            + " QPushButton:hover { background-color: %s; }" % Color.ACCENT_HOVER
        )
        button.setIcon(_glyph_icon(Color.TEXT_ON_ACCENT, upward=upward))
        button.setIconSize(QtCore.QSize(GLYPH_SIZE, GLYPH_SIZE))
        tip = TOOLTIPS["upload" if upward else "download"].format(
            version=_short_name(version, row["shot"])
        )
        set_custom_tooltip(button, tip)
        button.clicked.connect(lambda _c=False, r=row: handler(r))
        self.table.setCellWidget(index, COL_ACTION, button)

    def _fit_columns(self):
        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(COL_ACTION, ACTION_CELL_WIDTH)
        self.table.setColumnWidth(COL_GOTO, GOTO_CELL_WIDTH)
        for col in (COL_FLOW, COL_WASABI, COL_LOCAL):
            self.table.setColumnWidth(col, max(self.table.columnWidth(col), 64))
        visible = sum(1 for i in range(self.table.rowCount()) if not self.table.isRowHidden(i))
        height = self.table.horizontalHeader().sizeHint().height() + self.table.frameWidth() * 2
        height += Metric.ROW_HEIGHT * min(max(visible, 1), 22)
        self.table.setMinimumHeight(height)
        width = sum(self.table.columnWidth(c) for c in range(len(HEADERS) - 1)) + DETAIL_MIN_WIDTH
        self.resize(max(self.minimumWidth(), min(width, 1500)), self.sizeHint().height())

    def showEvent(self, event):
        super(TripleCheckDialog, self).showEvent(event)
        if self.keep_on_top:
            # Despues del show, como en el Flow Pull: si no, Qt pisa el topmost.
            QtCore.QTimer.singleShot(0, lambda: _set_topmost(self, True))

    def _set_keep_on_top(self, value):
        self.keep_on_top = bool(value)
        _save_keep_on_top(self.keep_on_top)
        if not _set_topmost(self, self.keep_on_top):
            flags = self.windowFlags()
            if self.keep_on_top:
                flags |= Qt.WindowStaysOnTopHint
            else:
                flags &= ~Qt.WindowStaysOnTopHint
            geometry = self.geometry()
            self.setWindowFlags(flags)
            self.setGeometry(geometry)
            self.show()
        debug_print("Keep on top: %s" % self.keep_on_top)

    # -- filtro y botones masivos
    def _visible_rows(self):
        return [
            self.rows[i] for i in range(self.table.rowCount()) if not self.table.isRowHidden(i)
        ]

    # -- orden
    def _sort_key(self, column):
        def _number(row, source):
            if source == "flow":
                value = row.get("flow") if row.get("task_in_flow") else None
            else:
                value = (row.get(source) or {}).get("number")
            return -1 if value is None else value

        def key(row):
            tie = (row["shot"].lower(), row["task"])
            if column == COL_TASK:
                return (row["task"],) + tie
            if column == COL_TASK_STATUS:
                return (self._status_info(row)[2],) + tie
            if column in (COL_FLOW, COL_WASABI, COL_LOCAL):
                source = {COL_FLOW: "flow", COL_WASABI: "wasabi", COL_LOCAL: "local"}[column]
                return (_number(row, source),) + tie
            if column == COL_STATUS:
                return (core.STATUS_PRIORITY.index(row["status"]),) + tie
            if column == COL_ACTION:
                return (0 if row["can_upload"] else 1 if row["can_download"] else 2,) + tie
            if column == COL_DETAIL:
                return (detail_text(row).lower(),) + tie
            return tie

        return key

    def _on_header_clicked(self, column):
        if column == self.sort_column:
            if self.sort_order == Qt.DescendingOrder:
                # Tercer click: vuelve al orden de entrada (por importancia).
                self.sort_column = None
            else:
                self.sort_order = Qt.DescendingOrder
        else:
            self.sort_column, self.sort_order = column, Qt.AscendingOrder
        header = self.table.horizontalHeader()
        if self.sort_column is None:
            self.rows = list(self.default_rows)
            header.setSortIndicatorShown(False)
        else:
            self.rows = sorted(
                self.default_rows,
                key=self._sort_key(self.sort_column),
                reverse=self.sort_order == Qt.DescendingOrder,
            )
            header.setSortIndicatorShown(True)
            header.setSortIndicator(self.sort_column, self.sort_order)
        debug_print("Orden: columna=%s descendente=%s" % (
            self.sort_column, self.sort_order == Qt.DescendingOrder))
        self.table.clearSelection()
        self._fill_table()
        self._apply_filter()

    def _apply_filter(self):
        only = self.only_issues.isChecked()
        wanted = self.status_filter.currentData()
        visible = 0
        for index, row in enumerate(self.rows):
            hide = only and not core.is_issue(row)
            if wanted is not None and (row.get("flow_status") or "") != wanted:
                hide = True
            self.table.setRowHidden(index, hide)
            visible += 0 if hide else 1
        self.table.setVisible(visible > 0)
        self.empty_label.setVisible(visible == 0)
        downloads = len(bulk_download_rows(self._visible_rows()))
        uploads = len(bulk_upload_rows(self._visible_rows()))
        self.download_all_btn.setText("Download all (%d)" % downloads)
        self.upload_all_btn.setText("Upload all (%d)" % uploads)
        self.download_all_btn.setEnabled(downloads > 0)
        self.upload_all_btn.setEnabled(uploads > 0)

    def _download_row(self, row):
        try:
            paths = download_rows([row])
            debug_print("Download fila %s: %s" % (row["shot"], paths))
        except Exception as exc:
            show_warning(self, "Download failed", str(exc))

    def _upload_row(self, row):
        if row.get("upload_needs_confirm"):
            if not row["task_in_flow"]:
                reason = "This shot has no %s task in Flow." % task_display_name(row["task"])
            else:
                reason = "It is newer than the last Version in Flow (%s)." % (
                    core.format_version(row["flow"]))
            if not ask_question(
                self, "Upload",
                "Upload local %s to Wasabi?<br>%s<br>"
                "Check that the folder is the right one before uploading it."
                % (emphasis(row["local"].get("name") or "-"), reason),
                yes_text="Upload", no_text="Cancel", recommended=False,
            ):
                return
        try:
            paths = upload_rows([row])
            debug_print("Upload fila %s: %s" % (row["shot"], paths))
        except Exception as exc:
            show_warning(self, "Upload failed", str(exc))

    def _download_all(self):
        rows = bulk_download_rows(self._visible_rows())
        if not rows:
            return
        if not ask_question(
            self, "Download all",
            "Download %s from Wasabi to the local shot folders?"
            % emphasis("%d version%s" % (len(rows), "" if len(rows) == 1 else "s")),
            yes_text="Download", no_text="Cancel",
        ):
            return
        try:
            download_rows(rows)
        except Exception as exc:
            show_warning(self, "Download failed", str(exc))

    def _upload_all(self):
        rows = bulk_upload_rows(self._visible_rows())
        if not rows:
            return
        if not ask_question(
            self, "Upload all",
            "Upload %s from the local shot folders to Wasabi?"
            % emphasis("%d version%s" % (len(rows), "" if len(rows) == 1 else "s")),
            yes_text="Upload", no_text="Cancel",
        ):
            return
        try:
            upload_rows(rows)
        except Exception as exc:
            show_warning(self, "Upload failed", str(exc))

    def _recheck(self):
        self.close()
        self.rerun()

    # -- navegacion
    def _goto_row(self, row):
        """Boton de la fila: lleva el timeline al shot. El click en la fila no
        navega (Lega, 2026-11-20): asi se puede seleccionar sin moverse."""
        try:
            from LGA_NKS_Shared.LGA_NKS_ShotNavigation import goto_shot

            goto_shot(row["project"], row["shot"], task=row["task"])
        except Exception as exc:
            debug_print("Navegacion fallida: %s" % exc)


# ── Status mientras corre ────────────────────────────────────────────────────
class TripleCheckProgress(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(TripleCheckProgress, self).__init__(parent)
        self.setWindowTitle(WINDOW_TITLE)
        self.setModal(False)
        self.setStyleSheet(Style.FORM)
        layout = QtWidgets.QVBoxLayout(self)
        m = Metric.WINDOW_MARGIN
        layout.setContentsMargins(m, m, m, m)
        self.label = QtWidgets.QLabel("Collecting timeline clips...")
        self.label.setMinimumWidth(Metric.DIALOG_MIN_WIDTH)
        layout.addWidget(self.label)
        apply_ui_font(self)

    def set_text(self, text):
        self.label.setText(text)


# Referencias vivas: sin esto el GC se lleva la ventana y el worker.
_state = {"window": None, "progress": None, "worker": None}


def main():
    _reset_log()
    seq = hiero.ui.activeSequence()
    if not seq:
        show_warning(None, WINDOW_TITLE, "There is no active sequence.")
        return
    from LGA_NKS_Shared.LGA_NKS_ContextProfile import get_context_mode

    context_mode = get_context_mode()
    tasks = active_track_tasks(context_mode)
    entries, unresolved = collect_timeline(seq, tasks)
    debug_print(
        "Secuencia=%s contexto=%s tasks=%s clips=%d sin resolver=%d"
        % (seq.name(), context_mode, tasks, len(entries), len(unresolved))
    )
    if not entries:
        tracks = ", ".join("'%s'" % exr_track_for_task(t) for t in tasks)
        show_warning(None, WINDOW_TITLE, "No clips found in the task tracks (%s)." % tracks)
        return

    progress = TripleCheckProgress()
    progress.show()
    _state["progress"] = progress

    worker = TripleCheckWorker(entries, tasks, context_mode)
    worker.setAutoDelete(False)
    worker.signals.progress.connect(progress.set_text)

    def _finished(result):
        progress.close()
        if unresolved:
            result.setdefault("notes", []).append(
                "Clips without a readable shot name: %s" % ", ".join(unresolved[:12])
            )
        window = TripleCheckDialog(result, seq.name(), main)
        _state["window"] = window
        window.show()

    def _failed(message):
        progress.close()
        show_warning(None, WINDOW_TITLE, "Triple Check failed:\n%s" % message)

    worker.signals.finished.connect(_finished)
    worker.signals.failed.connect(_failed)
    _state["worker"] = worker
    QtCore.QThreadPool.globalInstance().start(worker)


if __name__ == "__main__":
    main()
