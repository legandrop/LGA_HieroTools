"""
____________________________________________________________________

  LGA_NKS_BurnIn_Config v1.03 | Lega

  Capa de configuracion de LGA_BurnIn. Resuelve la config efectiva
  en dos niveles: defaults + archivo de usuario en AppData
  (%APPDATA%\\LGA\\HieroTools\\BurnIn.json) + override por proyecto
  (JSON guardado en un tag del proyecto, que viaja en el .hrox).
  Modulo puro: no importa nuke ni hiero, para poder testearlo fuera
  del host.

  v1.03: res_target acepta una LISTA de resoluciones validas ('timeline,
         3840x2160' o una lista JSON): parse_res_targets() y
         format_res_targets() (texto canonico + tokens invalidos).
  v1.02: Presets de usuario con nombre (list/load/save) en la seccion
         "presets" del BurnIn.json.
  v1.01: Frame/TC separados, campo colorspace, y pos como caja de
         panel (x, y, w, h) con el layout de dos filas balanceadas.
  v1.00: Version inicial.
____________________________________________________________________
"""

import copy
import json
import os
import re
import sys

CONFIG_DIR_NAME = "LGA"
CONFIG_SUBDIR_NAME = "HieroTools"
CONFIG_FILE_NAME = "BurnIn.json"

# Los settings por proyecto viajan en un tag del proyecto (.hrox).
# Las keys de metadata de tags DEBEN empezar con "tag." (lo exige Hiero).
PROJECT_TAG_NAME = "LGA_BurnIn_Settings"
PROJECT_TAG_KEY = "tag.lga_burnin_config"

# Config default completa. "pos" es la caja del PANEL de cada campo en
# fracciones del formato (x, y, w, h), igual que los knobs de Layout del
# gizmo, para que las posiciones se adapten solas a la resolucion.
# Layout: dos filas balanceadas (arriba: clip | colorspace | res; abajo:
# frame | tc | fps). Debe coincidir con FIELDS del generador del gizmo.
DEFAULTS = {
    "fields": {
        "clip": {"enabled": True, "pos": [0.02, 0.92, 0.34, 0.05]},
        "cspace": {"enabled": True, "pos": [0.40, 0.92, 0.20, 0.05]},
        "res": {"enabled": True, "pos": [0.86, 0.92, 0.12, 0.05]},
        "frame": {"enabled": True, "pos": [0.02, 0.03, 0.11, 0.05]},
        "tc": {"enabled": True, "pos": [0.145, 0.03, 0.155, 0.05]},
        "fps": {"enabled": True, "pos": [0.90, 0.03, 0.08, 0.05]},
    },
    # Lista de resoluciones validas, separadas por comas: "timeline" es el
    # formato de salida del timeline y "3840x2160" un valor explicito. El
    # plate esta bien si coincide con CUALQUIERA ("timeline, 3840x2160").
    "res_target": "timeline",
    # "timeline" compara contra hiero/sequence/frame_rate;
    # un numero (ej. 24) compara contra ese valor explicito.
    "fps_target": "timeline",
    # La comparacion de resolucion solo corre para estas extensiones
    # (plates). Refs/QuickTimes/etc quedan fuera a proposito.
    "compare_res_exts": ["exr"],
    "text_scale": 0.5,
    "opacity": 1.0,
}


# ── Rutas ─────────────────────────────────────────────────────────────────────


def _user_config_root():
    if sys.platform.startswith("win"):
        v = os.getenv("APPDATA")
        if v:
            return v
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support")
    return os.path.expanduser("~/.config")


def get_settings_path():
    """Ruta al BurnIn.json del usuario en AppData."""
    return os.path.join(
        _user_config_root(), CONFIG_DIR_NAME, CONFIG_SUBDIR_NAME, CONFIG_FILE_NAME
    )


# ── Merge y parseo ────────────────────────────────────────────────────────────


def _deep_merge(base, override):
    """Merge recursivo: override pisa base sin mutar ninguno de los dos."""
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def parse_res(value):
    """'3840x2160' -> (3840, 2160). None si no parsea o si es 'timeline'."""
    if not isinstance(value, str):
        return None
    text = value.strip().lower()
    if text == "timeline":
        return None
    for sep in ("x", "*"):
        if sep in text:
            parts = text.split(sep)
            if len(parts) == 2:
                try:
                    return (int(parts[0].strip()), int(parts[1].strip()))
                except ValueError:
                    return None
    return None


def _res_tokens(value):
    """Tokens de una lista de resoluciones: string separado por comas (o ;)
    o una lista JSON. '3840 x 2160' cuenta como un solo token."""
    if isinstance(value, (list, tuple)):
        raw = [str(v) for v in value]
    elif isinstance(value, str):
        raw = re.split(r"[,;|]", value)
    else:
        return []
    out = []
    for part in raw:
        part = re.sub(r"\s*[x*]\s*", "x", part.strip().lower())
        out.extend(p for p in part.split() if p)
    return out


