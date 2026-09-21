import ast
import os
import sys
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PANEL_DIR = ROOT / "LGA_NKS_Flow_S3_Panel_py"
sys.path.insert(0, str(PANEL_DIR))

import LGA_NKS_Flow_CreateShot_Folders as folders
from LGA_NKS_Flow_CreateShot_Folders import (
    calculate_shot_base_path,
    create_task_folders,
    ensure_folder_exists,
    folder_summary_has_results,
)


CREATE_SHOT_SOURCE = PANEL_DIR / "LGA_NKS_Flow_CreateShot.py"
MODIFY_SHOT_SOURCE = PANEL_DIR / "LGA_NKS_Flow_ModifyShot.py"


def run_find_shot_and_tasks(folder_summary, shot_base_path="/show/PROJA/010/shot"):
    tree = ast.parse(CREATE_SHOT_SOURCE.read_text(encoding="utf-8-sig"))
    manager_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "ShotGridManager"
    )
    namespace = {
        "debug_print": lambda *args, **kwargs: None,
        "calculate_shot_base_path": lambda file_path: shot_base_path,
        "create_folders_for_shot_tasks": lambda path, tasks: (
            folder_summary,
            [],
        ),
        "folder_summary_has_results": folder_summary_has_results,
    }
    exec(
        compile(ast.Module(body=[manager_node], type_ignores=[]), str(CREATE_SHOT_SOURCE), "exec"),
        namespace,
    )
    manager = namespace["ShotGridManager"].__new__(namespace["ShotGridManager"])
    manager.sg = type("SG", (), {"find": lambda self, *args: []})()
    manager.get_project_id = lambda project_name: 1
    manager.find_tasks_for_shot = lambda shot_id: [{"id": 8, "content": "Comp"}]

    def create_shot(*args, **kwargs):
        manager.last_create_result = {"status": "complete", "errors": []}
        return {"id": 7, "code": "PROJA_010_020"}

    manager.create_shot = create_shot
    result = manager.find_shot_and_tasks(
        "PROJA",
        "PROJA_010_020",
        {"tasks": {"Comp": {"enabled": True}}},
        file_path=os.path.abspath("media/file.exr"),
    )
    return manager, result


class CreateShotFolderPathTests(unittest.TestCase):
    def test_calculates_four_parents_from_absolute_media_path(self):
        media_path = os.path.abspath(
            os.path.join(
                os.sep,
                "VFX-PROJA",
                "010",
                "PROJA_010_020",
                "Comp",
                "4_publish",
                "file.exr",
            )
        )
        expected = media_path
        for _level in range(4):
            expected = os.path.dirname(expected)
        self.assertEqual(expected, calculate_shot_base_path(media_path))

    def test_rejects_relative_or_shallow_paths(self):
        self.assertIsNone(calculate_shot_base_path("relative/file.exr"))
        self.assertIsNone(calculate_shot_base_path(os.path.abspath(os.sep)))

    def test_folder_summary_requires_created_or_existing_paths(self):
        self.assertFalse(folder_summary_has_results(None))
        self.assertFalse(folder_summary_has_results({"created": [], "existing": []}))
        self.assertTrue(
            folder_summary_has_results({"created": ["shot/Comp"], "existing": []})
        )
        self.assertTrue(
            folder_summary_has_results({"created": [], "existing": ["shot/Comp"]})
        )
        self.assertFalse(
            folder_summary_has_results({
                "created": ["shot/Comp"],
                "existing": [],
                "failed": ["shot/Comp/4_publish"],
            })
        )

    def test_folder_creation_error_is_not_classified_as_existing(self):
        with mock.patch.object(folders.os.path, "exists", return_value=False), mock.patch.object(
            folders.os, "makedirs", side_effect=OSError("denied")
        ):
            status, message = ensure_folder_exists("shot/Comp/0_assets")
        self.assertEqual("error", status)
        self.assertIn("denied", message)

    def test_all_failed_folders_produce_empty_success_summary(self):
        with mock.patch.object(
            folders,
            "ensure_folder_exists",
            return_value=("error", "ERROR"),
        ):
            summary, _logs = create_task_folders("shot", ["Comp"])
        self.assertEqual([], summary["created"])
        self.assertEqual([], summary["existing"])
        self.assertEqual(5, len(summary["failed"]))
        self.assertFalse(folder_summary_has_results(summary))

    def test_create_shot_uses_module_helper_not_missing_instance_method(self):
        source = (
            PANEL_DIR / "LGA_NKS_Flow_CreateShot.py"
        ).read_text(encoding="utf-8-sig")
        self.assertNotIn("self.calculate_shot_base_path", source)
        self.assertIn("shot_base_path = calculate_shot_base_path(file_path)", source)

    def test_modify_shot_uses_same_module_helper(self):
        source = MODIFY_SHOT_SOURCE.read_text(encoding="utf-8-sig")
        self.assertNotIn("hiero_ops.calculate_shot_base_path", source)
        self.assertIn("shot_base_path = calculate_shot_base_path(", source)

    def test_postprocess_returns_created_shot_when_folders_exist(self):
        manager, result = run_find_shot_and_tasks(
            {"created": ["shot/Comp"], "existing": []}
        )
        self.assertEqual(7, result[0]["id"])
        self.assertTrue(result[2])
        self.assertEqual("complete", manager.last_create_result["status"])

    def test_empty_folder_summary_marks_created_shot_partial(self):
        manager, result = run_find_shot_and_tasks(
            {"created": [], "existing": []}
        )
        self.assertEqual(7, result[0]["id"])
        self.assertTrue(result[2])
        self.assertEqual("partial", manager.last_create_result["status"])
        self.assertIn(
            "Task folders could not be created.",
            manager.last_create_result["errors"],
        )

    def test_unresolved_folder_base_marks_created_shot_partial(self):
        manager, result = run_find_shot_and_tasks(
            {"created": [], "existing": []},
            shot_base_path=None,
        )
        self.assertEqual(7, result[0]["id"])
        self.assertTrue(result[2])
        self.assertEqual("partial", manager.last_create_result["status"])
        self.assertIn(
            "The task folder base path could not be resolved.",
            manager.last_create_result["errors"],
        )


if __name__ == "__main__":
    unittest.main()
