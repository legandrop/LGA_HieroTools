import json
import ast
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "LGA_NKS_Shared"))

from LGA_NKS_Shared import LGA_NKS_Flow_NamingUtils as naming
from LGA_NKS_Shared.LGA_NKS_AssignmentSaga import (
    ContextChangedError,
    load_in_stable_context,
    mirror_stats_assignees,
    run_canonical_wasabi_grant,
    run_post_flow_saga,
)
from LGA_NKS_Shared.LGA_NKS_ClientVendorAccess import (
    VendorAccessError,
    add_project_users,
    resolve_selected_reviewers,
    resolve_client_vendor_access,
    shot_vendor_fields,
    task_vendor_fields,
    with_internal_vendor_assignee,
)
from LGA_NKS_Shared.LGA_NKS_Flow_Reviewer_Config import (
    INTERNAL_VENDOR_ASSIGNEE_KEY,
    REVIEWER_KEY_TO_NAME,
)


class FakeSG:
    def __init__(self, vendors=("VEN",), user_ok=True):
        self.writes = []
        self.project = {
            "id": 1,
            "users": [{"type": "HumanUser", "id": 99}],
            "sg_pipesync_project_settings_json": json.dumps({"vendors": list(vendors)}),
            "sg_pipesync_vendor_access_json": json.dumps({"vendor_group_ids": {"VEN": 7}}),
        }
        groups = [{"type": "Group", "id": 7}] if user_ok else []
        self.users = [{"id": 8, "name": "Vendor User", "sg_vendor_group": {"type": "Group", "id": 7}, "groups": groups}]
        self.people = [{"id": 6, "name": "Lega Pugliese"}]

    def find_one(self, entity, filters, fields):
        if entity == "Project": return self.project
        if entity == "Group": return {"id": 7, "code": "Vendor Group", "users": self.users}
        return None

    def find(self, entity, filters, fields):
        if entity != "HumanUser":
            return []
        name_filter = next(
            (item for item in filters if item[0] == "name" and item[1] == "is"),
            None,
        )
        if name_filter:
            return [item for item in self.people if item.get("name") == name_filter[2]]
        return list(self.users)

    def update(self, entity, entity_id, data, **kwargs):
        self.writes.append((entity, entity_id, data, kwargs))
        return data


