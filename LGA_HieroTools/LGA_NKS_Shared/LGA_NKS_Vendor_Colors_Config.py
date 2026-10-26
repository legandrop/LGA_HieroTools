"""
____________________________________________________________________

  LGA_NKS_Vendor_Colors_Config v1.01 | Lega

  Color de cada vendor para HieroTools.

  La fuente de verdad es FLOW, via PipeSync, igual que los vendor codes
  (LGA_NKS_Vendors_Config): cada proyecto tiene sus grupos de vendor
  con token (`WAN`), nombre (`Vendor A`) y color. PipeSync los baja en
  su sync a `pipesync_stats.db`, en dos lugares que este modulo lee:

  - tabla `project_vendor_groups` (project_id, vendor_token,
    group_name, color): trae el NOMBRE, que es lo que suele venir
    escrito en una planilla.
  - `vendor_colors` del envelope de `project_settings_cache`
    ({token: color}): solo el token, de respaldo.

  La DB depende del contexto activo (studio o client), porque cada uno
  tiene su sitio de Flow y sus vendors: la resuelve LGA_NKS_PipeSyncPaths.

  NO HAY FALLBACK de colores inventados: si el vendor no esta en la DB
  se devuelve None y el caller muestra el texto sin color.

  Usado por runtime activo:
  - LGA_NKS_Review_Panel_py/LGA_NKS_ShotMarks_Nav.py

  v1.01: find_vendor_colors: una celda con varios vendors ("Vendor A,
         Vendor B") se separa y cada uno lleva su color. Antes se buscaba
         la celda entera como un solo vendor y salia sin color.
  v1.00: Version inicial.
____________________________________________________________________

"""

import json
import os
import re
import sqlite3
import time

try:
    from LGA_NKS_PipeSyncPaths import get_pipesync_db_path
except ImportError:  # importado como paquete desde afuera de LGA_NKS_Shared
    from LGA_NKS_Shared.LGA_NKS_PipeSyncPaths import get_pipesync_db_path

STATS_DB_FILENAME = "pipesync_stats.db"
HEX_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")
# Separadores de una celda con varios vendors: coma, barra, mas, ampersand,
# punto y coma, y "y" / "and" como palabra sola. El guion no separa: es parte
# de nombres como "Vendor-B".
VENDOR_SEPARATOR_PATTERN = re.compile(r"\s*(?:[,/+&;]|\by\b|\band\b)\s*", re.IGNORECASE)

# Cache de proceso con la misma invalidacion que LGA_NKS_Vendors_Config:
# mtime+size de la DB y de su -wal (la DB esta en modo WAL y los commits de
# PipeSync no tocan el .db principal hasta el checkpoint), mirado como mucho
# cada _STAMP_TTL_SEGUNDOS.
_cache = None
_cache_stamp = None
_cache_checked_at = None
_STAMP_TTL_SEGUNDOS = 2.0


def normalize_vendor(text):
    """Clave de comparacion: mayusculas y solo letras y numeros.

    Asi "Vendor-B", "VENDOR B" y "vendorb" son el mismo vendor.
    """
    return re.sub(r"[^A-Z0-9]", "", str(text or "").upper())


def _valid_color(value):
    color = str(value or "").strip()
    return color.upper() if HEX_COLOR_PATTERN.match(color) else None


def build_vendor_colors(group_rows, envelope_rows):
    """Arma {PROYECTO: {CLAVE_NORMALIZADA: '#RRGGBB'}}. Sin DB: se prueba solo.

    group_rows: (project_name, vendor_token, group_name, color).
    envelope_rows: (project_name, settings_json).
    Cada vendor queda bajo su token y bajo su nombre. El grupo le gana al
    envelope: es la tabla que trae el nombre y la que PipeSync usa al pintar.
    """
    colors = {}
    for project_name, settings_json in envelope_rows:
        try:
            envelope = json.loads(settings_json or "")
        except (ValueError, TypeError):
            continue
        raw = envelope.get("vendor_colors") if isinstance(envelope, dict) else None
        if not isinstance(raw, dict):
            continue
        target = colors.setdefault((project_name or "").strip().upper(), {})
        for token, value in raw.items():
            color = _valid_color(value)
            key = normalize_vendor(token)
            if color and key:
                target[key] = color
    for project_name, token, group_name, value in group_rows:
        color = _valid_color(value)
        if not color:
            continue
        target = colors.setdefault((project_name or "").strip().upper(), {})
        for key in (normalize_vendor(token), normalize_vendor(group_name)):
            if key:
                target[key] = color
    return colors


