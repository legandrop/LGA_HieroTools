"""
____________________________________________________________________

  LGA_NKS_ShotMarks_Google v1.00 | Lega

  Shot Marks desde un link de Google Sheets: baja la planilla como
  xlsx con la cuenta de Google del usuario y la deja en una cache
  local, para que el resto de Shot Marks la lea igual que un Excel
  (hojas, columnas, comentarios y fotos ancladas viajan en el xlsx).

  Sin host y sin librerias de Google: solo libreria estandar.

  - Permiso: cliente OAuth de escritorio (GOOGLE_OAUTH_CLIENT_ID y
    GOOGLE_OAUTH_CLIENT_SECRET, variables de entorno o
    ~/.lga-keys/google-oauth.env). La primera vez abre el navegador
    por defecto para el login (drive.readonly, PKCE, callback en
    127.0.0.1) y guarda el refresh token en
    ~/.lga-keys/google-oauth-token.env.
  - No usa files.export de la API: tiene un tope de 10 MB y una
    planilla con fotos lo pasa (medido: 403 exportSizeLimitExceeded con
    51 MB). Usa el exportLinks de xlsx con el token, sin ese tope.
  - Cache por id en %LOCALAPPDATA%\\LGA\\HieroTools\\ShotMarks_Google:
    si modifiedTime no cambio, no se vuelve a bajar.
  - Reintenta cada pedido ante un error de conexion: un firewall por
    aplicacion sin driver pierde el primer intento a cada IP nueva, y
    Google rota las IP de su servidor de descarga.

  v1.00: Version inicial.
____________________________________________________________________
"""

import base64
import hashlib
import http.server
import json
import os
import re
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SCOPE = "https://www.googleapis.com/auth/drive.readonly"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
DRIVE_FILES = "https://www.googleapis.com/drive/v3/files/"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
SHEET_MIME = "application/vnd.google-apps.spreadsheet"

CLIENT_FILE = "google-oauth.env"
TOKEN_FILE = "google-oauth-token.env"
CLIENT_ID_VAR = "GOOGLE_OAUTH_CLIENT_ID"
CLIENT_SECRET_VAR = "GOOGLE_OAUTH_CLIENT_SECRET"
REFRESH_VAR = "GOOGLE_OAUTH_REFRESH_TOKEN"

LOGIN_TIMEOUT = 300
ATTEMPTS = 4  # el primero y 3 reintentos
RETRY_WAIT = 5.0  # con 2 s, GateBouncer a veces no llegaba a aplicar la regla
CHUNK = 1 << 20

SHEET_ID_RE = re.compile(r"docs\.google\.com/spreadsheets/d/([A-Za-z0-9_-]{20,})")
_INVALID_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


class GoogleSheetError(Exception):
    """Error que se le puede mostrar al usuario tal cual."""


# -- link ----------------------------------------------------------------------

def sheet_id(text):
    """El id de un link de Google Sheets, o None si el texto no es uno."""
    match = SHEET_ID_RE.search(text or "")
    return match.group(1) if match else None


def is_link(text):
    return sheet_id(text) is not None


def safe_name(title):
    """Un titulo de Google como nombre de carpeta valido en Windows."""
    name = _INVALID_NAME.sub("_", title or "").strip(" .")
    return name or "Google Sheet"


# -- credenciales --------------------------------------------------------------

def keys_dir():
    return Path.home() / ".lga-keys"


def read_key(file_name, variable):
    """Variable de entorno, o ~/.lga-keys/<archivo>; None si no esta."""
    value = os.environ.get(variable, "").strip()
    if value:
        return value
    path = keys_dir() / file_name
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            name, _, val = line.partition("=")
            if name.strip() == variable and val.strip():
                return val.strip().strip('"').strip("'")
    return None


def client_credentials():
    client_id = read_key(CLIENT_FILE, CLIENT_ID_VAR)
    client_secret = read_key(CLIENT_FILE, CLIENT_SECRET_VAR)
    if not client_id or not client_secret:
        raise GoogleSheetError(
            "Google Sheets needs a Google sign-in client: %s and %s in %s."
            % (CLIENT_ID_VAR, CLIENT_SECRET_VAR, keys_dir() / CLIENT_FILE))
    return client_id, client_secret


def _save_refresh_token(token):
    folder = keys_dir()
    folder.mkdir(parents=True, exist_ok=True)
    text = ("# Refresh token de Google (drive.readonly) de Shot Marks de HieroTools.\n"
            "%s=%s\n" % (REFRESH_VAR, token))
    with open(str(folder / TOKEN_FILE), "w", newline="\n", encoding="utf-8") as handle:
        handle.write(text)


