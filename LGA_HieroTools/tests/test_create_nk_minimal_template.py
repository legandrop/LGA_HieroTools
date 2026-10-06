import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "LGA_NKS_Edit_Panel_py" / "LGA_NKS_CreateNKScript.py"


def load_script():
    spec = importlib.util.spec_from_file_location("create_nk_minimal_test", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def trio(label, read_name, anchor, stamp, x, with_file=False):
    """Trio Read + Anchor + Stamp como lo guarda Nuke. Sin with_file el Read
    queda vacio: Nuke no escribe los knobs que estan en su default."""
    read = ["Read {", " inputs 0"]
    if with_file:
        read += [" file PLACEHOLDER", " first 1", " last 1", " origfirst 1", " origlast 1"]
    read += [" origset true", " name %s" % read_name, " label %s" % label,
             " xpos %d" % x, " ypos 200", "}"]
    return read + [
        "NoOp {", " name %s" % anchor, " xpos %d" % x, " ypos 600",
        " title %s" % label, "}",
        "PostageStamp {", " inputs 0", " name %s" % stamp, " xpos %d" % x, " ypos 900",
        " title %s" % label, " anchor %s" % anchor, "}",
    ]


def template(*trios):
    lines = [
        "Root {",
        " inputs 0",
        " name T:/VFX-PROJA/001/PROJA_089_010/Comp/1_projects/PROJA_000_000_comp_v001.nk",
        " frame 1001",
        " first_frame 1001",
        " last_frame 1100",
        "}",
        "BackdropNode {",
        " inputs 0",
        " name BackdropNode1",
        " label input",
        " xpos 1152",
        " ypos 100",
        " bdwidth 997",
        " bdheight 900",
        "}",
    ]
    for item in trios:
        lines += item
    return "\n".join(lines)


A_PLATE = trio("aPlate", "Read4", "Anchor_a1", "Stamp1", 1500)
A_DENOISED = trio("aDenoised", "Read5", "Anchor_a2", "Stamp2", 1610)
B_PLATE = trio("bPlate", "Read6", "Anchor_b1", "Stamp3", 1720, with_file=True)
B_DENOISED = trio("bDenoised", "Read7", "Anchor_b2", "Stamp4", 1830, with_file=True)


def column(key, kind="plate"):
    token = key.replace("Plate", "").replace("Denoised", "")
    return {
        "key": key, "token": token, "kind": kind,
        "info": {"folder": "x", "path": "T:/seq/%s.%%04d.exr" % key, "first": 1001, "last": 1050},
    }


class MinimalTemplateTest(unittest.TestCase):
    def setUp(self):
        self.module = load_script()
        self.tmp = tempfile.TemporaryDirectory()
        self.shot_root = os.path.join(self.tmp.name, "001", "PROJA_503_010")
        os.makedirs(self.shot_root)

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, text, columns, **kwargs):
        self.warnings = []
        self.log = []
        return self.module.build_script(
            text, "PROJA_000_000_comp_v001.nk", self.shot_root,
            os.path.join(self.shot_root, "comp", "1_projects", "PROJA_503_010_comp_v000.nk"),
            self.log, columns=columns, unknown=[], editref_frames=None,
            warnings=self.warnings, **kwargs
        )

    def read_chunk(self, text, label):
        chunks = self.module.split_chunks(text.split("\n"))
        return chunks[self.module.find_read_chunks(chunks)[label]]

    def test_template_with_only_a_slots_builds(self):
        text = self.build(
            template(A_PLATE, A_DENOISED),
            [column("aPlate"), column("aDenoised", "denoised")],
        )
        chunk = self.read_chunk(text, "aPlate")
        # El Read venia vacio: file y rango se AGREGAN.
        self.assertEqual(self.module.chunk_knob(chunk, "file"), "T:/seq/aPlate.%04d.exr")
        self.assertEqual(self.module.chunk_knob(chunk, "first"), "1001")
        self.assertEqual(self.module.chunk_knob(chunk, "origlast"), "1050")
        # Las columnas se quedan donde las tiene el template.
        self.assertEqual(self.module.chunk_knob(chunk, "xpos"), "1500")
        self.assertEqual(
            self.module.chunk_knob(self.read_chunk(text, "aDenoised"), "xpos"), "1610"
        )
        self.assertIn(" bdwidth 997", text)

    def test_template_without_aplate_is_rejected(self):
        with self.assertRaises(self.module.CreateNKError) as ctx:
            self.build(template(A_DENOISED), [column("aPlate")])
        self.assertIn("aPlate", str(ctx.exception))

    def test_plate_without_slot_nor_model_is_reported(self):
        text = self.build(
            template(A_PLATE, A_DENOISED),
            [column("aPlate"), column("aDenoised", "denoised"), column("bPlate")],
        )
        self.assertNotIn("label bPlate", text)
        self.assertTrue(any(w.startswith("bPlate:") for w in self.warnings), self.warnings)

    def test_missing_slot_is_cloned_from_the_last_spare_one(self):
        text = self.build(
            template(A_PLATE, A_DENOISED, B_PLATE, B_DENOISED),
            [column("aPlate"), column("aDenoised", "denoised"),
             column("bPlate"), column("cPlate")],
            keep_missing_denoised=True,
        )
        chunk = self.read_chunk(text, "cPlate")
        self.assertEqual(self.module.chunk_knob(chunk, "file"), "T:/seq/cPlate.%04d.exr")
        # a, aDen, b, bDen (se conserva), c: paso de 110 medido en el template.
        self.assertEqual(self.module.chunk_knob(chunk, "xpos"), str(1500 + 4 * 110))
        self.assertIn(
            "bDenoised: kept the original template path (denoised missing)", self.warnings
        )
        self.assertFalse(any(w.startswith("cPlate:") for w in self.warnings), self.warnings)

    def test_missing_denoised_only_counts_template_slots(self):
        columns = [column("aPlate"), column("bPlate")]
        self.assertEqual(
            self.module.missing_denoised_keys(columns), ["aDenoised", "bDenoised"]
        )
        self.assertEqual(
            self.module.missing_denoised_keys(columns, ["aPlate", "aDenoised"]),
            ["aDenoised"],
        )

    def test_template_slot_keys(self):
        self.assertEqual(
            self.module.template_slot_keys(template(A_PLATE, A_DENOISED, B_PLATE)),
            ["aPlate", "aDenoised", "bPlate"],
        )


if __name__ == "__main__":
    unittest.main()
