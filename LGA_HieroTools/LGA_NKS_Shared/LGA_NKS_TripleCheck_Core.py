# -*- coding: utf-8 -*-
"""
____________________________________________________________________

  LGA_NKS_TripleCheck_Core v1.02 | Lega

  Logica del Triple Check del panel Flow | S3: compara la ultima version
  publicada (EXR) de cada shot y task en Flow, en Wasabi y en el disco
  local, y decide el estado de cada fila.

  Este modulo NO importa hiero ni Qt: lo usan la ventana del panel y los
  tests. Wasabi y el disco se leen con dos "listers" que exponen la misma
  interfaz (list_dir / has_files), asi el escaneo es uno solo y los tests
  pueden pasarle un arbol falso.

  Detalle de reglas y estados: docs/Docu_TripleCheck.md.

  v1.02: Con dos carpetas del mismo numero gana la del propio shot (antes
         ganaba la de otro shot por orden alfabetico y salia Wrong folder
         aunque la version propia estuviera). Las carpetas de otro shot que
         sobran se informan con el estado nuevo ST_STRAY. Textos de error y
         de bloqueo en castellano (se leen en la columna Detail).
  v1.01: task_status_info() y has_no_versions().
  v1.00: Version inicial.
____________________________________________________________________
"""

import os
import re
import time


# ── Estados de una fila ──────────────────────────────────────────────────────
# Ordenados por importancia: la columna de estado muestra el primero que
# aplique; el tooltip de la fila los nombra todos.
ST_ERROR = "error"
ST_NOT_IN_FLOW = "not_in_flow"
ST_TASK_NOT_IN_FLOW = "task_not_in_flow"
ST_NOT_IN_TIMELINE = "not_in_timeline"
ST_MISSING_STORAGE = "missing_storage"
ST_INCOMPLETE = "incomplete"
ST_MISNAMED = "misnamed"
ST_UPLOAD = "upload"
ST_DOWNLOAD = "download"
ST_NOT_IN_FLOW_VERSION = "not_in_flow_version"
ST_STRAY = "stray"
ST_OK = "ok"
ST_NO_VERSIONS = "no_versions"

STATUS_PRIORITY = (
    ST_ERROR,
    ST_NOT_IN_FLOW,
    ST_TASK_NOT_IN_FLOW,
    ST_NOT_IN_TIMELINE,
    ST_MISSING_STORAGE,
    ST_INCOMPLETE,
    ST_MISNAMED,
    ST_UPLOAD,
    ST_DOWNLOAD,
    ST_NOT_IN_FLOW_VERSION,
    ST_STRAY,
    ST_OK,
    ST_NO_VERSIONS,
)

# Estados que no son un problema: con "Only issues" se ocultan.
QUIET_STATUSES = (ST_OK, ST_NO_VERSIONS)

# Reintentos de red (regla de GateBouncer): 3 reintentos, 5 s entre intentos.
NET_ATTEMPTS = 4
NET_RETRY_DELAY = 5.0

# Estados de shot de Flow que se ignoran al buscar shots que faltan en el
# timeline: un shot omitido no es un faltante.
OMITTED_SHOT_STATUSES = ("omt", "omit", "na")


# ── Numero de version ────────────────────────────────────────────────────────
# El ULTIMO `vNNN` del nombre, precedido por `_`, `.` o `-`. Se toma el ultimo
# y no el primero por lo mismo que LGA_NKS_CG_Versions: un nombre puede traer
# un token con forma de version antes del sufijo real.
_RE_VERSION = re.compile(r"[_.\-]v(\d+)", re.IGNORECASE)


def version_number(name):
    """Numero de version de un nombre (`SHOT_comp_v052` -> 52), o None."""
    if not name:
        return None
    matches = _RE_VERSION.findall(str(name))
    if not matches:
        return None
    try:
        return int(matches[-1])
    except ValueError:
        return None


def format_version(number):
    """`52` -> `v052`. None -> `-`."""
    if number is None:
        return "-"
    return "v%03d" % int(number)


# ── Eleccion de carpetas sin distinguir mayusculas ───────────────────────────
def pick_folder(names, canonical):
    """Carpeta de `names` que corresponde a `canonical`, con su caso real.

    Misma regla que PipeSync (WasabiTaskFolders / VersionScanner): nombre
    exacto sin distinguir mayusculas; si conviven dos variantes (`Comp/` y
    `comp/`), gana la canonica y si no, la primera alfabetica.
    """
    if not canonical:
        return None
    target = str(canonical).lower()
    candidates = sorted(n for n in names if str(n).lower() == target)
    if not candidates:
        return None
    if canonical in candidates:
        return canonical
    return candidates[0]


