"""
Logica del Triple Check (LGA_NKS_TripleCheck_Core): regla de version, escaneo
de Wasabi y local, Versions de Flow y estados de cada fila.

Lo que tiene que seguir siendo cierto:
  - la version de una carpeta es la de PipeSync: `_vNNN` al final y el nombre
    de la task en el nombre base;
  - una carpeta de version vacia no cuenta, y v000 vale 0;
  - Flow solo cuenta las Versions que nombran al shot (no los minicuts);
  - cada combinacion de Flow / Wasabi / Local da el estado y el boton que
    dice docs/Docu_TripleCheck.md;
  - las rutas de Download y Upload llevan las mayusculas de Wasabi.

Datos SIEMPRE ficticios: el repo es publico.
"""

import os
import sys
import unittest
from pathlib import Path

SHARED = Path(__file__).resolve().parents[1] / "LGA_NKS_Shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

import LGA_NKS_TripleCheck_Core as core  # noqa: E402


class FakeLister(object):
    """Arbol en memoria: {"seq/shot/comp/4_publish/v": ["frame.exr", ...]}."""

    kind = "fake"

    def __init__(self, files, fail_on=None):
        self.files = files  # ruta de carpeta -> lista de archivos
        self.fail_on = fail_on

    def _dirs_under(self, prefix):
        out = set()
        for folder in self.files:
            if prefix and not folder.startswith(prefix + "/"):
                continue
            rest = folder[len(prefix) + 1:] if prefix else folder
            if rest:
                out.add(rest.split("/")[0])
        return sorted(out)

    def list_dir(self, parts):
        prefix = "/".join(parts)
        if self.fail_on and prefix == self.fail_on:
            raise core.ListError("denied")
        return self._dirs_under(prefix), list(self.files.get(prefix, []))

    def has_files(self, parts):
        prefix = "/".join(parts)
        return any(
            f for folder, files in self.files.items()
            if (folder == prefix or folder.startswith(prefix + "/"))
            for f in files if not f.startswith(".")
        )

    def content_stats(self, parts):
        prefix = "/".join(parts)
        count = 0
        for folder, files in self.files.items():
            if folder == prefix or folder.startswith(prefix + "/"):
                count += len([f for f in files if not f.startswith(".")])
        return count, count * 100


SHOT = "PROJA_1005_0100_VND"
BASE = "101/%s/comp/4_publish" % SHOT


def tree(*versions, extra=None, empty=()):
    files = {"101/%s/comp" % SHOT: [], BASE: []}
    for v in versions:
        name = "%s_comp_v%03d" % (SHOT, v)
        files["%s/%s" % (BASE, name)] = [] if v in empty else ["%s.1001.exr" % name]
    files.update(extra or {})
    return files


def scan(lister, cg=None):
    return core.scan_task(lister, ["101", SHOT], "cg" if cg else "comp", cg)


def row(flow=None, wasabi=None, local=None, **kw):
    r = {
        "in_timeline": True,
        "shot_in_flow": True,
        "task_in_flow": True,
        "is_cg": False,
        "flow": flow,
        "flow_code": "",
        "wasabi": wasabi or core.empty_scan(),
        "local": local or core.empty_scan(),
    }
    r.update(kw)
    return core.classify(r)


def found(number, name=None, publish="4_publish", task_dir="comp", parts=None):
    s = core.empty_scan()
    s["number"] = number
    s["name"] = name or "%s_comp_v%03d" % (SHOT, number)
    s["task_dir"] = task_dir
    s["publish_dir"] = publish
    s["shot_parts"] = parts or ["101", SHOT]
    return s