# -- red -----------------------------------------------------------------------

def _open(request, log, timeout=120):
    """urlopen con reintentos ante errores de conexion (no ante HTTP)."""
    for attempt in range(1, ATTEMPTS + 1):
        try:
            return urllib.request.urlopen(request, timeout=timeout)
        except urllib.error.HTTPError:
            raise
        except urllib.error.URLError as exc:
            host = urllib.parse.urlparse(request.full_url).netloc
            log("Sin conexion a %s (intento %d de %d): %s" % (host, attempt, ATTEMPTS, exc.reason))
            if attempt == ATTEMPTS:
                raise GoogleSheetError(
                    "Could not connect to %s. If a firewall asked about Nuke Studio, allow it "
                    "and open the sheet again." % host)
            time.sleep(RETRY_WAIT)


def _http_error_text(exc):
    try:
        err = json.loads(exc.read().decode("utf-8", "replace")).get("error", {})
        if isinstance(err, dict):
            reasons = ",".join(e.get("reason", "") for e in err.get("errors", []))
            return "%s %s (%s)" % (exc.code, err.get("message", ""), reasons)
        return "%s %s" % (exc.code, err)
    except Exception:
        return str(exc.code)


def _post_form(url, fields, log):
    data = urllib.parse.urlencode(fields).encode("ascii")
    with _open(urllib.request.Request(url, data=data, method="POST"), log, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def _get(url, token, log, timeout=120):
    request = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})
    return _open(request, log, timeout)


def open_default(url):
    """Programa por defecto del sistema, nunca un navegador por nombre."""
    if sys.platform == "darwin":
        import subprocess
        subprocess.Popen(["open", url])
    elif os.name == "nt":
        os.startfile(url)
    else:
        import subprocess
        subprocess.Popen(["xdg-open", url])


# -- login ---------------------------------------------------------------------

