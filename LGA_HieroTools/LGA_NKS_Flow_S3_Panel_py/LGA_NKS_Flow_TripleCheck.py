"""
____________________________________________________________________

  LGA_NKS_Flow_TripleCheck v1.00 | Lega

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

  v1.00: Version inicial.
____________________________________________________________________
"""

import os
import sys
import time
import logging
import threading
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

core = _importlib.reload(core)
from LGA_NKS_Shared.LGA_NKS_TaskScope import (
    active_track_tasks,
    exr_track_for_task,
    task_folder_name,
    task_display_name,
    CG_TASK_NAME,
)
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
    core.ST_NOT_IN_FLOW: "Not in Flow",
    core.ST_TASK_NOT_IN_FLOW: "Task not in Flow",
    core.ST_NOT_IN_TIMELINE: "Not in timeline",
    core.ST_MISSING_STORAGE: "Missing in Wasabi",
    core.ST_INCOMPLETE: "Incomplete",
    core.ST_MISNAMED: "Wrong folder",
    core.ST_UPLOAD: "Upload",
    core.ST_DOWNLOAD: "Download",
    core.ST_NOT_IN_FLOW_VERSION: "No Flow version",
    core.ST_OK: "OK",
    core.ST_NO_VERSIONS: "No versions",
}

STATUS_COLORS = {
    core.ST_ERROR: Color.ERROR_TEXT,
    core.ST_NOT_IN_FLOW: Color.ERROR_TEXT,
    core.ST_TASK_NOT_IN_FLOW: Color.ERROR_TEXT,
    core.ST_NOT_IN_TIMELINE: Color.INFO,
    core.ST_MISSING_STORAGE: Color.WARNING_TEXT,
    core.ST_INCOMPLETE: Color.WARNING_TEXT,
    core.ST_MISNAMED: Color.WARNING_TEXT,
    core.ST_UPLOAD: Color.WARNING_TEXT,
    core.ST_DOWNLOAD: Color.WARNING_TEXT,
    core.ST_NOT_IN_FLOW_VERSION: Color.WARNING_TEXT,
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
}

COL_SHOT, COL_TASK, COL_FLOW, COL_WASABI, COL_LOCAL, COL_STATUS, COL_ACTION, COL_DETAIL = range(8)
HEADERS = ["Shot", "Task", "Flow", "Wasabi", "Local", "Status", "", "Detail"]
ACTION_CELL_WIDTH = 36
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
                    scan["error"] = "No Wasabi bucket for this project."
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
    """Una oracion por estado, en ingles (texto visible)."""
    parts = []
    w = row.get("wasabi") or {}
    l = row.get("local") or {}
    for status in row.get("statuses", []):
        if status == core.ST_ERROR:
            for label, scan in (("Wasabi", w), ("Local", l)):
                if scan.get("error"):
                    parts.append("%s: %s" % (label, scan["error"]))
        elif status == core.ST_NOT_IN_FLOW:
            parts.append("Shot not found in Flow.")
        elif status == core.ST_TASK_NOT_IN_FLOW:
            parts.append("The shot has no %s task in Flow." % task_display_name(row["task"]))
        elif status == core.ST_NOT_IN_TIMELINE:
            parts.append("In Flow but not in the %s track." % exr_track_for_task(row["task"]))
        elif status == core.ST_MISSING_STORAGE:
            version = (
                _short_name(row["flow_code"], row["shot"]) if row["is_cg"]
                else core.format_version(row["flow"])
            )
            parts.append("Flow has %s, missing in Wasabi and local." % version)
        elif status == core.ST_DOWNLOAD:
            parts.append("Wasabi has %s, not on local disk." % (w.get("name") or "-"))
        elif status == core.ST_UPLOAD:
            parts.append("Local has %s, not in Wasabi." % (l.get("name") or "-"))
        elif status == core.ST_NOT_IN_FLOW_VERSION:
            top = max((w.get("number") or 0), (l.get("number") or 0))
            parts.append("%s has no Version in Flow." % core.format_version(top))
        elif status == core.ST_INCOMPLETE:
            content = row.get("content") or {}
            l_n, l_b = content.get("local", (0, 0))
            w_n, w_b = content.get("wasabi", (0, 0))
            if row.get("incomplete") == "differs":
                parts.append(
                    "%s has the same %d files in both, but %s differ in total size."
                    % (l.get("name"), l_n, _human_size(abs(l_b - w_b)))
                )
            else:
                parts.append(
                    "%s is incomplete: %d files local, %d in Wasabi."
                    % (l.get("name"), l_n, w_n)
                )
        elif status == core.ST_MISNAMED:
            for label, scan in (("Wasabi", w), ("Local", l)):
                if scan.get("foreign"):
                    parts.append("%s folder %s is named for another shot." % (label, scan.get("name")))
    if row.get("upload_blocked") and not l.get("foreign"):
        parts.append(row["upload_blocked"])
    if row.get("upload_needs_confirm"):
        parts.append("Check the local folder name before uploading.")
    return " ".join(parts)


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
        self.rows = sorted(
            result["rows"],
            key=lambda r: (
                not r["in_timeline"],
                core.STATUS_PRIORITY.index(r["status"]),
                r["shot"].lower(),
                r["task"],
            ),
        )
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
        options.addStretch(1)
        layout.addLayout(options)

        self.table = QtWidgets.QTableWidget(len(self.rows), len(HEADERS), self)
        self.table.setHorizontalHeaderLabels(HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setStyleSheet(Style.TABLE)
        self.table.horizontalHeader().setStretchLastSection(True)
        for index, row in enumerate(self.rows):
            self._fill_row(index, row)
        self.table.cellClicked.connect(self._on_cell_clicked)
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

    def _fill_row(self, index, row):
        center = int(Qt.AlignCenter)
        self.table.setItem(index, COL_SHOT, self._item(row["shot"]))
        self.table.setItem(index, COL_TASK, self._item(task_display_name(row["task"])))
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
        self.table.setItem(index, COL_DETAIL, self._item(detail_text(row), Color.TEXT_DIM))
        self._set_action_cell(index, row)
        self.table.setRowHeight(index, Metric.ROW_HEIGHT)

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
        button = QtWidgets.QPushButton()
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
        for col in (COL_FLOW, COL_WASABI, COL_LOCAL):
            self.table.setColumnWidth(col, max(self.table.columnWidth(col), 64))
        visible = sum(1 for i in range(self.table.rowCount()) if not self.table.isRowHidden(i))
        height = self.table.horizontalHeader().sizeHint().height() + self.table.frameWidth() * 2
        height += Metric.ROW_HEIGHT * min(max(visible, 1), 22)
        self.table.setMinimumHeight(height)
        width = sum(self.table.columnWidth(c) for c in range(len(HEADERS) - 1)) + 360
        self.resize(max(self.minimumWidth(), min(width, 1500)), self.sizeHint().height())

    # -- filtro y botones masivos
    def _visible_rows(self):
        return [
            self.rows[i] for i in range(self.table.rowCount()) if not self.table.isRowHidden(i)
        ]

    def _apply_filter(self):
        only = self.only_issues.isChecked()
        visible = 0
        for index, row in enumerate(self.rows):
            hide = only and not core.is_issue(row)
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
    def _on_cell_clicked(self, index, column):
        if column == COL_ACTION or index >= len(self.rows):
            return
        row = self.rows[index]
        if not row["in_timeline"]:
            return
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
