import ast
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDIT_PANEL = ROOT / "LGA_NKS_Edit_Panel.py"
REVIEW_PANEL = ROOT / "LGA_NKS_Review_Panel.py"
VIEWER_PANEL = ROOT / "LGA_NKS_ViewerTL_Panel.py"
REVIEW_DIR = ROOT / "LGA_NKS_Review_Panel_py"
VIEWER_DIR = ROOT / "LGA_NKS_ViewerTL_Panel_py"
EDIT_DIR = ROOT / "LGA_NKS_Edit_Panel_py"
CONTACT_SHEET = REVIEW_DIR / "LGA_Contact_Sheet_OpenInNukeX.py"
REVEAL_PROJECT = REVIEW_DIR / "LGA_NKS_RevealNKS_Project.py"
IN_OUT_EDITREF = ROOT / "LGA_NKS_ViewerTL_Panel_py" / "LGA_NKS_InOut_Editref.py"


def _button_tuples(panel_path):
    tree = ast.parse(panel_path.read_text(encoding="utf-8-sig"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "self"
            and target.attr == "buttons"
            and isinstance(node.value, ast.List)
        ):
            return [item for item in node.value.elts if isinstance(item, ast.Tuple)]
    raise AssertionError(f"No se encontro self.buttons en {panel_path}")


def _tuple_text(item, index):
    value = item.elts[index]
    return value.value if isinstance(value, ast.Constant) else None


def _local_button_list(panel_path, function_name, variable_name):
    tree = ast.parse(panel_path.read_text(encoding="utf-8-sig"))
    function = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    )
    for node in ast.walk(function):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if (
            isinstance(target, ast.Name)
            and target.id == variable_name
            and isinstance(node.value, ast.List)
        ):
            return [item for item in node.value.elts if isinstance(item, ast.Tuple)]
    raise AssertionError(f"No se encontro {variable_name} en {panel_path}")


def _load_standalone_function(path, function_name, namespace):
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    )
    module = ast.Module(body=[function], type_ignores=[])
    exec(compile(module, str(path), "exec"), namespace)
    return namespace[function_name]