def login(client_id, client_secret, log, open_url=open_default):
    """Login de app de escritorio con PKCE y callback en loopback. Bloquea
    hasta LOGIN_TIMEOUT: llamarlo fuera del hilo de UI."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode("ascii")
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    state = secrets.token_urlsafe(24)
    result = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if query.get("state", [""])[0] != state:
                self.send_response(400)
                self.end_headers()
                return
            result["code"] = query.get("code", [""])[0]
            result["error"] = query.get("error", [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            text = ("Signed in. You can close this tab and go back to Nuke Studio."
                    if result["code"] else "Sign-in cancelled: %s" % result["error"])
            self.wfile.write(("<html><body style='font-family:sans-serif'>%s</body></html>"
                              % text).encode("utf-8"))

        def log_message(self, *_args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    server.timeout = 1
    redirect = "http://127.0.0.1:%d" % server.server_address[1]
    url = AUTH_URL + "?" + urllib.parse.urlencode({
        "client_id": client_id, "redirect_uri": redirect, "response_type": "code",
        "scope": SCOPE, "access_type": "offline", "prompt": "consent",
        "code_challenge": challenge, "code_challenge_method": "S256", "state": state,
    })
    log("Login de Google: callback en %s, se abre el navegador por defecto" % redirect)
    open_url(url)
    start = time.time()
    try:
        while "code" not in result and time.time() - start < LOGIN_TIMEOUT:
            server.handle_request()
    finally:
        server.server_close()
    if not result.get("code"):
        raise GoogleSheetError("Google sign-in did not finish (%s)."
                               % (result.get("error") or "no answer in %d s" % LOGIN_TIMEOUT))
    tokens = _post_form(TOKEN_URL, {
        "code": result["code"], "client_id": client_id, "client_secret": client_secret,
        "redirect_uri": redirect, "grant_type": "authorization_code", "code_verifier": verifier,
    }, log)
    log("Login de Google: OK en %.1f s" % (time.time() - start))
    if tokens.get("refresh_token"):
        _save_refresh_token(tokens["refresh_token"])
    else:
        log("AVISO: Google no devolvio refresh token; el proximo uso pide login de nuevo")
    return tokens["access_token"]


def access_token(log, open_url=open_default):
    """Token de acceso: renueva el guardado y, si no hay o lo rechazan, pide login."""
    client_id, client_secret = client_credentials()
    refresh = read_key(TOKEN_FILE, REFRESH_VAR)
    if refresh:
        try:
            tokens = _post_form(TOKEN_URL, {
                "client_id": client_id, "client_secret": client_secret,
                "refresh_token": refresh, "grant_type": "refresh_token",
            }, log)
            return tokens["access_token"]
        except urllib.error.HTTPError as exc:
            log("Refresh token rechazado (%s): se pide login" % _http_error_text(exc))
    return login(client_id, client_secret, log, open_url)


# -- cache y descarga ----------------------------------------------------------

def cache_dir():
    if sys.platform == "win32":
        root = os.getenv("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        root = str(Path.home() / "Library" / "Caches")
    else:
        root = str(Path.home() / ".cache")
    return Path(root) / "LGA" / "HieroTools" / "ShotMarks_Google"


def _read_meta(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def cached(file_id, folder=None):
    """{path, title, modified} de la copia local, o None."""
    folder = Path(folder) if folder else cache_dir()
    xlsx, meta = folder / (file_id + ".xlsx"), _read_meta(folder / (file_id + ".json"))
    if xlsx.is_file() and meta:
        return {"path": str(xlsx), "title": meta.get("title", ""),
                "modified": meta.get("modifiedTime", "")}
    return None


def needs_download(meta, local):
    """Se baja si no hay copia o si la planilla cambio desde que se bajo."""
    return local is None or local.get("modified") != meta.get("modifiedTime")


def _download(url, token, dest, log):
    start = time.time()
    tmp = dest.with_name(dest.name + ".part")
    size = 0
    try:
        response = _get(url, token, log, timeout=180)
    except urllib.error.HTTPError as exc:
        raise GoogleSheetError("Google did not export the sheet: %s" % _http_error_text(exc))
    with response, open(str(tmp), "wb") as handle:
        while True:
            chunk = response.read(CHUNK)
            if not chunk:
                break
            handle.write(chunk)
            size += len(chunk)
    with open(str(tmp), "rb") as handle:
        if handle.read(2) != b"PK":
            tmp.unlink()
            raise GoogleSheetError("Google sent something that is not an xlsx file.")
    tmp.replace(dest)
    log("Descargada: %.1f MB en %.1f s" % (size / 1e6, time.time() - start))
    return size


def fetch(link, log=None, open_url=open_default, folder=None, force=False):
    """Deja la planilla del link en la cache y devuelve
    {path, title, modified, downloaded, stale}. Bloquea (red y quiza login):
    llamarlo fuera del hilo de UI.

    stale=True: no hubo conexion y se usa la copia anterior.
    """
    log = log or (lambda _msg: None)
    file_id = sheet_id(link)
    if not file_id:
        raise GoogleSheetError("This is not a Google Sheets link.")
    folder = Path(folder) if folder else cache_dir()
    folder.mkdir(parents=True, exist_ok=True)
    local = cached(file_id, folder)
    start = time.time()
    try:
        token = access_token(log, open_url)
        fields = "id,name,mimeType,modifiedTime,exportLinks"
        try:
            with _get(DRIVE_FILES + file_id + "?supportsAllDrives=true&fields=" + fields,
                      token, log) as response:
                meta = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise GoogleSheetError("Google says this sheet does not exist or your account "
                                       "cannot open it.")
            raise GoogleSheetError("Google did not answer about the sheet: %s"
                                   % _http_error_text(exc))
    except GoogleSheetError as exc:
        if local and "connect" in str(exc):
            log("Sin conexion: se usa la copia del %s" % local["modified"])
            return dict(local, downloaded=False, stale=True)
        raise
    if meta.get("mimeType") != SHEET_MIME:
        raise GoogleSheetError("The link is not a Google Sheets spreadsheet.")
    log("Planilla de Google: modificada %s (consulta %.2f s)" % (meta.get("modifiedTime"),
                                                                 time.time() - start))
    downloaded = False
    if force or needs_download(meta, local):
        link_xlsx = (meta.get("exportLinks") or {}).get(XLSX_MIME)
        if not link_xlsx:
            raise GoogleSheetError("Google does not offer this sheet as xlsx.")
        try:
            _download(link_xlsx, token, folder / (file_id + ".xlsx"), log)
        except GoogleSheetError as exc:
            if local and "connect" in str(exc):
                log("Sin conexion al bajarla: se usa la copia del %s" % local["modified"])
                return dict(local, downloaded=False, stale=True)
            raise
        with open(str(folder / (file_id + ".json")), "w", newline="\n", encoding="utf-8") as handle:
            json.dump({"title": meta.get("name", ""), "modifiedTime": meta.get("modifiedTime", "")},
                      handle, ensure_ascii=False)
        downloaded = True
    else:
        log("Sin cambios desde la ultima descarga: se usa la copia local")
    return {"path": str(folder / (file_id + ".xlsx")), "title": meta.get("name", ""),
            "modified": meta.get("modifiedTime", ""), "downloaded": downloaded, "stale": False}
