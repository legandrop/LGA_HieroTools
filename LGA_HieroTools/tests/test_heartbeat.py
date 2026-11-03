"""
Latido de Hiero/NKS (LGA_NKS_Heartbeat): el archivo que deja anotado que
proyecto y que timeline tiene al frente la sesion.

Lo que tiene que seguir siendo cierto:
  - el proyecto sale del timeline activo ("timeline"); sin timeline, del unico
    proyecto abierto ("only-open"); si no, es null ("none");
  - solo escribe si el estado cambio o pasaron 60 s, y nunca si la carpeta de
    latidos no existe (tampoco la crea);
  - la escritura es atomica (temporal + os.replace) y un fallo se reintenta
    en el chequeo siguiente, sin dejar basura ni dar el estado por escrito;
  - los eventos de Hiero solo adelantan el chequeo: el dato sale del estado
    de la sesion, nunca del evento;
  - kShutdown borra el archivo propio y nada mas, sin sacar handlers en pleno
    despacho (Hiero se saltearia al siguiente);
  - el modulo nunca llama a os.kill: en Windows os.kill(pid, 0) termina el
    proceso.

El modulo importa hiero, nuke y el adapter de Qt: se carga con stubs, sin
abrir el host. Los stubs quedan en sys.modules mientras dura cada test, porque
el modulo tambien importa hiero.ui y nuke adentro de sus funciones.
"""

import ast
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "LGA_NKS_Heartbeat.py"
NAMING_PATH = ROOT / "LGA_NKS_Shared" / "LGA_NKS_Flow_NamingUtils.py"

ACCELERATORS = (
    "kAfterNewProjectCreated",
    "kAfterProjectLoad",
    "kAfterProjectSave",
    "kAfterProjectClose",
    "kCurrentViewerChanged",
    "kContextChanged",
)
EVENT_NAMES = ACCELERATORS + ("kShutdown",)

PATH_A = "T:/VFX-PROJA/101_SUP/PROJA_SUP_v004.hrox"
PATH_B = "T:/VFX-PROJB/102_SUP/PROJB_SUP_v012.hrox"
VIEJO = 946684800  # 2000-01-01: marca para saber si un archivo se reescribio


class FakeProject:
    def __init__(self, name, path=""):
        self._name = name
        self._path = path

    def name(self):
        return self._name

    def path(self):
        return self._path


class FakeSequence:
    def __init__(self, name, project):
        self._name = name
        self._project = project

    def name(self):
        return self._name

    def project(self):
        return self._project


