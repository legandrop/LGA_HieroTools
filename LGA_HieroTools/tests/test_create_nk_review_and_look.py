import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "LGA_NKS_Edit_Panel_py" / "LGA_NKS_CreateNKScript.py"

SOURCE_LOOKS = "T:/VFX-PROJA/001/PROJA_089_010/_input/Look_Files"
REVIEW_FILE = r'"\[file dir \[value root.name]]/../3_review/\[file tail \[file rootname \[value root.name]]].mov"'


def load_script():
    spec = importlib.util.spec_from_file_location("create_nk_review_look_test", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def a_plate():
    return [
        "Read {", " inputs 0", " origset true", " name Read4", " label aPlate",
        " xpos 1500", " ypos 200", "}",
        "NoOp {", " name Anchor_a1", " xpos 1500", " ypos 600", " title aPlate", "}",
        "PostageStamp {", " inputs 0", " name Stamp1", " xpos 1500", " ypos 900",
        " title aPlate", " anchor Anchor_a1", "}",
    ]


def write_node(name, file_type=None, file=REVIEW_FILE, first=None, use_limit=None,
               disable=False, indent=""):
    """Write como lo guarda Nuke: sin los knobs que quedaron en su default."""
    lines = ["Write {"]
    if file is not None:
        lines.append(" file %s" % file)
    if file_type:
        lines.append(" file_type %s" % file_type)
    if first is not None:
        lines += [" first %d" % first, " last %d" % (first + 99)]
    if use_limit is not None:
        lines.append(" use_limit %s" % ("true" if use_limit else "false"))
    if disable:
        lines.append(" disable true")
    lines += [" name %s" % name, " xpos 10", " ypos 10", "}"]
    return [
        (indent + line) if (i == 0 or line == "}") else (indent + " " + line)
        for i, line in enumerate(lines)
    ]


def ocio_file(name, file=None, cls="OCIOFileTransform"):
    lines = [cls + " {"]
    if file is not None:
        lines.append(" file %s" % file)
    lines += [" name %s" % name, " xpos 10", " ypos 10", "}"]
    return lines


def group_with(inner_lines, name="Group1"):
    """Group como lo guarda Nuke: el contenido va DESPUES de la llave de
    cierre, indentado, y termina en end_group."""
    return (
        ["Group {", " inputs 0", " name %s" % name, " xpos 0", " ypos 0", "}"]
        + [" " + line for line in inner_lines]
        + ["end_group"]
    )


def template(*nodes):
    lines = [
        "Root {", " inputs 0",
        " name T:/VFX-PROJA/001/PROJA_089_010/Comp/1_projects/PROJA_000_000_comp_v001.nk",
        " frame 1001", " first_frame 1001", " last_frame 1100", "}",
    ] + a_plate()
    for node in nodes:
        lines += node
    return "\n".join(lines)


A_COLUMN = {
    "key": "aPlate", "token": "a", "kind": "plate",
    "info": {"folder": "x", "path": "T:/seq/aPlate.%04d.exr", "first": 1001, "last": 1100},
}


class ReviewWriteAndCubeTest(unittest.TestCase):
    def setUp(self):
        self.module = load_script()
        self.tmp = tempfile.TemporaryDirectory()
        self.shot_root = os.path.join(self.tmp.name, "001", "PROJA_503_010")
        self.look_dir = os.path.join(self.shot_root, "_input", "Look_Files")
        os.makedirs(self.look_dir)

    def tearDown(self):
        self.tmp.cleanup()

    def touch_look(self, *names):
        for name in names:
            Path(self.look_dir, name).write_text("x", encoding="utf-8")

    def look(self, name):
        return (self.look_dir + "/" + name).replace("\\", "/")

    def build(self, text, **kwargs):
        self.warnings = []
        self.log = []
        kwargs.setdefault("editref_frames", 90)
        kwargs.setdefault("editref_start", 1005)
        return self.module.build_script(
            text, "PROJA_000_000_comp_v001.nk", self.shot_root,
            os.path.join(self.shot_root, "comp", "1_projects", "PROJA_503_010_comp_v000.nk"),
            self.log, columns=[A_COLUMN], unknown=[], warnings=self.warnings, **kwargs
        )

    def node(self, text, name):
        for chunk in self.module.split_chunks(text.split("\n")):
            if self.module.chunk_knob(chunk, "name") == name:
                return chunk
        self.fail("no hay un nodo %s" % name)

    def knob(self, text, name, knob):
        return self.module.chunk_knob(self.node(text, name), knob)

    # ---- Writes de review -------------------------------------------------

    def assert_limited(self, text, name):
        self.assertEqual(self.knob(text, name, "use_limit"), "true", name)
        self.assertEqual(self.knob(text, name, "first"), "1005", name)
        self.assertEqual(self.knob(text, name, "last"), "1094", name)

    def test_review_write_with_any_name_gets_the_limit_range(self):
        for name in ("WRITE_DNXHD", "WRITE_REV", "Write_REV", "Write7"):
            text = self.build(template(write_node(name, first=1001, use_limit=True)))
            self.assert_limited(text, name)

    def test_limit_knobs_are_added_when_the_template_does_not_store_them(self):
        text = self.build(template(write_node("Write_REV")))
        self.assert_limited(text, "Write_REV")

    def test_two_video_outputs_both_get_it(self):
        text = self.build(template(
            write_node("WRITE_DNXHD", file_type="mov", first=1001, use_limit=True),
            write_node("Write_Delivery", file=r'"\[file dir \[value root.name]]/../x.mxf"'),
        ))
        self.assert_limited(text, "WRITE_DNXHD")
        self.assert_limited(text, "Write_Delivery")

    def test_image_writes_are_left_alone(self):
        exr = r'"\[file dir \[value root.name]]/../4_publish/x_%04d.exr"'
        text = self.build(template(
            write_node("Write_REV"),
            write_node("Write_EXR", file_type="exr", file=exr, first=1001, use_limit=True),
            write_node("Write_Tif", file=r'"\[file dir \[value root.name]]/../m.tif"'),
        ))
        self.assert_limited(text, "Write_REV")
        self.assertEqual(self.knob(text, "Write_EXR", "first"), "1001")
        self.assertEqual(self.knob(text, "Write_EXR", "last"), "1100")
        self.assertIsNone(self.knob(text, "Write_Tif", "use_limit"))
        self.assertIsNone(self.knob(text, "Write_Tif", "first"))

    def test_file_type_wins_over_the_extension(self):
        text = self.build(template(write_node("Write_A", file_type="exr", file="x.mov")))
        self.assertIsNone(self.knob(text, "Write_A", "use_limit"))
        text = self.build(template(write_node("Write_B", file_type="mov64", file="x.exr")))
        self.assert_limited(text, "Write_B")

    def test_extension_hidden_in_an_expression_is_not_guessed(self):
        text = self.build(template(write_node("Write_X", file='"\\[value some_knob]"')))
        self.assertIsNone(self.knob(text, "Write_X", "use_limit"))
        self.assertTrue(any("indeterminada" in line for line in self.log), self.log)

    def test_no_video_write_does_not_break_and_is_logged(self):
        text = self.build(template(write_node("Write_EXR", file_type="exr", file="x.exr")))
        self.assertIsNone(self.knob(text, "Write_EXR", "use_limit"))
        self.assertTrue(any("WRITE de video: ninguno" in line for line in self.log), self.log)
        text = self.build(template())
        self.assertTrue(any("0 Write(s)" in line for line in self.log), self.log)

    def test_disabled_write_is_adjusted_too(self):
        text = self.build(template(write_node("Write_REV", disable=True)))
        self.assert_limited(text, "Write_REV")
        self.assertTrue(any("[deshabilitado]" in line for line in self.log), self.log)

    def test_write_inside_a_group_is_adjusted_and_logged_with_its_group(self):
        text = self.build(template(
            group_with(write_node("Write_In", indent="")),
            write_node("Write_Top"),
        ))
        self.assert_limited(text, "Write_In")
        self.assert_limited(text, "Write_Top")
        self.assertTrue(
            any("Write_In (en el grupo Group1)" in line for line in self.log), self.log
        )
        self.assertTrue(any("Write_Top (suelto)" in line for line in self.log), self.log)

    def test_without_editref_duration_nothing_is_touched(self):
        text = self.build(template(write_node("Write_REV", first=1001, use_limit=True)),
                          editref_frames=None)
        self.assertEqual(self.knob(text, "Write_REV", "first"), "1001")
        self.assertTrue(any("WRITE de video: sin tocar" in line for line in self.log), self.log)

    # ---- Nodos de look con .cube -----------------------------------------

    def cube_template(self, file=SOURCE_LOOKS + "/PROJA_089_010_LMT_v01.cube"):
        return template(ocio_file("LMT", file))

    def test_cube_node_points_to_the_shot_cube(self):
        self.touch_look("PROJA_503_010_LMT_v01.cube")
        text = self.build(self.cube_template())
        self.assertEqual(
            self.knob(text, "LMT", "file"), self.look("PROJA_503_010_LMT_v01.cube")
        )
        self.assertFalse(any(".cube" in w for w in self.warnings), self.warnings)

    def test_cube_node_with_tcl_expression_is_recognized(self):
        # La expresion que busca *.cube en Look_Files es del look del shot.
        self.touch_look("PROJA_LMT_v03.CUBE")
        expr = (r'"\[lindex \[glob \[file dir \[value root.name]]'
                r'/../../_input/Look_Files/*.cube] 0]"')
        text = self.build(self.cube_template(expr))
        self.assertEqual(self.knob(text, "LMT", "file"), self.look("PROJA_LMT_v03.CUBE"))

    def test_several_cubes_pick_the_highest_version(self):
        self.touch_look("PROJA_LMT_v01.cube", "PROJA_LMT_v10.cube", "PROJA_LMT_v02.cube")
        text = self.build(self.cube_template())
        self.assertEqual(self.knob(text, "LMT", "file"), self.look("PROJA_LMT_v10.cube"))

    def test_cubes_without_version_pick_the_last_alphabetically(self):
        self.touch_look("a_lmt.cube", "b_lmt.cube")
        self.assertEqual(
            self.module.resolve_cube_file(self.shot_root), self.look("b_lmt.cube")
        )

    def test_shot_without_cube_keeps_the_template_path_and_warns(self):
        self.touch_look("PROJA_503_010_LMT_v01.clf")
        text = self.build(self.cube_template())
        # El nodo conserva el path del template (con el shot ya reemplazado).
        self.assertEqual(
            self.knob(text, "LMT", "file"),
            "T:/VFX-PROJA/001/PROJA_503_010/_input/Look_Files/PROJA_503_010_LMT_v01.cube",
        )
        self.assertTrue(any(w.startswith("No .cube LUT found") for w in self.warnings),
                        self.warnings)
        # Un template de .cube no pide .clf: el aviso del .clf no corresponde.
        self.assertFalse(any(".clf" in w for w in self.warnings), self.warnings)

    def test_cube_outside_look_files_is_not_touched(self):
        self.touch_look("PROJA_503_010_LMT_v01.cube")
        fixed = "T:/VFX-PROJA/LUTs/show_lmt.cube"
        text = self.build(self.cube_template(fixed))
        self.assertEqual(self.knob(text, "LMT", "file"), fixed)
        self.assertTrue(any("were not recognized as look nodes" in w for w in self.warnings),
                        self.warnings)

    def test_clf_and_cube_nodes_each_get_their_own_file(self):
        self.touch_look("PROJA_503_010_LMT_v01.cube", "show_lmt_acesap0.clf",
                        "PROJA_503_010_aPlate_v001.cdl")
        text = self.build(template(
            ocio_file("LMT_cube", SOURCE_LOOKS + "/x_v01.cube"),
            ocio_file("LMT_clf", SOURCE_LOOKS + "/x.clf"),
            ocio_file("CDL1", SOURCE_LOOKS + "/x_aPlate_v001.cdl", cls="OCIOCDLTransform"),
        ))
        self.assertEqual(self.knob(text, "LMT_cube", "file"),
                         self.look("PROJA_503_010_LMT_v01.cube"))
        self.assertEqual(self.knob(text, "LMT_clf", "file"), self.look("show_lmt_acesap0.clf"))
        self.assertEqual(self.knob(text, "CDL1", "file"),
                         self.look("PROJA_503_010_aPlate_v001.cdl"))

    def test_clf_template_behaves_as_before(self):
        self.touch_look("show_lmt_acesap0.clf", "other.cube")
        text = self.build(template(ocio_file("LMT", SOURCE_LOOKS + "/x.clf")))
        self.assertEqual(self.knob(text, "LMT", "file"), self.look("show_lmt_acesap0.clf"))
        # Sin nodos .cube en el template no hay aviso de .cube.
        text = self.build(template(ocio_file("LMT", SOURCE_LOOKS + "/x.clf")))
        self.assertFalse(any(".cube" in w for w in self.warnings), self.warnings)

    def test_clf_template_without_clf_still_warns(self):
        text = self.build(template(ocio_file("LMT", SOURCE_LOOKS + "/x.clf")))
        self.assertTrue(any(w.startswith("No .clf LUT found") for w in self.warnings),
                        self.warnings)

    def test_empty_file_node_is_still_assumed_to_be_clf(self):
        self.touch_look("PROJA_503_010_LMT_v01.cube", "show_lmt.clf")
        text = self.build(template(ocio_file("LMT", None)))
        self.assertEqual(self.knob(text, "LMT", "file"), self.look("show_lmt.clf"))

    def test_look_node_kind(self):
        kind = self.module.look_node_kind
        self.assertEqual(kind("OCIOCDLTransform", "x.cube"), "cdl")
        self.assertEqual(kind("OCIOFileTransform", "a/b.CUBE"), "cube")
        self.assertEqual(kind("OCIOFileTransform", "a/b.clf"), "clf")
        self.assertEqual(kind("OCIOFileTransform", ""), "clf")


if __name__ == "__main__":
    unittest.main()
