"""Pruebas del nucleo de Shot Marks: lectura de planillas, columnas y plan."""

import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

SCRIPT = (Path(__file__).resolve().parents[1] / "LGA_NKS_Review_Panel_py"
          / "LGA_NKS_ShotMarks_Sheet.py")
spec = importlib.util.spec_from_file_location("shotmarks_sheet", SCRIPT)
sheet = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sheet)

FPS = 24
START = sheet.parse_timecode("00:59:50:00", FPS)

# Planilla ficticia con la forma real: resumen arriba, encabezado en la fila 4,
# EP como float, REC TC y ST TC (camara) juntos, OUT exclusivo y un Omit.
ROWS = [
    ["", "", "Episodio", "Cant shots"],
    ["", "", 101.0, 3],
    [],
    ["EP", "SHOTNAME", "ST IN", "REC TC IN", "REC TC OUT", "BRIEF", "STATUS"],
    [101.0, "PROJA_1001_0100", "17:13:51:21", "01:00:07:09", "01:00:21:11", "Steam", "WIP"],
    [101.0, "PROJA_1001_0150", "17:15:03:17", "01:00:21:11", "01:00:33:04", "Steam", ""],
    [101.0, "PROJA_1003_0100", "", "", "", "Out of cut", "Omit"],
    [102.0, "PROJA_2005_0100", "17:53:57:07", "01:01:19:23", "01:01:25:06", "", ""],
    [101.0, "PROJA_1005_0100", "", "01:04:00:00", "01:04:00:00", "No length", ""],
]


def _col(index):
    return sheet.column_letters(index)


def write_xlsx(path, sheets):
    """xlsx minimo con sharedStrings, numeros e inlineStr."""
    strings = []

    def sid(text):
        if text not in strings:
            strings.append(text)
        return strings.index(text)

    sheet_xml = []
    for rows in sheets.values():
        out = ['<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
        for r, row in enumerate(rows, start=1):
            if not row:
                continue
            out.append('<row r="%d">' % r)
            for c, value in enumerate(row):
                ref = "%s%d" % (_col(c), r)
                if value == "":
                    continue
                if isinstance(value, (int, float)):
                    out.append('<c r="%s"><v>%s</v></c>' % (ref, value))
                elif value.startswith("inline:"):
                    out.append('<c r="%s" t="inlineStr"><is><t>%s</t></is></c>' % (ref, value[7:]))
                else:
                    out.append('<c r="%s" t="s"><v>%d</v></c>' % (ref, sid(value)))
            out.append("</row>")
        out.append("</sheetData></worksheet>")
        sheet_xml.append("".join(out))

    names = list(sheets)
    workbook = ('<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
                + "".join('<sheet name="%s" sheetId="%d" r:id="rId%d"/>' % (n, i + 1, i + 1)
                          for i, n in enumerate(names))
                + "</sheets></workbook>")
    rels = ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join('<Relationship Id="rId%d" Target="worksheets/sheet%d.xml"/>' % (i + 1, i + 1)
                      for i in range(len(names)))
            + "</Relationships>")
    shared = ('<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
              + "".join("<si><t>%s</t></si>" % s for s in strings) + "</sst>")
    with zipfile.ZipFile(str(path), "w") as archive:
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", rels)
        for i, xml in enumerate(sheet_xml):
            archive.writestr("xl/worksheets/sheet%d.xml" % (i + 1), xml)
        archive.writestr("xl/sharedStrings.xml", shared)


class ShotMarksSheetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.xlsx = self.root / "PROJA_breakdown.xlsx"
        edl = [["Reel", "Name", "Timecode In", "Timecode Out", "TCN"],
               ["A001", "clip", "01:00:07:09", "01:00:21:11", "PROJA_1001_0100"]]
        write_xlsx(self.xlsx, {"Notes": [["inline:just notes"]], "EDL": edl, "BREAKDOWN": ROWS})

    def tearDown(self):
        self.temp.cleanup()

    def _plan(self, **kwargs):
        table = sheet.load_table(self.xlsx, "BREAKDOWN")
        columns = sheet.detect_columns(table.headers)
        return table, columns, sheet.build_plan(table, columns, FPS, START, 60000, **kwargs)

    def test_lists_and_suggests_breakdown_sheet_over_edl(self):
        self.assertEqual(sheet.list_sheets(self.xlsx), ["Notes", "EDL", "BREAKDOWN"])
        self.assertEqual(sheet.suggest_sheet(self.xlsx), "BREAKDOWN")

    def test_header_row_and_rec_columns_win_over_camera_tc(self):
        table, columns, _plan = self._plan()
        self.assertEqual(table.header_row, 4)
        self.assertEqual(table.headers[columns["tc_in"]], "REC TC IN")
        self.assertEqual(table.headers[columns["tc_out"]], "REC TC OUT")
        self.assertEqual(table.headers[columns["shot"]], "SHOTNAME")
        self.assertEqual(table.headers[columns["note"]], "BRIEF")
        self.assertEqual(sheet.episode_values(table, columns["episode"]), ["101", "102"])

    def test_out_is_exclusive_and_maps_against_reference_start(self):
        _table, _columns, plan = self._plan(episode="101")
        first, second = plan.marks[0], plan.marks[1]
        # 01:00:21:11 - 00:59:50:00 = 755, el cuadro de corte medido en la media.
        self.assertEqual(second.frame_in, 755)
        self.assertEqual(first.frame_out, 754)
        self.assertEqual(plan.skipped_omit, 1)
        self.assertEqual(plan.skipped_episode, 1)

    def test_zero_length_row_is_a_one_frame_mark_with_warning(self):
        _table, _columns, plan = self._plan(episode="101")
        last = plan.marks[-1]
        self.assertEqual(last.shot, "PROJA_1005_0100")
        self.assertEqual(last.frame_in, last.frame_out)
        self.assertTrue(any(i.shot == "PROJA_1005_0100" and i.written for i in plan.issues))

    def test_omit_is_reported_when_not_skipped(self):
        _table, _columns, plan = self._plan(episode="101", skip_omit=False)
        errors = plan.errors()
        self.assertEqual([(i.shot, i.message) for i in errors], [("PROJA_1003_0100", "No TC IN")])

    def test_outside_timeline_is_not_written(self):
        table = sheet.load_table(self.xlsx, "BREAKDOWN")
        columns = sheet.detect_columns(table.headers)
        plan = sheet.build_plan(table, columns, FPS, START, 1000, episode="101")
        self.assertEqual([m.shot for m in plan.marks], ["PROJA_1001_0100", "PROJA_1001_0150"])
        self.assertEqual(plan.marks[1].frame_out, 999)
        self.assertIn("Outside the timeline", [i.message for i in plan.errors()])

    def test_timecode_parsing(self):
        self.assertEqual(sheet.parse_timecode("01:00:00:00", 24), 86400)
        self.assertEqual(sheet.parse_timecode("00:59:50:00", 24), 86160)
        self.assertIsNone(sheet.parse_timecode("01:00:00:24", 24))
        self.assertIsNone(sheet.parse_timecode("101", 24))
        self.assertEqual(sheet.format_timecode(86160, 24), "00:59:50:00")

    def test_csv_with_semicolons(self):
        path = self.root / "PROJA.csv"
        path.write_text("SHOT;REC TC IN;REC TC OUT\nPROJA_0010;01:00:00:00;01:00:01:00\n",
                        encoding="utf-8")
        table = sheet.load_table(path, "")
        columns = sheet.detect_columns(table.headers)
        plan = sheet.build_plan(table, columns, FPS, 86400, 1000)
        self.assertEqual([(m.shot, m.frame_in, m.frame_out) for m in plan.marks],
                         [("PROJA_0010", 0, 23)])

    def test_csv_multiline_cell_starting_with_quote(self):
        # Exportacion de Google Sheets: celda multilinea que empieza con una
        # comilla literal ("" escapada) y ningun otro "" en la muestra.
        path = self.root / "PROJA - BREAKDOWN.csv"
        brief = '"-Add the tower\n-Change the rail color\n-Replace the sign'
        quoted = '"%s"' % brief.replace('"', '""')
        # La celda va despues de los 4096 caracteres que mira el Sniffer:
        # en la planilla real el primer "" aparece recien en la fila 754.
        filler = "".join("PROJA_%04d,,,Paint out\r\n" % n for n in range(1000, 1300))
        # Bytes y no write_text: en Windows convertiria el \n de la celda en \r\n.
        path.write_bytes((
            "SHOT,REC TC IN,REC TC OUT,BRIEF\r\n" + filler +
            "PROJA_0010,01:00:00:00,01:00:01:00,%s\r\n"
            "PROJA_0020,01:00:01:00,01:00:02:00,Cleanup\r\n" % quoted).encode("utf-8"))
        table = sheet.load_table(path, "")
        columns = sheet.detect_columns(table.headers)
        plan = sheet.build_plan(table, columns, FPS, 86400, 1000)
        self.assertEqual([(m.shot, m.note) for m in plan.marks],
                         [("PROJA_0010", brief), ("PROJA_0020", "Cleanup")])
        self.assertEqual(len(table.rows), 302)

    def test_marks_carry_sheet_info_and_round_trip_through_metadata(self):
        _table, columns, plan = self._plan(episode="101")
        self.assertIsNotNone(columns["status"])
        first = plan.marks[0]
        self.assertEqual(first.info, {"status": "WIP", "episode": "101"})
        stored = sheet.mark_metadata(first, "PROJA.xlsx | BREAKDOWN")
        self.assertTrue(all(key.startswith("tag.") for key in stored))
        info = sheet.mark_info_from_metadata(stored.get)
        self.assertTrue(info["complete"])
        self.assertEqual((info["tc_in"], info["tc_out"], info["brief"], info["status"]),
                         ("01:00:07:09", "01:00:21:11", "Steam", "WIP"))
        self.assertEqual(info["description"], "")

    def test_metadata_from_first_version_is_incomplete(self):
        old = {"tag.lga_shotmarks": "1", "tag.lga_shotmarks_row": "8"}
        info = sheet.mark_info_from_metadata(old.get)
        self.assertFalse(info["complete"])
        self.assertEqual(info["row"], "8")

    def test_description_is_its_own_column(self):
        table = sheet.Table("x", "s", 1, ["SHOTNAME", "REC TC IN", "DESCRIPCIÓN", "BRIEF",
                                          "ESC", "SHOT CATEGORY", "VENDOR"], [])
        columns = sheet.detect_columns(table.headers)
        self.assertEqual([table.headers[columns[r]] for r in
                          ("description", "note", "scene", "category", "vendor")],
                         ["DESCRIPCIÓN", "BRIEF", "ESC", "SHOT CATEGORY", "VENDOR"])

    def test_next_and_previous_mark_wrap_around(self):
        starts = [10, 50, 90]
        self.assertEqual(sheet.next_mark_index(starts, 0, "next"), 0)
        self.assertEqual(sheet.next_mark_index(starts, 10, "next"), 1)
        self.assertEqual(sheet.next_mark_index(starts, 90, "next"), 0)
        self.assertEqual(sheet.next_mark_index(starts, 60, "previous"), 1)
        self.assertEqual(sheet.next_mark_index(starts, 50, "previous"), 0)
        self.assertEqual(sheet.next_mark_index(starts, 10, "previous"), 2)
        self.assertIsNone(sheet.next_mark_index([], 0, "next"))

    def test_mark_index_at_frame(self):
        starts, ends = [10, 50, 90], [49, 60, 120]
        self.assertIsNone(sheet.mark_index_at(starts, ends, 5))
        self.assertEqual(sheet.mark_index_at(starts, ends, 10), 0)
        self.assertEqual(sheet.mark_index_at(starts, ends, 49), 0)
        self.assertEqual(sheet.mark_index_at(starts, ends, 50), 1)
        self.assertEqual(sheet.mark_index_at(starts, ends, 60), 1)
        self.assertIsNone(sheet.mark_index_at(starts, ends, 70))
        self.assertEqual(sheet.mark_index_at(starts, ends, 120), 2)
        self.assertIsNone(sheet.mark_index_at(starts, ends, 121))
        self.assertIsNone(sheet.mark_index_at([], [], 0))
        # Una marca larga solapada cubre el hueco despues de la corta.
        self.assertEqual(sheet.mark_index_at([0, 10], [100, 20], 30), 0)

    def test_follow_ends_stretch_one_frame_marks(self):
        # 10 y 30 son de un cuadro; 50-60 tiene rango real; 90 es la ultima.
        starts, ends = [10, 30, 50, 90], [10, 30, 60, 90]
        follow = sheet.follow_ends(starts, ends, 200)
        self.assertEqual(follow, [29, 49, 60, 200])
        self.assertEqual(sheet.mark_index_at(starts, follow, 20), 0)
        self.assertEqual(sheet.mark_index_at(starts, follow, 45), 1)
        # Despues de una marca con rango real el hueco sigue sin marca.
        self.assertIsNone(sheet.mark_index_at(starts, follow, 70))
        self.assertEqual(sheet.mark_index_at(starts, follow, 150), 3)
        # Dos marcas en el mismo IN: llegan hasta la siguiente que empieza despues.
        self.assertEqual(sheet.follow_ends([5, 5, 9], [5, 5, 9], 9), [8, 8, 9])
        self.assertEqual(sheet.follow_ends([], [], 0), [])

    def test_sheet_without_shot_and_tc_is_rejected(self):
        with self.assertRaises(ValueError):
            sheet.load_table(self.xlsx, "Notes")