class VersionRuleTest(unittest.TestCase):
    def test_folder_version_is_pipesync_rule(self):
        names = [
            "%s_comp_v052" % SHOT,
            "%s_comp_v053_fix" % SHOT,  # no termina en _vNNN
            "%s_roto_v060" % SHOT,  # otra task
            "%s_cmp_v007" % SHOT,  # alias de comp
            "Originals",
        ]
        self.assertEqual(
            core.versioned_entries(names, "comp"),
            [("%s_comp_v052" % SHOT, 52), ("%s_cmp_v007" % SHOT, 7)],
        )

    def test_cg_does_not_filter_by_alias(self):
        names = ["%s_lighting_v016" % SHOT, "%s_animation_v005" % SHOT]
        self.assertEqual(len(core.versioned_entries(names, "cg")), 2)

    def test_pick_folder_prefers_canonical(self):
        self.assertEqual(core.pick_folder(["Comp", "comp"], "comp"), "comp")
        self.assertEqual(core.pick_folder(["Comp", "_input"], "comp"), "Comp")
        self.assertIsNone(core.pick_folder(["comp2"], "comp"))

    def test_pick_publish(self):
        self.assertEqual(core.pick_publish_folder(["3_review", "4_publish"]), "4_publish")


class ScanTest(unittest.TestCase):
    def test_highest_with_files(self):
        result = scan(FakeLister(tree(1, 2, 3)))
        self.assertEqual(result["number"], 3)
        self.assertEqual(result["task_dir"], "comp")

    def test_empty_top_folder_does_not_count(self):
        result = scan(FakeLister(tree(1, 2, 3, empty=(3,))))
        self.assertEqual(result["number"], 2)

    def test_v000_placeholder_is_zero(self):
        result = scan(FakeLister(tree(0)))
        self.assertEqual(result["number"], 0)

    def test_no_task_folder(self):
        result = scan(FakeLister({"101/%s/_input" % SHOT: []}))
        self.assertIsNone(result["number"])
        self.assertEqual(result["error"], "")

    def test_flat_publish_is_an_error(self):
        files = {"101/%s/comp" % SHOT: [], BASE: ["%s_comp_v001.1001.exr" % SHOT]}
        result = scan(FakeLister(files))
        self.assertIn("publish plano", result["error"])

    def test_list_error_is_reported(self):
        result = scan(FakeLister(tree(1), fail_on="101/%s" % SHOT))
        self.assertTrue(result["error"])

    def test_cg_presence(self):
        files = {
            "101/%s/cg" % SHOT: [],
            "101/%s/cg/4_publish" % SHOT: [],
            "101/%s/cg/4_publish/%s_lighting_v016" % (SHOT, SHOT): ["a.exr"],
        }
        result = core.scan_task(
            FakeLister(files), ["101", SHOT], "cg", "%s_lighting_v016_SeqRef" % SHOT
        )
        self.assertTrue(result["present"])

    def test_resolve_shot_parts_case_insensitive(self):
        lister = FakeLister({"101/%s/comp" % SHOT.lower(): []})
        parts, err = core.resolve_shot_parts({}, lister, "101", SHOT)
        self.assertEqual(parts, ["101", SHOT.lower()])
        self.assertEqual(err, "")


class FlowTest(unittest.TestCase):
    def test_minicut_is_ignored(self):
        versions = [
            {"code": "%s_comp_v052" % SHOT},
            {"code": "PROJA_1005_MINICUT_v80"},
            {"code": "PROJA_1005-1013_MINICUT_v03"},
        ]
        self.assertEqual(core.flow_highest(versions, SHOT), (52, "%s_comp_v052" % SHOT))

    def test_version_without_vendor_code_counts(self):
        versions = [{"code": "PROJA_1005_0100_comp_v004"}]
        self.assertEqual(core.flow_highest(versions, SHOT)[0], 4)

    def test_fetch_assigns_versions_without_task(self):
        class FakeSG(object):
            def find(self, entity, filters, fields):
                if entity == "Project":
                    return [{"id": 1, "name": "PROJA"}]
                if entity == "Shot":
                    return [{"id": 10, "code": SHOT, "sg_sequence": {"name": "101"},
                             "sg_status_list": "ip"}]
                if entity == "Task":
                    return [{"id": 100, "content": "Comp", "entity": {"id": 10},
                             "sg_status_list": "ip"}]
                return [
                    {"code": "%s_comp_v002" % SHOT, "sg_task": {"id": 100},
                     "entity": {"id": 10}, "created_at": None},
                    {"code": "%s_comp_v003" % SHOT, "sg_task": None,
                     "entity": {"id": 10}, "created_at": None},
                ]

        ok, shots, stats = core.fetch_flow_project(
            FakeSG(), "PROJA", lambda c: "comp" if str(c).lower() == "comp" else None
        )
        self.assertTrue(ok)
        versions = shots[SHOT.lower()]["tasks"]["comp"]["versions"]
        self.assertEqual(core.flow_highest(versions, SHOT)[0], 3)
        self.assertEqual(stats["without_task"], 1)
        self.assertEqual(stats["unassigned"], 0)


