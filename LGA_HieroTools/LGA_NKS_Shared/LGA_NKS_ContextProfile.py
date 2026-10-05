"""
____________________________________________________________________

  LGA_NKS_ContextProfile v1.01 | Lega

  Resolver de contexto Studio/Client para LGA_HieroTools: decide qué perfil
  de PipeSync se usa al resolver config.secure y bases locales.

  El modo es STUDIO salvo que algo diga lo contrario. Una instalación de
  estudio no lleva ningún archivo de contexto: que no haya nada ES studio.
  Se mira, en este orden:

    1. LGA_HIEROTOOLS_CONTEXT_INI, si la variable apunta a un archivo.
    2. El INI suelto junto a LGA_HieroTools_Startup.py. No lo instala nadie:
       lo escribe el switch Studio/Client del Projects Panel, que existe
       para un solo usuario. Es el cambio local, y por eso gana.
    3. El INI de ADENTRO de la carpeta del pack. Es la marca del build: solo
       viaja en el paquete client, donde lo pone el generador de release.
    4. Nada de lo anterior: studio.

  v1.01: La marca del build pasa a vivir adentro de la carpeta del pack.
         Antes el INI se instalaba suelto en Python/Startup en las dos
         variantes, y era un tercer item visible que el usuario no necesita
         conocer. get_override_ini_path() da la ruta donde escribe el switch,
         para que nunca caiga sobre la marca del build.
  v1.00: La cache client de Windows se resuelve en la instalación hermana
         `PipeSync_Client/cacheClient`.
____________________________________________________________________
"""

import configparser
import os
import sys
from pathlib import Path

MODE_STUDIO = "studio"
MODE_CLIENT = "client"

ENV_CONTEXT_INI = "LGA_HIEROTOOLS_CONTEXT_INI"
CONTEXT_FILE_NAME = "LGA_HieroTools_context.ini"
# "context.ini" es un nombre historico del INI suelto; se sigue leyendo.
DEFAULT_CONTEXT_FILES = (CONTEXT_FILE_NAME, "context.ini")


def _normalize_mode(raw_mode):
    mode = (raw_mode or "").strip().lower()
    return MODE_CLIENT if mode == MODE_CLIENT else MODE_STUDIO


def _startup_root():
    # .../Startup/LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_ContextProfile.py
    # -> .../Startup
    return Path(__file__).resolve().parents[2]


def _pack_root():
    # .../Startup/LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_ContextProfile.py
    # -> .../Startup/LGA_HieroTools
    return Path(__file__).resolve().parents[1]


def get_override_ini_path():
    """
    Ruta del INI donde se guarda un cambio LOCAL de contexto.

    Es la que usa el switch del Projects Panel. Nunca es la marca del build:
    escribir ahi modificaria un archivo del pack, que se pierde en la proxima
    instalacion y dejaria al build mintiendo sobre su propia variante.
    """
    env_path = (os.getenv(ENV_CONTEXT_INI) or "").strip()
    if env_path:
        return Path(env_path)
    return _startup_root() / CONTEXT_FILE_NAME


def _candidate_context_paths():
    env_path = (os.getenv(ENV_CONTEXT_INI) or "").strip()
    if env_path:
        yield Path(env_path)

    # Cambio local: el INI suelto que escribe el switch.
    startup_root = _startup_root()
    for file_name in DEFAULT_CONTEXT_FILES:
        yield startup_root / file_name

    # Marca del build: solo existe en el paquete client.
    yield _pack_root() / CONTEXT_FILE_NAME


def find_context_ini():
    seen = set()
    for candidate in _candidate_context_paths():
        try:
            candidate = candidate.resolve()
        except Exception:
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def get_context_mode():
    ini_path = find_context_ini()
    if not ini_path:
        return MODE_STUDIO

    parser = configparser.ConfigParser()
    try:
        parser.read(ini_path, encoding="utf-8")
    except Exception:
        return MODE_STUDIO

    candidates = [
        parser.get("Context", "mode", fallback=""),
        parser.get("Context", "Mode", fallback=""),
        parser.get("DEFAULT", "mode", fallback=""),
        parser.get("DEFAULT", "Mode", fallback=""),
    ]
    for value in candidates:
        if value:
            return _normalize_mode(value)
    return MODE_STUDIO


def is_client_context():
    return get_context_mode() == MODE_CLIENT


def get_pipesync_profile_folder():
    return "PipeSyncClient" if is_client_context() else "PipeSync"


def get_lga_appdata_root():
    if sys.platform == "win32":
        app_data = os.getenv("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(app_data) / "LGA"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "LGA"
    return Path.home() / ".config" / "LGA"


def get_pipesync_config_dir():
    return get_lga_appdata_root() / get_pipesync_profile_folder()


def get_secure_config_path():
    return get_pipesync_config_dir() / "config.secure"


def get_key_path():
    return get_pipesync_config_dir() / ".key"


def _default_cache_dir():
    if sys.platform == "win32":
        # Mantenemos compatibilidad con el layout histórico del entorno portable.
        if is_client_context():
            return Path("C:/Portable/LGA/PipeSync_Client/cacheClient")
        return Path("C:/Portable/LGA/PipeSync/cache")
    if sys.platform == "darwin":
        if is_client_context():
            return Path.home() / "Library" / "Caches" / "LGA" / "PipeSyncClient"
        return Path.home() / "Library" / "Caches" / "LGA" / "PipeSync"
    if is_client_context():
        return Path.home() / ".cache" / "LGA" / "PipeSyncClient"
    return Path.home() / ".cache" / "LGA" / "PipeSync"


def get_cache_dir_from_config(config_dict):
    if isinstance(config_dict, dict):
        app_cfg = config_dict.get("App", {})
        if isinstance(app_cfg, dict):
            cache_path = str(app_cfg.get("CachePath") or "").strip()
            if cache_path:
                normalized = cache_path.replace("\\", "/").rstrip("/").lower()
                if is_client_context() and (
                    normalized.endswith("/cacheproject")
                    or normalized.endswith("/cache/project")
                ):
                    return _default_cache_dir()
                return Path(cache_path)
    return _default_cache_dir()


def get_db_path(config_dict=None, filename="pipesync.db"):
    return get_cache_dir_from_config(config_dict) / filename
