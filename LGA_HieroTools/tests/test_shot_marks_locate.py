"""Pruebas de Shot Marks sin timecode: thumbs del xlsx, motor y TC ubicados."""

import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile

PANEL = Path(__file__).resolve().parents[1] / "LGA_NKS_Review_Panel_py"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, PANEL / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sheet = _load("LGA_NKS_ShotMarks_Sheet")
thumbs = _load("LGA_NKS_ShotMarks_Thumbs")
engine = _load("LGA_NKS_ShotMarks_Locate_Engine")

FPS = 24
PNG_1x1 = (b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR"
           + struct.pack(">II", 1, 1) + b"\x08\x02\x00\x00\x00" + b"\x00" * 4)


def _anchor(row_from, row_to, col, rel_id):
    return ('<xdr:twoCellAnchor><xdr:from><xdr:col>%d</xdr:col><xdr:row>%d</xdr:row></xdr:from>'
            '<xdr:to><xdr:col>%d</xdr:col><xdr:row>%d</xdr:row></xdr:to>'
            '<xdr:pic><xdr:blipFill><a:blip r:embed="%s"/></xdr:blipFill></xdr:pic>'
            '</xdr:twoCellAnchor>') % (col, row_from, col + 1, row_to, rel_id)


def write_xlsx_with_images(path):
    """Hoja de shots sin TC: encabezado en la fila 2 y fotos en la columna A."""
    shots = ["", "", "PROJA_001_010", "PROJA_001_020", "PROJA_001_010", "PROJA_002_010"]
    status = ["", "", "WIP", "POSIBLE VFX OMIT (en corte)", "WIP", "OMIT"]
    rows = ['<row r="2"><c r="A2" t="inlineStr"><is><t>Thumb</t></is></c>'
            '<c r="B2" t="inlineStr"><is><t>Shot name</t></is></c>'
            '<c r="C2" t="inlineStr"><is><t>Status</t></is></c></row>']
    for r in range(3, 7):
        rows.append('<row r="%d"><c r="B%d" t="inlineStr"><is><t>%s</t></is></c>'
                    '<c r="C%d" t="inlineStr"><is><t>%s</t></is></c></row>'
                    % (r, r, shots[r - 1], r, status[r - 1]))
    main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    pkg = "http://schemas.openxmlformats.org/package/2006/relationships"
    drawing = ('<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing" '
               'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="%s">' % rel
               # Fila 3: termina en el borde de la 4. Fila 4: dos fotos, gana la de la izquierda.
               + _anchor(2, 3, 0, "rId1") + _anchor(3, 3, 0, "rId2") + _anchor(3, 3, 4, "rId1")
               # Fila 5: misma foto que la 3. Fila 6: cruza tres filas, cuenta la del medio.
               + _anchor(4, 4, 0, "rId1") + _anchor(4, 6, 0, "rId2") + "</xdr:wsDr>")
    with zipfile.ZipFile(str(path), "w") as archive:
        archive.writestr("xl/workbook.xml",
                         '<workbook xmlns="%s" xmlns:r="%s"><sheets>'
                         '<sheet name="Shots" sheetId="1" r:id="rId1"/></sheets></workbook>' % (main, rel))
        archive.writestr("xl/_rels/workbook.xml.rels",
                         '<Relationships xmlns="%s"><Relationship Id="rId1" '
                         'Target="worksheets/sheet1.xml"/></Relationships>' % pkg)
        archive.writestr("xl/worksheets/sheet1.xml",
                         '<worksheet xmlns="%s"><sheetData>%s</sheetData></worksheet>' % (main, "".join(rows)))
        archive.writestr("xl/worksheets/_rels/sheet1.xml.rels",
                         '<Relationships xmlns="%s"><Relationship Id="rId1" '
                         'Target="../drawings/drawing1.xml"/></Relationships>' % pkg)
        archive.writestr("xl/drawings/drawing1.xml", drawing)
        archive.writestr("xl/drawings/_rels/drawing1.xml.rels",
                         '<Relationships xmlns="%s"><Relationship Id="rId1" Target="../media/image1.png"/>'
                         '<Relationship Id="rId2" Target="../media/image2.png"/></Relationships>' % pkg)
        archive.writestr("xl/media/image1.png", PNG_1x1)
        archive.writestr("xl/media/image2.png", PNG_1x1 + b"x")


class ThumbsAndLocatedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.xlsx = self.root / "PROJA_bkd.xlsx"
        write_xlsx_with_images(self.xlsx)

    def tearDown(self):
        self.temp.cleanup()

    def test_sheet_without_tc_loads_only_when_allowed(self):
        with self.assertRaises(ValueError):
            sheet.load_table(self.xlsx, "Shots")
        table = sheet.load_table(self.xlsx, "Shots", require_tc=False)
        self.assertEqual(table.header_row, 2)
        columns = sheet.detect_columns(table.headers)
        self.assertEqual(table.headers[columns["shot"]], "Shot name")
        self.assertIsNone(columns["tc_in"])
        self.assertEqual(sheet.suggest_sheet(self.xlsx), "Shots")

    def test_images_belong_to_their_row(self):
        rows = sorted((i["row"], i["col"], i["part"]) for i in thumbs.sheet_images(self.xlsx, "Shots"))
        self.assertEqual([r[0] for r in rows], [3, 4, 4, 5, 6])
        found = thumbs.extract_thumbs(self.xlsx, "Shots", [3, 4, 5, 6, 9], str(self.root / "t"))
        self.assertEqual(sorted(found), [3, 4, 5, 6])
        # La misma foto en dos filas se guarda una vez.
        self.assertEqual(found[3]["sha1"], found[5]["sha1"])
        self.assertEqual(found[3]["file"], found[5]["file"])
        # Dos fotos en la fila 4: gana la columna A (image2).
        self.assertEqual(found[4]["sha1"], found[6]["sha1"])
        self.assertFalse(thumbs.has_cell_images(self.xlsx))

    def test_maybe_omit_is_marked_and_colored_apart(self):
        self.assertEqual(sheet.status_kind("POSIBLE VFX OMIT (en corte)"), "maybe_omit")
        self.assertEqual(sheet.status_kind("OMIT CORTE CERO"), "omit")
        self.assertEqual(sheet.status_kind("WIP"), "")
        self.assertFalse(sheet.is_omit("POSIBLE VFX OMIT (en corte)"))
        self.assertTrue(sheet.is_omit("Omit"))

    def test_group_titles_are_not_shots(self):
        self.assertFalse(sheet.is_shot_name("PROJA_001_"))
        self.assertFalse(sheet.is_shot_name(""))
        self.assertTrue(sheet.is_shot_name("PROJA_001_010"))
        columns = sheet.detect_columns(["SHOT NAME", "STATUS\nVFX", "VFX Brief", "Notas"])
        self.assertEqual((columns["status"], columns["note"]), (1, 2))

    def test_located_timecodes_feed_the_same_plan(self):
        table = sheet.load_table(self.xlsx, "Shots", require_tc=False)
        located = {
            3: {"tc_in": "01:00:00:10", "tc_out": "01:00:01:00", "thumb": "C:/t/a.jpg", "level": "auto 0.98"},
            4: {"tc_in": "01:00:01:00", "tc_out": "01:00:02:00", "thumb": "C:/t/b.jpg", "level": "review 0.72"},
        }
        table = sheet.with_located_timecodes(table, located)
        columns = sheet.detect_columns(table.headers)
        self.assertEqual(table.headers[columns["tc_in"]], sheet.LOCATED_TC_IN)
        start = sheet.parse_timecode("01:00:00:00", FPS)
        plan = sheet.build_plan(table, columns, FPS, start, 1000)
        self.assertEqual([(m.shot, m.frame_in, m.frame_out) for m in plan.marks],
                         [("PROJA_001_010", 10, 23), ("PROJA_001_020", 24, 47)])
        self.assertEqual(plan.marks[1].info["status"], "POSIBLE VFX OMIT (en corte)")
        self.assertEqual(plan.marks[1].info["located"], "review 0.72")
        self.assertEqual(plan.marks[0].info["thumb"], "C:/t/a.jpg")
        # Fila 5 sin ubicar: aviso de error, no marca. Fila 6 (OMIT): salteada.
        self.assertEqual([(i.row, i.message) for i in plan.errors()], [(5, "No TC IN")])
        self.assertEqual(plan.skipped_omit, 1)
        meta = sheet.mark_metadata(plan.marks[0], "src")
        info = sheet.mark_info_from_metadata(meta.get)
        self.assertEqual((info["thumb"], info["located"]), ("C:/t/a.jpg", "auto 0.98"))


