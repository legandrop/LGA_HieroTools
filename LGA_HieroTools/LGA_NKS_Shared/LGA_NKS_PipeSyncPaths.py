# -*- coding: utf-8 -*-
"""
____________________________________________________________________

  LGA_NKS_PipeSyncPaths v1.03 | Lega

  Helpers de rutas de PipeSync para LGA_HieroTools.
  Centraliza resolución de DB/cache por contexto (studio/client).

  IMPORTANTE: La ruta de la DB/cache se resuelve SIEMPRE a la instalación
  estándar de PipeSync (C:/Portable/LGA/PipeSync/...), nunca al CachePath
  guardado en config.secure. Ese CachePath puede apuntar a un build de
  desarrollo (C:/Portable/LGA_PipeSync_2/...) cuando se corrió el PipeSync de
  dev, y no queremos que HieroTools lea/escriba ahí.

  v1.03: Expone rutas absolutas del runtime y scripts instalados de PipeSync;
         permite fijar el contexto de cada ruta durante una operación.
  v1.02: La cache del perfil client usa el layout instalado `PipeSync_Client/cacheClient`.
  v1.01: get_pipesync_db_path resuelve siempre a la instalación estándar e ignora
         el CachePath del config.secure (que podía apuntar al build de dev).
         Eliminados helpers de fallback (_legacy_cache_candidates, get_db_path).
  v1.00: Versión inicial - resolución de DB/cache y AltTPath por contexto.
____________________________________________________________________

"""

import os
import sys
from pathlib import Path

from LGA_NKS_ContextProfile import is_client_context
from SecureConfig_Reader import read_secure_config


def _installed_cache_dir(mode=None):
    """Directorio de cache INSTALADO estándar de PipeSync, por plataforma y contexto."""
    client = (mode or ("client" if is_client_context() else "studio")) == "client"
    if sys.platform == "win32":
        cache_name = "cacheClient" if client else "cache"
        if client:
            return Path("C:/Portable/LGA/PipeSync_Client") / cache_name
        return Path("C:/Portable/LGA/PipeSync") / cache_name

    if sys.platform == "darwin":
        profile_name = "PipeSyncClient" if client else "PipeSync"
        return Path.home() / "Library" / "Caches" / "LGA" / profile_name

    profile_name = "PipeSyncClient" if client else "PipeSync"
    return Path.home() / ".cache" / "LGA" / profile_name


def get_pipesync_db_path(filename="pipesync.db", mode=None):
    """Devuelve la ruta de una DB de PipeSync en la instalación estándar.

    Ignora a propósito el CachePath del config.secure (ver nota del módulo).
    """
    return os.path.normpath(str(_installed_cache_dir(mode=mode) / filename))


def get_pipesync_runtime_paths(script_name, exists=os.path.isfile):
    """Devuelve (python, script) de la instalación, sin consultar el PATH."""
    if sys.platform == "win32":
        root = Path("C:/Portable/LGA/PipeSync")
        python_candidates = [
            root / "python_runtime" / "windows" / "PipeSync_py.exe",
            root / "python_runtime" / "windows" / "python.exe",
        ]
        script_path = root / "py_scr" / script_name
    elif sys.platform == "darwin":
        resource_candidates = [
            Path("/Applications/LGA PipeSync.app/Contents/Resources"),
            Path("/Applications/PipeSync.app/Contents/Resources"),
        ]
        resources = next(
            (root for root in resource_candidates if exists(str(root / "py_scr" / script_name))),
            resource_candidates[0],
        )
        python_candidates = [
            resources / "python_runtime" / "macos" / "python3" / "PipeSync_py",
            resources / "python_runtime" / "macos" / "python3" / "bin" / "python3",
        ]
        script_path = resources / "py_scr" / script_name
    else:
        raise FileNotFoundError("PipeSync no tiene runtime instalado soportado en esta plataforma.")
    python_path = next((path for path in python_candidates if exists(str(path))), None)
    if python_path is None or not exists(str(script_path)):
        raise FileNotFoundError("No se encontró el runtime o el script instalado de PipeSync.")
    return os.path.normpath(str(python_path)), os.path.normpath(str(script_path))


def get_alt_work_root(default_root=None):
    if default_root is None:
        default_root = "N:\\" if is_client_context() else "T:\\"

    config = read_secure_config() or {}
    app_cfg = config.get("App", {}) if isinstance(config, dict) else {}
    raw_alt = str(app_cfg.get("AltTPath", "")).strip()
    if raw_alt:
        return os.path.normpath(raw_alt)
    return os.path.normpath(default_root)