def parse_res_targets(value):
    """Resoluciones validas de los plates: (usa_timeline, {(w, h), ...}, invalidos).

    Acepta una lista: 'timeline, 3840x2160' (string con comas) o
    ["timeline", "3840x2160"]. 'timeline' es el formato de la secuencia. Sin
    nada valido, vale el timeline (el default de siempre).
    """
    use_timeline = False
    sizes = set()
    bad = []
    for tok in _res_tokens(value):
        if tok == "timeline":
            use_timeline = True
            continue
        res = parse_res(tok)
        if res and res[0] > 0 and res[1] > 0:
            sizes.add(res)
        else:
            bad.append(tok)
    if not use_timeline and not sizes:
        use_timeline = True
    return use_timeline, frozenset(sizes), bad


def format_res_targets(value):
    """Texto canonico de la lista ('timeline, 3840x2160') y los tokens que
    no se entendieron (para avisar en el panel antes de guardar)."""
    tokens = _res_tokens(value)
    seen, parts, bad = set(), [], []
    for tok in tokens:
        if tok != "timeline":
            res = parse_res(tok)
            if not (res and res[0] > 0 and res[1] > 0):
                bad.append(tok)
                continue
            tok = "%dx%d" % res
        if tok not in seen:
            seen.add(tok)
            parts.append(tok)
    return (", ".join(parts) or "timeline"), bad


def parse_fps(value):
    """'timeline' -> None; numero o string numerico -> float."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text == "timeline":
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def match_project_section(projects_cfg, project_name):
    """Busca la seccion de proyecto cuyo nombre matchea por prefijo.

    Los proyectos de Hiero llevan version en el nombre (PROJA_SUP_v012),
    asi que la key de config es un prefijo. Gana el prefijo mas largo.
    """
    if not projects_cfg or not project_name:
        return None
    best_key = None
    for key in projects_cfg:
        if project_name.startswith(key):
            if best_key is None or len(key) > len(best_key):
                best_key = key
    return projects_cfg.get(best_key) if best_key else None


def load_user_file(path=None):
    """Lee el BurnIn.json de AppData. Estructura: {"default": {...}, "projects": {...}}.

    Devuelve (data, error). Si no existe devuelve ({}, None).
    """
    p = path or get_settings_path()
    if not os.path.exists(p):
        return {}, None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f) or {}, None
    except Exception as exc:
        return {}, "No se pudo leer {}: {}".format(p, exc)


def save_user_file(data, path=None):
    """Escribe el BurnIn.json (LF explicito). Devuelve error o None."""
    p = path or get_settings_path()
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", newline="\n", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        return None
    except Exception as exc:
        return "No se pudo escribir {}: {}".format(p, exc)


# ── Presets de usuario (viven en el mismo BurnIn.json, seccion "presets") ─────


def list_presets(path=None):
    """Nombres de presets guardados, ordenados."""
    data, _error = load_user_file(path)
    return sorted((data.get("presets") or {}).keys())


def load_preset(name, path=None):
    """Dict del preset o None si no existe."""
    data, _error = load_user_file(path)
    preset = (data.get("presets") or {}).get(name)
    return copy.deepcopy(preset) if isinstance(preset, dict) else None


def save_preset(name, preset, path=None):
    """Guarda/pisa un preset. Devuelve error o None."""
    if not name or not str(name).strip():
        return "El preset necesita un nombre"
    data, error = load_user_file(path)
    if error:
        return error
    data.setdefault("presets", {})[str(name).strip()] = copy.deepcopy(preset)
    return save_user_file(data, path)


def resolve(user_data, project_name, project_tag_json):
    """Config efectiva: DEFAULTS <- file default <- file[proyecto] <- tag del proyecto.

    user_data: dict ya leido del BurnIn.json (o {}).
    project_tag_json: string JSON guardado en el tag del proyecto (o None).
    Devuelve (config, warnings).
    """
    warnings = []
    cfg = _deep_merge(DEFAULTS, (user_data or {}).get("default"))

    section = match_project_section((user_data or {}).get("projects"), project_name)
    if section:
        cfg = _deep_merge(cfg, section)

    if project_tag_json:
        try:
            tag_cfg = json.loads(project_tag_json)
            if isinstance(tag_cfg, dict):
                cfg = _deep_merge(cfg, tag_cfg)
            else:
                warnings.append("El JSON del tag del proyecto no es un dict")
        except Exception as exc:
            warnings.append("JSON invalido en el tag del proyecto: {}".format(exc))

    return cfg, warnings
