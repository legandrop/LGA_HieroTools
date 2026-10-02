"""
____________________________________________________________________

  LGA_import_shots_transcode_queue v0.02 | Lega

  Coordina la cola global de Transcode Plates para Import Shot.
  Recibe jobs desde ventanas de Import Shot y garantiza que solo una
  secuencia EXR se convierta a la vez dentro de la misma sesion de
  Hiero/Nuke Studio.

  v0.02: skip_active_job() saltea el plate que se esta convirtiendo y la
         cola sigue con el siguiente (pedido: un plate colgado frenaba toda
         la fila). Un error fatal del worker ya no hace desaparecer el job:
         queda como Error con su motivo, y la ventana de origen recibe su
         batch_done cuando no le quedan jobs.
  v0.01: Manager global minimo para una ventana.
         Encola jobs individuales por plate, ejecuta un TranscodeWorker
         por vez y escribe log propio para diagnostico.

____________________________________________________________________
"""

import atexit
import logging
import queue
import re
import time
from logging.handlers import QueueHandler, QueueListener
from pathlib import Path

from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtCore
from LGA_NKS_Edit_Panel_py.LGA_import_shots_transcode import (
    TranscodeWorker,
    check_existing_outputs,
    delete_existing_outputs,
    show_overwrite_warning,
)


CURRENT_DIR = Path(__file__).resolve().parent
STARTUP_DIR = CURRENT_DIR.parent


# Logging - Sistema A: timer + limpieza por ejecucion.
DEBUG = True
DEBUG_CONSOLE = False
DEBUG_LOG = True
script_start_time = None
debug_log_listener = None


class RelativeTimeFormatter(logging.Formatter):
    def format(self, record):
        global script_start_time
        if script_start_time is None:
            script_start_time = record.created
        record.relative_time = "%.3fs" % (record.created - script_start_time)
        return super().format(record)


