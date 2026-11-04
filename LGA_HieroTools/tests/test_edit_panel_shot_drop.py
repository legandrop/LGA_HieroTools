"""
Drop de carpetas de shot sobre el Edit Panel -> Import Shot.

Se extraen los metodos por AST para no levantar hiero ni Qt: se prueba que el
drop acepta solo carpetas locales, que difiere la importacion y que main() de
Import Shot usa las carpetas recibidas sin abrir el selector.
"""

import ast
import copy
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
PANEL_PATH = ROOT / "LGA_NKS_Edit_Panel.py"
IMPORT_PATH = ROOT / "LGA_NKS_Edit_Panel_py" / "LGA_import_shots.py"


def _load_panel_methods(names, namespace):
    tree = ast.parse(PANEL_PATH.read_text(encoding="utf-8-sig"))
    panel_class = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "ReconnectMediaWidget"
    )
    selected = []
    for node in panel_class.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            node = copy.deepcopy(node)
            # El @staticmethod se saca y se vuelve a envolver abajo
            node.decorator_list = []
            selected.append(node)
    panel = ast.ClassDef(name="Panel", bases=[], keywords=[], body=selected,
                         decorator_list=[])
    module = ast.Module(body=[panel], type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(PANEL_PATH), "exec"), namespace)
    cls = namespace["Panel"]
    if "_shot_folders_from_mime" in names:
        cls._shot_folders_from_mime = staticmethod(cls._shot_folders_from_mime)
    return cls


def _load_module_function(path, name, namespace):
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    function = copy.deepcopy(next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    ))
    module = ast.Module(body=[function], type_ignores=[])
    exec(compile(module, str(path), "exec"), namespace)
    return namespace[name]


class _FakeUrl:
    def __init__(self, path, local=True):
        self.path = path
        self.local = local

    def isLocalFile(self):
        return self.local

    def toLocalFile(self):
        return self.path


class _FakeMime:
    def __init__(self, urls):
        self._urls = urls

    def hasUrls(self):
        return bool(self._urls)

    def urls(self):
        return self._urls