def pick_publish_folder(names):
    """Primera subcarpeta (alfabetica) cuyo nombre contiene `_publish`.

    PipeSync no usa un nombre fijo: Comp publica en `4_publish`, DMP en
    `3_publish`, y hay shots viejos con `<shot>_comp_publish`.
    """
    candidates = sorted(n for n in names if "_publish" in str(n).lower())
    return candidates[0] if candidates else None


# Regla de lectura de una carpeta de version: la MISMA de PipeSync
# (VersionRules::parseVersionedEntry): `_v` mas digitos al FINAL del nombre.
# `SHOT_comp_v052_fix/`, `.v001` o `-v3` no son versiones para PipeSync, y si
# este chequeo las contara las dos herramientas mostrarian numeros distintos.
_RE_FOLDER_VERSION = re.compile(r"_v(\d+)$", re.IGNORECASE)

# Alias de cada task para el nombre base de la carpeta (TaskNameMapper de
# PipeSync): `SHOT_cmp_v003` es de comp. CG no filtra por alias: sus carpetas
# llevan la disciplina (`lighting`) y se eligen por la entrega de Flow.
TASK_FOLDER_ALIASES = {
    "comp": ("comp", "cmp", "compo"),
}


def parse_versioned_folder(name):
    """(base, numero) de una carpeta `<base>_vNNN`, o None."""
    match = _RE_FOLDER_VERSION.search(str(name or ""))
    if not match:
        return None
    try:
        return name[: match.start()], int(match.group(1))
    except ValueError:
        return None


def versioned_entries(names, task=None):
    """[(nombre, numero)] de las carpetas de version de esa task.

    Las que no tienen numero (`Originals/`) quedan afuera, y con `task` (no
    CG) tambien las que no son de la task: el nombre base tiene que terminar
    en uno de sus alias, igual que en PipeSync. Asi una `SHOT_roto_v060/`
    dentro de `comp/4_publish` no se ofrece como version de comp.
    """
    aliases = None
    if task and task != "cg":
        aliases = TASK_FOLDER_ALIASES.get(task, (task,))
    out = []
    for name in names:
        parsed = parse_versioned_folder(name)
        if parsed is None:
            continue
        base, number = parsed
        if aliases and not any(base.lower().endswith(a) for a in aliases):
            continue
        out.append((name, number))
    return out


# ── Listers: la misma interfaz para disco y Wasabi ───────────────────────────
class ListError(Exception):
    """No se pudo leer un nivel (disco sin montar, policy de Wasabi, red)."""


# Errores de S3 que no se arreglan reintentando: la policy no cubre ese
# prefijo o el bucket no existe. Se informan al toque, sin esperar 15 s.
_NO_RETRY_CODES = ("AccessDenied", "NoSuchBucket", "InvalidAccessKeyId", "SignatureDoesNotMatch")


def _error_code(exc):
    response = getattr(exc, "response", None) or {}
    return (response.get("Error") or {}).get("Code") or ""


# Quien usa el modulo puede colgar aca su log: recibe un texto por reintento.
# Sirve para ver en el .log que un bloqueo del firewall (WinError 10013) se
# reintento y paso despues de autorizarlo.
on_retry = None


def _with_retries(func, describe):
    """Corre `func` con los reintentos de red. Relanza ListError al final.

    3 reintentos con 5 s entre intentos: el primer pedido de un programa nuevo
    lo frena el firewall de la maquina hasta que se autoriza, y el siguiente
    tiene que pasar.
    """
    last = None
    for attempt in range(NET_ATTEMPTS):
        try:
            return func()
        except ListError:
            raise
        except Exception as exc:  # red, permisos, firewall
            last = exc
            if _error_code(exc) in _NO_RETRY_CODES:
                break
            if on_retry:
                try:
                    on_retry("Reintento %d de %s: %s" % (attempt + 1, describe, exc))
                except Exception:
                    pass
            if attempt < NET_ATTEMPTS - 1:
                time.sleep(NET_RETRY_DELAY)
    code = _error_code(last)
    raise ListError("%s: %s" % (describe, code or last))