class ClassifyTest(unittest.TestCase):
    def test_all_match(self):
        self.assertEqual(row(5, found(5), found(5))["status"], core.ST_OK)

    def test_nothing_delivered(self):
        self.assertEqual(row(None)["status"], core.ST_NO_VERSIONS)
        self.assertEqual(row(None, found(0), found(0))["status"], core.ST_NO_VERSIONS)

    def test_download(self):
        r = row(10, found(10), found(8))
        self.assertEqual(r["status"], core.ST_DOWNLOAD)
        self.assertTrue(r["can_download"])
        self.assertFalse(r["can_upload"])

    def test_upload(self):
        r = row(10, found(8), found(10))
        self.assertEqual(r["status"], core.ST_UPLOAD)
        self.assertTrue(r["can_upload"])
        self.assertFalse(r["upload_needs_confirm"])

    def test_upload_newer_than_flow_needs_confirm(self):
        r = row(10, found(10), found(12))
        self.assertIn(core.ST_NOT_IN_FLOW_VERSION, r["statuses"])
        self.assertTrue(r["upload_needs_confirm"])

    def test_flow_ahead_of_both(self):
        r = row(10, found(8), found(5))
        self.assertEqual(r["status"], core.ST_MISSING_STORAGE)
        self.assertIn(core.ST_DOWNLOAD, r["statuses"])
        self.assertTrue(r["can_download"])

    def test_flow_ahead_placeholders(self):
        r = row(10, found(0), found(0))
        self.assertEqual(r["status"], core.ST_MISSING_STORAGE)
        self.assertFalse(r["can_download"] or r["can_upload"])

    def test_shot_not_in_flow(self):
        r = row(None, found(3), found(3), shot_in_flow=False, task_in_flow=False)
        self.assertEqual(r["status"], core.ST_NOT_IN_FLOW)
        self.assertNotIn(core.ST_NOT_IN_FLOW_VERSION, r["statuses"])

    def test_not_in_timeline(self):
        r = row(4, found(4), found(2), in_timeline=False)
        self.assertEqual(r["status"], core.ST_NOT_IN_TIMELINE)
        self.assertTrue(r["can_download"])

    def test_error_blocks_actions(self):
        bad = core.empty_scan()
        bad["error"] = "AccessDenied"
        r = row(4, bad, found(6))
        self.assertEqual(r["status"], core.ST_ERROR)
        self.assertFalse(r["can_upload"])

    def test_incomplete_local_offers_download(self):
        r = row(5, found(5), found(5), incomplete="local")
        self.assertEqual(r["status"], core.ST_INCOMPLETE)
        self.assertTrue(r["can_download"])

    def test_publish_name_differs_blocks_upload(self):
        r = row(10, found(8, publish="4_publish"), found(10, publish="3_publish"))
        self.assertFalse(r["can_upload"])
        self.assertTrue(r["upload_blocked"])

    def test_folder_of_another_shot_is_flagged_and_not_uploaded(self):
        local = found(6, name="PROJA_1005_0175_VND_comp_v006")
        local["foreign"] = True
        r = row(5, found(5), local)
        self.assertIn(core.ST_MISNAMED, r["statuses"])
        self.assertFalse(r["can_upload"])

    def test_scan_marks_foreign_folder(self):
        files = tree(1)
        files["%s/PROJA_1005_0175_VND_comp_v004" % BASE] = ["a.exr"]
        result = scan(FakeLister(files))
        self.assertEqual(result["number"], 4)
        self.assertTrue(result["foreign"])
        self.assertEqual(result["strays"], [])

    def test_own_folder_wins_tie_and_copy_is_a_stray(self):
        # Caso real: la v005 del shot y al lado una copia de la v005 de otro
        # shot. Por orden alfabetico ganaba la ajena y salia Wrong folder.
        files = tree(5)
        stray = "PROJA_1005_0175_VND_comp_v005"
        files["%s/%s" % (BASE, stray)] = ["a.exr"]
        result = scan(FakeLister(files))
        self.assertEqual(result["number"], 5)
        self.assertFalse(result["foreign"])
        self.assertEqual(result["strays"], [stray])
        r = row(5, dict(result), dict(result))
        self.assertNotIn(core.ST_MISNAMED, r["statuses"])
        self.assertEqual(r["statuses"], [core.ST_STRAY, core.ST_OK])
        self.assertTrue(core.is_issue(r))

    def test_wasabi_folder_of_another_shot_is_not_downloaded(self):
        wasabi = found(6, name="PROJA_1074_2000_VND_comp_v006")
        wasabi["foreign"] = True
        r = row(6, wasabi, found(0))
        self.assertIn(core.ST_MISNAMED, r["statuses"])
        self.assertFalse(r["can_download"])

    def test_upload_of_shot_not_in_flow_needs_confirm(self):
        r = row(None, found(0), found(3), shot_in_flow=False, task_in_flow=False)
        self.assertTrue(r["can_upload"])
        self.assertTrue(r["upload_needs_confirm"])

    def test_cg_states(self):
        present = core.empty_scan()
        present["present"] = True
        missing = core.empty_scan()
        r = row(16, present, missing, is_cg=True, flow_code="%s_lighting_v016" % SHOT)
        self.assertEqual(r["status"], core.ST_DOWNLOAD)
        r = row(16, missing, missing, is_cg=True, flow_code="%s_lighting_v016" % SHOT)
        self.assertEqual(r["status"], core.ST_MISSING_STORAGE)
        r = row(16, present, present, is_cg=True, flow_code="%s_lighting_v016" % SHOT)
        self.assertEqual(r["status"], core.ST_OK)


