"""
Tests de LGA_NKS_Vendor_Colors_Config: color de cada vendor desde la DB de
PipeSync. Arma una pipesync_stats.db sintetica en un temp dir, asi que NO
depende de una instalacion de PipeSync ni de los datos reales del estudio.
"""

import json
import os
import sqlite3
import sys
import unittest
from tempfile import TemporaryDirectory

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED_DIR = os.path.dirname(CURRENT_DIR)
if SHARED_DIR not in sys.path:
    sys.path.insert(0, SHARED_DIR)

import LGA_NKS_Vendor_Colors_Config as vc  # noqa: E402


def _build_db(path, with_groups=True):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE projects (id INTEGER PRIMARY KEY, project_name TEXT)")
    conn.execute("CREATE TABLE project_settings_cache (project_id INTEGER, settings_json TEXT)")
    conn.execute("INSERT INTO projects VALUES (1, 'PROJA'), (2, 'PROJB')")
    conn.execute("INSERT INTO project_settings_cache VALUES (?, ?)", (1, json.dumps(
        {"vendors": ["VNA", "VNB"], "vendor_colors": {"VNA": "#111111", "VNB": "#222222"}})))
    conn.execute("INSERT INTO project_settings_cache VALUES (?, ?)", (2, json.dumps(
        {"vendors": ["VNA"], "vendor_colors": {"VNA": "#999999"}})))
    if with_groups:
        conn.execute("CREATE TABLE project_vendor_groups (project_id INTEGER, vendor_token TEXT,"
                     " group_id INTEGER, group_name TEXT, synced_at TEXT, color TEXT)")
        conn.execute("INSERT INTO project_vendor_groups VALUES "
                     "(1, 'VNA', 1, 'Vendor A', '', '#6784BD'),"
                     "(1, 'VNC', 2, 'Vendor-B Lab', '', '#B53F45'),"
                     "(1, 'VND', 3, 'Bad', '', 'rojo')")
    conn.commit()
    conn.close()


class VendorColorsTest(unittest.TestCase):
    def _colors(self, with_groups=True):
        with TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "pipesync_stats.db")
            _build_db(path, with_groups)
            colors, ok = vc._read_db(path)
        self.assertTrue(ok)
        return colors

    def test_name_and_token_match_in_project(self):
        colors = self._colors()
        names = vc.project_names_for("PROJA_SUP_v001")
        self.assertEqual(names, ("PROJA_SUP_v001", "PROJA"))
        # El grupo le gana al envelope para el mismo token.
        self.assertEqual(vc.pick_vendor_color(colors, "VNA", names), "#6784BD")
        self.assertEqual(vc.pick_vendor_color(colors, "vendor a", names), "#6784BD")
        self.assertEqual(vc.pick_vendor_color(colors, "VENDOR B lab", names), "#B53F45")
        self.assertEqual(vc.pick_vendor_color(colors, "VNB", names), "#222222")
        self.assertIsNone(vc.pick_vendor_color(colors, "Bad", names))
        self.assertIsNone(vc.pick_vendor_color(colors, "Unknown", names))
        self.assertIsNone(vc.pick_vendor_color(colors, "", names))

    def test_other_project_uses_its_own_color(self):
        colors = self._colors()
        self.assertEqual(vc.pick_vendor_color(colors, "VNA", ("PROJB",)), "#999999")

    def test_unknown_project_only_when_unambiguous(self):
        colors = self._colors()
        # VNA tiene dos colores segun el proyecto: sin proyecto no se adivina.
        self.assertIsNone(vc.pick_vendor_color(colors, "VNA", ("PROJZ",)))
        self.assertEqual(vc.pick_vendor_color(colors, "Vendor A", ("PROJZ",)), "#6784BD")

    def test_db_without_groups_table(self):
        colors = self._colors(with_groups=False)
        self.assertEqual(vc.pick_vendor_color(colors, "VNA", ("PROJA",)), "#111111")
        self.assertIsNone(vc.pick_vendor_color(colors, "Vendor A", ("PROJA",)))

    def test_missing_db_is_empty(self):
        with TemporaryDirectory() as tmp:
            colors, ok = vc._read_db(os.path.join(tmp, "nada.db"))
        self.assertEqual((colors, ok), ({}, True))


if __name__ == "__main__":
    unittest.main()