class LocalLister(object):
    """Lee el disco a partir de la carpeta del proyecto (`N:/VFX-PROJA`)."""

    kind = "local"

    def __init__(self, root):
        self.root = os.path.normpath(str(root)) if root else ""

    def path_of(self, parts):
        return os.path.join(self.root, *parts) if parts else self.root

    def list_dir(self, parts):
        """(carpetas, archivos) de un nivel. Un nivel que no existe da ([], [])."""
        path = self.path_of(parts)
        if not parts and not os.path.isdir(path):
            raise ListError("No se encontró la carpeta local del proyecto: %s" % path)
        if not os.path.isdir(path):
            return [], []
        dirs, files = [], []
        try:
            with os.scandir(path) as it:
                for entry in it:
                    try:
                        if entry.is_dir():
                            dirs.append(entry.name)
                        else:
                            files.append(entry.name)
                    except OSError:
                        continue
        except OSError as exc:
            raise ListError("No se pudo leer %s: %s" % (path, exc))
        return dirs, files

    def has_files(self, parts):
        """True si la carpeta tiene al menos un archivo visible (recursivo).

        Misma regla que LocalVersionContent de PipeSync: no cuenta lo que
        empieza con punto (parciales de descarga, .DS_Store). Una carpeta que
        no se puede leer cuenta como con archivos, para no ofrecer bajar algo
        que quizas ya esta.
        """
        path = self.path_of(parts)
        try:
            for current, dirnames, filenames in os.walk(path):
                dirnames[:] = [d for d in dirnames if not d.startswith(".")]
                for name in filenames:
                    if not name.startswith("."):
                        return True
        except OSError:
            return True
        return False

    def content_stats(self, parts):
        """(archivos, bytes) visibles debajo de la carpeta, recursivo."""
        path = self.path_of(parts)
        count, total = 0, 0
        try:
            for current, dirnames, filenames in os.walk(path):
                dirnames[:] = [d for d in dirnames if not d.startswith(".")]
                for name in filenames:
                    if name.startswith("."):
                        continue
                    count += 1
                    try:
                        total += os.path.getsize(os.path.join(current, name))
                    except OSError:
                        pass
        except OSError as exc:
            raise ListError("No se pudo leer %s: %s" % (path, exc))
        return count, total


class WasabiLister(object):
    """Lee un bucket de Wasabi con un cliente boto3 (thread-safe).

    Si un pedido agota los reintentos por un error de RED (no de permisos),
    el lister queda "caido" y los siguientes fallan al instante: con ~600
    listados, esperar 15 s de reintentos en cada uno serian minutos.
    """

    kind = "wasabi"

    def __init__(self, client, bucket):
        self.client = client
        self.bucket = bucket
        self.dead = ""

    @staticmethod
    def prefix_of(parts):
        return "".join("%s/" % p for p in parts)

    def _call(self, func, describe):
        if self.dead:
            raise ListError(self.dead)
        try:
            return _with_retries(func, describe)
        except ListError as exc:
            text = str(exc)
            if not any(code in text for code in _NO_RETRY_CODES):
                self.dead = "Wasabi not reachable (%s)" % text
            raise

    def content_stats(self, parts):
        """(archivos, bytes) debajo de la carpeta, sin las keys de carpeta."""
        prefix = self.prefix_of(parts)

        def _run():
            count, total, token = 0, 0, None
            while True:
                kwargs = {"Bucket": self.bucket, "Prefix": prefix, "MaxKeys": 1000}
                if token:
                    kwargs["ContinuationToken"] = token
                resp = self.client.list_objects_v2(**kwargs)
                for item in resp.get("Contents", []) or []:
                    key = item.get("Key", "")
                    base = key.rstrip("/").rsplit("/", 1)[-1]
                    if key.endswith("/") or base.startswith("."):
                        continue
                    count += 1
                    total += int(item.get("Size") or 0)
                if resp.get("IsTruncated") and resp.get("NextContinuationToken"):
                    token = resp["NextContinuationToken"]
                    continue
                return count, total

        return self._call(_run, "Wasabi %s/%s" % (self.bucket, prefix))

    def list_dir(self, parts):
        prefix = self.prefix_of(parts)

        def _run():
            dirs, files = [], []
            token = None
            while True:
                kwargs = {
                    "Bucket": self.bucket,
                    "Prefix": prefix,
                    "Delimiter": "/",
                    "MaxKeys": 1000,
                }
                if token:
                    kwargs["ContinuationToken"] = token
                resp = self.client.list_objects_v2(**kwargs)
                for item in resp.get("CommonPrefixes", []) or []:
                    name = item.get("Prefix", "")[len(prefix):].rstrip("/")
                    if name:
                        dirs.append(name)
                for item in resp.get("Contents", []) or []:
                    name = item.get("Key", "")[len(prefix):]
                    if name and "/" not in name:
                        files.append(name)
                if resp.get("IsTruncated") and resp.get("NextContinuationToken"):
                    token = resp["NextContinuationToken"]
                    continue
                return dirs, files

        return self._call(_run, "Wasabi %s/%s" % (self.bucket, prefix))

    def has_files(self, parts):
        """True si debajo de la carpeta hay alguna key que no sea carpeta."""
        prefix = self.prefix_of(parts)

        def _run():
            resp = self.client.list_objects_v2(
                Bucket=self.bucket, Prefix=prefix, MaxKeys=20
            )
            for item in resp.get("Contents", []) or []:
                key = item.get("Key", "")
                base = key.rstrip("/").rsplit("/", 1)[-1]
                if not key.endswith("/") and not base.startswith("."):
                    return True
            return False

        return self._call(_run, "Wasabi %s/%s" % (self.bucket, prefix))