class ContentTest(unittest.TestCase):
    def test_partial_download_is_incomplete(self):
        name = "%s_comp_v005" % SHOT
        wasabi = FakeLister({"%s/%s" % (BASE, name): ["a", "b", "c"]})
        local = FakeLister({"%s/%s" % (BASE, name): ["a"]})
        r = {"wasabi": found(5), "local": found(5)}
        core.compare_content(r, local, wasabi)
        self.assertEqual(r["incomplete"], "local")

    def test_same_content_is_complete(self):
        name = "%s_comp_v005" % SHOT
        files = {"%s/%s" % (BASE, name): ["a", "b"]}
        r = {"wasabi": found(5), "local": found(5)}
        core.compare_content(r, FakeLister(files), FakeLister(files))
        self.assertEqual(r["incomplete"], "")


class PathsTest(unittest.TestCase):
    def test_download_uses_wasabi_case(self):
        r = {"wasabi": found(5, task_dir="Comp")}
        target = core.download_target("N:/VFX-PROJA", r)
        self.assertEqual(
            Path(target), Path("N:/VFX-PROJA/101/%s/Comp/4_publish/%s_comp_v005" % (SHOT, SHOT))
        )

    def test_upload_uses_wasabi_case_when_it_exists(self):
        r = {"wasabi": found(4, task_dir="Comp"), "local": found(5, task_dir="comp")}
        source = core.upload_source("N:/VFX-PROJA", r, "comp", isdir=lambda p: True)
        self.assertIn("%sComp%s" % (os.sep, os.sep), source)

    def test_upload_uses_canonical_when_wasabi_has_nothing(self):
        r = {"wasabi": core.empty_scan(), "local": found(5, task_dir="Comp")}
        source = core.upload_source("N:/VFX-PROJA", r, "comp", isdir=lambda p: True)
        self.assertIn("%scomp%s" % (os.sep, os.sep), source)

    def test_blocked_upload_has_no_source(self):
        r = {"wasabi": found(4), "local": found(5), "upload_blocked": "x"}
        self.assertIsNone(core.upload_source("N:/VFX-PROJA", r, "comp"))


