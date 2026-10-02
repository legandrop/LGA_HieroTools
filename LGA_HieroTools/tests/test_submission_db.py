"""Submission Note desde pipesync.db (Ctrl+Alt+Click en Rev Dir).

Ejecuta DBManager.read_submission/update_version_submission y
submission_version_code() del push sin abrir NKS (el modulo importa hiero),
contra una base temporal con el schema minimo de versions y tasks.
"""

import ast
import os
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path

PUSH_PATH = (
    Path(__file__).resolve().parents[1] / "LGA_NKS_Flow_Rev_Panel_py" / "LGA_NKS_Flow_Push.py"
)


def load_push_helpers(db_path):
    tree = ast.parse(PUSH_PATH.read_text(encoding="utf-8"))
    keep = [
        node
        for node in tree.body
        if (isinstance(node, ast.ClassDef) and node.name == "DBManager")
        or (isinstance(node, ast.FunctionDef) and node.name == "submission_version_code")
    ]
    namespace = {
        "os": os,
        "re": re,
        "sqlite3": sqlite3,
        "debug_print": lambda *args, **kwargs: None,
        "get_pipesync_db_path": lambda name: db_path,
    }
    exec(compile(ast.Module(body=keep, type_ignores=[]), str(PUSH_PATH), "exec"), namespace)
    return namespace["DBManager"], namespace["submission_version_code"]


def make_db(path, with_columns=True):
    conn = sqlite3.connect(path)
    extra = ", submission_note TEXT, submitting_for TEXT, media_color TEXT" if with_columns else ""
    conn.executescript(
        f"""
        CREATE TABLE tasks (id INTEGER PRIMARY KEY, shot_id INTEGER, task_type TEXT, task_status TEXT);
        CREATE TABLE versions (id INTEGER PRIMARY KEY, task_id INTEGER, version_number INTEGER,
                               version_sg_id INTEGER, version_code TEXT, status TEXT{extra});
        INSERT INTO tasks VALUES (1, 10, 'comp', 'rev_di');
        """
    )
    conn.commit()
    return conn


class SubmissionDbTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "pipesync.db")

    def tearDown(self):
        try:
            os.remove(self.db_path)
        except OSError:
            pass
        try:
            os.rmdir(self.tmp)
        except OSError:
            pass

    def reader(self):
        manager_cls, _code = load_push_helpers(self.db_path)
        return manager_cls()

    def test_version_code_takes_number_from_file_name(self):
        _cls, code = load_push_helpers(self.db_path)
        self.assertEqual(
            code("PROJA_1005_0100_VND_comp", "PROJA_1005_0100_VND_comp_v030.%04d.exr"),
            "PROJA_1005_0100_VND_comp_v030",
        )
        self.assertEqual(code("PROJA_1005_0100_VND_comp_v030", None), "PROJA_1005_0100_VND_comp_v030")

    def test_reads_synced_fields_and_task_status(self):
        conn = make_db(self.db_path)
        conn.execute(
            "INSERT INTO versions VALUES (1, 1, 30, 9030, 'PROJA_1005_0100_VND_comp_v030', 'vwd', "
            "'Sky fixed.', 'FINAL', 'Rec709 with show LUT')"
        )
        conn.commit()
        conn.close()
        manager = self.reader()
        result = manager.read_submission("proja_1005_0100_vnd_comp_v030")
        manager.conn.close()
        self.assertEqual(result["task_status"], "rev_di")
        self.assertEqual(result["version_id"], 9030)
        self.assertEqual(result["fields"]["sg_submission_note"], "Sky fixed.")
        self.assertEqual(result["fields"]["sg_submitting_for"], "FINAL")

    def test_empty_strings_are_known_values(self):
        conn = make_db(self.db_path)
        conn.execute("INSERT INTO versions VALUES (1, 1, 30, 9030, 'A_v030', 'vwd', '', '', '')")
        conn.commit()
        conn.close()
        manager = self.reader()
        result = manager.read_submission("A_v030")
        manager.conn.close()
        self.assertIsNotNone(result)
        self.assertEqual(result["fields"]["sg_submission_note"], "")

    def test_falls_back_to_flow_when_db_is_not_enough(self):
        cases = {
            "nunca sincronizada (NULL)": [("A_v030", None)],
            "no existe": [],
            "ambigua": [("A_v030", "x"), ("A_v030", "y")],
        }
        for label, rows in cases.items():
            with self.subTest(label):
                if os.path.exists(self.db_path):
                    os.remove(self.db_path)
                conn = make_db(self.db_path)
                for index, (code, note) in enumerate(rows, start=1):
                    conn.execute(
                        "INSERT INTO versions VALUES (?, 1, 30, ?, ?, 'vwd', ?, ?, ?)",
                        (index, 9000 + index, code, note, note, note),
                    )
                conn.commit()
                conn.close()
                manager = self.reader()
                self.assertIsNone(manager.read_submission("A_v030"))
                manager.conn.close()

    def test_old_schema_falls_back_and_is_not_written(self):
        conn = make_db(self.db_path, with_columns=False)
        conn.execute("INSERT INTO versions VALUES (1, 1, 30, 9030, 'A_v030', 'vwd')")
        conn.commit()
        conn.close()
        manager = self.reader()
        self.assertIsNone(manager.read_submission("A_v030"))
        self.assertFalse(manager.update_version_submission(9030, {"sg_submission_note": "x"}))
        manager.conn.close()

    def test_update_writes_only_that_version_and_only_synced_rows(self):
        conn = make_db(self.db_path)
        conn.execute("INSERT INTO versions VALUES (1, 1, 30, 9030, 'A_v030', 'vwd', '', '', '')")
        conn.execute("INSERT INTO versions VALUES (2, 1, 31, 9031, 'A_v031', 'vwd', '', '', '')")
        # Fila que el sync de este rol no mantiene (NULL): no se escribe.
        conn.execute("INSERT INTO versions VALUES (3, 1, 32, 9032, 'A_v032', 'vwd', NULL, NULL, NULL)")
        conn.commit()
        conn.close()
        manager = self.reader()
        fields = {"sg_submission_note": "Note", "sg_submitting_for": "WIP",
                  "sg_media_color": "Rec709 with show LUT"}
        self.assertTrue(manager.update_version_submission(9030, fields))
        self.assertFalse(manager.update_version_submission(9032, fields))
        self.assertEqual(manager.read_submission("A_v030")["fields"]["sg_submitting_for"], "WIP")
        self.assertEqual(manager.read_submission("A_v031")["fields"]["sg_submitting_for"], "")
        self.assertIsNone(manager.read_submission("A_v032"))
        manager.conn.close()

    def test_forget_sends_next_open_to_flow(self):
        conn = make_db(self.db_path)
        conn.execute("INSERT INTO versions VALUES (1, 1, 30, 9030, 'A_v030', 'vwd', 'old', 'WIP', 'x')")
        conn.commit()
        conn.close()
        manager = self.reader()
        self.assertIsNotNone(manager.read_submission("A_v030"))
        self.assertTrue(manager.forget_version_submission(9030))
        self.assertIsNone(manager.read_submission("A_v030"))
        manager.conn.close()

if __name__ == "__main__":
    unittest.main()