# ── Escaneo de una task ──────────────────────────────────────────────────────
def empty_scan():
    return {
        "number": None,       # numero de la ultima version con archivos (0 = v000)
        "name": "",           # nombre de la carpeta de esa version
        "task_dir": "",       # carpeta de la task con su caso real
        "publish_dir": "",    # carpeta *_publish con su caso real
        "shot_parts": [],     # [seq, shot] con su caso real
        "present": False,     # CG: si esta la entrega de Flow
        "foreign": False,     # la carpeta tope lleva el nombre de otro shot
        "strays": [],         # OTRAS carpetas de version con nombre de otro shot
        "error": "",
    }


def scan_task(lister, shot_parts, task_folder, cg_version_code=None):
    """Lee la ultima version publicada de una task en un lister.

    shot_parts: [seq, shot] con el caso REAL de ese lister (ya resuelto).
    task_folder: nombre canonico de la carpeta de la task (`comp`, `cg`).
    cg_version_code: si viene, es CG: en vez de la mas alta se busca ESA
    entrega (disciplina + numero) y se marca `present`.
    """
    result = empty_scan()
    result["shot_parts"] = list(shot_parts or [])
    if not shot_parts:
        return result
    try:
        shot_dirs, _ = lister.list_dir(shot_parts)
        task_dir = pick_folder(shot_dirs, task_folder)
        if not task_dir:
            return result
        result["task_dir"] = task_dir

        task_dirs, _ = lister.list_dir(shot_parts + [task_dir])
        publish_dir = pick_publish_folder(task_dirs)
        if not publish_dir:
            return result
        result["publish_dir"] = publish_dir

        base = shot_parts + [task_dir, publish_dir]
        version_dirs, loose_files = lister.list_dir(base)
        task_key = "cg" if cg_version_code else str(task_folder or "").lower()
        entries = versioned_entries(version_dirs, task_key)
        visible_files = [f for f in loose_files if not f.startswith(".")]
        if not entries and visible_files:
            # Publish plano: los frames sueltos en `4_publish`. Ni se compara
            # ni se ofrece nada: bajar la "version" crearia una subcarpeta y
            # duplicaria el material.
            result["error"] = "Archivos sueltos en %s (publish plano): no se compara." % publish_dir
            return result

        if cg_version_code:
            name = cg_folder_for(entries, cg_version_code)
            if name and lister.has_files(base + [name]):
                result["present"] = True
                result["name"] = name
                result["number"] = version_number(name)
            # La mas alta igual se informa, como referencia en el tooltip.
            return result

        # De la mas alta a la mas baja; la primera con archivos. v000 es el
        # placeholder de Create v000: vale como "hay carpeta" pero numero 0.
        # A igual numero gana la carpeta del PROPIO shot: con
        # `SHOT_comp_v005/` y una copia `OTRO_comp_v005/` al lado, el orden
        # alfabetico podia elegir la ajena y marcar Wrong folder aunque la
        # version propia estuviera completa.
        shot = shot_parts[-1]
        own = {name: version_belongs_to_shot(name, shot) for name, _n in entries}
        for name, number in sorted(entries, key=lambda e: (-e[1], not own[e[0]], e[0])):
            if lister.has_files(base + [name]):
                result["name"] = name
                result["number"] = number
                # Cuenta igual que en PipeSync, pero se marca: una carpeta con
                # el nombre de OTRO shot es material bajado al lugar equivocado.
                result["foreign"] = not own[name]
                break
        # Las demas carpetas con nombre de otro shot sobran en este publish
        # (una copia, o material bajado al shot equivocado): se informan.
        result["strays"] = sorted(
            name for name, _n in entries if not own[name] and name != result["name"]
        )
    except ListError as exc:
        result["error"] = str(exc)
    return result


