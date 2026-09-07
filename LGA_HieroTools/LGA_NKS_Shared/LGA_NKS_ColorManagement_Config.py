"""
____________________________________________________________________

  LGA_NKS_ColorManagement_Config v1.00 | Lega

  Config de color management por proyecto para HieroTools.

  La fuente de verdad es FLOW: la configuracion de color management se edita
  en el Project Settings tab de PipeSync y viaja en el envelope de Project
  Settings. PipeSync la baja en su sync y la deja en
  project_settings_cache.settings_json de pipesync_stats.db, bajo la clave
  `color_management`. Este modulo solo lee esa tabla; misma mecanica que
  LGA_NKS_Vendors_Config (misma DB, misma query, mismo read-only, mismo
  cache con TTL y stamp).

  Forma exacta de la clave en el envelope:

      "color_management": {
          "enabled": true,
          "workspace": "acescg",
          "plates": "acescg",
          "exr_publish": "aces2065-1"
      }

  La clave puede estar AUSENTE: eso significa proyecto no configurado (el
  caller usa el camino sin color management). `workspace` / `plates` /
  `exr_publish` son TOKENS NEUTROS, no nombres de OCIO: hoy PipeSync escribe
  "acescg" y "aces2065-1", pero un token desconocido NO se descarta ni se
  normaliza aca, se devuelve tal cual (mas adelante se agregan log, cineon,
  etc.). La resolucion contra un config OCIO real la hace resolve_ocio_name()
  mas abajo, en el momento de usar el token.

  NO HAY FALLBACK a un .ini local ni a un default hardcodeado: si la DB no
  tiene el proyecto, o el proyecto no tiene `color_management`, se devuelve
  None y el caller sigue con su comportamiento sin color management.

  Usado por runtime activo:
  - LGA_NKS_Edit_Panel_py/LGA_NKS_FixColorspaces.py

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

# Cache de proceso, misma estrategia que LGA_NKS_Vendors_Config: se invalida
# sola mirando mtime+size de la DB y de su `-wal` (ver _db_stamp), para que un
# sync de PipeSync se note sin tener que reiniciar Hiero.
_cache_color_management = None
_cache_stamp = None
_cache_checked_at = None

# Cada cuanto, como maximo, se vuelve a mirar el estado de la DB. Mismo motivo
# que en LGA_NKS_Vendors_Config: sin debounce, cada consulta paga el costo de
# resolver la ruta de la DB y stat-earla.
_STAMP_TTL_SEGUNDOS = 2.0


def get_color_management_db_path():
    """Ruta a la pipesync_stats.db del contexto activo (studio o client)."""
    return get_pipesync_db_path(STATS_DB_FILENAME)


def _db_stamp(db_path):
    """
    Huella de la DB para invalidar el cache: (mtime, size) del archivo principal
    Y del `-wal`.

    El `-wal` NO es opcional: pipesync_stats.db esta en journal_mode=wal, asi
    que los commits de PipeSync se escriben ahi y el .db principal no cambia
    ni de mtime ni de tamanio hasta el checkpoint, que puede tardar dias.
    Mirando solo el .db, un cambio de color management guardado hoy en el
    Project Settings tab no se veria hasta reiniciar Hiero.

    Devuelve None si no existe el archivo principal.
    """
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


def _extraer_color_management(settings_json):
    """
    Saca `color_management` de un envelope de Project Settings.

    Devuelve None si la clave no esta, no es un objeto, o el envelope no se
    puede parsear: en todos esos casos el proyecto se trata como "no
    configurado". Los tokens de workspace/plates/exr_publish se devuelven TAL
    CUAL vengan (string, o None si el campo no esta) - no se validan contra
    una lista de tokens conocidos.
    """
    if not settings_json:
        return None

    try:
        envelope = json.loads(settings_json)
    except (ValueError, TypeError):
        return None

    if not isinstance(envelope, dict):
        return None

    raw = envelope.get("color_management")
    if not isinstance(raw, dict):
        return None

    def _token(campo):
        valor = raw.get(campo)
        if valor is None:
            return None
        texto = str(valor).strip()
        return texto or None

    return {
        "enabled": bool(raw.get("enabled", False)),
        "workspace": _token("workspace"),
        "plates": _token("plates"),
        "exr_publish": _token("exr_publish"),
    }


def _load_color_management_uncached():
    """
    Lee la DB y devuelve (color_management_por_proyecto, leyo_ok).

    `leyo_ok` distingue "lei la DB y no hay datos" de "no pude leer la DB". La
    diferencia importa porque el resultado se cachea: un error transitorio
    (p. ej. `database is locked` con PipeSync escribiendo) no puede quedar
    congelado como "este proyecto no tiene color management" hasta el proximo
    cambio de la DB.
    """
    db_path = get_color_management_db_path()
    if not os.path.exists(db_path):
        # No es un error: PipeSync todavia no sincronizo en esta maquina. Se
        # cachea, porque el stamp cambia solo con que aparezca el archivo.
        return {}, True

    query = (
        "SELECT p.project_name, c.settings_json "
        "FROM projects p "
        "JOIN project_settings_cache c ON c.project_id = p.id"
    )

    connection = None
    try:
        # Read-only: HieroTools nunca escribe en la DB de PipeSync.
        connection = sqlite3.connect("file:{0}?mode=ro".format(db_path), uri=True)
        rows = connection.execute(query).fetchall()
    except sqlite3.Error:
        # Incluye el caso de que el archivo exista pero todavia no tenga las
        # tablas (OperationalError). Se reintenta en la proxima consulta.
        return {}, False
    finally:
        if connection is not None:
            connection.close()

    color_management_por_proyecto = {}
    for project_name, settings_json in rows:
        name = (project_name or "").strip()
        if not name:
            continue
        color_management_por_proyecto[name.upper()] = _extraer_color_management(
            settings_json
        )

    return color_management_por_proyecto, True


def load_project_color_management():
    """
    Devuelve {PROYECTO_EN_MAYUSCULAS: {...} | None} para el contexto activo.

    El valor es None cuando el proyecto esta en la DB pero no tiene
    `color_management` configurado (o vino invalido). Un proyecto ausente de
    la DB directamente no aparece en el dict.
    """
    global _cache_color_management, _cache_stamp, _cache_checked_at

    ahora = time.monotonic()
    if (
        _cache_color_management is not None
        and _cache_checked_at is not None
        and (ahora - _cache_checked_at) < _STAMP_TTL_SEGUNDOS
    ):
        return _cache_color_management

    _cache_checked_at = ahora
    stamp = _db_stamp(get_color_management_db_path())
    if _cache_color_management is not None and stamp == _cache_stamp:
        return _cache_color_management

    color_management, leyo_ok = _load_color_management_uncached()
    if not leyo_ok:
        # Lectura fallida: se devuelve lo que haya (o vacio) SIN cachear, asi
        # el proximo llamado reintenta en vez de quedarse pegado al error.
        _cache_checked_at = None
        return (
            _cache_color_management if _cache_color_management is not None else {}
        )

    _cache_color_management = color_management
    _cache_stamp = stamp
    return _cache_color_management


def refresh_cache():
    """Fuerza la relectura de la DB en la proxima consulta."""
    global _cache_color_management, _cache_stamp, _cache_checked_at
    _cache_color_management = None
    _cache_stamp = None
    _cache_checked_at = None


def get_color_management(project_name):
    """
    Devuelve el dict de color management del proyecto, o None si el proyecto
    no esta en la DB o no tiene `color_management` configurado.
    """
    target = (project_name or "").strip().upper()
    if not target:
        return None
    return load_project_color_management().get(target)


def is_color_managed(project_name):
    """True si el proyecto tiene color management configurado Y habilitado."""
    config = get_color_management(project_name)
    if not config:
        return False
    return bool(config.get("enabled"))


# ============================
# Resolucion de nombres OCIO
# ============================

# Mapa de tokens neutros (los que guarda PipeSync) al nombre de colorspace que
# se busca en la lista de transforms disponibles del config OCIO activo.
# "acescg" busca ACEScg; "aces2065-1" busca ACES2065-1. Un token que no
# figure aca se busca por su propio texto (ver resolve_ocio_name): asi un
# token nuevo (log, cineon, ...) no rompe, solo puede no resolver si el
# config no trae nada parecido.
TOKEN_TO_OCIO_NAME = {
    "acescg": "ACEScg",
    "aces2065-1": "ACES2065-1",
}


def _normalize(text):
    """
    Deja solo letras y numeros en minuscula, para comparar nombres de
    espacios sin que importen espacios, guiones ni mayusculas.

    Portado de _normalize() en LGA_ApplyAMF.py (repo LGA_ToolPack-B):
    C:/Users/leg4-pc/.nuke/LGA_ToolPack-B/py/LGA_ApplyAMF.py (linea ~184).
    """
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def resolve_ocio_name(token, available_transforms):
    """
    Resuelve un TOKEN NEUTRO (ver header del modulo) contra los transforms
    reales de un config OCIO. Devuelve el nombre real tal cual aparece en
    `available_transforms`, o None si no matchea ninguno.

    Algoritmo portado de match_colorspace_option() en LGA_ApplyAMF.py (repo
    LGA_ToolPack-B): C:/Users/leg4-pc/.nuke/LGA_ToolPack-B/py/LGA_ApplyAMF.py
    (linea ~624). Resuelve un nombre de espacio contra una lista de opciones
    reales con dos pasadas -primero los espacios nombrados DIRECTO (sin
    parentesis), despues la lista entera con los roles tipo
    'scene_linear (ACES - ACEScg)'- y en cada pasada de mas estricto a mas
    laxo: igualdad, sufijo, contencion. Asi 'acescg' resuelve al espacio
    'ACES - ACEScg' y no al rol 'scene_linear (ACES - ACEScg)', que tambien
    lo contiene.

    Recibe la lista de transforms como argumento (en vez de leerla de un knob
    de Nuke, como hace el original) para poder testearse sin Hiero.
    """
    if not token:
        return None
    if not available_transforms:
        return None

    wanted = TOKEN_TO_OCIO_NAME.get(str(token).strip().lower(), token)
    target = _normalize(wanted)
    if not target:
        return None

    options = list(available_transforms)
    # Espacios nombrados directo: sin parentesis. Los roles del config OCIO
    # aparecen con formato 'rol (Espacio - Real)' y son una indireccion; se
    # buscan solo si nada directo sirvio.
    directas = [o for o in options if "(" not in str(o)]

    for candidatas in (directas, options):
        for opcion in candidatas:
            if _normalize(opcion) == target:
                return opcion
        for opcion in candidatas:
            if _normalize(opcion).endswith(target):
                return opcion
        for opcion in candidatas:
            if target in _normalize(opcion):
                return opcion

    return None
