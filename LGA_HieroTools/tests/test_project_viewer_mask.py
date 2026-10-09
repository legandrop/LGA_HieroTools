"""
Mascara de viewer por proyecto (LGA_Projects_Panel_SwitchSequence +
LGA_NKS_Viewer_Mask.set_mask).

Lo que tiene que seguir siendo cierto:
  - al entrar a un timeline de un proyecto de PROJECT_VIEWER_MASKS el viewer
    queda con su mascara (aspect ratio y estilo), venga del root de studio o
    del de client y este escrita la carpeta VFX- como este escrita;
  - un proyecto que no figura no se toca, tampoco uno cuyo nombre solo EMPIEZA
    igual que uno de la tabla;
  - set_mask() deja un estado fijo: llamarla dos veces no rota el estilo;
  - con la mascara al 50% los burn-ins que otra mascara dejo corridos vuelven
    a su lugar;
  - la tabla real guarda hashes, nunca el nombre de un proyecto.

Los dos modulos importan `hiero`: se cargan con stubs calificados por paquete,
sin abrir el host.
"""

import importlib.util
import re
import sys
import types
import unittest
from pathlib import Path


PACK_DIR = Path(__file__).resolve().parents[1]
SWITCH_PATH = (
    PACK_DIR / "LGA_NKS_Projects_Panel_py" / "LGA_Projects_Panel_SwitchSequence.py"
)
MASK_PATH = PACK_DIR / "LGA_NKS_ViewerTL_Panel_py" / "LGA_NKS_Viewer_Mask.py"

STYLE_NONE = "eMaskOverlayNone"
STYLE_HALF = "eMaskOverlayHalf"
STYLE_FULL = "eMaskOverlayFull"


class FakeViewer:
    def __init__(self, style=STYLE_NONE):
        self.style = style
        self.aspect = None

    def maskOverlayStyle(self):
        return self.style

    def setMaskOverlayStyle(self, style):
        self.style = style

    def setMaskOverlayFromRemote(self, aspect):
        self.aspect = aspect


class FakeKnob:
    def __init__(self, value):
        self._value = value

    def value(self):
        return self._value

    def setValue(self, value):
        self._value = value


class FakeNode(dict):
    def knobs(self):
        return self


class FakeEffect:
    """Hace de hiero.core.EffectTrackItem: el modulo lo filtra con isinstance."""

    def __init__(self, name, box, opacity):
        self._name = name
        self._node = FakeNode(box=FakeKnob(box), opacity=FakeKnob(opacity))

    def name(self):
        return self._name

    def node(self):
        return self._node


class FakeTrack:
    def __init__(self, name, effects):
        self._name = name
        self._effects = effects

    def name(self):
        return self._name

    def subTrackItems(self):
        return [list(self._effects)]


class FakeFormat:
    def width(self):
        return 3840

    def height(self):
        return 2160


class FakeProject:
    def __init__(self, path):
        self._path = path

    def path(self):
        return self._path


class FakeSequence:
    def __init__(self, hrox_path, effects=()):
        self._project = FakeProject(hrox_path)
        self._tracks = [FakeTrack("BurnIn", list(effects))]

    def project(self):
        return self._project

    def videoTracks(self):
        return self._tracks

    def format(self):
        return FakeFormat()


