import ast
import copy
import os
import tempfile
import unittest
from pathlib import Path


PANEL_PATH = Path(__file__).resolve().parents[1] / "LGA_NKS_Projects_Panel.py"


def _load_static_method(name, namespace):
    tree = ast.parse(PANEL_PATH.read_text(encoding="utf-8-sig"))
    panel_class = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ProjectsPanel"
    )
    function = copy.deepcopy(
        next(
            node
            for node in panel_class.body
            if isinstance(node, ast.FunctionDef) and node.name == name
        )
    )
    function.decorator_list = []
    module = ast.Module(body=[function], type_ignores=[])
    exec(compile(module, str(PANEL_PATH), "exec"), namespace)
    return namespace[name]


def _load_panel_methods(names, namespace):
    tree = ast.parse(PANEL_PATH.read_text(encoding="utf-8-sig"))
    panel_class = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ProjectsPanel"
    )
    selected = [
        copy.deepcopy(node)
        for node in panel_class.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    panel = ast.ClassDef(
        name="ProjectsPanel",
        bases=[],
        keywords=[],
        body=selected or [ast.Pass()],
        decorator_list=[],
    )
    module = ast.Module(body=[panel], type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(PANEL_PATH), "exec"), namespace)
    return namespace["ProjectsPanel"]


class _FakeUrl:
    def __init__(self, path, local=True):
        self.path = path
        self.local = local

    def isLocalFile(self):
        return self.local

    def toLocalFile(self):
        return self.path


class _FakeMime:
    def __init__(self, urls):
        self._urls = urls

    def hasUrls(self):
        return bool(self._urls)

    def urls(self):
        return self._urls


class _FakeFileInfo:
    def __init__(self, first, last):
        self.first = first
        self.last = last

    def startFrame(self):
        return self.first

    def endFrame(self):
        return self.last


class _FakeMediaSource:
    def __init__(self, duration, ranges):
        self.duration_value = duration
        self.ranges = ranges

    def duration(self):
        return self.duration_value

    def fileinfos(self):
        return [_FakeFileInfo(first, last) for first, last in self.ranges]


class _FakeClip:
    def __init__(self, duration, ranges):
        self.source = _FakeMediaSource(duration, ranges)

    def mediaSource(self):
        return self.source


class _FakeEffect:
    pass


class _FakeTrackItem:
    def __init__(self, first, last):
        self.first = first
        self.last = last

    def timelineIn(self):
        return self.first

    def timelineOut(self):
        return self.last


class _FakeTrack:
    def __init__(self, name, items):
        self.track_name = name
        self.track_items = items

    def name(self):
        return self.track_name

    def items(self):
        return self.track_items


class _FakeLinkedTrackItem:
    def __init__(self, guid, linked=None, copyable=True):
        self.item_guid = guid
        self.links = linked or []
        self.track = object()
        if not copyable:
            self.copy = None

    def guid(self):
        return self.item_guid

    def linkedItems(self):
        return self.links

    def parentTrack(self):
        return self.track

    def copy(self):
        return self


