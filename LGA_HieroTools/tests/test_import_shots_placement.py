"""
Colocacion de Import Shot entre dos shots existentes.

Reproduce el caso real: el comp del shot anterior se habia importado con el
slate del frame 1000, terminaba un frame despues que su plate y cruzaba el
inicio del shot siguiente. El empuje lo movia junto con el siguiente y el
shot nuevo caia encima del anterior. Tambien cubre el recorte del slate de
los renders publicados.

Sin hiero ni Qt: el modulo de timeline se carga con un hiero falso y las
funciones de LGA_import_shots se extraen por AST.
"""

import ast
import copy
import importlib.util
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IMPORT_PATH = ROOT / "LGA_NKS_Edit_Panel_py" / "LGA_import_shots.py"
TIMELINE_PATH = ROOT / "LGA_NKS_Edit_Panel_py" / "LGA_import_shots_timeline.py"

PREV, NEW, NEXT = "PROJA_1010_0200", "PROJA_1010_0300", "PROJA_1012_0100"


class _EffectTrackItem:
    pass


def _fake_hiero():
    hiero = types.ModuleType("hiero")
    core = types.ModuleType("hiero.core")
    ui = types.ModuleType("hiero.ui")
    core.EffectTrackItem = _EffectTrackItem
    ui.getTimelineEditor = lambda seq: None
    hiero.core, hiero.ui = core, ui
    return hiero, core, ui