def load_modules(estado):
    """Carga los dos modulos con stubs y deja sys.modules como estaba.

    `estado` trae 'viewer' y 'seq', que es lo que devuelven currentViewer() y
    activeSequence().
    """
    hiero = types.ModuleType("hiero")
    hiero_core = types.ModuleType("hiero.core")
    hiero_ui = types.ModuleType("hiero.ui")
    hiero_core.EffectTrackItem = FakeEffect
    hiero_ui.Player = types.SimpleNamespace(
        MaskOverlayStyle=types.SimpleNamespace(
            eMaskOverlayNone=STYLE_NONE,
            eMaskOverlayHalf=STYLE_HALF,
            eMaskOverlayFull=STYLE_FULL,
        )
    )
    hiero_ui.currentViewer = lambda: estado.get("viewer")
    hiero_ui.activeSequence = lambda: estado.get("seq")
    hiero.core = hiero_core
    hiero.ui = hiero_ui

    panel_pkg = types.ModuleType("LGA_NKS_Projects_Panel_py")
    panel_pkg.__path__ = []
    logging_mod = types.ModuleType(
        "LGA_NKS_Projects_Panel_py.LGA_NKS_ProjectsPanel_Logging"
    )
    logging_mod.DEBUG = False
    logging_mod.DEBUG_CONSOLE = False
    logging_mod.DEBUG_LOG = False
    logging_mod.debug_print = lambda *args, **kwargs: None
    logging_mod.reset_debug_log = lambda: None
    memory_mod = types.ModuleType("LGA_NKS_Projects_Panel_py.LGA_NKS_TimelineMemory")
    panel_pkg.LGA_NKS_TimelineMemory = memory_mod

    shared_pkg = types.ModuleType("LGA_NKS_Shared")
    shared_pkg.__path__ = []
    qt_mod = types.ModuleType("LGA_NKS_Shared.LGA_QtAdapter_HieroTools")
    for nombre in ("QtWidgets", "QtGui", "QtCore", "Qt"):
        setattr(qt_mod, nombre, None)
    qt_mod.is_widget_alive = lambda widget: True
    qt_mod.iter_live_widgets = lambda: iter(())

    viewer_pkg = types.ModuleType("LGA_NKS_ViewerTL_Panel_py")
    viewer_pkg.__path__ = []

    stubs = {
        "hiero": hiero,
        "hiero.core": hiero_core,
        "hiero.ui": hiero_ui,
        "nuke": types.ModuleType("nuke"),
        "LGA_NKS_Projects_Panel_py": panel_pkg,
        "LGA_NKS_Projects_Panel_py.LGA_NKS_ProjectsPanel_Logging": logging_mod,
        "LGA_NKS_Projects_Panel_py.LGA_NKS_TimelineMemory": memory_mod,
        "LGA_NKS_Shared": shared_pkg,
        "LGA_NKS_Shared.LGA_QtAdapter_HieroTools": qt_mod,
        "LGA_NKS_ViewerTL_Panel_py": viewer_pkg,
    }
    previos = {nombre: sys.modules.get(nombre) for nombre in stubs}
    sys.modules.update(stubs)

    mask_name = "LGA_NKS_ViewerTL_Panel_py.LGA_NKS_Viewer_Mask"
    previos[mask_name] = sys.modules.get(mask_name)
    try:
        spec = importlib.util.spec_from_file_location(mask_name, MASK_PATH)
        mask_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mask_module)
        sys.modules[mask_name] = mask_module
        viewer_pkg.LGA_NKS_Viewer_Mask = mask_module

        spec = importlib.util.spec_from_file_location("switch_bajo_test", SWITCH_PATH)
        switch_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(switch_module)
    except Exception:
        restaurar_modulos(previos)
        raise

    return switch_module, mask_module, previos


def restaurar_modulos(previos):
    for nombre, modulo in previos.items():
        if modulo is None:
            sys.modules.pop(nombre, None)
        else:
            sys.modules[nombre] = modulo


