"""Persistencia de los checkboxes de la ventana de resultados del Flow Pull.

Ejecuta _load_window_setting() y _save_window_setting() sin abrir NKS (el
modulo importa hiero), contra un INI temporal. Cubre lo que se rompe sin
aviso: que un checkbox nuevo no persista, o que guardar uno pise a los otros.
"""

import ast
import configparser
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOW_PULL_PATH = ROOT / "LGA_NKS_Flow_Rev_Panel_py" / "LGA_NKS_Flow_Pull.py"

SETTINGS_NAMES = {"_FLOWPULL_SECTION", "_FLOWPULL_DEFAULTS"}
SETTINGS_FUNCS = {"_load_window_setting", "_save_window_setting"}


def load_settings_helpers(ini_path):
    tree = ast.parse(FLOW_PULL_PATH.read_text(encoding="utf-8"))
    keep = [
        node
        for node in tree.body
        if (isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") in SETTINGS_NAMES)
        or (isinstance(node, ast.FunctionDef) and node.name in SETTINGS_FUNCS)
    ]
    namespace = {
        "configparser": configparser,
        "debug_print": lambda *args, **kwargs: None,
        "_flowpull_settings_path": lambda: ini_path,
    }
    exec(compile(ast.Module(body=keep, type_ignores=[]), str(FLOW_PULL_PATH), "exec"), namespace)
    return namespace


class FlowPullWindowSettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ini = Path(self.tmp.name) / "LGA" / "HieroTools" / "FlowPull.ini"
        helpers = load_settings_helpers(self.ini)
        self.defaults = helpers["_FLOWPULL_DEFAULTS"]
        self.load = helpers["_load_window_setting"]
        self.save = helpers["_save_window_setting"]

    def tearDown(self):
        self.tmp.cleanup()

    def test_los_tres_checkboxes_persisten(self):
        self.assertEqual(
            set(self.defaults), {"keep_on_top", "only_in_review", "only_for_me"}
        )

    def test_sin_ini_devuelve_los_defaults(self):
        self.assertFalse(self.ini.exists())
        for key, default in self.defaults.items():
            self.assertEqual(self.load(key), default, key)

    def test_guardar_y_releer_cada_clave(self):
        for key, default in self.defaults.items():
            self.save(key, not default)
            self.assertEqual(self.load(key), (not default), key)

    def test_guardar_una_clave_no_pisa_las_otras(self):
        self.save("keep_on_top", False)
        self.save("only_for_me", True)
        self.save("only_in_review", False)
        self.save("only_in_review", True)
        self.assertFalse(self.load("keep_on_top"))
        self.assertTrue(self.load("only_for_me"))
        self.assertTrue(self.load("only_in_review"))

    def test_ini_previo_con_solo_keep_on_top(self):
        # El INI de quien ya usaba la ventana trae solo keep_on_top.
        self.ini.parent.mkdir(parents=True)
        self.ini.write_text("[FlowPullWindow]\nkeep_on_top = false\n", encoding="utf-8")
        self.assertFalse(self.load("keep_on_top"))
        self.assertTrue(self.load("only_in_review"))
        self.assertFalse(self.load("only_for_me"))

    def test_valor_ilegible_cae_al_default(self):
        self.ini.parent.mkdir(parents=True)
        self.ini.write_text("[FlowPullWindow]\nonly_for_me = quizas\n", encoding="utf-8")
        self.assertFalse(self.load("only_for_me"))


if __name__ == "__main__":
    unittest.main()
