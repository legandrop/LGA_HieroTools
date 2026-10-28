"""Pruebas del EDL del armado en Shot Marks: lectura, alineacion y planos."""

import importlib.util
from pathlib import Path
import tempfile
import unittest

PANEL = Path(__file__).resolve().parents[1] / "LGA_NKS_Review_Panel_py"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, PANEL / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


edl = _load("LGA_NKS_ShotMarks_EDL")
sheet = _load("LGA_NKS_ShotMarks_Sheet")
engine = _load("LGA_NKS_ShotMarks_Locate_Engine")

FPS = 24

# Armado ficticio con lo que trae un EDL real: titulo en negro con el texto en
# lineas sueltas, un reel con espacios y M2, dos planos del mismo clip, una
# disolvencia (evento de largo cero + evento D) y una pista de audio.
EDL_TEXT = """TITLE: PROJA_ARMADO_v001
FCM: NON-DROP FRAME

001  BL       V     C        00:59:50:00 00:59:51:00 00:59:50:00 00:59:51:00
* FROM CLIP NAME:
PROJA
Assembly cut

002  Countdown Leader V     C        00:00:09:00 00:00:09:01 00:59:58:00 00:59:58:01
M2   Countdown Leader       000.0                00:00:09:00
* FROM CLIP NAME: Countdown Leader.mov

003  A001C001 V     C        10:00:00:00 10:00:05:00 01:00:00:00 01:00:05:00
* FROM CLIP NAME: A001C001_PROJA.mov

004  A001C001 V     C        10:00:10:00 10:00:12:00 01:00:05:00 01:00:07:00
* FROM CLIP NAME: A001C001_PROJA.mov

005  B002C003 V     C        11:00:00:00 11:00:01:00 01:00:07:00 01:00:08:00
* FROM CLIP NAME: B002C003_PROJA.mov

006  B002C003 V     C        11:00:01:00 11:00:01:00 01:00:08:00 01:00:08:00
006  C003C001 V     D    012 12:00:00:00 12:00:02:00 01:00:08:00 01:00:10:00
* FROM CLIP NAME: B002C003_PROJA.mov
* TO CLIP NAME: C003C001_PROJA.mov

007  A001C001 A     C        10:00:00:00 10:00:05:00 01:00:00:00 01:00:05:00
"""


def tc(text):
    return edl.tc_frames(text, FPS)