class PanelReviewReorganizationTests(unittest.TestCase):
    def test_edit_order_and_colors_match_editing_groups(self):
        buttons = _button_tuples(EDIT_PANEL)
        names = [_tuple_text(item, 0) for item in buttons]

        self.assertEqual(
            names[names.index("Self ReplaceClip") : names.index("Clear Tag") + 1],
            ["Self ReplaceClip", "Fix Zombies", "Check Frames", "Clear Tag"],
        )
        self.assertNotIn("Match Rev Ver", names)
        self.assertNotIn("Compare Rev EdRef", names)
        self.assertNotIn("Compare EXR aPlate", names)

        colors = {_tuple_text(item, 0): _tuple_text(item, 2) for item in buttons}
        self.assertEqual(colors["New Video Track"], "#453434")
        self.assertEqual(colors["Extend &Edit"], "#453434")

    def test_review_order_keeps_frequent_actions_first_and_rare_comparisons_last(self):
        buttons = _button_tuples(REVIEW_PANEL)
        names = [_tuple_text(item, 0) for item in buttons]
        expected = [
            "Difference Mode",
            "Compare Versions",
            "Compare OFF",
            "Contact Sheet",
            "Previous Annotation",
            "Next Annotation",
            "Reveal in &Explorer",
            "Reveal NKS Project",
            "Reveal NK Sc&ript",
            "OpenInNuke&X",
            "Match Rev Ver",
            "Compare Rev EdRef",
            "Compare EXR aPlate",
        ]
        start = names.index("Difference Mode")
        self.assertEqual(names[start : start + len(expected)], expected)

        colors = {_tuple_text(item, 0): _tuple_text(item, 2) for item in buttons}
        utility_color = colors["Contact Sheet"]
        self.assertEqual(utility_color, "#263d43")
        self.assertEqual(colors["Previous Annotation"], utility_color)
        self.assertEqual(colors["Next Annotation"], utility_color)
        self.assertNotEqual(utility_color, colors["Difference Mode"])
        self.assertNotEqual(utility_color, colors["Compare Versions"])

        self.assertNotIn("ON Clips | OFF v00", names)
        self.assertNotIn("ON OFF _comp_", names)

    def test_viewertl_labels_and_groups_declare_their_scope(self):
        viewer_buttons = _local_button_list(
            VIEWER_PANEL, "create_dynamic_buttons", "viewer_buttons"
        )
        timeline_buttons = _local_button_list(
            VIEWER_PANEL, "create_dynamic_buttons", "timeline_buttons"
        )
        toggle_buttons = _local_button_list(
            VIEWER_PANEL, "create_dynamic_buttons", "toggle_buttons"
        )

        self.assertEqual(
            [_tuple_text(item, 0) for item in viewer_buttons],
            [
                "&Viewer | Rec.709",
                "Viewer | Mask 3:2",
                "Viewer | Frame Number",
                "Viewer | Snapshot",
            ],
        )
        self.assertEqual(
            [_tuple_text(item, 0) for item in timeline_buttons],
            ["TL | Refresh", "TL | Top Track", "TL | In/Out EditRef"],
        )
        self.assertEqual(
            [_tuple_text(item, 0) for item in toggle_buttons],
            ["TL | ON Clips / OFF v00", "TL | ON/OFF _comp_"],
        )

        viewer_colors = {
            _tuple_text(item, 0): _tuple_text(item, 2) for item in viewer_buttons
        }
        toggle_colors = {
            _tuple_text(item, 0): _tuple_text(item, 2) for item in toggle_buttons
        }
        self.assertEqual(
            viewer_colors["Viewer | Frame Number"],
            viewer_colors["&Viewer | Rec.709"],
        )
        self.assertNotEqual(
            viewer_colors["Viewer | Frame Number"],
            toggle_colors["TL | ON/OFF _comp_"],
        )

        source = VIEWER_PANEL.read_text(encoding="utf-8-sig")
        self.assertIn('f"TL | Prev Rev {config[\'nombre\']}"', source)
        self.assertIn('f"TL | Next Rev {config[\'nombre\']}"', source)
        self.assertIn('"TL | ON/OFF _%s_" % task', source)
        self.assertIn(
            "all_buttons = viewer_buttons + timeline_buttons + user_buttons + toggle_buttons",
            source,
        )

    def test_timeline_toggle_scripts_live_only_with_viewertl_panel(self):
        scripts = (
            "LGA_NKS_ON_Clips_OFF_v00-Clips.py",
            "LGA_NKS_Clip_DisableEXR.py",
            "LGA_NKS_Clip_DisableRoto.py",
            "LGA_NKS_Clip_DisableCG.py",
        )
        for script in scripts:
            self.assertTrue((VIEWER_DIR / script).is_file())
            self.assertFalse((REVIEW_DIR / script).exists())

        source = VIEWER_PANEL.read_text(encoding="utf-8-sig")
        self.assertIn('"LGA_NKS_ViewerTL_Panel_py", script_name', source)
        self.assertIn("self.clicked.connect(self._dispatch_click)", source)
        self.assertIn("QApplication.keyboardModifiers()", source)

    def test_comparison_scripts_live_only_with_review_panel(self):
        scripts = (
            "LGA_NKS_MatchVerToEXR.py",
            "LGA_NKS_CompareVerToEditref.py",
            "LGA_NKS_CompareEXR_to_aPlate.py",
        )
        for script in scripts:
            self.assertTrue((REVIEW_DIR / script).is_file())
            self.assertFalse((EDIT_DIR / script).exists())

        source = REVIEW_PANEL.read_text(encoding="utf-8-sig")
        self.assertIn('"LGA_NKS_Review_Panel_py", script_name', source)
        self.assertIn("force_all_clips=force_all_clips", source)

    def test_custom_review_buttons_dispatch_clicked_for_keyboard_access(self):
        source = REVIEW_PANEL.read_text(encoding="utf-8-sig")
        self.assertIn("self.clicked.connect(self._dispatch_click)", source)
        self.assertIn("QApplication.keyboardModifiers()", source)
        self.assertNotIn("def mousePressEvent(self, event):", source.split("class ReviewPanel", 1)[0])

    def test_contact_sheet_has_no_network_wait_on_main_path(self):
        tree = ast.parse(CONTACT_SHEET.read_text(encoding="utf-8-sig"))
        functions = {
            node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
        }
        self.assertNotIn("_ping_nukex", functions)
        self.assertIn("_send_paste_request", functions)
        self.assertIn("_send_paste_in_thread", functions)

        main_calls = {
            node.func.id
            for node in ast.walk(functions["main"])
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertIn("_send_paste_in_thread", main_calls)
        self.assertNotIn("_send_paste_request", main_calls)
        self.assertNotIn("_flush_log", main_calls)

        source = CONTACT_SHEET.read_text(encoding="utf-8-sig")
        self.assertIn('sock.sendall(b"paste_clipboard")', source)
        self.assertNotIn('sendall("ping"', source)
        self.assertIn("QtCore.Signal(bool, str)", source)

    def test_contact_sheet_worker_protocol_uses_one_paste_request(self):
        class FakeSocket:
            def __init__(self, response):
                self.response = response
                self.timeouts = []
                self.connected = None
                self.sent = []

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def settimeout(self, value):
                self.timeouts.append(value)

            def connect(self, address):
                self.connected = address

            def sendall(self, payload):
                self.sent.append(payload)

            def recv(self, _size):
                return self.response

        fake = FakeSocket(b"Clipboard pasted successfully")

        class SocketModule:
            AF_INET = object()
            SOCK_STREAM = object()

            @staticmethod
            def socket(_family, _kind):
                return fake

        send_request = _load_standalone_function(
            CONTACT_SHEET,
            "_send_paste_request",
            {
                "socket": SocketModule,
                "HOST": "localhost",
                "PORT": 54325,
                "debug_print": lambda *_args, **_kwargs: None,
                "RuntimeError": RuntimeError,
            },
        )

        self.assertEqual(send_request(), "Clipboard pasted successfully")
        self.assertEqual(fake.connected, ("localhost", 54325))
        self.assertEqual(fake.sent, [b"paste_clipboard"])
        self.assertEqual(fake.timeouts, [10, 120])

    def test_reveal_project_uses_active_sequence_and_safe_fallback(self):
        source = REVEAL_PROJECT.read_text(encoding="utf-8-sig")
        self.assertIn("hiero.ui.activeSequence()", source)
        self.assertIn("return sequence.project()", source)
        self.assertIn("projects[0] if len(projects) == 1 else None", source)
        self.assertNotIn("if projects:\n        return projects[0]", source)

    def test_reveal_project_prefers_owner_of_active_sequence(self):
        project_a = object()
        project_b = object()
        sequence = types.SimpleNamespace(project=lambda: project_b)
        hiero = types.SimpleNamespace(
            ui=types.SimpleNamespace(activeSequence=lambda: sequence),
            core=types.SimpleNamespace(projects=lambda: [project_a, project_b]),
        )
        get_active_project = _load_standalone_function(
            REVEAL_PROJECT,
            "get_active_project",
            {"hiero": hiero, "debug_print": lambda *_args: None},
        )
        self.assertIs(get_active_project(), project_b)

    def test_reveal_project_does_not_guess_between_multiple_projects(self):
        hiero = types.SimpleNamespace(
            ui=types.SimpleNamespace(activeSequence=lambda: None),
            core=types.SimpleNamespace(projects=lambda: [object(), object()]),
        )
        get_active_project = _load_standalone_function(
            REVEAL_PROJECT,
            "get_active_project",
            {"hiero": hiero, "debug_print": lambda *_args: None},
        )
        self.assertIsNone(get_active_project())

    def test_editref_zoom_uses_imported_qtcore_timer(self):
        source = IN_OUT_EDITREF.read_text(encoding="utf-8-sig")
        self.assertIn("QtCore.QTimer.singleShot(", source)
        self.assertNotIn("\n            QTimer.singleShot(", source)


if __name__ == "__main__":
    unittest.main()