def setup_debug_logging(script_name="ImportShotsTranscodeQueue"):
    global debug_log_listener
    log_path = STARTUP_DIR / "logs" / ("debugPy_%s.log" % script_name)
    log_path.parent.mkdir(exist_ok=True)
    try:
        log_path.write_text("Fecha: %s\n" % time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
    except Exception:
        pass

    logger = logging.getLogger("%s_logger" % script_name.lower())
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    if logger.handlers:
        logger.handlers.clear()

    fh = logging.FileHandler(str(log_path), encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(RelativeTimeFormatter("[%(relative_time)s] %(message)s"))

    lq = queue.Queue()
    qh = QueueHandler(lq)
    qh.setLevel(logging.DEBUG)
    logger.addHandler(qh)

    if debug_log_listener:
        try:
            debug_log_listener.stop()
        except Exception:
            pass

    debug_log_listener = QueueListener(lq, fh, respect_handler_level=True)
    debug_log_listener.daemon = True
    debug_log_listener.start()
    return logger


debug_logger = setup_debug_logging()


def debug_print(*message, **kwargs):
    global script_start_time
    level = kwargs.get("level", "info")
    msg = " ".join(str(a) for a in message)
    if DEBUG and DEBUG_LOG:
        if script_start_time is None:
            script_start_time = time.time()
        getattr(debug_logger, level)(msg)
    if DEBUG and DEBUG_CONSOLE:
        if script_start_time is None:
            script_start_time = time.time()
        print("[%.3fs] %s" % (time.time() - script_start_time, msg))


def cleanup_logging():
    global debug_log_listener
    if debug_log_listener:
        try:
            debug_log_listener.stop()
        except Exception:
            pass


atexit.register(cleanup_logging)


def _safe_key(value):
    text = str(value or "job").strip()
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text)
    return text or "job"


CPU_PRESETS = {
    "High": {"workers": 6, "exrmetrics_threads": 6},
    "Medium": {"workers": 4, "exrmetrics_threads": 4},
    "Low": {"workers": 2, "exrmetrics_threads": 2},
    "Minimal": {"workers": 1, "exrmetrics_threads": 1},
}
DEFAULT_CPU_PRESET = "High"


class TranscodeQueueManager(QtCore.QObject):
    """Singleton global que serializa los TranscodeWorker de Import Shot."""

    queue_changed = QtCore.Signal(list)
    cpu_preset_changed = QtCore.Signal(str, dict)
    log_message = QtCore.Signal(str, str)              # window_id, msg
    sequence_started = QtCore.Signal(str, int, str, int)
    sequence_done = QtCore.Signal(str, int, bool, dict)
    job_cancelled = QtCore.Signal(str, int, dict)
    batch_done = QtCore.Signal(str, list)
    fatal_error = QtCore.Signal(str, str)

    def __init__(self, parent=None):
        super(TranscodeQueueManager, self).__init__(parent)
        self._pending = []
        self._active_job = None
        self._active_worker = None
        self._results_by_window = {}
        self._completed_windows = set()
        self._open_windows = set()
        self._closed_windows = set()
        self._job_seq = 0
        self._cpu_preset = DEFAULT_CPU_PRESET
        debug_print("=== TranscodeQueueManager init ===")

    def enqueue_jobs(self, window_id, shot_name, job_sequences, global_opts, flags, shared_dir, ui_parent=None):
        """Agrega jobs individuales a la cola global y arranca si esta idle."""
        if not job_sequences:
            debug_print("enqueue_jobs ignorado: lista vacia window=%s" % window_id, level="warning")
            return []

        job_ids = []
        self._results_by_window[window_id] = []
        self._completed_windows.discard(window_id)
        for row_i, item, tw, th in job_sequences:
            self._job_seq += 1
            seq_name = item.get("name") or Path(item.get("path", "")).name
            job_id = "%s-%04d-%s" % (_safe_key(window_id), self._job_seq, _safe_key(seq_name))
            job = {
                "job_id": job_id,
                "window_id": window_id,
                "shot_name": shot_name,
                "row_i": row_i,
                "item": item,
                "target_w": tw,
                "target_h": th,
                "global_opts": dict(global_opts or {}),
                "flags": dict(flags or {}),
                "shared_dir": shared_dir,
                "ui_parent": ui_parent,
                "created_at": time.time(),
                "status": "queued",
                "name": seq_name,
            }
            self._pending.append(job)
            job_ids.append(job_id)
            debug_print(
                "job queued id=%s window=%s shot=%s row=%s name=%s"
                % (job_id, window_id, shot_name, row_i, seq_name)
            )

        self._emit_queue_changed()
        self._start_next_if_idle()
        return job_ids

    def is_busy(self):
        return self._active_job is not None or bool(self._pending)

    def note_window_opened(self, window_id, shot_name):
        if window_id in self._open_windows:
            debug_print("window opened duplicate window=%s shot=%s" % (window_id, shot_name), level="warning")
            return
        self._open_windows.add(window_id)
        self._closed_windows.discard(window_id)
        debug_print("window opened window=%s shot=%s" % (window_id, shot_name))

    def note_window_closed(self, window_id, shot_name, source="unknown"):
        if window_id in self._closed_windows:
            debug_print(
                "window closed duplicate source=%s window=%s shot=%s" % (source, window_id, shot_name)
            )
            return
        self._closed_windows.add(window_id)
        self._open_windows.discard(window_id)
        debug_print("window closed source=%s window=%s shot=%s" % (source, window_id, shot_name))
        self._remove_pending_jobs_for_window(window_id, shot_name)
        self._emit_queue_changed()
        self._start_next_if_idle()

    def skip_active_job(self):
        """Saltea el job en curso: corta su convert, restaura originales y sigue la cola.

        El job no se suelta aca: el worker termina por su camino normal de fallo
        (sequence_done + all_done con skipped=True) y recien ahi arranca el siguiente.
        Soltarlo antes dejaria dos workers moviendo originales a la vez.
        """
        job = self._active_job
        worker = self._active_worker
        if job is None or worker is None or job.get("skip_requested"):
            return False
        job["skip_requested"] = True
        debug_print(
            "skip requested job=%s window=%s shot=%s name=%s"
            % (job.get("job_id"), job.get("window_id"), job.get("shot_name"), job.get("name")),
            level="warning",
        )
        worker.request_skip()
        self._emit_queue_changed()
        return True

    def snapshot(self):
        data = []
        if self._active_job:
            data.append(self._job_snapshot(self._active_job, "running", 0))
        for pos, job in enumerate(self._pending, 1):
            data.append(self._job_snapshot(job, "queued", pos))
        return data

    def cpu_presets(self):
        return list(CPU_PRESETS.keys())

    def cpu_preset(self):
        return self._cpu_preset

    def cpu_options(self):
        return dict(CPU_PRESETS.get(self._cpu_preset, CPU_PRESETS[DEFAULT_CPU_PRESET]))

    def cpu_options_for_preset(self, preset):
        return dict(CPU_PRESETS.get(str(preset or ""), CPU_PRESETS[DEFAULT_CPU_PRESET]))

    def set_cpu_preset(self, preset):
        preset = str(preset or DEFAULT_CPU_PRESET)
        if preset not in CPU_PRESETS:
            preset = DEFAULT_CPU_PRESET
        if preset == self._cpu_preset:
            return
        self._cpu_preset = preset
        opts = self.cpu_options()
        debug_print(
            "cpu preset changed preset=%s workers=%s exrmetrics_threads=%s"
            % (preset, opts["workers"], opts["exrmetrics_threads"])
        )
        self.cpu_preset_changed.emit(preset, opts)

    def _start_next_if_idle(self):
        if self._active_job is not None:
            return

        while self._pending:
            job = self._pending.pop(0)
            job["status"] = "starting"
            self._active_job = job
            self._emit_queue_changed()

            if not self._prepare_job_or_cancel(job):
                self._active_job = None
                self._emit_queue_changed()
                continue

            self._launch_worker(job)
            return

        debug_print("queue empty")
        self._emit_completed_windows()
        self._emit_queue_changed()

    def _prepare_job_or_cancel(self, job):
        flags = job["flags"]
        item = job["item"]
        has_conflict, conflict_desc = check_existing_outputs(
            item, flags.get("test_mode", False), flags.get("move_originals", True)
        )
        if not has_conflict:
            return True

        seq_name = job.get("name") or Path(item.get("path", "")).name
        debug_print("conflict detected job=%s desc=%s" % (job["job_id"], conflict_desc), level="warning")
        proceed = show_overwrite_warning(seq_name, conflict_desc, parent=job.get("ui_parent"))
        if not proceed:
            result = {
                "row_i": job["row_i"],
                "ok": False,
                "cancelled": True,
                "name": seq_name,
                "job_id": job["job_id"],
                "window_id": job.get("window_id"),
                "shot_name": job.get("shot_name"),
                "frame_count": (job.get("item") or {}).get("frame_count"),
                "source_fps": (job.get("item") or {}).get("fps"),
            }
            self._results_by_window.setdefault(job["window_id"], []).append(result)
            self.job_cancelled.emit(job["window_id"], job["row_i"], result)
            debug_print("job cancelled by user id=%s" % job["job_id"], level="warning")
            return False

        try:
            deleted = delete_existing_outputs(
                item,
                flags.get("test_mode", False),
                flags.get("move_originals", True),
                log_fn=lambda msg: debug_print("conflict cleanup job=%s %s" % (job["job_id"], msg)),
            )
        except Exception as exc:
            result = {
                "row_i": job["row_i"],
                "ok": False,
                "error": str(exc),
                "name": seq_name,
                "job_id": job["job_id"],
                "window_id": job.get("window_id"),
                "shot_name": job.get("shot_name"),
                "frame_count": (job.get("item") or {}).get("frame_count"),
                "source_fps": (job.get("item") or {}).get("fps"),
            }
            self._results_by_window.setdefault(job["window_id"], []).append(result)
            self.job_cancelled.emit(job["window_id"], job["row_i"], result)
            debug_print("conflict cleanup failed job=%s error=%s" % (job["job_id"], exc), level="error")
            return False

        debug_print("conflict cleanup job=%s deleted=%s" % (job["job_id"], deleted))
        return True

    def _launch_worker(self, job):
        flags = job["flags"]
        global_opts = dict(job.get("global_opts") or {})
        cpu_opts = self.cpu_options()
        global_opts.update(cpu_opts)
        global_opts["cpu_preset"] = self._cpu_preset
        job["global_opts"] = global_opts
        debug_print(
            "job cpu options id=%s preset=%s workers=%s exrmetrics_threads=%s"
            % (job["job_id"], self._cpu_preset, cpu_opts["workers"], cpu_opts["exrmetrics_threads"])
        )
        worker = TranscodeWorker(
            [(job["row_i"], job["item"], job["target_w"], job["target_h"])],
            global_opts,
            test_mode=flags.get("test_mode", False),
            move_originals=flags.get("move_originals", True),
            delete_originals=flags.get("delete_originals", False),
            shared_dir=job["shared_dir"],
        )
        worker.signals.log_message.connect(
            lambda msg, window_id=job["window_id"]: self._on_worker_log(window_id, msg)
        )
        worker.signals.sequence_started.connect(
            lambda row_i, dst_dir, total_frames, window_id=job["window_id"]:
                self._on_sequence_started(window_id, row_i, dst_dir, total_frames)
        )
        worker.signals.sequence_done.connect(
            lambda row_i, ok, stats, window_id=job["window_id"]:
                self._on_sequence_done(window_id, row_i, ok, stats)
        )
        worker.signals.all_done.connect(
            lambda results, window_id=job["window_id"]: self._on_worker_done(window_id, results)
        )
        worker.signals.error.connect(
            lambda msg, window_id=job["window_id"]: self._on_worker_error(window_id, msg)
        )

        self._active_worker = worker
        job["status"] = "running"
        debug_print(
            "worker start job=%s window=%s shot=%s row=%s name=%s"
            % (job["job_id"], job["window_id"], job["shot_name"], job["row_i"], job["name"])
        )
        self._emit_queue_changed()
        QtCore.QThreadPool.globalInstance().start(worker)

    def _on_worker_log(self, window_id, msg):
        debug_print("worker log window=%s msg=%s" % (window_id, msg))
        self.log_message.emit(window_id, msg)

    def _on_sequence_started(self, window_id, row_i, dst_dir, total_frames):
        if self._active_job:
            self._active_job["dst_dir"] = dst_dir
            self._active_job["total_frames"] = total_frames
        debug_print(
            "sequence_started window=%s row=%s dst=%s total=%s"
            % (window_id, row_i, dst_dir, total_frames)
        )
        self.sequence_started.emit(window_id, row_i, dst_dir, total_frames)
        self._emit_queue_changed()

    def _on_sequence_done(self, window_id, row_i, ok, stats):
        stats = dict(stats or {})
        if self._active_job:
            stats["job_id"] = self._active_job.get("job_id")
            stats["name"] = self._active_job.get("name")
            stats["window_id"] = self._active_job.get("window_id")
            stats["shot_name"] = self._active_job.get("shot_name")
            stats["frame_count"] = stats.get("frame_count") or (self._active_job.get("item") or {}).get("frame_count")
            stats["source_fps"] = (self._active_job.get("item") or {}).get("fps")
            stats["cpu_preset"] = (self._active_job.get("global_opts") or {}).get("cpu_preset")
            stats["workers"] = (self._active_job.get("global_opts") or {}).get("workers")
            stats["exrmetrics_threads"] = (self._active_job.get("global_opts") or {}).get("exrmetrics_threads")
        debug_print("sequence_done window=%s row=%s ok=%s stats=%s" % (window_id, row_i, ok, stats))
        self.sequence_done.emit(window_id, row_i, ok, stats)

    def _on_worker_done(self, window_id, results):
        results = list(results or [])
        if self._active_job:
            for result in results:
                result.setdefault("job_id", self._active_job.get("job_id"))
                result.setdefault("name", self._active_job.get("name"))
                result.setdefault("cpu_preset", (self._active_job.get("global_opts") or {}).get("cpu_preset"))
                result.setdefault("workers", (self._active_job.get("global_opts") or {}).get("workers"))
                result.setdefault("exrmetrics_threads", (self._active_job.get("global_opts") or {}).get("exrmetrics_threads"))
        debug_print("worker done window=%s results=%d" % (window_id, len(results)))
        self._finish_active_job(window_id, results)

    def _on_worker_error(self, window_id, msg):
        """Excepcion que se escapo del worker (por ejemplo, un restore que fallo).

        Antes el job desaparecia de la cola sin dejar rastro y la ventana de origen
        nunca recibia batch_done. Es justo el caso que mas importa ver: se lo marca
        como Error con su motivo, igual que un fallo comun, y la cola sigue.
        """
        debug_print("worker fatal window=%s msg=%s" % (window_id, msg), level="error")
        job = self._active_job or {}
        row_i = job.get("row_i")
        stats = {"ok": False, "error": msg, "fatal": True, "frame_count": 0, "ok_count": 0}
        if row_i is not None:
            self._on_sequence_done(window_id, row_i, False, stats)
        self.fatal_error.emit(window_id, msg)
        result = dict(stats)
        result.update({
            "row_i": row_i,
            "name": job.get("name"),
            "job_id": job.get("job_id"),
            "window_id": window_id,
            "shot_name": job.get("shot_name"),
        })
        self._finish_active_job(window_id, [result])

    def _finish_active_job(self, window_id, results):
        self._results_by_window.setdefault(window_id, []).extend(results)
        all_results = list(self._results_by_window.get(window_id, []))

        self._active_job = None
        self._active_worker = None
        if not self._has_window_jobs(window_id):
            self._emit_window_done(window_id, all_results)

        self._emit_queue_changed()
        self._start_next_if_idle()

    def _has_window_jobs(self, window_id):
        if self._active_job and self._active_job.get("window_id") == window_id:
            return True
        return any(job.get("window_id") == window_id for job in self._pending)

    def _remove_pending_jobs_for_window(self, window_id, shot_name):
        kept = []
        removed = []
        for job in self._pending:
            if job.get("window_id") == window_id:
                job["status"] = "cancelled"
                removed.append(job)
            else:
                kept.append(job)
        self._pending = kept

        if not removed:
            debug_print("window close removed 0 pending jobs window=%s shot=%s" % (window_id, shot_name))
            return

        results = self._results_by_window.setdefault(window_id, [])
        for job in removed:
            result = {
                "row_i": job.get("row_i"),
                "ok": False,
                "cancelled": True,
                "name": job.get("name"),
                "job_id": job.get("job_id"),
                "window_id": job.get("window_id"),
                "shot_name": job.get("shot_name"),
                "frame_count": (job.get("item") or {}).get("frame_count"),
                "source_fps": (job.get("item") or {}).get("fps"),
                "closed_window": True,
            }
            results.append(result)
            self.job_cancelled.emit(window_id, job.get("row_i"), result)
            debug_print(
                "job removed because window closed id=%s window=%s shot=%s row=%s name=%s"
                % (job.get("job_id"), window_id, shot_name, job.get("row_i"), job.get("name"))
            )

    def _emit_completed_windows(self):
        for window_id, results in list(self._results_by_window.items()):
            if results and not self._has_window_jobs(window_id):
                self._emit_window_done(window_id, list(results))

    def _emit_window_done(self, window_id, results):
        if window_id in self._completed_windows:
            return
        self._completed_windows.add(window_id)
        self.batch_done.emit(window_id, results)
        debug_print("window batch_done window=%s total_results=%d" % (window_id, len(results)))

    def _emit_queue_changed(self):
        snap = self.snapshot()
        debug_print("queue_changed size=%d active=%s pending=%d" % (
            len(snap),
            self._active_job.get("job_id") if self._active_job else "",
            len(self._pending),
        ))
        self.queue_changed.emit(snap)

    @staticmethod
    def _job_snapshot(job, status, position):
        return {
            "job_id": job.get("job_id"),
            "window_id": job.get("window_id"),
            "shot_name": job.get("shot_name"),
            "row_i": job.get("row_i"),
            "name": job.get("name"),
            "status": status,
            "skip_requested": bool(job.get("skip_requested")),
            "position": position,
            "frame_count": (job.get("item") or {}).get("frame_count"),
            "source_fps": (job.get("item") or {}).get("fps"),
            "dst_dir": job.get("dst_dir"),
            "total_frames": job.get("total_frames"),
            "cpu_preset": (job.get("global_opts") or {}).get("cpu_preset"),
            "workers": (job.get("global_opts") or {}).get("workers"),
            "exrmetrics_threads": (job.get("global_opts") or {}).get("exrmetrics_threads"),
        }


_manager_instance = None


def get_manager():
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = TranscodeQueueManager()
    return _manager_instance