class ParseTests(unittest.TestCase):
    def setUp(self):
        self.parsed = edl.parse_edl(EDL_TEXT, FPS)
        self.offset = tc("00:59:50:00")

    def test_video_events_with_length(self):
        numbers = [e.number for e in self.parsed.events]
        # 006 de largo cero (lado "desde" de la disolvencia) y 007 de audio afuera.
        self.assertEqual(numbers, [1, 2, 3, 4, 5, 6])
        self.assertEqual(self.parsed.title, "PROJA_ARMADO_v001")
        self.assertFalse(self.parsed.drop_frame)

    def test_clip_names_reels_and_speed(self):
        events = {e.number: e for e in self.parsed.events}
        self.assertEqual(events[1].name(), "BL")  # titulo: sin clip, el reel
        self.assertEqual(events[2].reel, "Countdown Leader")
        self.assertTrue(events[2].speed)
        self.assertEqual(events[3].name(), "A001C001_PROJA")
        # La disolvencia es del clip entrante.
        self.assertEqual((events[6].name(), events[6].transition), ("C003C001_PROJA", "D"))

    def test_cuts_and_segments_in_movie_frames(self):
        total = tc("01:00:20:00") - self.offset
        cuts = edl.cut_frames(self.parsed, self.offset, total)
        start = tc("01:00:00:00") - self.offset
        self.assertIn(start, cuts)
        self.assertIn(start + 5 * FPS, cuts)  # A-A del mismo clip: igual es un corte
        segs = edl.segments(self.parsed, self.offset, total)
        seg = edl.segment_at(segs, start + 10)
        self.assertEqual((seg["in"], seg["out"], seg["event"]), (start, start + 5 * FPS - 1, 3))
        info = edl.source_info(seg, start + 10, FPS)
        self.assertEqual((info["clip"], info["src_in"], info["src_out"], info["src_frame"]),
                         ("A001C001_PROJA", "10:00:00:00", "10:00:05:00", "10:00:00:10"))
        # Hueco de la pista (entre el leader y el primer plano): sin evento.
        self.assertIsNone(edl.segment_at(segs, tc("00:59:59:00") - self.offset))

    def test_alignment_finds_the_shift_and_rejects_another_cut(self):
        total = tc("01:00:20:00") - self.offset
        cuts = edl.cut_frames(self.parsed, self.offset, total)
        self.assertEqual(edl.align(self.parsed, self.offset, cuts, total)[:2], (0, len(cuts)))
        # MOV con la cola cortada: el TC del video dice 10 s menos.
        shifted = [c - 240 for c in cuts if c >= 240]
        delta, matched, count = edl.align(self.parsed, self.offset, shifted, total)
        self.assertEqual(delta, 240)
        self.assertTrue(edl.is_aligned(matched, count))
        # Otro armado: nada coincide.
        other = [c + 37 * (i % 5) + 3 for i, c in enumerate(cuts)]
        delta, matched, count = edl.align(self.parsed, self.offset, other, total)
        self.assertFalse(edl.is_aligned(matched, count))

    def test_drop_frame_timecode(self):
        # 00:01:00;02 es el primer cuadro despues del salto de ;00 y ;01.
        self.assertEqual(edl.tc_frames("00:01:00;02", 30, drop_frame=True), 1800)
        self.assertEqual(edl.tc_frames("00:10:00;00", 30, drop_frame=True), 17982)


class EngineEdlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / "armado.edl")
        with open(self.path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(EDL_TEXT)
        self.info = {"fps": 24.0, "timecode": "00:59:50:00"}
        self.total = tc("01:00:20:00") - tc("00:59:50:00")
        parsed = edl.parse_edl(EDL_TEXT, FPS)
        self.cuts = edl.cut_frames(parsed, tc("00:59:50:00"), self.total)

    def tearDown(self):
        self.temp.cleanup()

    def test_matching_edl_is_used(self):
        # Al detector se le escapa un corte y marca uno que no existe.
        detected = sorted(self.cuts[:-1] + [self.cuts[-1] + 7])
        state, segs = engine.load_edl(self.path, self.info, self.total, detected)
        self.assertTrue(state["used"])
        self.assertEqual(state["cuts"], self.cuts)
        self.assertEqual((state["missed"], state["extra"]), (1, 1))
        self.assertEqual(len(segs), 6)

    def test_edl_of_another_cut_is_not_used(self):
        detected = [c + 11 for c in self.cuts]
        state, segs = engine.load_edl(self.path, self.info, self.total, detected[:1])
        self.assertFalse(state["used"])
        self.assertIn("match", state["reason"])
        self.assertEqual(segs, [])

    def test_missing_edl_falls_back(self):
        state, segs = engine.load_edl(self.path + "x", self.info, self.total, self.cuts)
        self.assertEqual((state["used"], segs), (False, []))
        self.assertEqual(engine.load_edl("", self.info, self.total, self.cuts)[0]["used"], False)


class ClipTextTests(unittest.TestCase):
    def test_round_trip(self):
        info = {"clip": "A001C001_PROJA", "src_in": "10:00:00:00", "src_out": "10:00:05:00",
                "src_frame": "10:00:00:10", "event": 3}
        text = sheet.clip_text(info)
        self.assertEqual(text, "A001C001_PROJA | 10:00:00:00 | 10:00:05:00 | 3")
        self.assertEqual(sheet.parse_clip(text)["src_out"], "10:00:05:00")
        self.assertEqual(sheet.clip_text(None), "")
        self.assertEqual(sheet.parse_clip(""), {})
        self.assertEqual(sheet.parse_clip("algo suelto"), {})


if __name__ == "__main__":
    unittest.main()