def compare_content(row, local_lister, wasabi_lister):
    """Compara archivos y bytes de la version tope cuando Wasabi y local coinciden.

    Una descarga o subida cortada deja la carpeta con ALGUNOS frames: por
    numero de version las dos fuentes coinciden y la fila diria OK. Solo se
    mira la version que coincide, no las anteriores. Deja en la fila:
      content: {"local": (n, bytes), "wasabi": (n, bytes)} o None
      incomplete: "local" / "wasabi" (la que tiene MENOS archivos),
                  "differs" (misma cantidad, distinto peso) o "".
    """
    row["content"] = None
    row["incomplete"] = ""
    w = row.get("wasabi") or {}
    l = row.get("local") or {}
    if w.get("error") or l.get("error") or wasabi_lister is None:
        return row
    if not w.get("name") or not l.get("name"):
        return row
    if w["name"].lower() != l["name"].lower() or not (w.get("number") or 0):
        return row
    try:
        w_stats = wasabi_lister.content_stats(
            w["shot_parts"] + [w["task_dir"], w["publish_dir"], w["name"]]
        )
        l_stats = local_lister.content_stats(
            l["shot_parts"] + [l["task_dir"], l["publish_dir"], l["name"]]
        )
    except ListError:
        return row
    row["content"] = {"local": l_stats, "wasabi": w_stats}
    if l_stats[0] < w_stats[0]:
        row["incomplete"] = "local"
    elif w_stats[0] < l_stats[0]:
        row["incomplete"] = "wasabi"
    elif l_stats[1] != w_stats[1]:
        row["incomplete"] = "differs"
    return row


def cg_folder_for(entries, version_code):
    """Carpeta (de `entries`) de la entrega CG `version_code`, o None.

    Misma regla que LGA_NKS_CG_Versions.carpeta_de_version_cg pero sobre una
    lista de nombres (sirve para Wasabi): primero disciplina + numero; si no
    hay, solo numero y solo si hay UNA candidata.
    """
    try:
        from LGA_NKS_CG_Versions import misma_entrega, clave_de_version
    except ImportError:
        from LGA_NKS_Shared.LGA_NKS_CG_Versions import misma_entrega, clave_de_version
    names = sorted(name for name, _n in entries)
    for name in names:
        if misma_entrega(name, version_code):
            return name
    clave = clave_de_version(version_code)
    if clave is None:
        return None
    same_number = [n for n in names if (clave_de_version(n) or (None, None))[1] == clave[1]]
    return same_number[0] if len(same_number) == 1 else None


def resolve_shot_parts(level_cache, lister, seq, shot):
    """[seq, shot] con el caso real del lister, o ([], motivo).

    Lista la raiz y la secuencia una sola vez por lister (`level_cache`): un
    listado por secuencia en vez de uno por shot, y de paso resuelve
    mayusculas (`vfx-proja/101/PROJA_...` contra `VFX-PROJA/101/proja_...`).
    """
    def _level(parts):
        key = (lister.kind, tuple(p.lower() for p in parts))
        if key not in level_cache:
            try:
                level_cache[key] = (lister.list_dir(parts)[0], "")
            except ListError as exc:
                level_cache[key] = ([], str(exc))
        return level_cache[key]

    root_dirs, err = _level([])
    if err:
        return [], err
    seq_real = pick_folder(root_dirs, seq) if seq else None
    if not seq_real:
        return [], ""
    seq_dirs, err = _level([seq_real])
    if err:
        return [], err
    shot_real = pick_folder(seq_dirs, shot)
    if not shot_real:
        return [], ""
    return [seq_real, shot_real], ""


# ── Flow ─────────────────────────────────────────────────────────────────────
def shot_prefixes(shot_code):
    """Prefijos de version_code que pertenecen al shot.

    El shot entero (`PROJA_1005_0150_VND`) y, si tiene mas de tres bloques, el
    nucleo `PROY_SEQ_SHOT` (`PROJA_1005_0150`): hay vendors que nombran la
    version sin su codigo. Un minicut (`PROJA_1005_MINICUT_v08`) no matchea
    ninguno de los dos.
    """
    shot = str(shot_code or "").lower()
    if not shot:
        return ()
    out = [shot]
    blocks = shot.split("_")
    if len(blocks) > 3:
        out.append("_".join(blocks[:3]))
    return tuple(out)


def version_belongs_to_shot(version_code, shot_code):
    code = str(version_code or "").lower()
    for prefix in shot_prefixes(shot_code):
        if code == prefix or code.startswith(prefix + "_") or code.startswith(prefix + "."):
            return True
    return False


