import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "LGA_NKS_Edit_Panel_py" / "LGA_NKS_CreateNKScript.py"


def load_script():
    spec = importlib.util.spec_from_file_location("create_nk_naming_test", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Template de un proyecto SIN vendor: el shot de origen es PROJA_089_010 y el
# nombre del template lleva el placeholder PROJA_000_000.
TEMPLATE_SIN_VENDOR = "\n".join(
    [
        "Root {",
        " name T:/vfx-proja/001-100/PROJA_089_010/Comp/1_projects/PROJA_000_000_comp_v002.nk",
        "}",
        "Read {",
        " file T:/VFX-PROJA/001-100/PROJA_089_010/_input/PROJA_089_010_aPlate_v03/PROJA_089_010_aPlate_v03_%04d.exr",
        "}",
        "Read {",
        " file T:/VFX-PROJA/001-100/PROJA_089_010/_input/PROJA_089_010_EditRef_v01.mov",
        "}",
        "Read {",
        " file T:/vfx-proja/4_publish/PROJA_000_000_comp_v001/PROJA_000_000_comp_v001_####.exr",
        "}",
    ]
)

# Template de un proyecto CON vendor al final del nombre.
TEMPLATE_CON_VENDOR = "\n".join(
    [
        "Root {",
        " name T:/vfx-projb/101/PROJB_1013_0800_VEN/Comp/1_projects/PROJB_0000_0000_VEN_comp_v009.nk",
        "}",
        "Read {",
        " file T:/vfx-projb/101/PROJB_1013_0800_VEN/_input/PROJB_1013_0800_VEN_aPlate_v001/PROJB_1013_0800_VEN_aPlate_v001_####.exr",
        "}",
        "Read {",
        " file T:/vfx-projb/101/PROJB_1013_0800_VEN/Comp/4_publish/PROJB_0000_0000_VEN_comp_v000/PROJB_0000_0000_VEN_comp_v000_####.exr",
        "}",
    ]
)


class ShotFolderNameTest(unittest.TestCase):
    def setUp(self):
        self.module = load_script()

    def test_vendor_is_optional(self):
        for name in ("PROJA_503_010", "PROJB_1013_0800_VEN", "PROJC_101_010_0200"):
            self.assertTrue(self.module.SHOT_NAME_RE.match(name), name)

    def test_non_shot_names_are_rejected(self):
        for name in ("PROJA_503", "PROJA_503_010_aPlate", "PROJA_503_010_comp_v000", "Comp"):
            self.assertFalse(self.module.SHOT_NAME_RE.match(name), name)


class DetectSourceShotTest(unittest.TestCase):
    def setUp(self):
        self.module = load_script()

    def test_template_without_vendor(self):
        # El bloque que sigue al shot ("_aPlate", "_EditRef") NO es un vendor.
        self.assertEqual(
            self.module.detect_source_shot(
                TEMPLATE_SIN_VENDOR, "PROJA_000_000_comp_v002.nk", "PROJA_503_010"
            ),
            ("PROJA_089_010", "001-100"),
        )

    def test_template_with_vendor(self):
        self.assertEqual(
            self.module.detect_source_shot(
                TEMPLATE_CON_VENDOR, "PROJB_0000_0000_VEN_comp_v009.nk", "PROJB_1010_0200_VEN"
            ),
            ("PROJB_1013_0800_VEN", "101"),
        )

    def test_fallback_without_shot_folders(self):
        # Sin ninguna ruta con la carpeta del shot, la forma del shot destino
        # decide cuantos bloques tiene el nombre.
        sin_rutas = TEMPLATE_SIN_VENDOR.replace("/", " ")
        self.assertEqual(
            self.module.detect_source_shot(
                sin_rutas, "PROJA_000_000_comp_v002.nk", "PROJA_503_010"
            )[0],
            "PROJA_089_010",
        )
        sin_rutas = TEMPLATE_CON_VENDOR.replace("/", " ")
        self.assertEqual(
            self.module.detect_source_shot(
                sin_rutas, "PROJB_0000_0000_VEN_comp_v009.nk", "PROJB_1010_0200_VEN"
            )[0],
            "PROJB_1013_0800_VEN",
        )

    def test_template_own_placeholder_is_never_the_source(self):
        solo_placeholder = " file T:/vfx-proja/001-100/PROJA_000_000/_input/x.exr"
        with self.assertRaises(self.module.CreateNKError):
            self.module.detect_source_shot(
                solo_placeholder, "PROJA_000_000_comp_v002.nk", "PROJA_503_010"
            )


if __name__ == "__main__":
    unittest.main()
