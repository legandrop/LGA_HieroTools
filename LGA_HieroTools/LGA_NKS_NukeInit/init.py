"""
____________________________________________________________________

  LGA_NKS_NukeInit v1.00 | Lega

  Saca los "Can't restore panel ' com.lega.XPanel ' because it hasn't been
  registered." que NukeStudio imprime en consola al arrancar.

  Por que pasa: al abrir, NukeStudio rearma el workspace guardado y, por
  cada panel, busca su id con nukescripts.restorePanel(). Los paneles de
  HieroTools se crean en Python/Startup, que carga DESPUES de ese rearmado
  (medido: la ventana ya esta visible cuando carga Python/Startup), asi que
  sus ids todavia no estan y sale el mensaje. Despues los paneles se ubican
  igual, con windowManager().addWindow().

  Que hace: registra cada id con un comando que devuelve None, que es
  EXACTAMENTE lo que devuelve restorePanel() despues de imprimir el error.
  El rearmado queda igual y solo desaparece el mensaje. Los ids se leen de
  los setObjectName("com.lega.") de los paneles, asi que un panel nuevo
  entra solo.

  Como se instala: una linea en el init.py de la carpeta .nuke, igual que
  los ToolPacks (ver README.md, seccion Installation):
      nuke.pluginAddPath("./Python/Startup/LGA_HieroTools/LGA_NKS_NukeInit")

  v1.00: Primera version.
____________________________________________________________________
"""

import os
import re

PANEL_ID_PATTERN = re.compile(r"""setObjectName\(\s*["'](com\.lega\.[A-Za-z0-9_.]+)["']\s*\)""")


def _this_dir():
    # Nuke ejecuta este init.py desde C++ y __file__ no siempre existe: se
    # busca la carpeta en el plugin path, que pluginAddPath ya dejo cargado.
    here = globals().get("__file__")
    if here:
        return os.path.dirname(os.path.abspath(here))
    try:
        import nuke

        for path in nuke.pluginPath():
            if os.path.basename(os.path.normpath(path)).casefold() == "lga_nks_nukeinit":
                return path
    except Exception:
        pass
    return None


def hierotools_panel_ids(tools_dir):
    """Ids de los paneles de HieroTools, leidos de los .py de la raiz del pack."""
    ids = []
    try:
        names = sorted(os.listdir(tools_dir))
    except OSError:
        return ids
    for name in names:
        if not name.endswith(".py"):
            continue
        try:
            with open(os.path.join(tools_dir, name), encoding="utf-8", errors="ignore") as handle:
                for panel_id in PANEL_ID_PATTERN.findall(handle.read()):
                    if panel_id not in ids:
                        ids.append(panel_id)
        except OSError:
            continue
    return ids


def _placeholder():
    # Mismo resultado que restorePanel() con el id sin registrar, sin el print.
    return None


def register_panel_placeholders():
    try:
        import nukescripts
    except Exception:
        return []
    here = _this_dir()
    if not here:
        return []
    tools_dir = os.path.dirname(here)
    registered = []
    for panel_id in hierotools_panel_ids(tools_dir):
        try:
            nukescripts.registerPanel(panel_id, _placeholder)
            registered.append(panel_id)
        except Exception:
            pass
    return registered


register_panel_placeholders()