def flow_highest(versions, shot_code):
    """(numero, code) de la Version mas alta del shot, o (None, '')."""
    best = (None, "")
    for v in versions or []:
        code = v.get("code") or ""
        if not version_belongs_to_shot(code, shot_code):
            continue
        number = version_number(code)
        if number is None:
            continue
        if best[0] is None or number > best[0]:
            best = (number, code)
    return best


def flow_latest_cg(versions, shot_code):
    """Version CG mas nueva POR FECHA del shot: dict o None."""
    try:
        from LGA_NKS_CG_Versions import ultima_version_cg
    except ImportError:
        from LGA_NKS_Shared.LGA_NKS_CG_Versions import ultima_version_cg
    candidates = [
        {
            "version_code": v.get("code"),
            "created_on": v.get("created_at"),
            "version_number": version_number(v.get("code")) or 0,
        }
        for v in versions or []
        if v.get("code")
    ]
    if not candidates:
        return None
    return ultima_version_cg(candidates)


def fetch_flow_project(sg, project_name, task_key_of):
    """Shots, tasks y versions de un proyecto de Flow, en tres consultas.

    Devuelve (proyecto_encontrado, {shot_lower: shot}, stats) donde cada shot es:
      {"code", "sequence", "status", "tasks": {task_key: {"status", "versions"}}}
    y stats cuenta las Versions leidas, las que no tenian task y las que no
    se pudieron asignar a ninguna task del pack.
    task_key_of(content) normaliza el nombre de la task de Flow (`Comp`) a la
    clave del pack (`comp`); si devuelve None la task se ignora.
    """
    projects = sg.find("Project", [["name", "is", project_name]], ["id", "name"])
    if not projects:
        return False, {}, {}
    project = {"type": "Project", "id": projects[0]["id"]}

    shots = {}
    shot_by_id = {}
    for s in sg.find(
        "Shot",
        [["project", "is", project]],
        ["code", "sg_sequence", "sg_status_list"],
    ):
        code = s.get("code") or ""
        if not code:
            continue
        seq = s.get("sg_sequence") or {}
        entry = {
            "code": code,
            "sequence": (seq.get("name") or seq.get("code") or "") if isinstance(seq, dict) else "",
            "status": s.get("sg_status_list") or "",
            "tasks": {},
        }
        shots[code.lower()] = entry
        shot_by_id[s["id"]] = entry

    task_by_id = {}
    for t in sg.find(
        "Task",
        [["project", "is", project], ["entity", "type_is", "Shot"]],
        ["content", "entity", "sg_status_list"],
    ):
        shot = shot_by_id.get((t.get("entity") or {}).get("id"))
        key = task_key_of(t.get("content"))
        if not shot or not key:
            continue
        task = shot["tasks"].setdefault(key, {"status": "", "versions": []})
        task["status"] = t.get("sg_status_list") or task["status"]
        task_by_id[t["id"]] = task

    stats = {"versions": 0, "without_task": 0, "unassigned": 0}
    for v in sg.find(
        "Version",
        [["project", "is", project], ["entity", "type_is", "Shot"]],
        ["code", "sg_task", "entity", "created_at", "sg_status_list"],
    ):
        stats["versions"] += 1
        task = task_by_id.get((v.get("sg_task") or {}).get("id"))
        if task is None and not v.get("sg_task"):
            # Version colgada del shot sin task: se asigna por el token de task
            # del codigo (`SHOT_comp_v003` -> comp), si el shot tiene esa task.
            stats["without_task"] += 1
            shot = shot_by_id.get((v.get("entity") or {}).get("id"))
            match = _RE_TASK_TOKEN.search(v.get("code") or "")
            key = task_key_of(match.group(1)) if match else None
            if shot and key:
                task = shot["tasks"].get(key)
        if task is None:
            stats["unassigned"] += 1
            continue
        created = v.get("created_at")
        task["versions"].append(
            {
                "code": v.get("code") or "",
                "created_at": created.isoformat() if hasattr(created, "isoformat") else (created or ""),
                "status": v.get("sg_status_list") or "",
            }
        )
    return True, shots, stats


# Token de task de un version_code: el bloque antes del ultimo `_vNNN`.
_RE_TASK_TOKEN = re.compile(r"_([A-Za-z0-9]+)_v\d+(?!.*_v\d)", re.IGNORECASE)