def _load_timeline_module():
    hiero, core, ui = _fake_hiero()
    saved = {k: sys.modules.get(k) for k in ("hiero", "hiero.core", "hiero.ui")}
    sys.modules.update({"hiero": hiero, "hiero.core": core, "hiero.ui": ui})
    try:
        spec = importlib.util.spec_from_file_location("_tl_under_test", TIMELINE_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        for key, value in saved.items():
            if value is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = value
    return module, hiero


def _load_functions(names, namespace):
    tree = ast.parse(IMPORT_PATH.read_text(encoding="utf-8-sig"))
    body = [
        copy.deepcopy(node) for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    module = ast.Module(body=body, type_ignores=[])
    exec(compile(module, str(IMPORT_PATH), "exec"), namespace)
    return namespace


class _Item:
    def __init__(self, name, tl_in, tl_out):
        self._name, self.tl_in, self.tl_out = name, tl_in, tl_out
        self.times = None

    def name(self):
        return self._name

    def setName(self, name):
        self._name = name

    def timelineIn(self):
        return self.tl_in

    def timelineOut(self):
        return self.tl_out

    def setTimelineIn(self, value):
        self.tl_in = value

    def setTimelineOut(self, value):
        self.tl_out = value

    def setTimes(self, tl_in, tl_out, src_in, src_out):
        self.tl_in, self.tl_out = tl_in, tl_out
        self.times = (tl_in, tl_out, src_in, src_out)

    def setVersionLinkedToBin(self, _value):
        pass


class _Effect(_EffectTrackItem):
    """Soft effect falso. linked = clip al que esta linkeado (o None)."""

    def __init__(self, name, tl_in, tl_out, linked=None):
        self._name, self.tl_in, self.tl_out = name, tl_in, tl_out
        self.linked = linked

    def name(self):
        return self._name

    def timelineIn(self):
        return self.tl_in

    def timelineOut(self):
        return self.tl_out

    def linkedItems(self):
        return [self.linked] if self.linked is not None else []

    def setTimelineIn(self, value):
        if self.linked is not None:
            # Lo que mide NKS: un linkeado no se mueve a mano.
            raise RuntimeError("Selected time is wrong.")
        self.tl_in = value

    def setTimelineOut(self, value):
        if self.linked is not None:
            raise RuntimeError("Selected time is wrong.")
        self.tl_out = value


class _Track:
    def __init__(self, name, items, effects=()):
        self._name, self._items = name, list(items)
        self._effects = list(effects)

    def name(self):
        return self._name

    def items(self):
        return list(self._items)

    def subTrackItems(self):
        return [list(self._effects)] if self._effects else []

    def addTrackItem(self, clip, tl_in):
        item = _Item(clip, tl_in, tl_in)
        self._items.append(item)
        return item


class _Seq:
    def __init__(self, tracks):
        self._tracks = tracks

    def videoTracks(self):
        return list(self._tracks)


def _timeline(prev_comp_out):
    """Timeline del caso real: el anterior, y el siguiente desde el 6453."""
    return _Seq([
        _Track("_comp_", [_Item(PREV, 6355, prev_comp_out), _Item(NEXT, 6454, 6893)]),
        _Track("aPlate", [_Item(PREV, 6355, 6452), _Item(NEXT, 6453, 6893)]),
        _Track("EditRef", [_Item(PREV, 6363, 6444), _Item(NEXT, 6461, 6885)]),
    ])


def _ranges(seq):
    return {
        (track.name(), item.name()): (item.tl_in, item.tl_out)
        for track in seq.videoTracks() for item in track.items()
    }


class ImportShotPlacementTests(unittest.TestCase):
    def setUp(self):
        self.timeline, hiero = _load_timeline_module()
        self.ns = _load_functions(
            {"_collect_timeline_shots", "_find_insert_frame", "_shot_names_before"},
            {
                "hiero": hiero,
                "_is_burnin_track": lambda name: name.lower() == "burnin",
                "debug_print": lambda *a, **k: None,
            },
        )

    def _import(self, seq, duration=115):
        insert, push, prev, nxt = self.ns["_find_insert_frame"](seq, NEW, duration)
        self.assertEqual((PREV, NEXT), (prev, nxt))
        self.timeline.push_clips_right(
            seq, insert, push, keep_names=self.ns["_shot_names_before"](seq, NEW))
        return insert, push

    def test_previous_comp_with_slate_is_not_dragged_and_new_shot_goes_after_it(self):
        # El comp anterior con el slate entero termina en 6453, sobre el siguiente.
        seq = _timeline(prev_comp_out=6453)
        insert, push = self._import(seq)
        self.assertEqual((6454, 116), (insert, push))
        after = _ranges(seq)
        # El shot anterior no se movio
        self.assertEqual((6355, 6453), after[("_comp_", PREV)])
        self.assertEqual((6355, 6452), after[("aPlate", PREV)])
        self.assertEqual((6363, 6444), after[("EditRef", PREV)])
        # El siguiente quedo justo despues del nuevo (6454..6568)
        self.assertEqual((6569, 7009), after[("aPlate", NEXT)])
        self.assertEqual(6454 + 115, after[("aPlate", NEXT)][0])

    def test_clean_timeline_inserts_at_next_shot_start(self):
        seq = _timeline(prev_comp_out=6452)
        insert, push = self._import(seq)
        self.assertEqual((6453, 115), (insert, push))
        after = _ranges(seq)
        self.assertEqual((6355, 6452), after[("_comp_", PREV)])
        self.assertEqual((6568, 7008), after[("aPlate", NEXT)])
        self.assertEqual((6569, 7008), after[("_comp_", NEXT)])

    def test_without_keep_names_the_previous_comp_is_still_dragged(self):
        # Contrato del parametro: sin keep_names (Projects Panel) no cambia nada.
        seq = _timeline(prev_comp_out=6453)
        _moved, min_in = self.timeline.push_clips_right(seq, 6453, 115)
        self.assertEqual(6355, min_in)
        self.assertEqual((6470, 6568), _ranges(seq)[("_comp_", PREV)])

    def test_effects_linked_are_left_to_their_clip_and_crossing_loose_are_stretched(self):
        # Lo medido en NKS 17 con +Building_Blocks/explore_push_effects.py
        clip_b = _Item("B", 60, 119)
        linked = _Effect("Grade1", 60, 119, linked=clip_b)
        loose = _Effect("Grade2", 130, 170)
        crossing = _Effect("Grade3", 10, 150)
        seq = _Seq([_Track("_comp_", [_Item("A", 0, 59), clip_b, _Item("C", 120, 179)],
                           effects=[linked, loose, crossing])])
        logs = []
        self.timeline.set_debug_print(lambda *a, **k: logs.append(" ".join(map(str, a))))
        try:
            self.timeline.push_clips_right(seq, 60, 30)
        finally:
            self.timeline.set_debug_print(None)
        self.assertFalse([line for line in logs if "error moviendo" in line], logs)
        # El linkeado no se toca (en NKS lo mueve su clip)
        self.assertEqual((60, 119), (linked.tl_in, linked.tl_out))
        self.assertEqual((160, 200), (loose.tl_in, loose.tl_out))
        # El suelto que cruza el punto se estira: sigue cubriendo desde el 10
        self.assertEqual((10, 180), (crossing.tl_in, crossing.tl_out))

    def test_place_clip_skips_slate_with_source_in(self):
        seq = _Seq([_Track("_comp_", [])])
        item, error = self.timeline.place_clip_in_timeline(
            seq, "clip", "_comp_", 6453, 115, NEW, source_in=1)
        self.assertIsNone(error)
        self.assertEqual((6453, 6567, 1, 115), item.times)
        item, error = self.timeline.place_clip_in_timeline(
            seq, "clip", "_comp_", 7000, 50, NEW)
        self.assertEqual((7000, 7049, 0, 49), item.times)


class RenderSlateTrimTests(unittest.TestCase):
    def setUp(self):
        ns = _load_functions({"_trim_render_slates"}, {"debug_print": lambda *a, **k: None})
        self.trim = ns["_trim_render_slates"]

    @staticmethod
    def _plate(first=1001, count=115, latest=True):
        return {"kind": "exr_seq", "is_latest": latest, "first_frame": first,
                "frame_count": count, "name": "PROJA_1010_0300_aPlate_v001"}

    @staticmethod
    def _render(first, count, name="PROJA_1010_0300_comp_v003"):
        return {"kind": "exr_seq", "first_frame": first, "frame_count": count,
                "last_frame": first + count - 1, "name": name}

    def test_slate_frame_1000_is_cut(self):
        comp = self._render(1000, 116)
        self.assertEqual(1, self.trim([self._plate()], [comp]))
        self.assertEqual((1, 1001, 115, 1115),
                         (comp["slate_frames"], comp["first_frame"],
                          comp["frame_count"], comp["last_frame"]))

    def test_trim_is_idempotent(self):
        comp = self._render(1000, 116)
        self.trim([self._plate()], [comp])
        self.assertEqual(0, self.trim([self._plate()], [comp]))
        self.assertEqual((1, 115), (comp["slate_frames"], comp["frame_count"]))

    def test_render_without_slate_or_without_plate_is_untouched(self):
        clean = self._render(1001, 115)
        later = self._render(1009, 99)
        self.assertEqual(0, self.trim([self._plate()], [clean, later]))
        self.assertNotIn("slate_frames", clean)
        self.assertNotIn("slate_frames", later)
        orphan = self._render(1000, 116)
        self.assertEqual(0, self.trim([], [orphan]))
        self.assertEqual(0, self.trim([self._plate(latest=False)], [orphan]))
        self.assertNotIn("slate_frames", orphan)

    def test_only_exr_renders_are_trimmed(self):
        mov = {"kind": "mov", "first_frame": None, "frame_count": 116,
               "name": "PROJA_1010_0300_comp_v003"}
        self.assertEqual(0, self.trim([self._plate()], [mov]))
        self.assertEqual(116, mov["frame_count"])


class RetimeShotLengthTests(unittest.TestCase):
    """Comp de un plano realentado: mas largo que su plate."""

    def setUp(self):
        ns = _load_functions(
            {"_trim_render_slates", "_plate_frames", "_shot_frames",
             "_default_import_items"},
            {"debug_print": lambda *a, **k: None},
        )
        self.ns = ns

    def _shot(self):
        # Medido en un plano real: plate 1001-1074, comp 1000-1092 con slate,
        # EditRef de 76 (60 de corte + 8 de handle por lado sobre el comp).
        plate = {"kind": "exr_seq", "is_latest": True, "first_frame": 1001,
                 "frame_count": 74, "name": "PROJA_1052_0200_aPlate_v001"}
        old_plate = {"kind": "exr_seq", "is_latest": False, "first_frame": 1001,
                     "frame_count": 200, "name": "PROJA_1052_0200_aPlate_v000"}
        editref = {"kind": "mov", "frame_count": 76,
                   "name": "PROJA_1052_0200_EditRef_v001"}
        comp = {"kind": "exr_seq", "is_latest": True, "first_frame": 1000,
                "frame_count": 93, "name": "PROJA_1052_0200_comp_v009"}
        return [plate, old_plate, editref], [comp]

    def test_retimed_comp_sets_the_shot_length(self):
        inputs, publish = self._shot()
        self.ns["_trim_render_slates"](inputs, publish)
        self.assertEqual(74, self.ns["_plate_frames"](inputs))
        items = self.ns["_default_import_items"](inputs, publish)
        self.assertEqual({"PROJA_1052_0200_aPlate_v001", "PROJA_1052_0200_comp_v009"},
                         {it["name"] for it in items})
        # 92 = comp sin el slate; el plate viejo de 200 no cuenta
        self.assertEqual(92, self.ns["_shot_frames"](inputs, items))
        # Con el EditRef centrado sobre el comp: (92 - 76) / 2 = 8 de handle
        self.assertEqual(8, (92 - 76) // 2)

    def test_unselected_comp_falls_back_to_plate(self):
        inputs, _publish = self._shot()
        plate = inputs[0]
        self.assertEqual(74, self.ns["_shot_frames"](inputs, [plate]))
        self.assertEqual(74, self.ns["_shot_frames"](inputs, []))

    def test_short_comp_does_not_shrink_the_shot(self):
        # El otro plano del mismo import: comp de 2 frames contra plate de 150
        inputs = [{"kind": "exr_seq", "is_latest": True, "frame_count": 150}]
        comp = {"kind": "exr_seq", "is_latest": True, "frame_count": 2}
        self.assertEqual(150, self.ns["_shot_frames"](inputs, [comp]))


if __name__ == "__main__":
    unittest.main()
