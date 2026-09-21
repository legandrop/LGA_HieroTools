import ast
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = ROOT / "LGA_NKS_Shared" / "LGA_NKS_ThumbnailCapture.py"


def load_helper():
    spec = importlib.util.spec_from_file_location("thumbnail_capture_test", HELPER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeTrack:
    def __init__(
        self,
        name,
        enabled=True,
        fail_on_disable=False,
        ignore_disable=False,
        ignore_enable=False,
    ):
        self._name = name
        self._enabled = enabled
        self.fail_on_disable = fail_on_disable
        self.ignore_disable = ignore_disable
        self.ignore_enable = ignore_enable
        self.states = []

    def name(self):
        return self._name

    def isEnabled(self):
        return self._enabled

    def setEnabled(self, enabled):
        if not enabled and self.ignore_disable:
            self.states.append(enabled)
            return
        if enabled and self.ignore_enable:
            self.states.append(enabled)
            return
        if not enabled and self.fail_on_disable:
            self.states.append(enabled)
            raise RuntimeError("disable failed")
        self._enabled = enabled
        self.states.append(enabled)


class FakeSequence:
    def __init__(self, tracks):
        self._tracks = tracks

    def videoTracks(self):
        return self._tracks


class BurnInCaptureTests(unittest.TestCase):
    def setUp(self):
        self.helper = load_helper()

    def test_disables_exact_burnin_track_during_capture_and_restores_it(self):
        burnin = FakeTrack("BurnIn")
        lookalikes = [
            FakeTrack("burn-in"),
            FakeTrack("BURN_IN"),
            FakeTrack("burn in"),
        ]
        other = FakeTrack("Comp")
        events = []

        def capture():
            self.assertFalse(burnin.isEnabled())
            self.assertTrue(all(track.isEnabled() for track in lookalikes))
            self.assertTrue(other.isEnabled())
            self.assertEqual(1, len(events))
            return "image"

        result = self.helper.capture_viewer_image_without_burnin(
            FakeSequence([other, burnin, *lookalikes]),
            capture,
            process_events=lambda: events.append("refresh"),
        )

        self.assertEqual("image", result)
        self.assertTrue(burnin.isEnabled())
        self.assertTrue(all(track.isEnabled() for track in lookalikes))
        self.assertEqual([], other.states)
        self.assertEqual(2, len(events))

    def test_preserves_a_burnin_that_was_already_disabled(self):
        burnin = FakeTrack("BurnIn", enabled=False)

        result = self.helper.capture_viewer_image_without_burnin(
            FakeSequence([burnin]), lambda: "image"
        )

        self.assertEqual("image", result)
        self.assertFalse(burnin.isEnabled())
        self.assertEqual([], burnin.states)

    def test_restores_track_when_viewer_capture_fails(self):
        burnin = FakeTrack("BurnIn")

        def fail_capture():
            self.assertFalse(burnin.isEnabled())
            raise RuntimeError("viewer failed")

        with self.assertRaisesRegex(RuntimeError, "viewer failed"):
            self.helper.capture_viewer_image_without_burnin(
                FakeSequence([burnin]), fail_capture
            )

        self.assertTrue(burnin.isEnabled())
        self.assertEqual([False, True], burnin.states)

    def test_aborts_capture_and_restores_if_a_burnin_cannot_be_disabled(self):
        first = FakeTrack("BurnIn")
        failing = FakeTrack("BurnIn", fail_on_disable=True)
        capture_calls = []

        with self.assertRaises(self.helper.BurnInTrackError):
            self.helper.capture_viewer_image_without_burnin(
                FakeSequence([first, failing]),
                lambda: capture_calls.append("captured"),
            )

        self.assertEqual([], capture_calls)
        self.assertTrue(first.isEnabled())
        self.assertTrue(failing.isEnabled())

    def test_aborts_if_hiero_silently_keeps_the_burnin_enabled(self):
        burnin = FakeTrack("BurnIn", ignore_disable=True)
        capture_calls = []

        with self.assertRaises(self.helper.BurnInTrackError):
            self.helper.capture_viewer_image_without_burnin(
                FakeSequence([burnin]),
                lambda: capture_calls.append("captured"),
            )

        self.assertEqual([], capture_calls)
        self.assertTrue(burnin.isEnabled())

    def test_no_sequence_still_allows_capture(self):
        self.assertEqual(
            "image",
            self.helper.capture_viewer_image_without_burnin(None, lambda: "image"),
        )

    def test_restore_failure_is_reported_even_when_capture_also_fails(self):
        burnin = FakeTrack("BurnIn", ignore_enable=True)

        with self.assertRaisesRegex(
            self.helper.BurnInTrackError, "No se pudo restaurar"
        ) as raised:
            self.helper.capture_viewer_image_without_burnin(
                FakeSequence([burnin]),
                lambda: (_ for _ in ()).throw(RuntimeError("viewer failed")),
            )

        self.assertIsInstance(raised.exception.__cause__, RuntimeError)
        self.assertFalse(burnin.isEnabled())


class CaptureIntegrationTests(unittest.TestCase):
    CASES = (
        (
            ROOT / "LGA_NKS_Flow_S3_Panel_py" / "LGA_NKS_Flow_Thumbs.py",
            "main",
        ),
        (
            ROOT / "LGA_NKS_Flow_S3_Panel_py" / "LGA_NKS_Flow_UpdateThumb.py",
            "capture_viewer_snapshot_to_temp",
        ),
        (
            ROOT / "LGA_NKS_Flow_S3_Panel_py" / "LGA_NKS_Flow_CreateShot.py",
            "create_shot_thumbnail",
        ),
    )

    def test_every_thumbnail_entry_point_uses_the_shared_guard(self):
        for source_path, function_name in self.CASES:
            with self.subTest(source=source_path.name, function=function_name):
                tree = ast.parse(source_path.read_text(encoding="utf-8-sig"))
                function = next(
                    node
                    for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == function_name
                )
                calls = {
                    node.func.id
                    for node in ast.walk(function)
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                }
                self.assertIn("capture_viewer_image_without_burnin", calls)

                guard_call = next(
                    node
                    for node in ast.walk(function)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "capture_viewer_image_without_burnin"
                )
                self.assertEqual(
                    "capture_after_track_settles",
                    getattr(guard_call.args[1], "id", None),
                )

                settle_function = next(
                    node
                    for node in ast.walk(function)
                    if isinstance(node, ast.FunctionDef)
                    and node.name == "capture_after_track_settles"
                )
                settle_calls = {
                    (getattr(node.func.value, "id", None), node.func.attr)
                    for node in ast.walk(settle_function)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                }
                self.assertIn(("time", "sleep"), settle_calls)
                self.assertIn(("viewer", "image"), settle_calls)


if __name__ == "__main__":
    unittest.main()