# ── Clasificacion ────────────────────────────────────────────────────────────
def classify(row):
    """Calcula los estados de una fila y los guarda en ella.

    La fila trae: in_timeline, shot_in_flow, task_in_flow, is_cg, flow
    (numero o None), flow_code, wasabi y local (dicts de scan_task) y,
    opcional, incomplete (de compare_content). Agrega:
      statuses: lista de estados que aplican, en orden de importancia.
      status: el primero.
      can_download / can_upload: si la fila ofrece el boton.
      upload_needs_confirm: la local es mas nueva que Flow (en client suele
        ser una carpeta mal nombrada): se pregunta antes de subir y no entra
        en Upload all.
      upload_blocked: motivo por el que no se ofrece subir aunque haga falta.
    """
    statuses = []
    version_statuses = []
    wasabi = row.get("wasabi") or empty_scan()
    local = row.get("local") or empty_scan()
    w_known = not wasabi.get("error")
    l_known = not local.get("error")
    if not (w_known and l_known):
        statuses.append(ST_ERROR)
    if not row.get("shot_in_flow"):
        statuses.append(ST_NOT_IN_FLOW)
    elif not row.get("task_in_flow"):
        statuses.append(ST_TASK_NOT_IN_FLOW)
    if not row.get("in_timeline"):
        statuses.append(ST_NOT_IN_TIMELINE)

    can_download = False
    can_upload = False
    needs_confirm = False
    both_known = w_known and l_known

    if row.get("is_cg"):
        # CG se compara por PRESENCIA de la entrega de Flow, no por numero:
        # cada disciplina tiene su contador.
        has_flow = bool(row.get("flow_code"))
        w_ok = bool(wasabi.get("present"))
        l_ok = bool(local.get("present"))
        if has_flow and both_known:
            if not w_ok and not l_ok:
                version_statuses.append(ST_MISSING_STORAGE)
            elif l_ok and not w_ok:
                version_statuses.append(ST_UPLOAD)
                can_upload = True
            elif w_ok and not l_ok:
                version_statuses.append(ST_DOWNLOAD)
                can_download = True
        if both_known and not version_statuses:
            version_statuses.append(ST_OK if has_flow else ST_NO_VERSIONS)
    else:
        f = row.get("flow") or 0
        w = wasabi.get("number") or 0
        l = local.get("number") or 0
        if both_known:
            if row.get("task_in_flow") and f > max(w, l):
                version_statuses.append(ST_MISSING_STORAGE)
            if l > w:
                version_statuses.append(ST_UPLOAD)
                can_upload = True
                needs_confirm = row.get("task_in_flow") and l > f
            if w > l:
                version_statuses.append(ST_DOWNLOAD)
                can_download = True
            if row.get("task_in_flow") and max(w, l) > f:
                version_statuses.append(ST_NOT_IN_FLOW_VERSION)
            incomplete = row.get("incomplete") or ""
            if incomplete:
                version_statuses.append(ST_INCOMPLETE)
                if incomplete == "local":
                    can_download = True
                elif incomplete == "wasabi":
                    can_upload = True
                    needs_confirm = needs_confirm or (row.get("task_in_flow") and l > f)
            if wasabi.get("foreign") or local.get("foreign"):
                version_statuses.append(ST_MISNAMED)
            if not version_statuses:
                version_statuses.append(ST_OK if f > 0 else ST_NO_VERSIONS)
            if wasabi.get("strays") or local.get("strays"):
                # Aparte del OK: las versiones coinciden, pero en el publish
                # hay una carpeta de otro shot que sobra.
                version_statuses.append(ST_STRAY)

    # Subir algo de un shot que Flow no tiene (o sin esa task) suele ser un
    # timeline de otro contexto o una carpeta equivocada: se pregunta.
    if can_upload and not row.get("task_in_flow"):
        needs_confirm = True

    if can_download and wasabi.get("foreign"):
        # Bajarla copiaria al disco el material de otro shot.
        can_download = False

    blocked = ""
    if can_upload and local.get("foreign"):
        # Subirla replicaria en Wasabi el error de nombre.
        blocked = "La carpeta local %s lleva el nombre de otro shot." % local.get("name")
        can_upload = False
    if can_upload and not blocked:
        w_pub = (wasabi.get("publish_dir") or "").lower()
        l_pub = (local.get("publish_dir") or "").lower()
        if w_pub and l_pub and w_pub != l_pub:
            # FileManagerS3 sube a la ruta tal cual: con otro nombre de
            # publish quedarian dos carpetas de publish en Wasabi.
            blocked = "El publish se llama distinto: local '%s', Wasabi '%s'." % (
                local.get("publish_dir"), wasabi.get("publish_dir"))
            can_upload = False

    statuses.extend(version_statuses)
    ordered = [s for s in STATUS_PRIORITY if s in statuses]
    row["statuses"] = ordered
    row["status"] = ordered[0] if ordered else ST_OK
    row["can_download"] = can_download
    row["can_upload"] = can_upload
    row["upload_needs_confirm"] = bool(needs_confirm) and can_upload
    row["upload_blocked"] = blocked
    return row