class VendorSecurityTests(unittest.TestCase):
    def setUp(self):
        naming._vendor_lookup = False

    def test_new_policy_helpers_do_not_import_host_or_qt_modules(self):
        for file_name in ("LGA_NKS_AssignmentSaga.py", "LGA_NKS_ClientVendorAccess.py"):
            tree = ast.parse(
                (ROOT / "LGA_NKS_Shared" / file_name).read_text(encoding="utf-8-sig")
            )
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])
            self.assertTrue(imported.isdisjoint({"hiero", "nuke", "PySide", "PySide2", "PySide6"}))

    def test_sup_is_internal_case_insensitive_and_remains_in_shot(self):
        self.assertEqual("SUP", naming.extract_vendor_token("PROJA_010_020_sup_comp"))
        self.assertEqual("PROJA_010_020_SUP", naming.extract_shot_code("PROJA_010_020_SUP_comp"))
        self.assertEqual("comp", naming.extract_task_name("PROJA_010_020_SUP_comp"))

    def test_external_vendor_remains_in_flow_shot_code(self):
        naming._vendor_lookup = lambda token, project: token.upper() == "VEN"
        self.assertEqual("VEN", naming.extract_vendor_token("PROJA_010_020_VEN_comp"))
        self.assertEqual(
            "PROJA_010_020_VEN",
            naming.extract_shot_code("PROJA_010_020_VEN_comp"),
        )

    def test_unknown_unambiguous_vendor_slot_is_rejected(self):
        self.assertEqual("XXX", naming.find_unknown_vendor_slot("PROJA_010_020_XXX_comp", ["comp"]))
        self.assertEqual("XXX", naming.find_unknown_vendor_slot("PROJA_010_020_XXX_Compo", ["comp", "compo"]))
        self.assertEqual("", naming.find_unknown_vendor_slot("PROJA_010_020_SUP_comp", ["comp"]))

    def test_stale_local_cache_defers_vendor_candidate_to_live_flow(self):
        candidate = naming.find_unknown_vendor_slot(
            "PROJA_010_020_VEN_layout", ["comp", "layout"]
        )
        self.assertEqual("VEN", candidate)
        self.assertEqual(
            "PROJA_010_020_VEN",
            naming.extract_shot_code_with_vendor_candidate(
                "PROJA_010_020_VEN_layout", candidate
            ),
        )
        plan = resolve_client_vendor_access(FakeSG(vendors=("VEN",)), 1, [candidate])
        self.assertEqual("external", plan["kind"])

    def test_client_cg_stream_not_in_a_finite_list_still_validates_vendor_slot(self):
        candidate = naming.find_unknown_vendor_slot(
            "PROJA_010_020_XXX_simulation", ["comp"],
            client_cg_by_exclusion=True,
        )
        self.assertEqual("XXX", candidate)
        self.assertEqual(
            "PROJA_010_020_XXX",
            naming.extract_shot_code_with_vendor_candidate(
                "PROJA_010_020_XXX_simulation", candidate
            ),
        )
        sg = FakeSG(vendors=("VEN",))
        with self.assertRaises(VendorAccessError):
            resolve_client_vendor_access(sg, 1, [candidate])
        self.assertEqual([], sg.writes)

    def test_live_flow_rejects_unknown_candidate_without_writes(self):
        sg = FakeSG(vendors=("VEN",))
        candidate = naming.find_unknown_vendor_slot(
            "PROJA_010_020_XXX_anim", ["comp", "anim"]
        )
        with self.assertRaises(VendorAccessError):
            resolve_client_vendor_access(sg, 1, [candidate])
        self.assertEqual([], sg.writes)

    def test_collision_with_sup_aborts_without_writes(self):
        sg = FakeSG(vendors=(" sup ",))
        with self.assertRaises(VendorAccessError):
            resolve_client_vendor_access(sg, 1, ["SUP"])
        self.assertEqual([], sg.writes)

    def test_project_sup_collision_also_aborts_plain_shot(self):
        sg = FakeSG(vendors=("SUP",))
        with self.assertRaises(VendorAccessError):
            resolve_client_vendor_access(sg, 1, [])
        self.assertEqual([], sg.writes)

    def test_external_vendor_payloads_and_additive_project_members(self):
        sg = FakeSG()
        plan = resolve_client_vendor_access(sg, 1, [" ven "])
        self.assertEqual({"sg_vendor_groups": [{"type": "Group", "id": 7}]}, shot_vendor_fields(plan))
        self.assertEqual({"task_assignees": [{"type": "HumanUser", "id": 8}]}, task_vendor_fields(plan))
        add_project_users(sg, 1, plan)
        users = sg.writes[0][2]["users"]
        self.assertEqual([8], [item["id"] for item in users])
        self.assertEqual(
            {"users": "add"},
            sg.writes[0][3]["multi_entity_update_modes"],
        )

    def test_inconsistent_normal_group_aborts_without_writes(self):
        sg = FakeSG(user_ok=False)
        with self.assertRaises(VendorAccessError):
            resolve_client_vendor_access(sg, 1, ["VEN"])
        self.assertEqual([], sg.writes)

    def test_malformed_group_mapping_aborts_without_writes(self):
        sg = FakeSG()
        sg.project["sg_pipesync_vendor_access_json"] = json.dumps({
            "vendor_group_ids": {"VEN": "not-an-id"}
        })
        with self.assertRaises(VendorAccessError):
            resolve_client_vendor_access(sg, 1, ["VEN"])
        self.assertEqual([], sg.writes)

    def test_selected_reviewer_must_resolve_uniquely_without_writes(self):
        class ReviewerSG(FakeSG):
            def find(self, entity, filters, fields):
                if entity == "HumanUser":
                    return []
                return super().find(entity, filters, fields)

        sg = ReviewerSG()
        with self.assertRaises(VendorAccessError):
            resolve_selected_reviewers(
                sg, {"reviewer_a": True}, {"reviewer_a": "Reviewer"}
            )
        self.assertEqual([], sg.writes)

    def test_reviewer_lookup_error_aborts_without_writes(self):
        class ReviewerSG(FakeSG):
            def find(self, entity, filters, fields):
                raise RuntimeError("offline")

        sg = ReviewerSG()
        with self.assertRaises(RuntimeError):
            resolve_selected_reviewers(
                sg, {"reviewer_a": True}, {"reviewer_a": "Reviewer"}
            )
        self.assertEqual([], sg.writes)

    def test_multiple_external_vendors_abort_without_reads_or_writes(self):
        sg = FakeSG()
        with self.assertRaises(VendorAccessError):
            resolve_client_vendor_access(sg, 1, ["VEN", "VEX"])
        self.assertEqual([], sg.writes)

    def test_sup_assigns_tasks_to_lega_without_vendor_or_project_access(self):
        sg = FakeSG()
        plan = resolve_client_vendor_access(sg, 1, ["sup"])
        self.assertEqual("internal", plan["kind"])
        self.assertEqual([], plan["users"])
        plan = with_internal_vendor_assignee(
            sg,
            plan,
            REVIEWER_KEY_TO_NAME,
            INTERNAL_VENDOR_ASSIGNEE_KEY,
        )
        self.assertEqual(
            [{"type": "HumanUser", "id": 6}],
            plan["users"],
        )
        self.assertEqual({}, shot_vendor_fields(plan))
        self.assertEqual(
            {"task_assignees": [{"type": "HumanUser", "id": 6}]},
            task_vendor_fields(plan),
        )
        self.assertEqual([], add_project_users(sg, 1, plan))
        self.assertEqual([], sg.writes)

    def test_sup_missing_or_ambiguous_assignee_aborts_without_writes(self):
        for people in (
            [],
            [
                {"id": 6, "name": "Lega Pugliese"},
                {"id": 9, "name": "Lega Pugliese"},
            ],
        ):
            sg = FakeSG()
            sg.people = people
            with self.assertRaises(VendorAccessError):
                plan = resolve_client_vendor_access(sg, 1, ["SUP"])
                with_internal_vendor_assignee(
                    sg,
                    plan,
                    REVIEWER_KEY_TO_NAME,
                    INTERNAL_VENDOR_ASSIGNEE_KEY,
                )
            self.assertEqual([], sg.writes)

    def test_plain_client_plan_does_not_gain_the_sup_assignee(self):
        sg = FakeSG()
        plan = resolve_client_vendor_access(sg, 1, [])
        self.assertIs(
            plan,
            with_internal_vendor_assignee(
                sg,
                plan,
                REVIEWER_KEY_TO_NAME,
                INTERNAL_VENDOR_ASSIGNEE_KEY,
            ),
        )
        self.assertEqual({}, task_vendor_fields(plan))

    def test_saga_orders_main_stats_grant_and_reports_partial(self):
        calls = []
        result = run_post_flow_saga(
            lambda: calls.append("main") or False,
            lambda: calls.append("stats") or True,
            lambda: calls.append("grant") or {"status": "complete"},
        )
        self.assertEqual(["main", "stats", "grant"], calls)
        self.assertEqual("partial", result["status"])

    def test_double_failure_reports_main_and_wasabi_errors(self):
        result = run_post_flow_saga(
            lambda: False,
            lambda: True,
            lambda: {"status": "partial", "error": "IAM denied"},
        )
        self.assertEqual("partial", result["status"])
        self.assertTrue(any("pipesync.db" in error for error in result["errors"]))
        self.assertIn("IAM denied", result["errors"])

    def test_stats_failure_blocks_grant(self):
        calls = []
        result = run_post_flow_saga(lambda: True, lambda: False, lambda: calls.append("grant"))
        self.assertEqual([], calls)
        self.assertEqual("partial", result["status"])

    def test_client_never_runs_wasabi(self):
        called = []
        result = run_canonical_wasabi_grant("User", is_client=True, runner=lambda *a, **k: called.append(True))
        self.assertTrue(result["skipped"])
        self.assertEqual([], called)

    def test_context_change_during_sensitive_load_aborts_before_mutation(self):
        state = {"mode": "studio"}
        writes = []

        def load_credentials():
            state["mode"] = "client"
            return ("url", "login", "password")

        with self.assertRaises(ContextChangedError):
            load_in_stable_context(lambda: state["mode"], load_credentials)
        self.assertEqual([], writes)

    def test_frozen_context_rejects_a_later_profile_read(self):
        state = {"mode": "studio"}
        state["mode"] = "client"
        with self.assertRaises(ContextChangedError):
            load_in_stable_context(
                lambda: state["mode"], lambda: {"wasabi_user": "iam-user"},
                expected_mode="studio",
            )

    def test_unmanaged_profiles_are_successful_noops(self):
        for profile in ({"skip_wasabi_policy": True, "wasabi_user": "iam"}, {"wasabi_user": ""}):
            called = []
            result = run_canonical_wasabi_grant(
                "Flow User", profile=profile, runner=lambda *a, **k: called.append(True)
            )
            self.assertEqual("complete", result["status"])
            self.assertTrue(result["skipped"])
            self.assertEqual([], called)

    def test_canonical_command_is_grant_only(self):
        class Done:
            returncode = 0
            stderr = ""
            stdout = 'WASABI_POLICY_SYNC_JSON:{"ok": true, "failed_users": []}'
        calls = []
        def runner(command, **kwargs):
            calls.append(command)
            return Done()
        result = run_canonical_wasabi_grant(
            "Flow User", profile={"wasabi_user": "iam-user"}, runner=runner,
            path_resolver=lambda name: ("C:/runtime/PipeSync_py.exe", "C:/app/py_scr/" + name),
        )
        self.assertEqual("complete", result["status"])
        self.assertEqual(["--apply", "--grant-only", "--user", "Flow User"], calls[0][2:])

    def test_canonical_reports_partial_when_planned_grant_was_not_applied(self):
        class Done:
            returncode = 0
            stderr = ""
            stdout = 'WASABI_POLICY_SYNC_JSON:{"ok": true, "failed_users": [], "total_add": 2, "applied_users": 0}'
        result = run_canonical_wasabi_grant(
            "Flow User", profile={"wasabi_user": "iam-user"}, runner=lambda *a, **k: Done(),
            path_resolver=lambda name: ("C:/runtime/PipeSync_py.exe", "C:/app/py_scr/" + name),
        )
        self.assertEqual("partial", result["status"])

    def test_stats_mirror_is_idempotent_and_preserves_reviewers(self):
        handle, path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        try:
            conn = sqlite3.connect(path)
            conn.executescript("""
                CREATE TABLE tasks(id INTEGER PRIMARY KEY);
                CREATE TABLE users(id INTEGER PRIMARY KEY, name TEXT);
                CREATE TABLE task_assignments(task_id INTEGER, user_id INTEGER, role TEXT,
                    UNIQUE(task_id, user_id, role));
                INSERT INTO tasks VALUES(12);
                INSERT INTO users VALUES(3, 'Reviewer');
                INSERT INTO task_assignments VALUES(12, 3, 'reviewer');
            """)
            conn.commit(); conn.close()
            users = [{"id": 8, "name": "Artist"}]
            self.assertTrue(mirror_stats_assignees(path, 12, users))
            self.assertTrue(mirror_stats_assignees(path, 12, users))
            conn = sqlite3.connect(path)
            rows = conn.execute("SELECT user_id, role FROM task_assignments ORDER BY role").fetchall()
            conn.close()
            self.assertEqual([(8, "assignee"), (3, "reviewer")], rows)
        finally:
            os.unlink(path)

    def test_normal_and_shift_callsites_use_the_same_canonical_engine(self):
        files = [
            ROOT / "LGA_NKS_Assignee_Panel.py",
            ROOT / "LGA_NKS_Assignee_Panel_py" / "LGA_NKS_Flow_Assign_Assignee.py",
        ]
        for path in files:
            source = path.read_text(encoding="utf-8-sig")
            tree = ast.parse(source)
            calls = [
                node.func.id for node in ast.walk(tree)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "run_canonical_wasabi_grant"
            ]
            self.assertTrue(calls, str(path))
        self.assertNotIn("LGA_NKS_Wasabi_PolicyAssign", files[0].read_text(encoding="utf-8-sig"))

    def test_mutating_workers_require_the_context_captured_by_the_ui_flow(self):
        expectations = {
            ROOT / "LGA_NKS_Assignee_Panel.py": {"CanonicalGrantWorker"},
            ROOT / "LGA_NKS_Assignee_Panel_py" / "LGA_NKS_Flow_Assign_Assignee.py": {
                "AssignSelectedTasksWorker",
            },
            ROOT / "LGA_NKS_Flow_S3_Panel_py" / "LGA_NKS_Flow_CreateShot.py": {
                "CreateShotWorker", "ShotExistenceCheckWorker",
            },
        }
        for path, class_names in expectations.items():
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            classes = {
                node.name: node for node in tree.body
                if isinstance(node, ast.ClassDef) and node.name in class_names
            }
            self.assertEqual(class_names, set(classes), str(path))
            for class_name, class_node in classes.items():
                guarded_calls = [
                    call for call in ast.walk(class_node)
                    if isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Name)
                    and call.func.id == "load_in_stable_context"
                    and any(keyword.arg == "expected_mode" for keyword in call.keywords)
                ]
                self.assertTrue(guarded_calls, "{0}:{1}".format(path, class_name))


if __name__ == "__main__":
    unittest.main()