def _db_stamp(db_path):
    try:
        info = os.stat(db_path)
    except OSError:
        return None
    stamp = [info.st_mtime, info.st_size]
    try:
        wal = os.stat(db_path + "-wal")
        stamp += [wal.st_mtime, wal.st_size]
    except OSError:
        stamp += [None, None]
    return tuple(stamp)


def _read_db(db_path):
    """(colores, leyo_ok). Un error de lectura no se cachea."""
    if not os.path.exists(db_path):
        return {}, True
    connection = None
    try:
        # Read-only: HieroTools nunca escribe en la DB de PipeSync.
        connection = sqlite3.connect("file:{0}?mode=ro".format(db_path), uri=True)
        envelopes = connection.execute(
            "SELECT p.project_name, c.settings_json FROM projects p "
            "JOIN project_settings_cache c ON c.project_id = p.id"
        ).fetchall()
        try:
            groups = connection.execute(
                "SELECT p.project_name, g.vendor_token, g.group_name, g.color "
                "FROM project_vendor_groups g JOIN projects p ON p.id = g.project_id"
            ).fetchall()
        except sqlite3.OperationalError:
            # PipeSync viejo, sin la tabla de grupos: queda el envelope.
            groups = []
    except sqlite3.Error:
        return {}, False
    finally:
        if connection is not None:
            connection.close()
    return build_vendor_colors(groups, envelopes), True


def load_vendor_colors():
    """{PROYECTO: {CLAVE: '#RRGGBB'}} del contexto activo, cacheado."""
    global _cache, _cache_stamp, _cache_checked_at
    now = time.monotonic()
    if (_cache is not None and _cache_checked_at is not None
            and now - _cache_checked_at < _STAMP_TTL_SEGUNDOS):
        return _cache
    _cache_checked_at = now
    db_path = get_pipesync_db_path(STATS_DB_FILENAME)
    stamp = _db_stamp(db_path)
    if _cache is not None and stamp == _cache_stamp:
        return _cache
    colors, ok = _read_db(db_path)
    if not ok:
        _cache_checked_at = None
        return _cache if _cache is not None else {}
    _cache, _cache_stamp = colors, stamp
    return _cache


def pick_vendor_color(colors, vendor, project_names=()):
    """Color de `vendor` en el mapa de build_vendor_colors, o None.

    Busca primero en los proyectos de `project_names` (el nombre del .hrox
    y su prefijo); si ninguno esta en la DB, en todos. Un nombre de vendor
    que coincide en dos proyectos con colores distintos, fuera de esos
    proyectos, no se colorea: no hay forma de saber cual es.
    """
    key = normalize_vendor(vendor)
    if not key or not colors:
        return None
    for name in project_names:
        project = colors.get((name or "").strip().upper())
        if project is not None:
            return project.get(key)
    found = {project[key] for project in colors.values() if key in project}
    return found.pop() if len(found) == 1 else None


def project_names_for(hiero_project_name):
    """Candidatos de nombre de proyecto en la DB para un .hrox ('PROJA_SUP_v001'
    -> 'PROJA_SUP_v001', 'PROJA')."""
    name = (hiero_project_name or "").strip()
    if not name:
        return ()
    prefix = name.split("_", 1)[0]
    return (name, prefix) if prefix != name else (name,)


def find_vendor_color(vendor, hiero_project_name=None):
    """Color '#RRGGBB' del vendor en el contexto activo, o None."""
    return pick_vendor_color(load_vendor_colors(), vendor,
                             project_names_for(hiero_project_name))


def split_vendors(text):
    """Los vendors de una celda, en orden ("Vendor A, Vendor B" -> 2)."""
    return [part.strip() for part in VENDOR_SEPARATOR_PATTERN.split(str(text or ""))
            if part.strip()]


def pick_vendor_colors(colors, text, project_names=()):
    """[(vendor, '#RRGGBB' o None)] de una celda que puede traer varios.

    Si la celda entera es un vendor conocido se respeta tal cual: un nombre
    con barra o "y" adentro no se parte.
    """
    whole = pick_vendor_color(colors, text, project_names)
    if whole:
        return [(str(text).strip(), whole)]
    return [(part, pick_vendor_color(colors, part, project_names))
            for part in split_vendors(text)]


def find_vendor_colors(text, hiero_project_name=None):
    """[(vendor, '#RRGGBB' o None)] de la celda en el contexto activo."""
    return pick_vendor_colors(load_vendor_colors(), text,
                              project_names_for(hiero_project_name))
