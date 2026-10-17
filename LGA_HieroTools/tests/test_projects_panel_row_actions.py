"""Pruebas de Save incremental y de los marcadores de Upload to Wasabi del Projects Panel."""

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "LGA_NKS_Projects_Panel_py"
    / "LGA_NKS_ProjectRowActions.py"
)
spec = importlib.util.spec_from_file_location("project_row_actions", SCRIPT)
actions = importlib.util.module_from_spec(spec)
spec.loader.exec_module(actions)


class IncrementalSaveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name) / "VFX-PROJA" / "PROJA_SUP"
        self.folder.mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def touch(self, *names):
        for name in names:
            (self.folder / name).write_text("x")

    def test_next_version_keeps_padding(self):
        self.touch("PROJA_SUP_v012.hrox")
        plan = actions.plan_incremental_save(str(self.folder / "PROJA_SUP_v012.hrox"))
        self.assertTrue(plan["ok"])
        self.assertFalse(plan["conflict"])
        self.assertEqual(plan["next_label"], "v013")
        self.assertEqual(os.path.basename(plan["next_path"]), "PROJA_SUP_v013.hrox")

    def test_existing_next_version_is_a_conflict(self):
        self.touch("PROJA_SUP_v012.hrox", "PROJA_SUP_v013.hrox", "PROJA_SUP_v014.hrox")
        plan = actions.plan_incremental_save(str(self.folder / "PROJA_SUP_v012.hrox"))
        self.assertTrue(plan["conflict"])
        self.assertEqual(plan["highest_label"], "v014")
        self.assertEqual(os.path.basename(plan["free_path"]), "PROJA_SUP_v015.hrox")

    def test_ignores_autosaves_and_other_project_groups(self):
        self.touch(
            "PROJA_SUP_v012.hrox",
            "PROJA_SUP_v020.hrox.autosave",
            "PROJA_SUP_Previa_v030.hrox",
        )
        plan = actions.plan_incremental_save(str(self.folder / "PROJA_SUP_v012.hrox"))
        self.assertFalse(plan["conflict"])
        self.assertEqual(plan["next_label"], "v013")

    def test_suffix_after_version_is_kept(self):
        self.touch("PROJA_SUP_v007_test.hrox")
        plan = actions.plan_incremental_save(str(self.folder / "PROJA_SUP_v007_test.hrox"))
        self.assertEqual(os.path.basename(plan["next_path"]), "PROJA_SUP_v008_test.hrox")

    def test_padding_grows_past_999(self):
        self.touch("PROJA_SUP_v999.hrox")
        plan = actions.plan_incremental_save(str(self.folder / "PROJA_SUP_v999.hrox"))
        self.assertEqual(plan["next_label"], "v1000")

    def test_name_without_version_is_refused(self):
        plan = actions.plan_incremental_save(str(self.folder / "PROJA_SUP.hrox"))
        self.assertFalse(plan["ok"])
        self.assertIn("_v###", plan["error"])


class UploadMarkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.notify = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write_marker(self, name, data):
        (self.notify / name).write_text(json.dumps(data), encoding="utf-8")

    def test_marker_path_matches_regardless_of_slashes_and_case(self):
        local = r"T:\VFX-PROJA\PROJA_SUP\PROJA_SUP_v013.hrox"
        self.write_marker("task1.json", {
            "task_id": "task1", "success": True,
            "items": [{"path": "T:/VFX-PROJA/PROJA_SUP/PROJA_SUP_v013.hrox", "kind": "file"}],
        })
        markers = actions.read_markers(str(self.notify))
        self.assertEqual(len(markers), 1)
        self.assertIn(actions.normalize_path(local), actions.marker_paths(markers[0][1]))
        self.assertEqual(actions.marker_result(markers[0][1]), (True, ""))

    def test_failure_and_cancel_markers(self):
        failure = {"success": False, "error_code": "network", "error_message": "Wasabi is unreachable."}
        cancel = {"success": False, "error_code": "cancelled", "error_message": "Upload cancelled."}
        self.assertEqual(actions.marker_result(failure), (False, "Wasabi is unreachable."))
        self.assertFalse(actions.is_cancel_marker(failure))
        self.assertTrue(actions.is_cancel_marker(cancel))

    def test_tmp_and_unreadable_markers(self):
        (self.notify / "task2.json.tmp").write_text("{}")
        (self.notify / "task3.json").write_text("not json")
        markers = actions.read_markers(str(self.notify))
        self.assertEqual([os.path.basename(p) for p, _ in markers], ["task3.json"])
        self.assertIsNone(markers[0][1])

    def test_upload_args(self):
        self.assertEqual(
            actions.build_upload_args("T:/a.hrox", "C:/n"),
            ["--upload-file", "T:/a.hrox", "--notify-completion", "C:/n"],
        )


if __name__ == "__main__":
    unittest.main()
