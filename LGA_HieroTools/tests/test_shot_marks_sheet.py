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

    def test_sheet_without_shot_and_tc_is_rejected(self):
        with self.assertRaises(ValueError):
            sheet.load_table(self.xlsx, "Notes")


if __name__ == "__main__":
    unittest.main()
