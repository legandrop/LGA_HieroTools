"""Pruebas de la vista previa de Shot Marks (filas, filtro, columnas), sin host."""

import importlib.util
from pathlib import Path
import unittest

FOLDER = Path(__file__).resolve().parents[1] / "LGA_NKS_Review_Panel_py"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, FOLDER / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


preview = _load("LGA_NKS_ShotMarks_Preview")
sheet = _load("LGA_NKS_ShotMarks_Sheet")
TC_KEY = sheet.meta_key("tc_in")


def _mark(row, shot, change="", changed=None):
    mark = sheet.Mark(row, shot, row * 100, row * 100 + 50, "01:00:00:%02d" % row,
                      "01:00:01:%02d" % row, "brief")
    mark.change = change
    mark.changed = changed or {}
    return mark


def _plan():
    plan = sheet.Plan()
    plan.marks = [_mark(2, "PROJA_010_0100", "unchanged"),
                  _mark(3, "PROJA_010_0150", "changed", {"brief": "old"}),
                  _mark(4, "PROJA_010_0200", "new"),
                  _mark(5, "PROJA_010_0250", "unchanged")]
    plan.issues = [sheet.Issue(5, "PROJA_010_0250", "01:00:00:05", "1-frame mark", True),
                   sheet.Issue(6, "PROJA_010_0300", "01:59:00:00", "Outside the timeline", False),
                   sheet.Issue(7, "PROJA_010_0350", "02:00:00:00", "Outside the timeline", False)]
    return plan


def _removed():
    return [{"shot": "PROJA_010_0900", "frame_in": 900, "frame_out": 950, "reason": "",
             "metadata": {TC_KEY: "01:00:09:00"}},
            {"shot": "PROJA_010_0350", "frame_in": 960, "frame_out": 990,
             "reason": "Outside the timeline", "metadata": {TC_KEY: "01:00:09:10"}}]


class EntriesTests(unittest.TestCase):
    def setUp(self):
        self.entries = preview.preview_entries(_plan(), _removed(), sheet.CHANGE_FIELDS, TC_KEY)
        self.by_shot = {e["shot"]: e for e in self.entries}

    def test_order_red_changes_problems_rest(self):
        self.assertEqual([e["shot"] for e in self.entries],
                         ["PROJA_010_0900", "PROJA_010_0350", "PROJA_010_0150", "PROJA_010_0200",
                          "PROJA_010_0300", "PROJA_010_0250", "PROJA_010_0100"])

    def test_texts_and_kinds(self):
        changed = self.by_shot["PROJA_010_0150"]
        self.assertEqual(changed["change"], "Changed: brief")
        self.assertEqual(changed["result"], "Mark")
        self.assertEqual(changed["result_kind"], "ok")
        warned = self.by_shot["PROJA_010_0250"]
        self.assertEqual((warned["result"], warned["result_kind"]), ("1-frame mark", "warning"))
        gone = self.by_shot["PROJA_010_0900"]
        self.assertEqual((gone["change"], gone["result"]),
                         ("No longer in the sheet", "Red mark where it was"))
        unplaced = self.by_shot["PROJA_010_0350"]
        self.assertEqual(unplaced["change"], "Not placed")
        self.assertEqual(unplaced["result"], "Red mark where it was: Outside the timeline")
        self.assertEqual(self.by_shot["PROJA_010_0300"]["result_kind"], "error")

    def test_red_shot_is_not_repeated_as_error(self):
        self.assertEqual(sum(1 for e in self.entries if e["shot"] == "PROJA_010_0350"), 1)

    def test_filters(self):
        changes = preview.filter_entries(self.entries, preview.FILTER_CHANGES)
        self.assertEqual({e["shot"] for e in changes},
                         {"PROJA_010_0900", "PROJA_010_0350", "PROJA_010_0150", "PROJA_010_0200"})
        problems = preview.filter_entries(self.entries, preview.FILTER_PROBLEMS)
        self.assertEqual({e["shot"] for e in problems},
                         {"PROJA_010_0350", "PROJA_010_0300", "PROJA_010_0250"})
        self.assertEqual(len(preview.filter_entries(self.entries, preview.FILTER_ALL)), 7)
        self.assertEqual(preview.filter_counts(self.entries),
                         {"all": 7, "changes": 4, "problems": 3})

    def test_first_run_has_no_changes(self):
        plan = _plan()
        for mark in plan.marks:
            mark.change, mark.changed = "", {}
        entries = preview.preview_entries(plan, [], sheet.CHANGE_FIELDS, TC_KEY)
        self.assertEqual(preview.filter_counts(entries)["changes"], 0)
        self.assertTrue(all(e["change"] == "" for e in entries))


class ColumnsTests(unittest.TestCase):
    def test_missing_required(self):
        self.assertEqual(preview.missing_required({"shot": 1, "tc_in": None}, False), ["tc_in"])
        self.assertEqual(preview.missing_required({"shot": 1, "tc_in": None}, True), [])
        self.assertEqual(preview.missing_required({}, True), ["shot"])
        self.assertEqual(preview.missing_required({"shot": 0, "tc_in": 2}, False), [])

    def test_data_column_count(self):
        columns = {"shot": 0, "tc_in": 1, "status": 3, "note": 4, "difficulty": 9,
                   "vendor": None, "thumb": 7}
        self.assertEqual(preview.data_column_count(columns), 3)

    def test_grid_rows(self):
        self.assertEqual(preview.grid_rows(range(10), 15), (list(range(10)), 0))
        self.assertEqual(preview.grid_rows(range(15), 15), (list(range(15)), 0))
        shown, more = preview.grid_rows(range(803), 15)
        self.assertEqual((len(shown), more), (14, 789))


if __name__ == "__main__":
    unittest.main()
