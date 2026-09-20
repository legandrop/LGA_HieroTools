# -*- coding: utf-8 -*-
"""
____________________________________________________________________

  LGA_NKS_AssignmentSaga v1.01 | Lega

  Orquestación pura de la post-asignación: mirrors locales y grant canónico.

  v1.01: Congela el contexto alrededor de lecturas sensibles.
  v1.00: Orden y resultado estructurado para Flow/main/stats/Wasabi.
____________________________________________________________________
"""

import json
import os
import subprocess
import sqlite3

from LGA_NKS_Shared.LGA_NKS_PipeSyncPaths import get_pipesync_runtime_paths

RESULT_PREFIX = "WASABI_POLICY_SYNC_JSON:"


class ContextChangedError(RuntimeError):
    pass


def load_in_stable_context(read_mode, loader, expected_mode=None):
    """Carga un valor sólo si el contexto permanece estable durante la lectura."""
    before = read_mode()
    if expected_mode is not None and before != expected_mode:
        raise ContextChangedError(
            "The Studio/Client context changed before the operation. Nothing was written."
        )
    value = loader()
    after = read_mode()
    if after != before or (expected_mode is not None and after != expected_mode):
        raise ContextChangedError(
            "The Studio/Client context changed during the operation. Nothing was written."
        )
    return before, value


def parse_wasabi_result(stdout):
    for line in reversed((stdout or "").splitlines()):
        if line.startswith(RESULT_PREFIX):
            return json.loads(line[len(RESULT_PREFIX):].strip())
    raise ValueError("PipeSync did not return a structured Wasabi result.")


def run_canonical_wasabi_grant(flow_user_name, is_client=False, profile=None, runner=subprocess.run, path_resolver=get_pipesync_runtime_paths):
    """Ejecuta el motor oficial instalado. En client es un no-op obligatorio."""
    if is_client:
        return {"status": "complete", "skipped": True, "reason": "client"}
    profile = profile or {}
    if profile.get("skip_wasabi_policy") or not str(profile.get("wasabi_user") or "").strip():
        return {"status": "complete", "skipped": True, "reason": "profile"}
    try:
        python_path, script_path = path_resolver("wasabi_policy_sync.py")
        env = os.environ.copy()
        env["PIPESYNC_CONTEXT"] = "studio"
        completed = runner(
            [python_path, script_path, "--apply", "--grant-only", "--user", str(flow_user_name)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=180, env=env, check=False,
        )
    except Exception as exc:
        return {"status": "partial", "skipped": False, "error": str(exc)}
    if completed.returncode != 0:
        return {"status": "partial", "skipped": False, "error": (completed.stderr or completed.stdout or "IAM error").strip()}
    try:
        data = parse_wasabi_result(completed.stdout)
    except Exception as exc:
        return {"status": "partial", "skipped": False, "error": str(exc)}
    grants_missing = int(data.get("total_add") or 0) > 0 and int(data.get("applied_users") or 0) == 0
    ok = bool(data.get("ok")) and not data.get("failed_users") and not grants_missing
    return {"status": "complete" if ok else "partial", "skipped": False, "data": data, "error": None if ok else "PipeSync reported IAM failures."}


def run_post_flow_saga(main_mirror, stats_mirror, grant):
    """Main puede fallar; stats es la barrera de seguridad anterior a Wasabi."""
    result = {"status": "complete", "main": False, "stats": False, "wasabi": None, "errors": []}
    try:
        result["main"] = bool(main_mirror())
    except Exception as exc:
        result["errors"].append("main: {0}".format(exc))
    if not result["main"]:
        result["errors"].append("pipesync.db could not be updated.")
    try:
        result["stats"] = bool(stats_mirror())
    except Exception as exc:
        result["errors"].append("stats: {0}".format(exc))
    if not result["stats"]:
        result["errors"].append("pipesync_stats.db could not be updated; Wasabi was not run.")
        result["status"] = "partial"
        return result
    try:
        result["wasabi"] = grant()
    except Exception as exc:
        result["wasabi"] = {"status": "partial", "error": str(exc)}
    if not isinstance(result["wasabi"], dict):
        result["errors"].append("Wasabi returned an invalid result.")
    elif result["wasabi"].get("status") != "complete":
        wasabi_error = result["wasabi"].get("error") or "Wasabi access could not be synchronized."
        if wasabi_error not in result["errors"]:
            result["errors"].append(wasabi_error)
    if not result["main"] or not isinstance(result["wasabi"], dict) or result["wasabi"].get("status") != "complete":
        result["status"] = "partial"
    return result


def mirror_stats_assignees(db_path, task_id, users, connect=sqlite3.connect):
    """Snapshot idempotente de assignees; conserva filas con rol reviewer."""
    if not os.path.isfile(db_path):
        return False
    conn = connect(db_path)
    try:
        task = conn.execute("SELECT id FROM tasks WHERE id = ?", (int(task_id),)).fetchone()
        if not task:
            return False
        for user in users or []:
            conn.execute(
                "INSERT INTO users (id, name) VALUES (?, ?) "
                "ON CONFLICT(id) DO UPDATE SET name = COALESCE(NULLIF(excluded.name, ''), users.name)",
                (int(user["id"]), user.get("name") or ""),
            )
        conn.execute("DELETE FROM task_assignments WHERE task_id = ? AND role = 'assignee'", (int(task_id),))
        for user in users or []:
            conn.execute(
                "INSERT INTO task_assignments (task_id, user_id, role) VALUES (?, ?, 'assignee') "
                "ON CONFLICT(task_id, user_id, role) DO NOTHING",
                (int(task_id), int(user["id"])),
            )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()