class ProjectsPanelMediaDropTests(unittest.TestCase):
    def setUp(self):
        namespace = {
            "os": os,
            "_DROP_MEDIA_EXTENSIONS": {".mp4", ".mov", ".mxf", ".jpg", ".png", ".exr"},
            "_DROP_IMAGE_EXTENSIONS": {".jpg", ".png", ".exr"},
            "debug_print": lambda *args, **kwargs: None,
        }
        self.media_from_mime = _load_static_method("_single_media_from_mime", namespace)
        self.detect_kind = _load_static_method("_detected_drop_media_kind", namespace)

    def test_accepts_each_requested_local_format_and_only_one_url(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            for extension in (".mp4", ".mov", ".mxf", ".jpg", ".png", ".exr"):
                path = os.path.join(temp_dir, "media" + extension)
                Path(path).touch()
                self.assertEqual(path, self.media_from_mime(_FakeMime([_FakeUrl(path)])))

            path = os.path.join(temp_dir, "media.jpg")
            self.assertIsNone(self.media_from_mime(_FakeMime([_FakeUrl(path), _FakeUrl(path)])))
            self.assertIsNone(self.media_from_mime(_FakeMime([_FakeUrl(path, local=False)])))

            unsupported = os.path.join(temp_dir, "media.tif")
            Path(unsupported).touch()
            self.assertIsNone(self.media_from_mime(_FakeMime([_FakeUrl(unsupported)])))
            self.assertIsNone(self.media_from_mime(_FakeMime([_FakeUrl(temp_dir)])))

    def test_image_kind_comes_from_hiero_detected_range(self):
        self.assertEqual("video", self.detect_kind(_FakeClip(100, [(0, 99)]), ".mov"))
        self.assertEqual("single image", self.detect_kind(_FakeClip(1, [(1001, 1001)]), ".exr"))
        self.assertEqual("image sequence", self.detect_kind(_FakeClip(12, [(1001, 1012)]), ".png"))

    def test_import_path_does_not_call_rescan_inside_undo(self):
        tree = ast.parse(PANEL_PATH.read_text(encoding="utf-8-sig"))
        panel_class = next(
            node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ProjectsPanel"
        )
        import_method = next(
            node
            for node in panel_class.body
            if isinstance(node, ast.FunctionDef) and node.name == "_import_dropped_media"
        )
        rescan_calls = [
            node
            for node in ast.walk(import_method)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "rescan"
        ]
        self.assertEqual([], rescan_calls)

    def test_gap_accepts_a_playhead_in_the_middle_of_a_long_enough_gap(self):
        fake_hiero = type(
            "FakeHiero",
            (),
            {"core": type("FakeCore", (), {"EffectTrackItem": _FakeEffect})},
        )
        panel = _load_panel_methods(
            {"_real_track_items", "_track_has_free_interval"},
            {"hiero": fake_hiero},
        )
        track = _FakeTrack(
            "Edit",
            [_FakeTrackItem(0, 99), _FakeTrackItem(200, 299)],
        )
        self.assertTrue(panel._track_has_free_interval(track, 120, 80))
        self.assertFalse(panel._track_has_free_interval(track, 120, 81))
        self.assertFalse(panel._track_has_free_interval(track, 50, 10))

    def test_ripple_contract_includes_audio_and_excludes_burnin(self):
        source = PANEL_PATH.read_text(encoding="utf-8-sig")
        tree = ast.parse(source)
        panel_class = next(
            node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ProjectsPanel"
        )
        all_tracks = next(
            node
            for node in panel_class.body
            if isinstance(node, ast.FunctionDef) and node.name == "_all_edit_tracks"
        )
        calls = [
            node.func.attr
            for node in ast.walk(all_tracks)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        ]
        self.assertIn("videoTracks", calls)
        self.assertIn("audioTracks", calls)
        self.assertIn("_is_burnin_track", calls)

    def test_split_rejects_partial_link_and_accepts_a_complete_link_pair(self):
        panel = _load_panel_methods({"_split_link_error"}, {})
        video = _FakeLinkedTrackItem("video")
        audio = _FakeLinkedTrackItem("audio")
        video.links = [audio]
        audio.links = [video]
        self.assertIsNone(panel._split_link_error([video, audio]))
        self.assertIn("does not cross", panel._split_link_error([video]))

    def test_ripple_uses_a_cancellable_undo_after_media_is_validated(self):
        source = PANEL_PATH.read_text(encoding="utf-8-sig")
        tree = ast.parse(source)
        panel_class = next(
            node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ProjectsPanel"
        )
        import_method = next(
            node
            for node in panel_class.body
            if isinstance(node, ast.FunctionDef) and node.name == "_import_media_at"
        )
        calls = [
            node.func.attr
            for node in ast.walk(import_method)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        ]
        self.assertIn("cancelUndo", calls)
        method_source = ast.get_source_segment(source, import_method)
        self.assertLess(
            method_source.index("hiero.core.Clip"),
            method_source.index("project.beginUndo"),
        )


if __name__ == "__main__":
    unittest.main()
