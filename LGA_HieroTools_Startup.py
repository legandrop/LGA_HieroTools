"""
____________________________________________________________________

  LGA_HieroTools_Startup v1.02 | Lega

  Arranque del pack: suma las fuentes del pack al font path de Nuke y
  carga los modulos de MODULES.

  v1.02: _refresh_font_cache(): borra el cache de fuentes de Nuke si le
         falta alguna fuente del pack (Nuke no re-escanea una carpeta que
         ya conoce; la fuente LGA Shapes nueva no aparecia).
  v1.01: NUKE_FONT_PATH con os.pathsep y ruta completa. En Windows Nuke
         parte por ";" y con ":" no registraba ninguna fuente del pack.
  v1.00: Version inicial del header.
____________________________________________________________________
"""

import importlib
import os
import sys
import traceback


STARTUP_DIR = os.path.dirname(__file__)
TOOLS_DIR = os.path.join(STARTUP_DIR, "LGA_HieroTools")

if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

# La fuente Inter del pack (LGA_NKS_Shared/fonts/) tiene que estar en el
# font-path de Nuke para que el burn-in la renderice SIN instalar nada en la
# maquina del usuario. NUKE_FONT_PATH se lee al ESCANEAR las fuentes (una vez,
# al arrancar), no en runtime; por eso va aca, lo mas temprano posible. Se
# antepone para que el Inter del repo gane sobre un Inter de sistema si existe
# (asi la medicion y el render usan el MISMO Inter en toda maquina).
#
# MEDIDO (NKS 17.0v4, 2026-11-23): en Windows Nuke parte NUKE_FONT_PATH por
# ";" (os.pathsep) y acepta la ruta CON letra de unidad. Con "x;C:/.../fonts"
# getFonts registro la fuente; con el armado viejo (ruta sin unidad unida por
# ":") no registraba NINGUNA fuente del pack y Text2 caia a la del sistema.
_FONTS_DIR = os.path.join(TOOLS_DIR, "LGA_NKS_Shared", "fonts")
if os.path.isdir(_FONTS_DIR):
    _fonts_nuke = os.path.abspath(_FONTS_DIR).replace("\\", "/")
    _prev = os.environ.get("NUKE_FONT_PATH", "")
    if _fonts_nuke not in _prev.split(os.pathsep):
        os.environ["NUKE_FONT_PATH"] = (
            _fonts_nuke + (os.pathsep + _prev if _prev else "")
        )


def _font_cache_dirs():
    """Carpetas donde Nuke guarda su cache de fuentes (fontmapping.*.fcache)."""
    import tempfile

    dirs = []
    if os.environ.get("NUKE_TEMP_DIR"):
        dirs.append(os.environ["NUKE_TEMP_DIR"])
    dirs.append(os.path.join(tempfile.gettempdir(), "nuke"))
    if sys.platform == "darwin" and hasattr(os, "getuid"):
        dirs.append("/var/tmp/nuke-u%d" % os.getuid())
    return dirs


def _refresh_font_cache(fonts_dir):
    """Borra el cache de fuentes de Nuke si conoce la carpeta del pack pero le
    falta alguna de sus fuentes.

    MEDIDO (NKS 17.0v4, 2026-11-23): Nuke guarda la lista de fuentes en
    <temp>/nuke/fontmapping.<version>.fcache, con un hash de las carpetas, y
    no vuelve a mirar una carpeta conocida: una fuente nueva del pack (LGA
    Shapes, de los fondos del burn-in) no aparecia en getFonts hasta borrar
    el cache. Es un cache regenerable: Nuke lo rehace al escanear."""
    try:
        wanted = [
            os.path.abspath(os.path.join(fonts_dir, n)).replace("\\", "/")
            for n in os.listdir(fonts_dir)
            if n.lower().endswith((".ttf", ".otf"))
        ]
        folder = os.path.abspath(fonts_dir).replace("\\", "/")
        for cache_dir in _font_cache_dirs():
            if not os.path.isdir(cache_dir):
                continue
            for name in os.listdir(cache_dir):
                if not (name.startswith("fontmapping.") and name.endswith(".fcache")):
                    continue
                path = os.path.join(cache_dir, name)
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    text = fh.read().replace("\\", "/")
                if folder in text and any(w not in text for w in wanted):
                    os.remove(path)
    except Exception:
        pass


if os.path.isdir(_FONTS_DIR):
    _refresh_font_cache(_FONTS_DIR)

MODULES = [
    "LGA_NKS_Assignee_Panel",
    "LGA_NKS_BurnIn",
    "LGA_NKS_ClipColor_Panel",
    "LGA_NKS_Flow_S3_Panel",
    "LGA_NKS_Edit_Panel",
    "LGA_NKS_Flow_Panel",
    "LGA_NKS_Projects_Panel",
    "LGA_NKS_RemoteNav",
    "LGA_NKS_Heartbeat",
    "LGA_NKS_Review_Panel",
    "LGA_NKS_Shortcuts",
    "LGA_NKS_ViewerTL_Panel",
    "z_clear_outpoint_workaround",
    "z_version_everywhere",
]

for module_name in MODULES:
    try:
        importlib.import_module(module_name)
    except Exception:
        print("[LGA_HieroTools_Startup] Error loading {}".format(module_name))
        traceback.print_exc()
