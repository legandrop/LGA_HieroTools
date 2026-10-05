"""
Cuida las dos promesas de LGA_NKS_NukeInit:

1. "Un panel nuevo entra solo": el modulo lee los ids de los .py de la RAIZ del
   pack. Si alguien declara un panel `com.lega.*` en una subcarpeta, el modulo
   no lo ve y su aviso "Can't restore panel" vuelve sin que nada falle.
2. Funciona como lo carga Nuke: ejecutado desde C++, sin `__file__`, tiene que
   encontrar su carpeta por el plugin path y registrar todos los ids.
"""

import os
import re
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_DIR = ROOT / "LGA_NKS_NukeInit"
INIT_PATH = MODULE_DIR / "init.py"
PANEL_ID = re.compile(r"""setObjectName\(\s*["'](com\.lega\.[A-Za-z0-9_.]+)["']\s*\)""")


def run_init(with_file):
    """Ejecuta el init.py con nuke/nukescripts de mentira; devuelve (globals, registro)."""
    registro = {}

    nuke = types.ModuleType("nuke")
    # Como lo deja nuke.pluginAddPath: con barras hacia adelante.
    nuke.pluginPath = lambda: ["C:/otro/plugin", MODULE_DIR.as_posix()]
    nukescripts = types.ModuleType("nukescripts")
    nukescripts.registerPanel = lambda panel_id, command: registro.__setitem__(panel_id, command)

    previos = {name: sys.modules.get(name) for name in ("nuke", "nukescripts")}
    sys.modules["nuke"] = nuke
    sys.modules["nukescripts"] = nukescripts
    try:
        entorno = {"__name__": "lga_nks_nukeinit_test"}
        if with_file:
            entorno["__file__"] = str(INIT_PATH)
        codigo = compile(INIT_PATH.read_text(encoding="utf-8"), str(INIT_PATH), "exec")
        exec(codigo, entorno)
    finally:
        for name, module in previos.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
    return entorno, registro


def panel_ids_en_todo_el_pack():
    """Ids `com.lega.*` declarados en cualquier .py propio del pack, con su archivo."""
    encontrados = {}
    for carpeta, subcarpetas, archivos in os.walk(ROOT):
        # Afuera: material que no es runtime y binarios de terceros vendorizados.
        subcarpetas[:] = [
            d
            for d in subcarpetas
            if not d.startswith("+")
            and d not in ("__pycache__", "tests", "exploracion", "LGA_NKS_NukeInit")
            and not d.endswith(("_Win", "_Mac"))
        ]
        for nombre in archivos:
            if not (nombre.startswith("LGA_") and nombre.endswith(".py")):
                continue
            ruta = Path(carpeta) / nombre
            texto = ruta.read_text(encoding="utf-8", errors="ignore")
            for panel_id in PANEL_ID.findall(texto):
                encontrados.setdefault(panel_id, ruta.relative_to(ROOT).as_posix())
    return encontrados


class NukeInitPanelIdsTest(unittest.TestCase):
    def test_el_modulo_ve_todos_los_paneles_del_pack(self):
        entorno, _registro = run_init(with_file=True)
        vistos = set(entorno["hierotools_panel_ids"](str(ROOT)))
        declarados = panel_ids_en_todo_el_pack()

        self.assertTrue(declarados, "No se encontro ningun panel com.lega.* en el pack")
        faltan = {pid: donde for pid, donde in declarados.items() if pid not in vistos}
        self.assertEqual(
            faltan,
            {},
            "Paneles fuera de la raiz del pack: LGA_NKS_NukeInit solo lee los .py "
            "de la raiz, asi que su aviso de arranque no se saca.",
        )

    def test_registra_todos_los_ids_sin_file(self):
        # Nuke ejecuta los init.py desde C++ y __file__ no siempre existe.
        _entorno, registro = run_init(with_file=False)
        self.assertEqual(set(registro), set(panel_ids_en_todo_el_pack()))

    def test_el_comando_registrado_devuelve_none(self):
        # Es lo que devuelve nukescripts.restorePanel() despues de imprimir el
        # aviso: el rearmado del workspace tiene que recibir lo mismo que antes.
        _entorno, registro = run_init(with_file=True)
        self.assertTrue(registro)
        for panel_id, command in registro.items():
            self.assertIsNone(command(), panel_id)


if __name__ == "__main__":
    unittest.main()
