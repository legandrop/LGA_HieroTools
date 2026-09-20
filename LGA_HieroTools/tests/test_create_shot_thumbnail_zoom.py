import ast
import types
import unittest
from pathlib import Path


SOURCE_PATH = (
    Path(__file__).resolve().parents[1]
    / "LGA_NKS_Coordination_Panel_py"
    / "LGA_NKS_Flow_CreateShot.py"
)


def load_thumbnail_functions(current_viewer):
    tree = ast.parse(SOURCE_PATH.read_text(encoding="utf-8-sig"))
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    module = ast.Module(
        body=[functions["zoom_to_fill_in_viewer"], functions["create_shot_thumbnail"]],
        type_ignores=[],
    )
    events = []
    namespace = {
        "hiero": types.SimpleNamespace(
            ui=types.SimpleNamespace(currentViewer=current_viewer)
        ),
        "QApplication": types.SimpleNamespace(
            processEvents=lambda: events.append("events")
        ),
        "debug_print": lambda *args, **kwargs: None,
    }
    exec(compile(module, str(SOURCE_PATH), "exec"), namespace)
    return namespace, events, functions


class ThumbnailZoomTests(unittest.TestCase):
    def test_uses_viewer_zoom_before_legacy_player(self):
        calls = []
        player = types.SimpleNamespace(zoomToFill=lambda: calls.append("player"))
        viewer = types.SimpleNamespace(
            zoomToFill=lambda: calls.append("viewer"), player=lambda: player
        )
        namespace, events, _ = load_thumbnail_functions(lambda: viewer)

        self.assertTrue(namespace["zoom_to_fill_in_viewer"]())
        self.assertEqual(["viewer"], calls)
        self.assertEqual(["events"], events)

    def test_falls_back_to_legacy_player(self):
        calls = []

        class Viewer:
            def player(self):
                return types.SimpleNamespace(
                    zoomToFill=lambda: calls.append("player")
                )

        namespace, _, _ = load_thumbnail_functions(lambda: Viewer())
        self.assertTrue(namespace["zoom_to_fill_in_viewer"]())
        self.assertEqual(["player"], calls)

    def test_missing_zoom_does_not_abort_thumbnail_capture(self):
        namespace, _, functions = load_thumbnail_functions(
            lambda: types.SimpleNamespace(player=lambda: object())
        )
        self.assertFalse(namespace["zoom_to_fill_in_viewer"]())

        create_function = functions["create_shot_thumbnail"]
        zoom_guard = next(
            node
            for node in create_function.body
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.UnaryOp)
            and isinstance(node.test.operand, ast.Call)
            and getattr(node.test.operand.func, "id", "") == "zoom_to_fill_in_viewer"
        )
        self.assertFalse(
            any(isinstance(node, ast.Return) for node in ast.walk(zoom_guard))
        )


if __name__ == "__main__":
    unittest.main()