class Session:
    """El modulo recien cargado, con el Hiero y el Qt falsos de una sesion."""

    def __init__(self, config_root, log_path):
        self.projects = []      # lo que devuelve hiero.core.projects()
        self.active = None      # lo que devuelve hiero.ui.activeSequence()
        self.window = object()  # lo que devuelve hiero.ui.mainWindow()
        self.timers = []
        self.single_shots = []  # (ms, callback) de QTimer.singleShot
        self.registered = []    # (evento, callback) vigentes
        self.unregistered = []  # lo que se saco con unregisterInterest
        self._build(config_root, log_path)

    def _build(self, config_root, log_path):
        session = self

        class Signal:
            def __init__(self):
                self.callbacks = []

            def connect(self, callback):
                self.callbacks.append(callback)

        class Timer:
            def __init__(self, parent=None):
                self.timeout = Signal()
                self.single = False
                self.active = False
                self.interval = None
                self.starts = []
                session.timers.append(self)

            def setSingleShot(self, flag):
                self.single = flag

            def start(self, ms):
                self.active, self.interval = True, ms
                self.starts.append(ms)

            def stop(self):
                self.active = False

            def fire(self):
                for callback in list(self.timeout.callbacks):
                    callback()

            @staticmethod
            def singleShot(ms, callback):
                session.single_shots.append((ms, callback))

        class Application:
            @classmethod
            def instance(cls):
                return session.app

        self.app = Application()

        events = types.ModuleType("hiero.core.events")
        events.EventType = types.SimpleNamespace(**{name: name for name in EVENT_NAMES})
        events.registerInterest = lambda event_type, callback: self.registered.append((event_type, callback))

        def unregister(event_type, callback):
            self.unregistered.append((event_type, callback))
            self.registered[:] = [r for r in self.registered if r != (event_type, callback)]

        events.unregisterInterest = unregister

        self.core = types.ModuleType("hiero.core")
        self.core.projects = lambda: list(self.projects)
        self.core.events = events
        self.ui = types.ModuleType("hiero.ui")
        self.ui.activeSequence = lambda: self.active
        self.ui.mainWindow = lambda: self.window
        hiero = types.ModuleType("hiero")
        hiero.core, hiero.ui = self.core, self.ui

        self.nuke = types.ModuleType("nuke")
        self.nuke.env = {"studio": True}
        self.nuke.NUKE_VERSION_STRING = "17.0v4"

        adapter = types.ModuleType("LGA_NKS_Shared.LGA_QtAdapter_HieroTools")
        # Sin QCoreApplication al importar: el modulo no se autoarranca.
        adapter.QtCore = types.SimpleNamespace(
            QTimer=Timer, QCoreApplication=types.SimpleNamespace(instance=lambda: None)
        )
        adapter.QtWidgets = types.SimpleNamespace(QApplication=Application)

        # El naming es Python puro: se usa el de verdad para probar la clave del proyecto.
        naming_spec = importlib.util.spec_from_file_location(
            "LGA_NKS_Shared.LGA_NKS_Flow_NamingUtils", str(NAMING_PATH)
        )
        naming = importlib.util.module_from_spec(naming_spec)
        naming_spec.loader.exec_module(naming)

        stubs = {
            "hiero": hiero,
            "hiero.core": self.core,
            "hiero.core.events": events,
            "hiero.ui": self.ui,
            "nuke": self.nuke,
            "LGA_NKS_Shared": types.ModuleType("LGA_NKS_Shared"),
            "LGA_NKS_Shared.LGA_QtAdapter_HieroTools": adapter,
            "LGA_NKS_Shared.LGA_NKS_Flow_NamingUtils": naming,
        }
        self._saved = {name: sys.modules.get(name) for name in stubs}
        sys.modules.update(stubs)
        spec = importlib.util.spec_from_file_location("heartbeat_under_test", str(MODULE_PATH))
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.module.LOG_PATH = log_path  # el test no escribe en el .log real de la tool
        self.original_config_root = self.module._user_config_root
        self.module._user_config_root = lambda: config_root

    def close(self):
        for name, previous in self._saved.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


class HeartbeatTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="heartbeat_test_")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.folder = os.path.join(self.root, "LGA", "Heartbeat")
        os.makedirs(self.folder)
        self.s = Session(self.root, os.path.join(self.root, "debug.log"))
        self.addCleanup(self.s.close)
        self.beat = self.s.module.Heartbeat()
        self.path = os.path.join(self.folder, "nukestudio-%d.json" % os.getpid())

    # -- helpers --------------------------------------------------------------

    def read(self):
        with open(self.path, encoding="utf-8") as handle:
            return json.load(handle)

    def age_file(self):
        os.utime(self.path, (VIEJO, VIEJO))

    def rewritten(self):
        return os.stat(self.path).st_mtime > VIEJO + 1

    def open_project_a(self, sequence="101"):
        a = FakeProject("PROJA_SUP_v004", PATH_A)
        self.s.projects, self.s.active = [a], FakeSequence(sequence, a)
        return a

    # -- el proyecto: los tres basis -------------------------------------------

    def test_basis_timeline_es_el_proyecto_de_la_secuencia_activa(self):
        a, b = FakeProject("PROJA_SUP_v004", PATH_A), FakeProject("PROJB_SUP_v012", PATH_B)
        self.s.projects, self.s.active = [a, b], FakeSequence("102", b)
        self.assertTrue(self.beat.publish(now=0))
        data = self.read()
        self.assertEqual(data["basis"], "timeline")
        self.assertEqual(data["project"], {"name": "PROJB_SUP_v012", "key": "PROJB", "path": PATH_B})
        self.assertEqual(data["sequence"], "102")
        self.assertEqual(
            data["open"],
            [{"name": "PROJA_SUP_v004", "key": "PROJA"}, {"name": "PROJB_SUP_v012", "key": "PROJB"}],
        )

    def test_basis_only_open_sin_timeline_y_con_un_solo_proyecto(self):
        a = FakeProject("PROJA_SUP_v004", PATH_A)
        self.s.projects = [a]
        self.beat.publish(now=0)
        data = self.read()
        self.assertEqual(data["basis"], "only-open")
        self.assertEqual(data["project"], {"name": "PROJA_SUP_v004", "key": "PROJA", "path": PATH_A})
        self.assertIsNone(data["sequence"])
        self.assertEqual(data["open"], [{"name": "PROJA_SUP_v004", "key": "PROJA"}])

    def test_basis_none_sin_timeline_y_con_dos_proyectos(self):
        a, b = FakeProject("PROJA_SUP_v004", PATH_A), FakeProject("PROJB_SUP_v012", PATH_B)
        self.s.projects = [a, b]
        self.beat.publish(now=0)
        data = self.read()
        self.assertEqual(data["basis"], "none")
        self.assertIsNone(data["project"])
        self.assertIsNone(data["sequence"])
        self.assertEqual([p["key"] for p in data["open"]], ["PROJA", "PROJB"])

    def test_basis_none_sin_proyectos_abiertos(self):
        self.beat.publish(now=0)
        data = self.read()
        self.assertEqual((data["basis"], data["project"], data["sequence"], data["open"]), ("none", None, None, []))

    def test_proyecto_sin_guardar_tiene_ruta_vacia_y_key_null(self):
        nuevo = FakeProject("Untitled")
        self.s.projects, self.s.active = [nuevo], FakeSequence("Sequence 1", nuevo)
        self.beat.publish(now=0)
        data = self.read()
        self.assertEqual(data["project"], {"name": "Untitled", "key": None, "path": ""})
        self.assertEqual(data["open"], [{"name": "Untitled", "key": None}])

    # -- el formato v1 ----------------------------------------------------------

    def test_formato_v1(self):
        self.open_project_a()
        self.beat.publish(now=0)
        data = self.read()
        self.assertEqual(
            set(data), {"v", "app", "host", "pid", "updatedAt", "basis", "project", "sequence", "open"}
        )
        self.assertEqual(data["v"], 1)
        self.assertEqual(data["app"], "nukestudio")
        self.assertEqual(data["host"], "17.0v4")
        self.assertEqual(data["pid"], os.getpid())
        self.assertRegex(data["updatedAt"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertEqual(set(data["project"]), {"name", "key", "path"})
        self.assertTrue(all(set(p) == {"name", "key"} for p in data["open"]))

    def test_un_nombre_con_acentos_viaja_intacto_y_el_archivo_es_ascii(self):
        nuevo = FakeProject("PROJA_Ca\u00f1\u00f3n_v001", "T:/VFX-PROJA/Ca\u00f1\u00f3n/PROJA_Ca\u00f1\u00f3n_v001.hrox")
        self.s.projects, self.s.active = [nuevo], FakeSequence("Secuencia \u00fanica", nuevo)
        self.beat.publish(now=0)
        with open(self.path, "rb") as handle:
            crudo = handle.read()
        self.assertTrue(crudo.isascii())  # sin depender de la codificacion del lector
        data = json.loads(crudo)
        self.assertEqual(data["project"]["name"], "PROJA_Ca\u00f1\u00f3n_v001")
        self.assertEqual(data["sequence"], "Secuencia \u00fanica")

    def test_sin_modo_studio_el_archivo_es_de_hiero(self):
        self.s.nuke.env["studio"] = False
        hiero_beat = self.s.module.Heartbeat()
        hiero_beat.publish(now=0)
        with open(os.path.join(self.folder, "hiero-%d.json" % os.getpid()), encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["app"], "hiero")

    def test_la_carpeta_es_LGA_Heartbeat_dentro_de_la_raiz_de_config(self):
        self.s.module._user_config_root = self.s.original_config_root
        with mock.patch.object(sys, "platform", "win32"), mock.patch.dict(
            os.environ, {"APPDATA": r"C:\Users\x\AppData\Roaming"}
        ):
            self.assertEqual(
                self.s.module.heartbeat_dir(),
                os.path.join(r"C:\Users\x\AppData\Roaming", "LGA", "Heartbeat"),
            )
        with mock.patch.object(sys, "platform", "darwin"):
            self.assertEqual(
                self.s.module.heartbeat_dir(),
                os.path.join(os.path.expanduser("~/Library/Application Support"), "LGA", "Heartbeat"),
            )

    # -- cuando escribe ---------------------------------------------------------

    def test_no_escribe_si_no_cambio_y_pasaron_menos_de_60_s(self):
        self.open_project_a()
        self.assertTrue(self.beat.publish(now=100))
        self.age_file()
        self.assertFalse(self.beat.publish(now=100 + 59.9))
        self.assertFalse(self.rewritten())

    def test_escribe_a_los_60_s_aunque_no_haya_cambiado(self):
        self.open_project_a()
        self.beat.publish(now=100)
        self.age_file()
        self.assertTrue(self.beat.publish(now=160))
        self.assertTrue(self.rewritten())

    def test_escribe_enseguida_si_cambio_el_estado(self):
        a = self.open_project_a("101")
        self.beat.publish(now=100)
        self.age_file()
        self.s.active = FakeSequence("102", a)
        self.assertTrue(self.beat.publish(now=101))
        self.assertTrue(self.rewritten())
        self.assertEqual(self.read()["sequence"], "102")

    def test_sin_la_carpeta_no_escribe_ni_la_crea(self):
        sin_carpeta = tempfile.mkdtemp(prefix="heartbeat_test_")
        self.addCleanup(shutil.rmtree, sin_carpeta, ignore_errors=True)
        self.s.module._user_config_root = lambda: sin_carpeta
        self.open_project_a()
        self.assertFalse(self.beat.publish(now=0))
        self.assertEqual(os.listdir(sin_carpeta), [])
        # Ni siquiera lo intenta: lo deja dicho en el log y no hay ningun error.
        log = Path(self.root, "debug.log").read_text(encoding="utf-8")
        self.assertIn("no existe, no se escribe nada", log)
        self.assertNotIn("Error", log)
        # Si la carpeta aparece despues (la crea quien lee), escribe en el chequeo siguiente.
        os.makedirs(os.path.join(sin_carpeta, "LGA", "Heartbeat"))
        self.assertTrue(self.beat.publish(now=1))
        self.assertEqual(
            os.listdir(os.path.join(sin_carpeta, "LGA", "Heartbeat")), ["nukestudio-%d.json" % os.getpid()]
        )

    def test_si_hiero_falla_no_escribe_un_dato_falso_ni_levanta(self):
        a = self.open_project_a("101")
        self.beat.publish(now=0)
        self.age_file()

        def en_transicion():
            raise RuntimeError("timeline en transicion")

        self.s.ui.activeSequence = en_transicion
        self.assertFalse(self.beat.publish(now=1000))
        self.assertFalse(self.rewritten())
        self.s.ui.activeSequence = lambda: FakeSequence("102", a)
        self.assertTrue(self.beat.publish(now=1001))
        self.assertEqual(self.read()["sequence"], "102")

    # -- escritura atomica ------------------------------------------------------

    def test_escribe_un_temporal_y_lo_reemplaza_sobre_el_archivo_final(self):
        self.open_project_a()
        real_open, real_replace = open, os.replace
        abiertos, reemplazos = [], []

        def espia_open(path, mode="r", *args, **kwargs):
            if any(c in mode for c in "wax+"):
                abiertos.append(os.path.abspath(path))
            return real_open(path, mode, *args, **kwargs)

        def espia_replace(src, dst):
            reemplazos.append((os.path.abspath(src), os.path.abspath(dst)))
            return real_replace(src, dst)

        with mock.patch("builtins.open", espia_open), mock.patch("os.replace", espia_replace):
            self.beat.publish(now=0)
        final = os.path.abspath(self.path)
        self.assertNotIn(final, abiertos)  # al final nunca se le abre para escribir
        self.assertEqual(len(reemplazos), 1)
        origen, destino = reemplazos[0]
        self.assertEqual(destino, final)
        self.assertNotEqual(origen, final)
        self.assertEqual(os.path.dirname(origen), os.path.dirname(final))  # mismo volumen
        self.assertEqual(os.listdir(self.folder), [os.path.basename(final)])

    def test_si_el_reemplazo_falla_no_deja_basura_y_el_chequeo_siguiente_reintenta(self):
        a = self.open_project_a("101")
        self.beat.publish(now=0)
        antes = self.read()
        self.s.active = FakeSequence("102", a)
        # En Windows os.replace falla si el lector tiene el archivo abierto.
        with mock.patch("os.replace", side_effect=PermissionError("lo tiene abierto el lector")):
            self.assertFalse(self.beat.publish(now=1))
        self.assertEqual(os.listdir(self.folder), [os.path.basename(self.path)])  # sin temporal
        self.assertEqual(self.read(), antes)  # el archivo viejo sigue entero
        self.assertTrue(self.beat.publish(now=2))  # el estado no se dio por escrito
        self.assertEqual(self.read()["sequence"], "102")

    # -- eventos y timers -------------------------------------------------------

    def test_arranca_con_un_timer_de_5_s_y_escribe_el_primer_latido(self):
        a = self.open_project_a("101")
        self.s.module.start_heartbeat()
        tick = [t for t in self.s.timers if not t.single][0]
        self.assertTrue(tick.active)
        self.assertEqual(tick.interval, 5000)
        self.assertEqual(self.read()["sequence"], "101")
        self.age_file()
        tick.fire()  # nada cambio y pasaron segundos: no escribe
        self.assertFalse(self.rewritten())
        self.s.active = FakeSequence("102", a)
        tick.fire()  # el timer es la garantia: ve el cambio aunque ningun evento haya avisado
        self.assertEqual(self.read()["sequence"], "102")

    def test_los_eventos_solo_adelantan_el_chequeo_y_no_cargan_el_dato(self):
        a = self.open_project_a("101")
        self.s.module.start_heartbeat()
        handlers = dict(self.s.registered)
        self.assertEqual(set(handlers), set(EVENT_NAMES))
        self.age_file()
        self.s.active = FakeSequence("102", a)
        for name in ACCELERATORS:
            # Un evento con datos que contradicen a Hiero: el archivo tiene que seguir a Hiero.
            handlers[name](types.SimpleNamespace(sender=FakeProject("OTRO", PATH_B)))
        self.assertFalse(self.rewritten())  # el evento solo no escribe
        settle = [t for t in self.s.timers if t.single][0]
        self.assertTrue(settle.active)
        self.assertEqual(settle.starts, [400] * len(ACCELERATORS))  # cada evento reprograma a 400 ms
        settle.fire()
        data = self.read()
        self.assertEqual((data["sequence"], data["project"]["key"]), ("102", "PROJA"))

    def test_sin_ventana_no_arranca_nada_y_con_ventana_si(self):
        self.s.window = None
        self.s.module._start_deferred()
        reintentos = 0
        while self.s.single_shots:
            ms, callback = self.s.single_shots.pop(0)
            self.assertEqual(ms, 500)
            callback()
            reintentos += 1
        self.assertEqual(reintentos, 20)  # 20 reintentos de 500 ms y despues se rinde
        self.assertEqual((self.s.timers, self.s.registered, os.listdir(self.folder)), ([], [], []))
        self.assertFalse(hasattr(self.s.core, "_lga_heartbeat"))
        self.s.window = object()
        self.s.module._start_deferred()
        self.assertTrue(hasattr(self.s.core, "_lga_heartbeat"))
        self.assertEqual(len(self.s.registered), len(EVENT_NAMES))
        self.assertEqual(os.listdir(self.folder), [os.path.basename(self.path)])

    def test_recargar_el_modulo_reemplaza_al_latido_anterior(self):
        self.s.module.start_heartbeat()
        primero = self.s.core._lga_heartbeat
        self.s.module.start_heartbeat()
        segundo = self.s.core._lga_heartbeat
        self.assertIsNot(primero, segundo)
        self.assertFalse(primero._tick.active or primero._settle.active)
        self.assertEqual(len(self.s.registered), len(EVENT_NAMES))
        self.assertTrue(all(callback.__self__ is segundo for _, callback in self.s.registered))

    # -- kShutdown ----------------------------------------------------------------

    def test_kshutdown_borra_solo_el_archivo_propio(self):
        ajenos = [
            os.path.join(self.folder, "nukestudio-1.json"),                # otro proceso
            os.path.join(self.folder, "hiero-%d.json" % os.getpid()),       # mismo pid, otra app
            os.path.join(self.folder, "notas.txt"),
        ]
        for ajeno in ajenos:
            with open(ajeno, "w", encoding="utf-8") as handle:
                handle.write("{}")
        self.open_project_a()
        self.s.module.start_heartbeat()
        beat = self.s.core._lga_heartbeat
        self.assertTrue(os.path.exists(self.path))
        handlers = dict(self.s.registered)
        handlers["kShutdown"](types.SimpleNamespace())
        self.assertFalse(os.path.exists(self.path))
        self.assertTrue(all(os.path.exists(ajeno) for ajeno in ajenos))
        # Sacar un handler en pleno despacho haria que Hiero se saltee al siguiente.
        self.assertEqual(self.s.unregistered, [])
        # Ya bajo: ni el chequeo ni un evento tardio reviven timers ni vuelven a escribir.
        self.assertFalse(beat.publish(now=1e9))
        handlers["kAfterProjectLoad"](types.SimpleNamespace())
        self.assertFalse(any(t.active for t in self.s.timers))
        self.assertFalse(os.path.exists(self.path))

    def test_kshutdown_sin_carpeta_ni_archivo_no_falla(self):
        sin_carpeta = tempfile.mkdtemp(prefix="heartbeat_test_")
        self.addCleanup(shutil.rmtree, sin_carpeta, ignore_errors=True)
        self.s.module._user_config_root = lambda: sin_carpeta
        self.s.module.start_heartbeat()
        dict(self.s.registered)["kShutdown"](types.SimpleNamespace())
        self.assertEqual(os.listdir(sin_carpeta), [])

    # -- lo que no se negocia -----------------------------------------------------

    def test_el_modulo_nunca_llama_a_os_kill(self):
        arbol = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        llamadas = [
            n for n in ast.walk(arbol)
            if (isinstance(n, ast.Attribute) and n.attr == "kill")
            or (isinstance(n, ast.ImportFrom) and n.module == "os" and any(a.name == "kill" for a in n.names))
        ]
        self.assertEqual(llamadas, [])


if __name__ == "__main__":
    unittest.main()
