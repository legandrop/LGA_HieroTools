"""
Apply AMF de NKS (LGA_NKS_ApplyAMF): las piezas puras del plan de color.

Lo que tiene que seguir siendo cierto:
  - un .cube se valida por estructura (tamano declarado y filas exactas) y un
    archivo inexistente, vacio o roto se rechaza ANTES de crear el efecto;
  - con varios .cube se elige uno de forma determinista (version mas alta de
    cada LUT y, entre LUT distintos, el ultimo alfabetico);
  - el working space de un .cube sale del nombre y, sin pista, es ACEScct;
  - match_colorspace_option devuelve el NOMBRE CORTO (antes del primer TAB) y
    deja los alias y los roles para el final;
  - la cadena va en un bloque contiguo de subtracks por ENCIMA del mas alto
    ocupado, nunca en uno ocupado (crear sobre uno ocupado borra el efecto que
    estaba) ni partida por un efecto del artista;
  - un efecto AJENO (fuera de Look_Files) no hace saltear el nuestro;
  - Node.hasError() en True no saca el efecto ni lo cuenta como error: marca
    efectos sanos cuando el working space no esta en el config de nuke.root().

El modulo importa `hiero`: se carga con stubs, sin abrir el host.
"""

import importlib.util
import os
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "LGA_NKS_Edit_Panel_py"
    / "LGA_NKS_ApplyAMF.py"
)


def load_module():
    """Carga el modulo con `hiero` stubbeado y deja sys.modules como estaba."""
    nombres = ("hiero", "hiero.core", "hiero.ui")
    guardados = {n: sys.modules.get(n) for n in nombres}
    hiero = types.ModuleType("hiero")
    hiero.core = types.ModuleType("hiero.core")
    hiero.ui = types.ModuleType("hiero.ui")
    sys.modules.update({"hiero": hiero, "hiero.core": hiero.core, "hiero.ui": hiero.ui})
    try:
        spec = importlib.util.spec_from_file_location("apply_amf_nks_under_test", str(SCRIPT_PATH))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        for nombre, previo in guardados.items():
            if previo is None:
                sys.modules.pop(nombre, None)
            else:
                sys.modules[nombre] = previo
    return module


class FakeKnob:
    def __init__(self, values):
        self._values = values

    def values(self):
        return self._values


class FakeNode:
    def __init__(self, values):
        self._knobs = {"working_space": FakeKnob(values)}

    def __getitem__(self, name):
        return self._knobs[name]


# Opciones como las devuelve el enum de Nuke 17 (medidas en NKS y en Nuke).
ACES12 = [
    "color_picking\tcolor_picking (Output - sRGB)",
    "default\tdefault (ACES - ACES2065-1)",
    "scene_linear\tscene_linear (ACES - ACEScg)",
    "ACES - ACES2065-1\tColorspaces/ACES/ACES - ACES2065-1",
    "ACES - ACEScc\tColorspaces/ACES/ACES - ACEScc",
    "ACES - ACEScct\tColorspaces/ACES/ACES - ACEScct",
    "ACES - ACEScg\tColorspaces/ACES/ACES - ACEScg",
    "Input - ARRI - V3 LogC (EI160) - Wide Gamut\tColorspaces/Input/ARRI/Input - ARRI - V3 LogC (EI160) - Wide Gamut",
    "acescc\tColorspaces/Utility/Aliases/acescc",
    "acescct\tColorspaces/Utility/Aliases/acescct",
    "acescg\tColorspaces/Utility/Aliases/acescg",
]
V2 = [
    "aces_interchange\taces_interchange (ACES2065-1)",
    "scene_linear\tscene_linear (ACEScg)",
    "ACES2065-1\tColorspaces/ACES/ACES2065-1\t\taces2065_1,aces,ACES - ACES2065-1,lin_ap0,lin_ap0_scene",
    "ACEScc\tColorspaces/ACES/ACEScc\t\tACES - ACEScc,acescc_ap1",
    "ACEScct\tColorspaces/ACES/ACEScct\t\tACES - ACEScct,acescct_ap1",
    "ACEScg\tColorspaces/ACES/ACEScg\t\tACES - ACEScg,lin_ap1,lin_ap1_scene",
]


class ApplyAmfNksTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_module()

    def setUp(self):
        self.m.reset_caches()
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, nombre, texto):
        path = os.path.join(self.tmp, nombre)
        with open(path, "w", newline="\n", encoding="utf-8") as handle:
            handle.write(texto)
        return path.replace("\\", "/")

    def cube3(self, nombre, n, filas=None):
        filas = n ** 3 if filas is None else filas
        texto = "TITLE \"t\"\nLUT_3D_SIZE %d\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n" % n
        return self.write(nombre, texto + "0.1 0.2 0.3\n" * filas)

    # ------------------------------------------------------------ validacion
    def test_cube_valido_3d_y_1d(self):
        self.assertIsNone(self.m._motivo_cube_invalido(self.cube3("a.cube", 2)))
        uno_d = self.write("b.cube", "LUT_1D_SIZE 4\n" + "0 0 0\n" * 4)
        self.assertIsNone(self.m._motivo_cube_invalido(uno_d))

    def test_cube_ignora_palabras_clave_desconocidas(self):
        texto = "# c\nLUT_3D_SIZE 2\nLUT_IN_VIDEO_RANGE 0 1\n" + "0 0 0\n" * 8
        self.assertIsNone(self.m._motivo_cube_invalido(self.write("c.cube", texto)))

    def test_cube_truncado_con_filas_de_mas_y_sin_header(self):
        self.assertIn("truncated", self.m._motivo_cube_invalido(self.cube3("t.cube", 2, filas=3)))
        self.assertIn("extra", self.m._motivo_cube_invalido(self.cube3("e.cube", 2, filas=10)))
        self.assertIn("LUT_1D_SIZE", self.m._motivo_cube_invalido(self.write("h.cube", "foo bar\n")))
        self.assertIn("not a valid", self.m._motivo_cube_invalido(self.write("s.cube", "LUT_3D_SIZE abc\n")))

    def test_motivo_archivo_inutil(self):
        inexistente = os.path.join(self.tmp, "no_existe.cube").replace("\\", "/")
        self.assertIn("does not exist", self.m.motivo_archivo_inutil(inexistente))
        self.assertIn("is empty", self.m.motivo_archivo_inutil(self.write("v.cube", "")))
        self.assertIn("not valid XML", self.m.motivo_archivo_inutil(self.write("r.clf", "<ProcessList><Matrix")))
        self.assertIsNone(self.m.motivo_archivo_inutil(self.write("ok.clf", "<ProcessList/>")))
        self.assertIsNone(self.m.motivo_archivo_inutil(self.cube3("ok.cube", 2)))

    # ------------------------------------------------------------ pick_cube
    def test_pick_cube_sin_cubes_y_con_uno(self):
        self.assertIsNone(self.m.pick_cube(self.tmp.replace("\\", "/")))
        self.m.reset_caches()
        self.cube3("PROJA_LMT_v001.cube", 2)
        elegido = self.m.pick_cube(self.tmp.replace("\\", "/"))
        self.assertTrue(elegido.endswith("PROJA_LMT_v001.cube"))
        self.assertEqual(self.m._AVISOS_CORRIDA, [])

    def test_pick_cube_toma_la_version_mas_alta_sin_distinguir_mayusculas(self):
        for nombre in ("X_LMT_v001.cube", "X_LMT_V003.cube", "X_LMT_v002.cube"):
            self.cube3(nombre, 2)
        elegido = self.m.pick_cube(self.tmp.replace("\\", "/"))
        self.assertTrue(elegido.endswith("X_LMT_V003.cube"), elegido)
        self.assertEqual(self.m._AVISOS_CORRIDA, [])

    def test_pick_cube_varios_lut_elige_el_ultimo_alfabetico_y_avisa(self):
        for nombre in ("PROJA_Preview_v002.cube", "PROJA_Preview_v001.cube", "PROJA_Final_v001.cube"):
            self.cube3(nombre, 2)
        elegido = self.m.pick_cube(self.tmp.replace("\\", "/"))
        self.assertTrue(elegido.endswith("PROJA_Preview_v002.cube"), elegido)
        self.assertEqual(len(self.m._AVISOS_CORRIDA), 1)
        self.assertIn("PROJA_Final_v001.cube", self.m._AVISOS_CORRIDA[0])
        # Cacheado: una segunda pregunta no repite el aviso.
        self.m.pick_cube(self.tmp.replace("\\", "/"))
        self.assertEqual(len(self.m._AVISOS_CORRIDA), 1)

    # ------------------------------------------------------ working space
    def test_cube_working_space(self):
        casos = {
            "PROJA_LMT_ACEScct_v001.cube": ("ACEScct", "nombre"),
            "PROJA_acescc.cube": ("ACEScc", "nombre"),
            "show_ACEScg_look.cube": ("ACEScg", "nombre"),
            "show_AP1.cube": ("ACEScg", "nombre"),
            "show_ap0.cube": ("ACES2065-1", "nombre"),
            "show_Linear.cube": ("ACES2065-1", "nombre"),
            "show_nonlinear.cube": ("ACEScct", "default"),
            "PROJA_nohint.cube": ("ACEScct", "default"),
            "ACEScg_to_ACEScct.cube": ("ACEScg", "nombre"),
        }
        for nombre, esperado in casos.items():
            self.assertEqual(self.m.cube_working_space(nombre), esperado, nombre)

    # --------------------------------------------- match_colorspace_option
    def match(self, opciones, pedido):
        return self.m.match_colorspace_option(FakeNode(opciones), "working_space", pedido)

    def test_match_devuelve_el_nombre_corto_en_aces12(self):
        self.assertEqual(self.match(ACES12, "ACEScct"), "ACES - ACEScct")
        self.assertEqual(self.match(ACES12, "ACEScc"), "ACES - ACEScc")
        self.assertEqual(self.match(ACES12, "ACEScg"), "ACES - ACEScg")
        self.assertEqual(self.match(ACES12, "ACES2065-1"), "ACES - ACES2065-1")

    def test_match_con_configs_v2_no_arrastra_los_campos_con_tab(self):
        for pedido in ("ACEScct", "ACEScc", "ACEScg", "ACES2065-1"):
            resultado = self.match(V2, pedido)
            self.assertEqual(resultado, pedido)
            self.assertNotIn("\t", resultado)

    def test_match_alias_y_roles_quedan_para_el_final(self):
        # Los alias en minuscula no le ganan al nombre del espacio...
        self.assertEqual(self.match(ACES12, "ACEScct"), "ACES - ACEScct")
        # ...pero si es lo unico que hay, se usan.
        solo_alias = [o for o in ACES12 if "Aliases" in o]
        self.assertEqual(self.match(solo_alias, "ACEScct"), "acescct")
        # Un rol no le gana a un espacio directo.
        self.assertEqual(self.match(ACES12, "ACES2065-1"), "ACES - ACES2065-1")

    def test_match_con_parentesis_en_el_nombre_y_sin_resultado(self):
        self.assertEqual(
            self.match(ACES12, "Input - ARRI - V3 LogC (EI160) - Wide Gamut"),
            "Input - ARRI - V3 LogC (EI160) - Wide Gamut",
        )
        self.assertIsNone(self.match(V2, "NoExisteEnElConfig"))
        self.assertIsNone(self.match(V2, None))

    # ------------------------------------------------ subtracks de la cadena
    def efectos(self, *subs, **extra):
        return [dict({"sub": s}, **extra) for s in subs]

    def test_cadena_sin_ajenos_es_el_0_y_el_1(self):
        self.assertEqual(self.m.subtracks_para_la_cadena([], 2), [0, 1])
        self.assertEqual(self.m.subtracks_para_la_cadena([], 1), [0])
        self.assertEqual(self.m.subtracks_para_la_cadena([], 0), [])

    def test_cadena_va_por_encima_del_mas_alto_ocupado(self):
        casos = {
            (0,): [1, 2],
            (0, 1): [2, 3],
            (1,): [2, 3],      # un ajeno solo en el 1 NO se deja en el medio
            (2, 0, 5): [6, 7],
        }
        for ocupados, esperado in casos.items():
            self.assertEqual(
                self.m.subtracks_para_la_cadena(self.efectos(*ocupados), 2), esperado, ocupados
            )

    def test_cadena_es_contigua_y_no_usa_los_huecos_de_abajo(self):
        libres = self.m.subtracks_para_la_cadena(self.efectos(3), 3)
        self.assertEqual(libres, [4, 5, 6])
        self.assertTrue(all(b - a == 1 for a, b in zip(libres, libres[1:])))
        self.assertNotIn(0, libres)

    def test_cadena_con_un_solo_eslabon_pendiente(self):
        # El otro ya existe (ocupa el 0) o se descarto por su archivo.
        self.assertEqual(self.m.subtracks_para_la_cadena(self.efectos(0), 1), [1])
        self.assertEqual(self.m.subtracks_para_la_cadena([], 1), [0])

    def test_cadena_sin_dato_de_subtrack_no_se_arriesga(self):
        self.assertIsNone(self.m.subtracks_para_la_cadena([{"sub": 0}, {"sub": None}], 2))

    # ---------------------------------------- efectos ajenos vs. nuestros
    def test_un_efecto_ajeno_no_hace_saltear_el_nuestro(self):
        ajeno = {
            "class": "OCIOFileTransform", "linked": True, "same_range": True,
            "file": "D:/Mi_Carpeta/mi_lut.cube", "sub": 0,
        }
        nuestro = {
            "class": "OCIOFileTransform", "linked": True, "same_range": True,
            "file": "T:/VFX-PROJA/101/PROJA_101_0010/_input/Look_Files/x.cube", "sub": 1,
        }
        self.assertIsNone(self.m.find_existing_effect([ajeno], "OCIOFileTransform"))
        self.assertIs(self.m.find_existing_effect([ajeno, nuestro], "OCIOFileTransform"), nuestro)
        self.assertIsNone(self.m.find_existing_effect([nuestro], "OCIOCDLTransform"))

    # ------------------------------------------- Node.hasError() no decide
    def test_has_error_no_saca_el_efecto_ni_lo_cuenta_como_error(self):
        class Knob:
            def __init__(self, values=()):
                self._values, self._value = list(values), None

            def values(self):
                return self._values

            def setValue(self, value):
                self._value = value

            def value(self):
                return self._value

        class Node:
            def __init__(self):
                self._knobs = {
                    "file": Knob(),
                    "working_space": Knob(ACES12),
                }

            def __getitem__(self, name):
                return self._knobs[name]

            def knobs(self):
                return self._knobs

            def hasError(self):
                return True

            def error(self):
                return True

        class Effect:
            def __init__(self):
                self._node = Node()

            def node(self):
                return self._node

            def name(self):
                return "OCIOFileTransform1"

        class Track:
            def __init__(self):
                self.quitados = []

            def createEffect(self, **kwargs):
                return Effect()

            def removeSubTrackItem(self, *args):
                self.quitados.append(args)

        class TrackItem:
            def __init__(self):
                self.track = Track()

            def parent(self):
                return self.track

        item = TrackItem()
        fallos = {}
        spec = {
            "type": "OCIOFileTransform",
            "file": "T:/VFX-PROJA/101/PROJA_101_0010/_input/Look_Files/lmt.clf",
            "cccid": None,
            "working_space": "ACES2065-1",
        }
        self.assertEqual(self.m.apply_effect(item, spec, [], 0, fallos, "PROJA_101_0010"), "creado")
        self.assertEqual(item.track.quitados, [])
        self.assertEqual(fallos, {})


if __name__ == "__main__":
    unittest.main()
