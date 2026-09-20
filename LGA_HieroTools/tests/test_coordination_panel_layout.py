import ast
import unittest
from pathlib import Path


PANEL_PATH = Path(__file__).resolve().parents[1] / "LGA_NKS_Coordination_Panel.py"


class CoordinationPanelLayoutTests(unittest.TestCase):
    def test_shot_workflow_buttons_are_first_and_share_color(self):
        tree = ast.parse(PANEL_PATH.read_text(encoding="utf-8"))
        fixed_buttons = None

        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target = node.targets[0]
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
                and target.attr == "fixed_buttons"
            ):
                fixed_buttons = node.value
                break

        self.assertIsInstance(fixed_buttons, ast.List)
        first_four = fixed_buttons.elts[:4]
        names = [item.elts[0].value for item in first_four]
        colors = [item.elts[2].id for item in first_four]

        self.assertEqual(
            names,
            ["Create Shot", "Modify Shot", "Check Shots Exist", "Thumbnail"],
        )
        self.assertEqual(colors, ["SHOT_WORKFLOW_COLOR"] * 4)


if __name__ == "__main__":
    unittest.main()
