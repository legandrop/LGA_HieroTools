"""
Orden de resolucion del contexto Studio/Client (LGA_NKS_ContextProfile).

Lo que tiene que seguir siendo cierto:
  - sin ningun archivo, el modo es studio (asi viaja el paquete studio);
  - la marca de ADENTRO del pack da el modo del paquete client;
  - el INI suelto, que escribe el switch, le gana a la marca del build;
  - el switch escribe siempre en el INI suelto, nunca sobre la marca.

Se prueba sobre una COPIA del modulo en una carpeta temporal, porque el modulo
resuelve las rutas a partir de su propia ubicacion.
"""

import importlib.util
import os
import shutil
import tempfile
import unittest
from pathlib import Path


SOURCE = (
    Path(__file__).resolve().parents[1] / "LGA_NKS_Shared" / "LGA_NKS_ContextProfile.py"
)
ENV_VAR = "LGA_HIEROTOOLS_CONTEXT_INI"
INI_NAME = "LGA_HieroTools_context.ini"


def write_ini(path, mode):
    path.write_text("[Context]\nmode = %s\n" % mode, encoding="utf-8")


class ContextProfileResolutionTest(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp())
        self.startup = self.base / "Startup"
        self.pack = self.startup / "LGA_HieroTools"
        shared = self.pack / "LGA_NKS_Shared"
        shared.mkdir(parents=True)
        shutil.copy(str(SOURCE), str(shared))

        spec = importlib.util.spec_from_file_location(
            "ctx_profile_under_test", str(shared / SOURCE.name)
        )
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

        self.loose_ini = self.startup / INI_NAME
        self.build_marker = self.pack / INI_NAME
        self._env_before = os.environ.pop(ENV_VAR, None)

    def tearDown(self):
        os.environ.pop(ENV_VAR, None)
        if self._env_before is not None:
            os.environ[ENV_VAR] = self._env_before
        shutil.rmtree(str(self.base), ignore_errors=True)

    def test_sin_ningun_archivo_es_studio(self):
        self.assertIsNone(self.module.find_context_ini())
        self.assertEqual(self.module.get_context_mode(), "studio")

    def test_la_marca_del_pack_define_el_paquete_client(self):
        write_ini(self.build_marker, "client")
        self.assertEqual(self.module.get_context_mode(), "client")

    def test_el_ini_suelto_le_gana_a_la_marca_del_build(self):
        write_ini(self.build_marker, "client")
        write_ini(self.loose_ini, "studio")
        self.assertEqual(self.module.get_context_mode(), "studio")

    def test_el_ini_suelto_solo_tambien_cambia_el_modo(self):
        write_ini(self.loose_ini, "client")
        self.assertEqual(self.module.get_context_mode(), "client")

    def test_la_variable_de_entorno_gana_a_todo(self):
        write_ini(self.build_marker, "client")
        write_ini(self.loose_ini, "client")
        otro = self.base / "otro.ini"
        write_ini(otro, "studio")
        os.environ[ENV_VAR] = str(otro)
        self.assertEqual(self.module.get_context_mode(), "studio")

    def test_el_switch_escribe_en_el_suelto_aunque_solo_exista_la_marca(self):
        # En un paquete client el unico INI que existe es la marca del build.
        write_ini(self.build_marker, "client")
        destino = Path(self.module.get_override_ini_path())
        self.assertEqual(destino.resolve(), self.loose_ini.resolve())
        self.assertNotEqual(destino.resolve(), self.build_marker.resolve())

    def test_un_modo_desconocido_cae_en_studio(self):
        write_ini(self.build_marker, "cualquiera")
        self.assertEqual(self.module.get_context_mode(), "studio")


if __name__ == "__main__":
    unittest.main()
