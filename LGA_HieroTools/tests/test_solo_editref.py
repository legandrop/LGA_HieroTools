import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "LGA_NKS_ViewerTL_Panel_py" / "LGA_NKS_Solo_EditRef.py"


def load_script():
    spec = importlib.util.spec_from_file_location("solo_editref_test", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeItem:
    def __init__(self, start, end):
        self._start = start
        self._end = end

    def timelineIn(self):
        return self._start

    def timelineOut(self):
        return self._end


class FakeTrack:
    def __init__(self, name, enabled=True, clips=(), effects=()):
        self._name = name
        self._enabled = enabled
        self._clips = [FakeItem(a, b) for a, b in clips]
        self._effects = [[FakeItem(a, b) for a, b in effects]] if effects else []

    def name(self):
        return self._name

    def isEnabled(self):
        return self._enabled

    def setEnabled(self, enabled):
        self._enabled = enabled

    def items(self):
        return self._clips

    def subTrackItems(self):
        return self._effects


def build_tracks():
    return [
        FakeTrack("EditRef", clips=[(0, 100)]),
        FakeTrack("EditRef"),
        FakeTrack("aPlate", clips=[(0, 100)]),
        FakeTrack("bPlate"),
        FakeTrack("_comp_", clips=[(0, 100)]),
        FakeTrack("BurnIn", enabled=False, effects=[(0, 100)]),
    ]


def states(tracks):
    return [t.isEnabled() for t in tracks]


class SoloEditRefTests(unittest.TestCase):
    def setUp(self):
        self.script = load_script()

    def toggle(self, tracks, frame=50):
        action = self.script.decide_action(tracks, frame)
        self.script.apply_action(tracks, action)
        return action

    def test_first_toggle_leaves_both_editrefs_and_keeps_burnin_untouched(self):
        tracks = build_tracks()
        self.assertEqual(self.toggle(tracks), "solo")
        self.assertEqual(states(tracks), [True, True, False, False, False, False])

    def test_second_toggle_turns_everything_back_on_except_burnin(self):
        tracks = build_tracks()
        self.toggle(tracks)
        self.assertEqual(self.toggle(tracks), "restore")
        self.assertEqual(states(tracks), [True, True, True, True, True, False])

    def test_burnin_on_stays_on_in_solo(self):
        tracks = build_tracks()
        tracks[-1].setEnabled(True)
        self.toggle(tracks)
        self.assertTrue(tracks[-1].isEnabled())

    def test_disabled_editref_is_turned_on_in_solo(self):
        tracks = build_tracks()
        tracks[0].setEnabled(False)
        self.toggle(tracks)
        self.assertTrue(tracks[0].isEnabled())

    def test_other_track_visible_at_playhead_means_solo(self):
        tracks = build_tracks()
        self.toggle(tracks)
        tracks[2].setEnabled(True)  # aPlate prendido a mano
        self.assertEqual(self.toggle(tracks), "solo")
        self.assertFalse(tracks[2].isEnabled())

    def test_everything_on_and_only_editref_at_playhead_still_solos(self):
        tracks = build_tracks()
        self.assertEqual(self.toggle(tracks, frame=500), "solo")
        self.assertEqual(states(tracks), [True, True, False, False, False, False])

    def test_soft_effect_at_playhead_counts_as_visible(self):
        tracks = [
            FakeTrack("EditRef", clips=[(0, 100)]),
            FakeTrack("Grade", effects=[(0, 100)]),
        ]
        self.assertEqual(self.script.decide_action(tracks, 50), "solo")


if __name__ == "__main__":
    unittest.main()
