# -*- coding: utf-8 -*-
"""
____________________________________________________________________

  LGA_NKS_ProjectRowActions v1.00 | Lega

  Logica de los dos iconos de la fila de proyecto del Projects Panel:
  Save incremental (guarda el .hrox abierto como version +1) y Upload to
  Wasabi (sube ese .hrox con FileManager S3).

  No importa hiero ni Qt: es logica de rutas, de comando y de marcadores,
  testeable sin host. La parte que toca el proyecto vive en el panel.

  v1.00: Version inicial. Plan de version incremental que detecta versiones
         ya existentes en disco, comando --upload-file con
         --notify-completion, y lectura de los marcadores de fin.
____________________________________________________________________
"""

import json
import os
import re
import time
from pathlib import Path

# Ultimo token de version del nombre: "_v012" en PROJA_SUP_v012.hrox o en
# PROJA_SUP_v012_test.hrox. Se toma el ultimo porque el nombre del proyecto
# podria contener otra "v" seguida de digitos.
_VERSION_RE = re.compile(r"(?i)(_v)(\d+)")

HROX_EXTENSION = ".hrox"

# Carpeta de marcadores propia. NO es la del Download Clip: su watcher borra
# todo marcador que no reconoce, y se comeria los de las subidas.
_NOTIFY_SUBDIR = ("logs", "upload_project_done")

# Un marcador que no corresponde a ninguna subida pendiente se borra pasado
# este tiempo (una subida de una sesion anterior de NKS, por ejemplo).
ORPHAN_MARKER_TTL_SECONDS = 600

# Si FileManager S3 no escribe el marcador (se cerro, crasheo o es una version
# vieja sin --upload-file), la fila deja de mostrar la subida pasado este tiempo.
UPLOAD_TIMEOUT_SECONDS = 2 * 60 * 60


def split_version(path):
    """
    Separa el nombre del .hrox en prefijo, numero de version y sufijo.

    Devuelve (carpeta, prefijo, numero_str, sufijo) o None si el nombre no
    tiene token _v###. El sufijo incluye la extension.
    """
    folder, name = os.path.split(path)
    matches = list(_VERSION_RE.finditer(name))
    if not matches:
        return None
    last = matches[-1]
    prefix = name[: last.start(2)]
    number = last.group(2)
    suffix = name[last.end(2):]
    return folder, prefix, number, suffix


def _format_version(number, width):
    return str(number).zfill(width)


def existing_versions(folder, prefix, suffix, listdir=os.listdir):
    """Numeros de version en disco con el mismo prefijo y sufijo (sin autosaves)."""
    pattern = re.compile(
        r"^" + re.escape(prefix) + r"(\d+)" + re.escape(suffix) + r"$", re.IGNORECASE
    )
    versions = set()
    try:
        names = listdir(folder)
    except OSError:
        return versions
    for name in names:
        match = pattern.match(name)
        if match:
            versions.add(int(match.group(1)))
    return versions


def plan_incremental_save(path, listdir=os.listdir):
    """
    Decide a que archivo guarda Save incremental.

    Devuelve un dict:
      ok            False si el nombre no tiene version (error en "error")
      current       version actual (int)
      next_path     la version +1
      next_label    "v013"
      conflict      True si en disco ya hay una version mayor a la actual:
                    guardar como +1 pisaria un archivo o quedaria por debajo
                    de la mas nueva. El panel pregunta antes de seguir.
      highest       la version mas alta en disco
      free_path     la mas alta del disco +1: lo que se ofrece si hay conflicto
      free_label    "v015"
    """
    if not path:
        return {"ok": False, "error": "The project has no file on disk yet."}
    parts = split_version(path)
    if parts is None:
        return {
            "ok": False,
            "error": "The file name has no version number (_v###): "
            + os.path.basename(path),
        }
    folder, prefix, number, suffix = parts
    width = len(number)
    current = int(number)
    versions = existing_versions(folder, prefix, suffix, listdir=listdir)
    versions.add(current)
    highest = max(versions)

    def build(version):
        name = prefix + _format_version(version, width) + suffix
        return os.path.join(folder, name), "v" + _format_version(version, width)

    next_path, next_label = build(current + 1)
    free_path, free_label = build(highest + 1)
    return {
        "ok": True,
        "current": current,
        "current_label": "v" + number,
        "next_path": next_path,
        "next_label": next_label,
        "conflict": highest > current,
        "highest": highest,
        "highest_label": "v" + _format_version(highest, width),
        "free_path": free_path,
        "free_label": free_label,
    }


def normalize_path(path):
    """Ruta comparable: absoluta, barras del sistema y mayusculas en Windows."""
    if not path:
        return ""
    return os.path.normcase(os.path.normpath(os.path.abspath(str(path))))


def get_notify_dir():
    """Carpeta donde FileManager S3 deja el marcador de fin de cada subida."""
    pack_dir = Path(__file__).resolve().parent.parent
    return str(pack_dir.joinpath(*_NOTIFY_SUBDIR))


def build_upload_args(hrox_path, notify_dir):
    """Argumentos CLI de FileManager S3 para subir un solo archivo y avisar al terminar."""
    return ["--upload-file", hrox_path, "--notify-completion", notify_dir]


def read_markers(notify_dir):
    """
    Marcadores .json de la carpeta. Devuelve [(ruta_marcador, datos o None)].

    datos es None si el archivo no se pudo leer o no es JSON: el llamador lo
    borra igual. Los .tmp no se leen: FileManager S3 escribe .tmp y renombra.
    """
    markers = []
    try:
        names = os.listdir(notify_dir)
    except OSError:
        return markers
    for name in sorted(names):
        if not name.lower().endswith(".json"):
            continue
        marker_path = os.path.join(notify_dir, name)
        try:
            with open(marker_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            data = None
        markers.append((marker_path, data))
    return markers


def marker_paths(data):
    """Rutas normalizadas de los items de un marcador."""
    paths = []
    if not isinstance(data, dict):
        return paths
    for item in data.get("items") or []:
        if isinstance(item, dict) and item.get("path"):
            paths.append(normalize_path(item["path"]))
    return paths


def marker_result(data):
    """(exito, mensaje) de un marcador. El mensaje ya viene apto para UI."""
    if not isinstance(data, dict):
        return False, "FileManager S3 wrote an unreadable result."
    if data.get("success"):
        return True, ""
    message = data.get("error_message") or data.get("error_code") or "Upload failed."
    return False, str(message)


def is_cancel_marker(data):
    """True si el usuario no piso el archivo existente (Skip existing o Escape en FileManager S3)."""
    return isinstance(data, dict) and str(data.get("error_code", "")).lower() == "cancelled"


def marker_age_seconds(marker_path, now=None):
    try:
        return (now or time.time()) - os.path.getmtime(marker_path)
    except OSError:
        return 0.0


def safe_remove(path):
    try:
        os.remove(path)
        return True
    except OSError:
        return False