class WasabiListerTest(unittest.TestCase):
    def setUp(self):
        self._delay = core.NET_RETRY_DELAY
        core.NET_RETRY_DELAY = 0

    def tearDown(self):
        core.NET_RETRY_DELAY = self._delay

    def test_pagination_and_files(self):
        class Client(object):
            def list_objects_v2(self, **kw):
                if kw.get("Delimiter"):
                    if not kw.get("ContinuationToken"):
                        return {"CommonPrefixes": [{"Prefix": "101/a/"}],
                                "IsTruncated": True, "NextContinuationToken": "t"}
                    return {"CommonPrefixes": [{"Prefix": "101/b/"}],
                            "Contents": [{"Key": "101/", "Size": 0}]}
                return {"Contents": [{"Key": "101/a/", "Size": 0},
                                     {"Key": "101/a/f.exr", "Size": 7}]}

        lister = core.WasabiLister(Client(), "bucket")
        self.assertEqual(lister.list_dir(["101"]), (["a", "b"], []))
        self.assertTrue(lister.has_files(["101", "a"]))
        self.assertEqual(lister.content_stats(["101", "a"]), (1, 7))

    def test_access_denied_does_not_retry_nor_kill(self):
        calls = []

        class Denied(Exception):
            response = {"Error": {"Code": "AccessDenied"}}

        class Client(object):
            def list_objects_v2(self, **kw):
                calls.append(kw)
                raise Denied("no")

        lister = core.WasabiLister(Client(), "bucket")
        with self.assertRaises(core.ListError):
            lister.list_dir(["101"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(lister.dead, "")

    def test_network_failure_marks_lister_dead(self):
        calls = []

        class Client(object):
            def list_objects_v2(self, **kw):
                calls.append(kw)
                raise OSError("unreachable")

        lister = core.WasabiLister(Client(), "bucket")
        with self.assertRaises(core.ListError):
            lister.list_dir(["101"])
        self.assertEqual(len(calls), core.NET_ATTEMPTS)
        with self.assertRaises(core.ListError):
            lister.list_dir(["102"])
        self.assertEqual(len(calls), core.NET_ATTEMPTS)


class TaskStatusTest(unittest.TestCase):
    # Mismo formato que LGA_NKS_Flow_Status_Config: code -> (nombre, color, tag),
    # en el orden del flujo de trabajo.
    CATALOG = {
        "noread": ("Not ready", "#000000", None),
        "progre": ("In progress", "#7d4cff", None),
        "revleg": ("Review Lega", "#69135e", "Rev_Lega"),
        "apr": ("Delivery Apr", "#266612", "Approved"),
    }

    def test_known_status_follows_workflow_order(self):
        self.assertEqual(
            core.task_status_info("revleg", self.CATALOG), ("Review Lega", "#69135e", 2)
        )
        orders = [core.task_status_info(c, self.CATALOG)[2] for c in ("apr", "noread", "progre")]
        self.assertEqual(orders, [3, 0, 1])

    def test_unknown_code_is_shown_raw_after_known(self):
        self.assertEqual(core.task_status_info("xyz", self.CATALOG), ("xyz", None, 4))

    def test_no_task_goes_last(self):
        self.assertEqual(core.task_status_info("", self.CATALOG), ("", None, 5))

    def test_has_no_versions(self):
        empty = core.empty_scan()
        row = {"flow": None, "wasabi": empty, "local": empty}
        self.assertTrue(core.has_no_versions(row))
        # v000 es el placeholder: no es una entrega.
        v000 = dict(empty, number=0)
        self.assertTrue(core.has_no_versions(dict(row, local=v000)))
        self.assertFalse(core.has_no_versions(dict(row, wasabi=dict(empty, number=3))))
        self.assertFalse(core.has_no_versions(dict(row, flow=2)))


if __name__ == "__main__":
    unittest.main()