class EngineTests(unittest.TestCase):
    def test_cuts_keep_the_strongest_of_close_detections(self):
        scores = [0, 0, 9, 12, 0, 0, 0, 0, 7, 0, 3]
        self.assertEqual(engine.cut_frames(scores, threshold=6, radius=3), [3, 8])
        self.assertEqual(engine.shot_range([3, 8], 5, 11), (3, 7))
        self.assertEqual(engine.shot_range([3, 8], 1, 11), (0, 2))
        self.assertEqual(engine.shot_range([3, 8], 9, 11), (8, 10))

    def test_batch_crop_is_the_mode_of_well_shaped_detections(self):
        good = (22, 18, 530, 288)
        rects = {(576, 324): [good] * 6 + [(100, 18, 300, 288), (22, 60, 530, 100)],
                 (800, 600): [(0, 0, 800, 600)] * 2}
        lots = engine.batch_rects(rects, 1.85)
        self.assertEqual(lots, {(576, 324): good})

    def test_picture_rect_drops_bars_and_forces_the_aspect(self):
        w, h = 40, 30
        gray = bytearray(w * h)
        for y in range(5, 25):  # imagen 40x20 entre barras negras arriba y abajo
            for x in range(w):
                gray[y * w + x] = 120
        self.assertEqual(engine.picture_rect(bytes(gray), w, h, 2.0), (0, 5, 40, 20))
        # Escena oscura a la izquierda: el ancho sale del aspecto.
        for y in range(5, 25):
            for x in range(0, 15):
                gray[y * w + x] = 5
        x, y, pw, ph = engine.picture_rect(bytes(gray), w, h, 2.0)
        self.assertEqual((pw, ph), (40, 20))

    def test_image_size_reads_png_and_jpeg_headers(self):
        self.assertEqual(engine.image_size(PNG_1x1), (1, 1))
        jpeg = b"\xff\xd8" + b"\xff\xe0" + struct.pack(">H", 4) + b"JF" \
            + b"\xff\xc0" + struct.pack(">HBHH", 17, 8, 324, 576) + b"\x00" * 12
        self.assertEqual(engine.image_size(jpeg), (576, 324))
        self.assertIsNone(engine.image_size(b"nope"))

    def test_margin_is_against_other_shots_nearby(self):
        # (score, cuadro, segmento, hamming): el 2do del mismo plano no cuenta.
        cands = [(0.97, 1000, 5, 3), (0.96, 1004, 5, 4), (0.80, 1800, 7, 9), (0.95, 90000, 40, 6)]
        glob, local = engine.margins(cands)
        self.assertAlmostEqual(glob, 0.17)
        self.assertAlmostEqual(local, 0.17)
        self.assertEqual(engine.margins([]), (0.0, 0.0))

    def test_moved_scene_breaks_the_order(self):
        positions = [100, 200, 300, 9000, 400, 500, 600]
        self.assertEqual(engine.order_breaks(positions), {3})
        self.assertEqual(engine.order_breaks([1, 2, 3, 4, 5]), set())

    def test_classify(self):
        self.assertEqual(engine.classify(0.97, 0.2, True), "auto")
        self.assertEqual(engine.classify(0.97, 0.02, True), "review")
        self.assertEqual(engine.classify(0.97, 0.2, False), "review")
        self.assertEqual(engine.classify(0.4, 0.2, True), "not_found")

    def test_ncc_ignores_exposure(self):
        ref = engine.normalized([10, 20, 30, 40, 50, 60])
        self.assertAlmostEqual(engine.ncc(ref, bytes([110, 130, 150, 170, 190, 210])), 1.0, places=5)
        self.assertAlmostEqual(engine.ncc(ref, bytes([60, 50, 40, 30, 20, 10])), -1.0, places=5)
        self.assertEqual(engine.ncc(ref, bytes([7] * 6)), 0.0)


if __name__ == "__main__":
    unittest.main()