def is_issue(row):
    """True si la fila tiene algo que mirar (no es solo OK / No versions)."""
    return any(s not in QUIET_STATUSES for s in row.get("statuses", []))


def has_no_versions(row):
    """True si ningun lado tiene una version real (Flow, Wasabi y local en 0)."""
    return not any(
        (row.get(source) if source == "flow" else (row.get(source) or {}).get("number"))
        for source in ("flow", "wasabi", "local")
    )


def task_status_info(code, catalog):
    """(nombre visible, color de fondo, orden) del estado de la task en Flow.

    catalog: code -> (nombre, color, ...) en el orden del flujo de trabajo
    (Not ready -> In progress -> reviews -> entregas), el de
    LGA_NKS_Flow_Status_Config. Ordenar por estado sigue ese orden, no el
    alfabetico. Un codigo que el catalogo no conoce se muestra crudo, sin
    color, despues de los conocidos; sin task en Flow va al final.
    """
    codes = list(catalog)
    if not code:
        return "", None, len(codes) + 1
    if code in catalog:
        info = catalog[code]
        return info[0], info[1], codes.index(code)
    return code, None, len(codes)


# ── Rutas de las acciones ────────────────────────────────────────────────────
def download_target(local_root, row):
    """Carpeta local donde cae la version de Wasabi, con el caso de Wasabi.

    FileManagerS3 traduce la ruta local a la key de S3 tal cual, asi que la
    ruta tiene que llevar las mayusculas que tiene en Wasabi (`Comp/`).
    """
    w = row.get("wasabi") or {}
    if not (w.get("shot_parts") and w.get("task_dir") and w.get("publish_dir") and w.get("name")):
        return None
    return os.path.join(
        local_root, *(w["shot_parts"] + [w["task_dir"], w["publish_dir"], w["name"]])
    )


def upload_source(local_root, row, canonical_task_dir, isdir=os.path.isdir):
    """Carpeta local de la version a subir, o None si no se puede subir.

    FileManagerS3 arma la key de S3 con los tramos de la ruta TAL CUAL, asi
    que cada tramo lleva las mayusculas que ya tiene en Wasabi: con `Comp/`
    en Wasabi y `comp/` en la ruta se crearia una carpeta paralela. Un tramo
    que todavia no existe en Wasabi va con el nombre canonico (`comp`), como
    lo crea PipeSync. En Windows la ruta resuelve igual (el disco no
    distingue mayusculas); si con ese caso no existe (macOS), se usa la ruta
    local real.
    """
    l = row.get("local") or {}
    w = row.get("wasabi") or {}
    if not (l.get("shot_parts") and l.get("task_dir") and l.get("publish_dir") and l.get("name")):
        return None
    if row.get("upload_blocked"):
        return None
    shot_parts = w.get("shot_parts") or l["shot_parts"]
    task_dir = w.get("task_dir") or canonical_task_dir or l["task_dir"]
    publish_dir = w.get("publish_dir") or l["publish_dir"]
    candidate = os.path.join(local_root, *(shot_parts + [task_dir, publish_dir, l["name"]]))
    if isdir(candidate):
        return candidate
    return os.path.join(local_root, *(l["shot_parts"] + [l["task_dir"], l["publish_dir"], l["name"]]))


__all__ = [
    "ST_ERROR",
    "ST_NOT_IN_FLOW",
    "ST_TASK_NOT_IN_FLOW",
    "ST_NOT_IN_TIMELINE",
    "ST_MISSING_STORAGE",
    "ST_INCOMPLETE",
    "ST_MISNAMED",
    "compare_content",
    "parse_versioned_folder",
    "ST_UPLOAD",
    "ST_DOWNLOAD",
    "ST_NOT_IN_FLOW_VERSION",
    "ST_OK",
    "ST_NO_VERSIONS",
    "STATUS_PRIORITY",
    "version_number",
    "format_version",
    "pick_folder",
    "pick_publish_folder",
    "versioned_entries",
    "ListError",
    "LocalLister",
    "WasabiLister",
    "scan_task",
    "cg_folder_for",
    "resolve_shot_parts",
    "shot_prefixes",
    "version_belongs_to_shot",
    "flow_highest",
    "flow_latest_cg",
    "fetch_flow_project",
    "classify",
    "is_issue",
    "download_target",
    "upload_source",
]
