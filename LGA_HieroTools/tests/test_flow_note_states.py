"""Estados que piden nota en el Flow Push y efecto sobre la Version.

OK for Delivery (pubsh) abre el dialogo de nota pero no manda la Version a
`vwd`; el resto de los estados con nota si. Corre execute_full_push_operation
del conector sin red, con un sg_manager falso que registra las llamadas.
"""

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "LGA_NKS_Shared"))

from LGA_NKS_Flow_Status_Config import (  # noqa: E402
    NOTE_CAPABLE_CODES,
    is_note_capable,
    marks_version_viewed,
)

CONNECTOR_PATH = ROOT / "LGA_NKS_Flow_Rev_Panel_py" / "LGA_NKS_Flow_Push_connector.py"


def load_connector():
    spec = importlib.util.spec_from_file_location("flow_push_connector", CONNECTOR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeManager:
    def __init__(self):
        self.calls = []
        self.attach_errors = []

    def find_shot_and_tasks(self, project_name, shot_code):
        return {"id": 1}, {"id": 2, "code": shot_code}, [{"id": 3, "content": "comp"}]

    def get_task_assignees(self, task_id):
        return []

    def find_specific_version_for_shot(self, *args, **kwargs):
        version = {"id": 4, "code": "PROJA_010_0010_comp_v003", "user": None}
        return version, "3", None, None

    def update_task_status(self, task_id, status):
        self.calls.append(("task", status))
        return True, None

    def update_version_status(self, project, shot, version_label, status, **kwargs):
        self.calls.append(("version", status))
        return True, None

    def add_comment_to_version(self, *args, **kwargs):
        self.calls.append(("note", args[2]))
        return {"id": 5}, None


class NoteStatesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.connector = load_connector()

    def push(self, button_name, message):
        manager = FakeManager()
        result = self.connector.execute_full_push_operation(
            manager,
            button_name,
            "PROJA_010_0010_comp_v003",
            message,
            [],
            original_file_name="PROJA_010_0010_comp_v003.%04d.exr",
            file_path="T:/VFX-PROJA/010/PROJA_010_0010/Comp/4_publish/PROJA_010_0010_comp_v003/x.exr",
        )
        return result, manager.calls

    def test_ok_for_delivery_asks_note_without_viewed(self):
        self.assertTrue(is_note_capable("pubsh"))
        self.assertFalse(marks_version_viewed("pubsh"))

    def test_other_note_states_still_mark_viewed(self):
        for code in NOTE_CAPABLE_CODES:
            if code != "pubsh":
                self.assertTrue(marks_version_viewed(code), code)
        self.assertFalse(marks_version_viewed("rev_su"))

    def test_ok_for_delivery_push_creates_note_and_keeps_version(self):
        result, calls = self.push("OK for Delivery", "Ready, ship it")
        self.assertTrue(result["success"], result)
        self.assertIn(("task", "pubsh"), calls)
        self.assertIn(("note", "Ready, ship it"), calls)
        self.assertFalse([c for c in calls if c[0] == "version"])
        self.assertFalse(result["applied"]["version_status"])
        self.assertTrue(result["applied"]["note"])

    def test_ok_for_delivery_empty_note_creates_nothing(self):
        result, calls = self.push("OK for Delivery", "")
        self.assertTrue(result["success"], result)
        self.assertEqual(calls, [("task", "pubsh")])

    def test_corrections_marks_version_viewed(self):
        result, calls = self.push("Corrections", "Fix the edge")
        self.assertTrue(result["success"], result)
        self.assertIn(("version", "vwd"), calls)
        self.assertIn(("note", "Fix the edge"), calls)


if __name__ == "__main__":
    unittest.main()
