"""Comprobacion contra Flow antes de guardar la Submission Note.

Ejecuta submission_stale_reason() del conector sin red, con un sg_manager falso.
"""

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "LGA_NKS_Shared"))

from LGA_NKS_Slate_Config import DELIVERY_QUEUE_CODES, VERSION_SUBMISSION_FIELDS  # noqa: E402

CONNECTOR_PATH = ROOT / "LGA_NKS_Flow_Rev_Panel_py" / "LGA_NKS_Flow_Push_connector.py"


def load_stale_reason():
    tree = ast.parse(CONNECTOR_PATH.read_text(encoding="utf-8"))
    keep = [
        node
        for node in tree.body
        if (isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "STALE_SUBMISSION_HINT")
        or (isinstance(node, ast.FunctionDef) and node.name == "submission_stale_reason")
    ]
    namespace = {
        "DELIVERY_QUEUE_CODES": DELIVERY_QUEUE_CODES,
        "VERSION_SUBMISSION_FIELDS": VERSION_SUBMISSION_FIELDS,
        "debug_print": lambda *args, **kwargs: None,
    }
    exec(compile(ast.Module(body=keep, type_ignores=[]), str(CONNECTOR_PATH), "exec"), namespace)
    return namespace["submission_stale_reason"]


class FakeSg:
    def __init__(self, fields):
        self.fields = fields

    def read_version_fields(self, version_id, fields):
        return dict(self.fields), None


EMPTY = {name: "" for name in VERSION_SUBMISSION_FIELDS}


class SubmissionStaleTests(unittest.TestCase):
    def setUp(self):
        self.reason = load_stale_reason()
        self.version = {"id": 9030}

    def check(self, flow_fields, flow_status, shown_fields, shown_status, submission_only=False):
        tasks = [{"content": "Comp", "sg_status_list": flow_status}]
        expected = {"fields": shown_fields, "task_status": shown_status}
        return self.reason(FakeSg(flow_fields), self.version, tasks, "comp", expected, submission_only)

    def test_unchanged_passes(self):
        self.assertIsNone(self.check(EMPTY, "rev_di", EMPTY, "rev_di"))

    def test_note_changed_in_flow_blocks(self):
        flow = dict(EMPTY, sg_submission_note="Written by someone else")
        self.assertIn("changed in Flow", self.check(flow, "rev_di", EMPTY, "rev_di"))

    def test_task_entered_delivery_queue_blocks(self):
        reason = self.check(EMPTY, DELIVERY_QUEUE_CODES[0], EMPTY, "rev_di")
        self.assertIn("delivery queue", reason)

    def test_note_only_in_queue_passes(self):
        queued = DELIVERY_QUEUE_CODES[0]
        self.assertIsNone(self.check(EMPTY, queued, EMPTY, queued, submission_only=True))

    def test_whitespace_differences_do_not_block(self):
        flow = dict(EMPTY, sg_submitting_for="WIP ")
        shown = dict(EMPTY, sg_submitting_for="WIP")
        self.assertIsNone(self.check(flow, "rev_di", shown, "rev_di"))


if __name__ == "__main__":
    unittest.main()