class EditPanelShotDropTests(unittest.TestCase):
    def setUp(self):
        self.pending = []
        namespace = {
            "os": os,
            "debug_print": lambda *args, **kwargs: None,
            "is_widget_alive": lambda widget: True,
            "QtCore": SimpleNamespace(QTimer=SimpleNamespace(
                singleShot=lambda delay, callback: self.pending.append(callback))),
        }
        self.panel_type = _load_panel_methods(
            {"_shot_folders_from_mime", "dragEnterEvent", "dropEvent"}, namespace)

    def _panel(self):
        panel = self.panel_type()
        panel.overlay_calls = []
        panel._set_shot_drop_overlay_visible = (
            lambda visible, count=0: panel.overlay_calls.append((visible, count)))
        panel.imported = []
        panel.import_shot_folders = panel.imported.append
        return panel

    def test_only_local_folders_are_accepted(self):
        folders_from = self.panel_type._shot_folders_from_mime
        with tempfile.TemporaryDirectory() as temp_dir:
            shot_a = os.path.join(temp_dir, "PROJA_1013_0800")
            shot_b = os.path.join(temp_dir, "PROJA_1013_0900")
            os.makedirs(shot_a)
            os.makedirs(shot_b)
            loose = os.path.join(temp_dir, "plate.exr")
            Path(loose).touch()

            norm = lambda p: p.replace("\\", "/")
            self.assertEqual(
                [norm(shot_a), norm(shot_b)],
                folders_from(_FakeMime([_FakeUrl(shot_a), _FakeUrl(shot_b + "/")])),
            )
            # Repetida, cuenta una vez
            self.assertEqual([norm(shot_a)],
                             folders_from(_FakeMime([_FakeUrl(shot_a), _FakeUrl(shot_a)])))
            # Un archivo mezclado anula todo el drag: no se importa a medias
            self.assertEqual([], folders_from(_FakeMime([_FakeUrl(shot_a), _FakeUrl(loose)])))
            self.assertEqual([], folders_from(_FakeMime([_FakeUrl(shot_a, local=False)])))
            self.assertEqual([], folders_from(_FakeMime([_FakeUrl(os.path.join(temp_dir, "nope"))])))
            self.assertEqual([], folders_from(_FakeMime([])))
            self.assertEqual([], folders_from(None))

    def test_drag_enter_shows_overlay_with_folder_count(self):
        panel = self._panel()
        with tempfile.TemporaryDirectory() as temp_dir:
            for name in ("PROJA_1013_0800", "PROJA_1013_0900", "PROJA_1013_1000"):
                os.makedirs(os.path.join(temp_dir, name))
            urls = [_FakeUrl(os.path.join(temp_dir, n)) for n in sorted(os.listdir(temp_dir))]
            accepted = []
            event = SimpleNamespace(mimeData=lambda: _FakeMime(urls),
                                    acceptProposedAction=lambda: accepted.append(True),
                                    ignore=lambda: accepted.append(False))
            panel.dragEnterEvent(event)
            self.assertEqual([True], accepted)
            self.assertEqual([(True, 3)], panel.overlay_calls)

            file_path = os.path.join(temp_dir, "edit.mov")
            Path(file_path).touch()
            panel.overlay_calls = []
            accepted = []
            event = SimpleNamespace(mimeData=lambda: _FakeMime([_FakeUrl(file_path)]),
                                    acceptProposedAction=lambda: accepted.append(True),
                                    ignore=lambda: accepted.append(False))
            panel.dragEnterEvent(event)
            self.assertEqual([False], accepted)
            self.assertEqual([], panel.overlay_calls)

    def test_drop_is_deferred_and_passes_all_folders(self):
        panel = self._panel()
        with tempfile.TemporaryDirectory() as temp_dir:
            shot_a = os.path.join(temp_dir, "PROJA_1013_0800")
            shot_b = os.path.join(temp_dir, "PROJA_1013_0900")
            os.makedirs(shot_a)
            os.makedirs(shot_b)
            accepted = []
            event = SimpleNamespace(
                mimeData=lambda: _FakeMime([_FakeUrl(shot_a), _FakeUrl(shot_b)]),
                acceptProposedAction=lambda: accepted.append(True),
                ignore=lambda: accepted.append(False))
            panel.dropEvent(event)
            self.assertEqual([True], accepted)
            self.assertEqual([(False, 0)], panel.overlay_calls)
            # Nada se importa adentro del dropEvent: va al siguiente ciclo de Qt
            self.assertEqual([], panel.imported)
            self.pending.pop()()
            norm = lambda p: p.replace("\\", "/")
            self.assertEqual([[norm(shot_a), norm(shot_b)]], panel.imported)


class _Stop(Exception):
    """Corta main() justo despues de decidir que carpetas usar."""


class ImportShotsMainTests(unittest.TestCase):
    def _main(self, picker_result):
        calls = SimpleNamespace(picker=0, roots=None)

        def picker():
            calls.picker += 1
            return picker_result

        def shot_name(root):
            calls.roots = root
            raise _Stop()

        namespace = {
            "hiero": SimpleNamespace(ui=SimpleNamespace(activeSequence=lambda: object())),
            "show_warning": lambda *args: None,
            "debug_print": lambda *args, **kwargs: None,
            "_pick_and_remember_shot_folders": picker,
            "_get_shot_name_from_folder": shot_name,
        }
        main = _load_module_function(IMPORT_PATH, "main", namespace)
        return main, calls

    def test_dropped_folders_skip_the_picker(self):
        main, calls = self._main(picker_result=["T:/VFX-PROJA/PICKED"])
        with self.assertRaises(_Stop):
            main(shot_roots=["T:\\VFX-PROJA\\PROJA_1013_0800\\"])
        self.assertEqual(0, calls.picker)
        self.assertEqual("T:/VFX-PROJA/PROJA_1013_0800", calls.roots)

    def test_without_folders_main_opens_the_picker(self):
        main, calls = self._main(picker_result=["T:/VFX-PROJA/PROJA_1013_0800"])
        with self.assertRaises(_Stop):
            main()
        self.assertEqual(1, calls.picker)
        self.assertEqual("T:/VFX-PROJA/PROJA_1013_0800", calls.roots)

    def test_cancelled_picker_imports_nothing(self):
        main, calls = self._main(picker_result=[])
        self.assertIsNone(main())
        self.assertEqual(1, calls.picker)
        self.assertIsNone(calls.roots)


if __name__ == "__main__":
    unittest.main()
