"""Tooltips de los botones de estado del panel Flow Review.

Ejecuta PUSH_TOOLTIPS y status_button_tooltip() del panel sin abrir NKS (el
modulo importa hiero), con las configs reales de estados y del slate.
"""

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from LGA_NKS_Shared.LGA_NKS_Flow_Status_Config import get_push_buttons, is_note_capable  # noqa: E402
from LGA_NKS_Shared.LGA_NKS_Slate_Config import (  # noqa: E402
    SLATE_CONTEXT_MODE,
    SUBMISSION_BUTTON_LABEL,
    TOOLTIPS as SLATE_TOOLTIPS,
)

FLOW_PANEL_PATH = ROOT / "LGA_NKS_Flow_Panel.py"
CLEAR_TAG_BUTTONS = ("Rev Dir", "Corrections")


def load_tooltip_helpers():
    tree = ast.parse(FLOW_PANEL_PATH.read_text(encoding="utf-8"))
    keep = [
        node
        for node in tree.body
        if (isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "PUSH_TOOLTIPS")
        or (isinstance(node, ast.FunctionDef) and node.name == "status_button_tooltip")
    ]
    namespace = {"is_note_capable": is_note_capable, "SLATE_TOOLTIPS": SLATE_TOOLTIPS}
    exec(compile(ast.Module(body=keep, type_ignores=[]), str(FLOW_PANEL_PATH), "exec"), namespace)
    return namespace["PUSH_TOOLTIPS"], namespace["status_button_tooltip"]


class FlowPanelTooltipTests(unittest.TestCase):
    def setUp(self):
        self.texts, self.tooltip = load_tooltip_helpers()

    def tooltip_for(self, button, mode):
        label = button["label"]
        return self.tooltip(
            label,
            button["code"],
            label in CLEAR_TAG_BUTTONS,
            label == SUBMISSION_BUTTON_LABEL and mode == SLATE_CONTEXT_MODE,
        )

    def test_every_status_button_explains_its_gestures(self):
        for mode in ("studio", "client"):
            for button in get_push_buttons(mode):
                text = self.tooltip_for(button, mode)
                with self.subTest(mode=mode, button=button["label"]):
                    self.assertTrue(text.startswith("Click: "))
                    self.assertIn(button["label"], text)
                    # Shift+Click solo se anuncia donde cambia algo: los estados con nota.
                    self.assertEqual("Shift+Click:" in text, is_note_capable(button["code"]))

    def test_submission_gesture_only_on_rev_dir_in_studio(self):
        for mode in ("studio", "client"):
            for button in get_push_buttons(mode):
                text = self.tooltip_for(button, mode)
                expected = button["label"] == SUBMISSION_BUTTON_LABEL and mode == SLATE_CONTEXT_MODE
                with self.subTest(mode=mode, button=button["label"]):
                    self.assertEqual("Ctrl+Alt+Click:" in text, expected)

    def test_fixed_button_texts_have_no_mojibake(self):
        for key in ("fpt_pull", "review_pic", "shot_info"):
            with self.subTest(key=key):
                self.assertNotRegex(self.texts[key], r"\w\?\w")


if __name__ == "__main__":
    unittest.main()