class ProjectViewerMaskTest(unittest.TestCase):
    def setUp(self):
        self.estado = {"viewer": FakeViewer()}
        self.switch, self.mask, previos = load_modules(self.estado)
        self.addCleanup(restaurar_modulos, previos)
        # La tabla real apunta a un proyecto real: aca se prueba con uno ficticio.
        self.switch.PROJECT_VIEWER_MASKS = {
            self.switch.project_mask_key("PROJA"): ("3:2", "half"),
        }

    def entrar(self, hrox_path, effects=()):
        seq = FakeSequence(hrox_path, effects)
        self.estado["seq"] = seq
        return self.switch.apply_project_viewer_mask(seq)

    def test_proyecto_de_la_tabla_queda_con_la_mascara_al_50(self):
        self.assertTrue(self.entrar("T:/VFX-PROJA/PROJA_SUP/PROJA_SUP_v001.hrox"))
        self.assertEqual(self.estado["viewer"].style, STYLE_HALF)
        self.assertEqual(self.estado["viewer"].aspect, "3:2")

    def test_vale_igual_en_el_root_de_client_y_con_otra_escritura(self):
        self.assertTrue(self.entrar("N:\\vfx-proja\\PROJA_SUP\\PROJA_v001.hrox"))
        self.assertEqual(self.estado["viewer"].style, STYLE_HALF)
        self.assertEqual(self.estado["viewer"].aspect, "3:2")

    def test_otro_proyecto_no_se_toca(self):
        self.estado["viewer"] = FakeViewer(STYLE_FULL)
        self.assertFalse(self.entrar("T:/VFX-PROJB/PROJB_SUP/PROJB_SUP_v001.hrox"))
        self.assertEqual(self.estado["viewer"].style, STYLE_FULL)
        self.assertIsNone(self.estado["viewer"].aspect)

    def test_un_nombre_que_solo_empieza_igual_no_cuenta(self):
        self.assertFalse(self.entrar("T:/VFX-PROJALT/PROJALT_SUP/PROJALT_SUP_v001.hrox"))
        self.assertEqual(self.estado["viewer"].style, STYLE_NONE)

    def test_proyecto_fuera_de_una_carpeta_vfx_no_se_toca(self):
        self.assertFalse(self.entrar("C:/Users/artista/Desktop/prueba.hrox"))
        self.assertEqual(self.estado["viewer"].style, STYLE_NONE)

    def test_aplicarla_dos_veces_no_rota_el_estilo(self):
        ruta = "T:/VFX-PROJA/PROJA_SUP/PROJA_SUP_v001.hrox"
        self.assertTrue(self.entrar(ruta))
        self.assertTrue(self.entrar(ruta))
        self.assertEqual(self.estado["viewer"].style, STYLE_HALF)

    def test_sin_viewer_no_falla(self):
        self.estado["viewer"] = None
        self.assertFalse(self.entrar("T:/VFX-PROJA/PROJA_SUP/PROJA_SUP_v001.hrox"))

    def test_al_50_los_burnins_corridos_vuelven_a_su_lugar(self):
        # 3840x2160 con mascara 3:2 deja barras de 300 px: asi queda un
        # burn-in que la mascara Full achico por los dos lados.
        corrido = FakeEffect("Shot_Name", (300, 0, 3540, 100), self.mask.MARK_PILLARBOX)
        self.assertTrue(
            self.entrar("T:/VFX-PROJA/PROJA_SUP/PROJA_SUP_v001.hrox", [corrido])
        )
        self.assertEqual(corrido.node()["box"].value(), (0, 0, 3840, 100))
        self.assertEqual(corrido.node()["opacity"].value(), self.mask.MARK_BASE)

    def test_el_boton_sigue_rotando(self):
        self.estado["seq"] = FakeSequence("T:/VFX-PROJB/PROJB_SUP/PROJB_SUP_v001.hrox")
        estilos = []
        for _ in range(3):
            self.mask.main("3:2")
            estilos.append(self.estado["viewer"].style)
        self.assertEqual(estilos, [STYLE_HALF, STYLE_FULL, STYLE_NONE])


class TablaRealTest(unittest.TestCase):
    def test_la_tabla_guarda_hashes_y_mascaras_validas(self):
        estado = {"viewer": FakeViewer()}
        switch, mask, previos = load_modules(estado)
        self.addCleanup(restaurar_modulos, previos)

        self.assertTrue(switch.PROJECT_VIEWER_MASKS)
        for clave, (aspect_ratio, style_name) in switch.PROJECT_VIEWER_MASKS.items():
            # Un nombre de proyecto escrito a mano como clave no pasa de aca.
            self.assertRegex(clave, re.compile(r"^[0-9a-f]{64}$"))
            self.assertIn(aspect_ratio, mask.MASK_MODE_BY_ASPECT)
            self.assertIn(style_name, mask.MASK_STYLE_BY_NAME)


if __name__ == "__main__":
    unittest.main()
