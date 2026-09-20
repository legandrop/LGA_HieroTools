import ast
import importlib.util
import unittest
from pathlib import Path


PANEL_PATH = Path(__file__).resolve().parents[1] / "LGA_NKS_Coordination_Panel.py"
FLOW_PANEL_PATH = Path(__file__).resolve().parents[1] / "LGA_NKS_Flow_Panel.py"
VIEWER_PANEL_PATH = Path(__file__).resolve().parents[1] / "LGA_NKS_ViewerTL_Panel.py"
STYLE_UTILS_PATH = (
    Path(__file__).resolve().parents[1]
    / "LGA_NKS_Shared"
    / "LGA_NKS_StyleUtils.py"
)


class CoordinationPanelLayoutTests(unittest.TestCase):
    def test_flow_actions_precede_s3_actions_and_use_semantic_styles(self):
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
        buttons = fixed_buttons.elts
        names = [item.elts[0].value for item in buttons]

        self.assertEqual(
            names,
            [
                "Create Shot",
                "Modify Shot",
                "Check Shots Exist",
                "Thumbnail",
                "Shot Priority",
                "Reveal in Flow",
                "FileManagerS3",
                "Download Shot",
                "Upload Shot",
                "Download Clip",
                "Download AMF",
            ],
        )
        self.assertEqual(
            [item.elts[2].id for item in buttons[:4]],
            ["SHOT_WORKFLOW_COLOR"] * 4,
        )
        self.assertEqual(buttons[4].elts[2].value, "gradient_flow_priority")
        self.assertEqual(buttons[5].elts[2].value, "gradient_flow_reveal")
        self.assertEqual(
            [item.elts[2].value for item in buttons[6:]],
            ["gradient_magenta_violet"] * 5,
        )
        self.assertNotIn(".Psync", names)

    def test_psync_tool_is_retained_but_not_exposed(self):
        source = PANEL_PATH.read_text(encoding="utf-8")
        legacy_script = (
            PANEL_PATH.parent
            / "LGA_NKS_Flow_S3_Panel_py"
            / "LGA_NKS_PipeSync_CreatePsync.py"
        )

        self.assertIn("def create_pipesync_token_file", source)
        self.assertTrue(legacy_script.is_file())

    def test_visible_titles_change_without_renaming_dock_ids(self):
        flow_tree = ast.parse(FLOW_PANEL_PATH.read_text(encoding="utf-8"))
        s3_tree = ast.parse(PANEL_PATH.read_text(encoding="utf-8"))
        viewer_tree = ast.parse(VIEWER_PANEL_PATH.read_text(encoding="utf-8"))

        def string_calls(tree, method_name):
            return [
                node.args[0].value
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == method_name
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ]

        self.assertIn("Flow Review", string_calls(flow_tree, "setWindowTitle"))
        self.assertIn("Flow | S3", string_calls(s3_tree, "setWindowTitle"))
        self.assertIn("Viewer | TL", string_calls(viewer_tree, "setWindowTitle"))
        self.assertIn("com.lega.FPTPanel", string_calls(flow_tree, "setObjectName"))
        self.assertIn("com.lega.FlowProdPanel", string_calls(s3_tree, "setObjectName"))

    def test_private_directories_use_visible_panel_names(self):
        root = PANEL_PATH.parent
        self.assertTrue((root / "LGA_NKS_Flow_Rev_Panel_py").is_dir())
        self.assertTrue((root / "LGA_NKS_Flow_S3_Panel_py").is_dir())
        self.assertFalse((root / "LGA_NKS_Flow_Panel_py").exists())
        self.assertFalse((root / "LGA_NKS_Coordination_Panel_py").exists())

    def test_semantic_gradients_render_all_states(self):
        spec = importlib.util.spec_from_file_location("style_utils", STYLE_UTILS_PATH)
        style_utils = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(style_utils)

        expected = {
            "gradient_magenta_violet": ("#443a91", "#543a91", "#5b3a91"),
            "gradient_flow_priority": ("#2a4d3a", "#450101"),
            "gradient_flow_reveal": ("#2a4d3a", "#1f1f1f"),
        }
        self.assertEqual(style_utils.GRADIENT_COLORS, expected)

        for gradient_name, colors in expected.items():
            stylesheet = style_utils.create_gradient_style(gradient_name)
            self.assertIn("QPushButton:hover", stylesheet)
            self.assertIn("QPushButton:pressed", stylesheet)
            for color in colors:
                self.assertIn(color, stylesheet)


if __name__ == "__main__":
    unittest.main()