def _mark(shot, frame_in, note="", **info):
    return sheet.Mark(1, shot, frame_in, frame_in + 10, "", "", note, info)


def _previous(mark, change=""):
    """Un tag anterior tal como lo lee previous_marks."""
    mark.change, mark.changed = change, {}
    data = sheet.mark_metadata(mark, "planilla.xlsx | Shots")
    return sheet.previous_mark(mark.shot, mark.frame_in, mark.frame_out, data.get, mark.note)


class ShotMarksCompareTests(unittest.TestCase):
    def test_colors_by_change_against_previous_run(self):
        previous = [
            _previous(_mark("PROJA_0100", 0, "Steam", description="Old")),
            _previous(_mark("PROJA_0200", 50, "Sky", status="WIP")),
            _previous(_mark("PROJA_0300", 100, "Gone")),
        ]
        marks = [
            # Se movio en el corte y el brief solo cambio de fin de linea: sin cambio.
            _mark("PROJA_0200", 80, "Sky\r\n", status="WIP"),
            _mark("PROJA_0100", 0, "Steam", description='"New"'),
            _mark("PROJA_0400", 200, "Added"),
        ]
        removed = sheet.compare_marks(marks, previous)
        by_shot = {m.shot: m for m in marks}
        self.assertEqual(by_shot["PROJA_0200"].change, sheet.CHANGE_UNCHANGED)
        self.assertEqual(by_shot["PROJA_0100"].change, sheet.CHANGE_CHANGED)
        self.assertEqual(by_shot["PROJA_0100"].changed, {"description": "Old"})
        self.assertEqual(by_shot["PROJA_0400"].change, sheet.CHANGE_NEW)
        self.assertEqual([old["shot"] for old in removed], ["PROJA_0300"])
        counts = sheet.change_counts(marks, removed)
        self.assertEqual(counts, {"unchanged": 1, "changed": 1, "new": 1, "removed": 1,
                                  "unplaced": 0})

    def test_change_round_trips_through_metadata(self):
        mark = _mark("PROJA_0100", 0, "Brief", status="Omit")
        mark.change, mark.changed = sheet.CHANGE_CHANGED, {"status": "WIP", "brief": ""}
        data = sheet.mark_metadata(mark, "x")
        info = sheet.mark_info_from_metadata(data.get)
        self.assertEqual(info["change"], "changed")
        self.assertEqual(info["changed"], {"brief": "", "status": "WIP"})

    def test_removed_shot_still_in_sheet_carries_the_reason(self):
        previous = [_previous(_mark("PROJA_0300", 100, "Late")),
                    _previous(_mark("PROJA_0400", 200, "Gone"))]
        issues = [sheet.Issue(9, "PROJA_0300", "01:41:00:00", "Outside the timeline", False)]
        removed = sheet.compare_marks([], previous, issues)
        self.assertEqual([(old["shot"], old["reason"]) for old in removed],
                         [("PROJA_0300", "Outside the timeline"), ("PROJA_0400", "")])
        self.assertEqual(sheet.change_counts([], removed)["unplaced"], 1)

    def test_previous_removed_marks_are_not_compared(self):
        previous = [_previous(_mark("PROJA_0300", 100, "Gone"), change=sheet.CHANGE_REMOVED)]
        marks = [_mark("PROJA_0300", 100, "Gone")]
        self.assertEqual(sheet.compare_marks(marks, previous), [])
        self.assertEqual(marks[0].change, sheet.CHANGE_NEW)

    def test_repeated_shot_pairs_in_order(self):
        previous = [_previous(_mark("PROJA_0100", 0, "A")), _previous(_mark("PROJA_0100", 90, "B"))]
        marks = [_mark("PROJA_0100", 5, "A"), _mark("PROJA_0100", 95, "B changed")]
        sheet.compare_marks(marks, previous)
        self.assertEqual([m.change for m in marks], ["unchanged", "changed"])

    def test_first_version_tags_only_compare_the_brief(self):
        previous = [sheet.previous_mark("PROJA_0100", 0, 10, {}.get, note="Steam")]
        marks = [_mark("PROJA_0100", 0, "Steam", description="Any", vendor="Vendor A")]
        sheet.compare_marks(marks, previous)
        self.assertEqual(marks[0].change, sheet.CHANGE_UNCHANGED)


if __name__ == "__main__":
    unittest.main()
