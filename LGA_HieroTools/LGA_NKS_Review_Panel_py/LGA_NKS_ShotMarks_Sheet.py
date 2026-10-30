"""
____________________________________________________________________

  LGA_NKS_ShotMarks_Sheet v1.08 | Lega

  Nucleo sin host de Shot Marks: lee una planilla (xlsx o csv),
  detecta la fila de encabezado y las columnas de shot y timecode,
  y arma el plan de marcas (cuadro de timeline por shot) con la
  lista de problemas de cada fila. No importa hiero ni Qt: se
  prueba con unittest y corre fuera del hilo de UI.

  El xlsx se lee con zipfile + iterparse (solo el XML de la hoja y
  los sharedStrings), sin openpyxl: NKS no lo trae, y asi una
  planilla de cientos de MB por las imagenes se lee en segundos.

  v1.08: search_marks / find_match / next_match: la busqueda de la
         ventana Find Shot Mark (texto en cualquier campo de la marca,
         sin mayusculas ni acentos; Find prefiere el shot con ese nombre
         exacto y Next sigue desde el resultado o el playhead).
  v1.07: compare_marks / previous_mark / change_counts: diferencias por
         shot contra la corrida anterior (sin cambios, cambio de algun
         campo de CHANGE_FIELDS, nuevo, ya no esta o no se ubica). La
         metadata del tag guarda el cambio y el texto anterior de lo que
         cambio. META_FIELDS pasa a ser publico.
  v1.06: CSV: del Sniffer solo se toma el separador; las comillas van
         siempre como Excel/Google (""). Un brief de varias lineas que
         empezaba con comilla se cortaba en la primera linea.
  v1.05: follow_ends: para seguir al playhead, una marca de un cuadro
         llega hasta la siguiente (si no, solo se veia al pisar su IN).
  v1.04: Columna LGA Clip (clip de camara, SRC TC IN/OUT y evento del
         EDL del armado) para las filas ubicadas con EDL: viaja a la
         metadata del tag como rol "clip" ("source" ya era el origen de
         la marca: archivo y hoja). clip_text / parse_clip.
  v1.03: Hojas sin timecode (solo shot + thumbnail): load_table las acepta
         con require_tc=False y with_located_timecodes les suma las
         columnas de TC que ubico el motor de thumbnails, mas el thumb y
         el nivel de confianza de cada fila. is_omit ya no descarta
         "POSIBLE VFX OMIT (en corte)": un posible omit sigue en el corte.
         status_kind distingue omit de posible omit para colorearlos.
         Columnas "STATUS VFX" y "VFX Brief"; is_shot_name descarta los
         titulos de grupo ("PROJA_001_") de una hoja con thumbnails.
  v1.02: mark_index_at: que marca cubre un cuadro, para que la ventana
         de Previous/Next Mark siga al playhead.
  v1.01: Columnas de descripcion, escena, vendor y categoria; cada marca
         lleva su info para la ventana de Previous/Next Mark.
  v1.00: Version inicial.
____________________________________________________________________
"""

import bisect
import csv
import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

XLSX_MAIN_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
XLSX_REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
XLSX_PKG_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
CELL_REF_RE = re.compile(r"^([A-Z]+)([0-9]+)$")
TC_RE = re.compile(r"^(\d{1,2})[:;.](\d{2})[:;.](\d{2})[:;.](\d{2})$")

# Filas maximas donde se busca el encabezado y columnas maximas por fila.
HEADER_SEARCH_ROWS = 60
MAX_COLUMNS = 400

# Encabezados normalizados (minusculas, sin espacios ni simbolos) por rol.
# El orden es la prioridad: REC TC gana sobre TC a secas, y nunca se toma
# ST IN / SOURCE IN, que es el timecode de camara y no el del montaje.
SHOT_HEADERS = ("shotname", "shot", "shotcode", "vfxshot", "vfxshotname", "tcn")
TC_IN_HEADERS = (
    "rectcin", "recordtcin", "recin", "recordin", "rectc", "tcin",
    "timecodein", "mastertc", "start", "rectcinlocated",
)
TC_OUT_HEADERS = (
    "rectcout", "recordtcout", "recout", "recordout", "tcout",
    "timecodeout", "end", "rectcoutlocated",
)
EPISODE_HEADERS = ("ep", "episode", "episodio", "epi", "reel")
STATUS_HEADERS = ("status", "estado", "shotstatus", "statusvfx", "vfxstatus", "estadovfx")
# "note" es el brief: va a la nota del tag. La descripcion es aparte.
NOTE_HEADERS = ("brief", "vfxbrief", "notes", "notas", "vfxnotes")
DESCRIPTION_HEADERS = ("descripcion", "description", "desc", "shotdescription")
SCENE_HEADERS = ("esc", "escena", "scene", "sc")
VENDOR_HEADERS = ("vendor", "proveedor")
CATEGORY_HEADERS = ("shotcategory", "category", "categoria", "type")
# Columnas que agrega Shot Marks cuando ubica los TC desde los thumbnails.
LOCATED_TC_IN = "REC TC IN (located)"
LOCATED_TC_OUT = "REC TC OUT (located)"
LOCATED_THUMB = "LGA Thumb"
LOCATED_LEVEL = "LGA Located"
LOCATED_CLIP = "LGA Clip"
THUMB_HEADERS = ("lgathumb",)
LOCATED_HEADERS = ("lgalocated",)
CLIP_HEADERS = ("lgaclip",)

OMIT_TOKENS = ("omit", "omitted", "cbb", "removed")
# "POSIBLE VFX OMIT (en corte)": todavia esta en el corte, se marca.
MAYBE_TOKENS = ("posible", "possible", "maybe", "tentative")

ROLES = ("shot", "tc_in", "tc_out", "episode", "status", "note",
         "description", "scene", "vendor", "category", "thumb", "located", "clip")
# Roles que viajan como texto a cada marca, para la ventana de info.
INFO_ROLES = ("status", "description", "scene", "vendor", "category", "episode",
              "thumb", "located", "clip")
# Campos que, si cambian entre una corrida y la siguiente, pintan la marca de
# amarillo. El TC no esta: un shot que se movio es un cambio de corte, no de
# planilla. Thumb, nivel de ubicacion y clip tampoco: salen de Shot Marks.
CHANGE_FIELDS = ("brief", "description", "status", "scene", "vendor", "category")
CHANGE_UNCHANGED = "unchanged"
CHANGE_CHANGED = "changed"
CHANGE_NEW = "new"
CHANGE_REMOVED = "removed"
_ROLE_HEADERS = {
    "shot": SHOT_HEADERS,
    "tc_in": TC_IN_HEADERS,
    "tc_out": TC_OUT_HEADERS,
    "episode": EPISODE_HEADERS,
    "status": STATUS_HEADERS,
    "note": NOTE_HEADERS,
    "description": DESCRIPTION_HEADERS,
    "scene": SCENE_HEADERS,
    "vendor": VENDOR_HEADERS,
    "category": CATEGORY_HEADERS,
    "thumb": THUMB_HEADERS,
    "located": LOCATED_HEADERS,
    "clip": CLIP_HEADERS,
}


class Table(object):
    """Planilla ya leida: encabezados unicos y filas de texto."""

    def __init__(self, path, sheet, header_row, headers, rows):
        self.path = path
        self.sheet = sheet
        self.header_row = header_row  # numero de fila (1-based) del encabezado
        self.headers = headers
        self.rows = rows  # lista de (numero_de_fila, [valores str])

    def column_values(self, index):
        values = []
        for _number, row in self.rows:
            if index is not None and index < len(row) and row[index]:
                values.append(row[index])
        return values


class Mark(object):
    def __init__(self, row, shot, frame_in, frame_out, tc_in, tc_out, note, info=None):
        self.row = row
        self.shot = shot
        self.frame_in = frame_in
        self.frame_out = frame_out  # inclusivo
        self.tc_in = tc_in
        self.tc_out = tc_out
        self.note = note
        self.info = info or {}  # {rol: texto} de INFO_ROLES con valor
        # Contra la corrida anterior (compare_marks): CHANGE_* o "" en la
        # primera corrida, y los campos que cambiaron {campo: texto anterior}.
        self.change = ""
        self.changed = {}

    def field_values(self):
        """{campo: texto} de CHANGE_FIELDS, para comparar contra el tag anterior."""
        values = {"brief": self.note}
        for field in CHANGE_FIELDS[1:]:
            values[field] = self.info.get(field, "")
        return values


class Issue(object):
    def __init__(self, row, shot, tc_in, message, written):
        self.row = row
        self.shot = shot
        self.tc_in = tc_in
        self.message = message
        self.written = written  # True: se escribe igual, es solo aviso


class Plan(object):
    def __init__(self):
        self.marks = []
        self.issues = []
        self.skipped_omit = 0
        self.skipped_episode = 0

    def errors(self):
        return [i for i in self.issues if not i.written]

    def warnings(self):
        return [i for i in self.issues if i.written]


# -- texto -----------------------------------------------------------------

def normalize_header(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", "", text)


def normalize_episode(value):
    """'101.0' y '101' son el mismo episodio: Excel guarda el numero como float."""
    text = str(value or "").strip()
    if re.fullmatch(r"\d+\.0+", text):
        return text.split(".")[0]
    return text


def cell_text(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def make_unique_headers(raw_headers):
    headers = []
    seen = {}
    for index, raw in enumerate(raw_headers):
        base = str(raw or "").strip() or "Column %s" % column_letters(index)
        count = seen.get(base, 0) + 1
        seen[base] = count
        headers.append(base if count == 1 else "%s (%d)" % (base, count))
    return headers


def column_letters(index):
    letters = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(65 + rest) + letters
    return letters


def _cell_column(ref):
    match = CELL_REF_RE.match((ref or "").upper().replace("$", ""))
    if not match:
        return None
    col = 0
    for char in match.group(1):
        col = col * 26 + (ord(char) - 64)
    return col - 1


# -- xlsx ------------------------------------------------------------------

def list_sheets(path):
    """Nombres de hoja en orden; csv devuelve una sola hoja sin nombre."""
    path = Path(path)
    if path.suffix.lower() == ".csv":
        return [""]
    with zipfile.ZipFile(str(path)) as archive:
        root = ET.fromstring(archive.read("xl/workbook.xml"))
        return [str(n.get("name") or "") for n in root.iter(XLSX_MAIN_NS + "sheet")]


def _sheet_xml_path(archive, sheet_name):
    root = ET.fromstring(archive.read("xl/workbook.xml"))
    rel_id = ""
    for node in root.iter(XLSX_MAIN_NS + "sheet"):
        if str(node.get("name") or "") == sheet_name:
            rel_id = str(node.get(XLSX_REL_NS + "id") or "")
            break
    if not rel_id:
        raise ValueError("La hoja '%s' no existe en el archivo." % sheet_name)
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    for node in rels.iter(XLSX_PKG_REL_NS + "Relationship"):
        if str(node.get("Id") or "") == rel_id:
            target = str(node.get("Target") or "").lstrip("/")
            return target if target.startswith("xl/") else "xl/" + target
    raise ValueError("No se encontro el XML de la hoja '%s'." % sheet_name)


def _shared_strings(archive):
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    strings = []
    with archive.open("xl/sharedStrings.xml") as handle:
        for _event, node in ET.iterparse(handle):
            if node.tag == XLSX_MAIN_NS + "si":
                # Texto enriquecido: un <si> puede traer varios <r><t>.
                strings.append("".join(t.text or "" for t in node.iter(XLSX_MAIN_NS + "t")))
                node.clear()
    return strings


def _iter_xlsx_rows(archive, xml_path, strings, max_rows=None):
    """(numero_de_fila, [valores]) de cada fila con algun dato."""
    with archive.open(xml_path) as handle:
        for _event, node in ET.iterparse(handle):
            if node.tag != XLSX_MAIN_NS + "row":
                continue
            number = int(node.get("r") or 0)
            values = {}
            for cell in node.iter(XLSX_MAIN_NS + "c"):
                col = _cell_column(cell.get("r"))
                if col is None or col >= MAX_COLUMNS:
                    continue
                kind = cell.get("t") or "n"
                if kind == "inlineStr":
                    text = "".join(t.text or "" for t in cell.iter(XLSX_MAIN_NS + "t"))
                else:
                    raw = cell.find(XLSX_MAIN_NS + "v")
                    text = raw.text if raw is not None and raw.text is not None else ""
                    if kind == "s" and text:
                        index = int(text)
                        text = strings[index] if index < len(strings) else ""
                    elif kind == "n" and text:
                        try:
                            text = cell_text(float(text))
                        except ValueError:
                            pass
                text = text.strip()
                if text:
                    values[col] = text
            node.clear()
            if values:
                row = [""] * (max(values) + 1)
                for col, text in values.items():
                    row[col] = text
                yield number, row
            if max_rows is not None and number >= max_rows:
                return


def _read_rows(path, sheet, max_rows=None):
    path = Path(path)
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            sample = handle.read(4096)
            handle.seek(0)
            # Del Sniffer solo se toma el separador. Las comillas se leen
            # siempre como las escriben Excel y Google Sheets (comilla doble
            # escapada como ""): si en la muestra no hay ningun "", el
            # Sniffer adivina doublequote=False y una celda que empieza con
            # comilla ("""-Agregado...) se corta en la primera linea y el
            # resto se derrama en filas sueltas.
            try:
                delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t").delimiter
            except csv.Error:
                delimiter = ","
            rows = []
            for number, values in enumerate(csv.reader(handle, csv.excel, delimiter=delimiter),
                                            start=1):
                cleaned = [str(v or "").strip() for v in values[:MAX_COLUMNS]]
                if any(cleaned):
                    rows.append((number, cleaned))
                if max_rows is not None and number >= max_rows:
                    break
            return rows
    with zipfile.ZipFile(str(path)) as archive:
        xml_path = _sheet_xml_path(archive, sheet)
        strings = _shared_strings(archive)
        return list(_iter_xlsx_rows(archive, xml_path, strings, max_rows))


# -- encabezado y columnas -------------------------------------------------

def _header_score(values, require_tc=True):
    """Cuanto se parece una fila a un encabezado de breakdown con timecode.

    Sin require_tc solo cuenta la columna de shot: es la hoja que tiene
    thumbnails en lugar de timecode.
    """
    norm = [normalize_header(v) for v in values]
    score = 0
    if any(n in SHOT_HEADERS for n in norm):
        score += 2
    if not require_tc:
        return score + (1 if "shotname" in norm else 0)
    if any(n in TC_IN_HEADERS for n in norm):
        score += 2
    if any(n in TC_OUT_HEADERS for n in norm):
        score += 1
    # Bonus a los nombres explicitos de montaje: desempata contra hojas de
    # EDL o de bid que tienen "Timecode In" o "Shot" a secas.
    if "shotname" in norm:
        score += 1
    if any(n.startswith("rec") for n in norm if n in TC_IN_HEADERS):
        score += 1
    return score


def detect_header_row(rows, require_tc=True):
    """Indice en `rows` de la fila de encabezado, o None si ninguna sirve."""
    best_index, best_score = None, 0
    for index, (_number, values) in enumerate(rows[:HEADER_SEARCH_ROWS]):
        score = _header_score(values, require_tc)
        if score > best_score:
            best_index, best_score = index, score
    # Hace falta al menos shot + tc in (o solo shot, sin require_tc).
    return best_index if best_score >= (4 if require_tc else 2) else None


def detect_columns(headers):
    """{rol: indice de columna o None}, por prioridad de nombres conocidos."""
    norm = [normalize_header(h) for h in headers]
    result = {}
    for role in ROLES:
        result[role] = None
        for candidate in _ROLE_HEADERS[role]:
            if candidate in norm:
                result[role] = norm.index(candidate)
                break
    return result


def _rows_score(rows, require_tc=True):
    index = detect_header_row(rows, require_tc)
    return _header_score(rows[index][1], require_tc) if index is not None else 0


def suggest_sheet(path, sheets=None):
    """La hoja con mejor encabezado de shot + timecode, o None.

    El zip y los sharedStrings se abren una sola vez: releerlos por hoja
    costaba 14 s en una planilla real de 55 hojas.
    """
    path = Path(path)
    if path.suffix.lower() == ".csv":
        return "" if _rows_score(_read_rows(path, "", HEADER_SEARCH_ROWS)) else None
    best, best_score = None, 0
    shot_only, shot_score = None, 0
    with zipfile.ZipFile(str(path)) as archive:
        strings = _shared_strings(archive)
        for sheet in sheets if sheets is not None else list_sheets(path):
            try:
                xml_path = _sheet_xml_path(archive, sheet)
                rows = list(_iter_xlsx_rows(archive, xml_path, strings, HEADER_SEARCH_ROWS))
            except Exception:
                continue
            score = _rows_score(rows)
            if score > best_score:
                best, best_score = sheet, score
            score = _rows_score(rows, require_tc=False)
            if score > shot_score:
                shot_only, shot_score = sheet, score
    # Sin ninguna hoja con timecode: la que mejor parece de shots (thumbnails).
    return best if best is not None else shot_only


def load_table(path, sheet, require_tc=True):
    """Tabla de la hoja. Sin require_tc alcanza con la columna de shot."""
    rows = _read_rows(path, sheet)
    if not rows:
        raise ValueError("La hoja esta vacia.")
    index = detect_header_row(rows)
    if index is None and not require_tc:
        index = detect_header_row(rows, require_tc=False)
    if index is None:
        raise ValueError(
            "No se encontro una fila de encabezado con columnas de shot y timecode."
        )
    header_number, header_values = rows[index]
    headers = make_unique_headers(header_values)
    width = len(headers)
    data = []
    for number, values in rows[index + 1:]:
        padded = (values + [""] * width)[:max(width, len(values))]
        data.append((number, padded))
    return Table(str(path), sheet, header_number, headers, data)


# -- metadata del tag ------------------------------------------------------

# Las keys de metadata de un Tag tienen que empezar con "tag.": si no,
# DataCollection.setValue tira RuntimeError.
META_KEY = "tag.lga_shotmarks"
META_FIELDS = ("row", "source", "tc_in", "tc_out", "brief") + INFO_ROLES


def meta_key(field):
    return "%s_%s" % (META_KEY, field)


def mark_metadata(mark, source):
    """{key: texto} que se guarda en el tag de una marca."""
    values = {
        META_KEY: "1",
        meta_key("row"): str(mark.row),
        meta_key("source"): source,
        meta_key("tc_in"): mark.tc_in,
        meta_key("tc_out"): mark.tc_out,
        meta_key("brief"): mark.note,
    }
    for role, text in mark.info.items():
        values[meta_key(role)] = text
    if mark.change:
        values[meta_key("change")] = mark.change
        values[meta_key("changed")] = ",".join(f for f in CHANGE_FIELDS if f in mark.changed)
        for field, before in mark.changed.items():
            values[meta_key("prev_" + field)] = before
    return values


def mark_info_from_metadata(get):
    """Lee lo guardado por mark_metadata. `get(key)` devuelve texto o None.

    Los tags creados por la v1.00 solo tienen fila y origen: lo que falta
    vuelve vacio y la ventana avisa que hay que volver a correr Shot Marks.
    "change" es CHANGE_* (o "" si la marca es de la primera corrida) y
    "changed", {campo: texto anterior} de lo que cambio.
    """
    info = {}
    for field in META_FIELDS:
        value = get(meta_key(field))
        info[field] = str(value) if value is not None else ""
    info["complete"] = get(meta_key("tc_in")) is not None
    info["change"] = str(get(meta_key("change")) or "")
    # Solo en las rojas cuyo shot sigue en la planilla: por que no se ubico.
    info["change_reason"] = str(get(meta_key("change_reason")) or "")
    info["changed"] = {}
    for field in str(get(meta_key("changed")) or "").split(","):
        if field:
            before = get(meta_key("prev_" + field))
            info["changed"][field] = str(before) if before is not None else ""
    return info


# -- diferencias contra la corrida anterior ---------------------------------

def _comparable(text):
    """Texto para comparar: sin diferencias de fin de linea ni espacios sobrantes."""
    text = str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    return "\n".join(line.rstrip() for line in text.split("\n"))


def previous_mark(shot, frame_in, frame_out, get, note=""):
    """Lo que hace falta de un tag propio anterior para compararlo.

    `get(key)` lee su metadata. Los tags de la v1.00 no guardaban columnas:
    de esos solo se compara el brief (la nota del tag).
    """
    info = mark_info_from_metadata(get)
    if not info["brief"]:
        info["brief"] = note
    fields = CHANGE_FIELDS if info["complete"] else ("brief",)
    return {
        "shot": shot,
        "frame_in": int(frame_in),
        "frame_out": int(frame_out),
        "values": {field: info.get(field, "") for field in fields},
        "change": info["change"],
    }


def compare_marks(marks, previous, issues=()):
    """Compara las marcas nuevas contra las de la corrida anterior.

    Pone en cada marca `change` (CHANGE_UNCHANGED, CHANGE_CHANGED o
    CHANGE_NEW) y en `changed` los campos que cambiaron con su texto
    anterior. Devuelve las anteriores que ya no estan (CHANGE_REMOVED), cada
    una con "reason": vacio si el shot ya no esta en la planilla, o el motivo
    si esta pero no se pudo ubicar (`issues` del plan que no se escriben, por
    ejemplo "Outside the timeline" cuando la planilla ya es de otro corte).

    Se empareja por nombre de shot; un shot repetido se empareja en orden de
    IN. Que el shot se haya movido no es un cambio: es otro corte. Las marcas
    que la corrida anterior ya dio por borradas no cuentan: se avisaron una
    vez y se van; si el shot vuelve, es nuevo.
    """
    by_shot = {}
    for old in sorted(previous, key=lambda p: (p["frame_in"], p["shot"])):
        if old.get("change") != CHANGE_REMOVED:
            by_shot.setdefault(old["shot"], []).append(old)
    for mark in sorted(marks, key=lambda m: (m.frame_in, m.row)):
        olds = by_shot.get(mark.shot)
        if not olds:
            mark.change, mark.changed = CHANGE_NEW, {}
            continue
        old = olds.pop(0)
        current = mark.field_values()
        mark.changed = {field: before for field, before in old["values"].items()
                        if _comparable(before) != _comparable(current.get(field, ""))}
        mark.change = CHANGE_CHANGED if mark.changed else CHANGE_UNCHANGED
    unplaced = {}
    for issue in issues:
        if not issue.written and issue.shot:
            unplaced.setdefault(issue.shot, issue.message)
    removed = [dict(old, reason=unplaced.get(old["shot"], ""))
               for olds in by_shot.values() for old in olds]
    removed.sort(key=lambda p: (p["frame_in"], p["shot"]))
    return removed


def change_counts(marks, removed):
    """{CHANGE_*: cantidad} para el resumen del dialogo. "unplaced" son las
    rojas cuyo shot sigue en la planilla pero no se pudo ubicar."""
    counts = {CHANGE_UNCHANGED: 0, CHANGE_CHANGED: 0, CHANGE_NEW: 0,
              CHANGE_REMOVED: len(removed),
              "unplaced": sum(1 for old in removed if old.get("reason"))}
    for mark in marks:
        if mark.change in counts:
            counts[mark.change] += 1
    return counts


def next_mark_index(starts, current, direction):
    """Indice de la marca a la que salta Next/Previous Mark, o None si no hay.

    `starts` son los IN ordenados. Next va al primer IN despues del playhead;
    Previous, al ultimo antes (si el playhead esta adentro de un shot, vuelve
    a su IN). En los extremos da la vuelta, como las anotaciones (Shift+Click).
    """
    if not starts:
        return None
    if direction == "next":
        for index, start in enumerate(starts):
            if start > current:
                return index
        return 0
    for index in range(len(starts) - 1, -1, -1):
        if starts[index] < current:
            return index
    return len(starts) - 1


def mark_index_at(starts, ends, frame):
    """Indice de la marca que cubre `frame` (IN y OUT inclusivos), o None.

    La llama la ventana de Previous/Next Mark en CADA cambio de cuadro del
    visor, tambien durante el playback: por eso es una busqueda binaria sobre
    listas ya armadas y no recorre los tags. `starts` va ordenado. Si dos
    marcas se solapan (shot repetido en la planilla), gana la que empieza
    mas tarde.
    """
    # Entre dos marcas el retroceso recorre las anteriores (una marca larga y
    # solapada podria cubrir el cuadro): con 200 marcas son microsegundos.
    for index in range(bisect.bisect_right(starts, frame) - 1, -1, -1):
        if ends[index] >= frame:
            return index
    return None


# -- busqueda (ventana Find Shot Mark) ---------------------------------------

# Campos donde busca Find Shot Mark. El orden decide que campo se informa
# cuando el texto aparece en varios: el shot primero.
SEARCH_FIELDS = ("shot", "description", "brief", "status", "vendor", "scene",
                 "category", "episode", "tc_in", "tc_out", "clip")


def search_text(text):
    """Texto comparable: sin mayusculas ni acentos y con los espacios unidos.

    Los espacios se unen porque un brief de varias lineas trae saltos donde el
    usuario escribe un espacio.
    """
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()
    return " ".join(text.split())


def search_marks(entries, query):
    """[(indice, campo)] de las marcas que contienen `query`.

    `entries` son {campo: texto} de cada marca, en orden de timeline. El campo
    es el primero de SEARCH_FIELDS donde aparece. Sin texto, no hay resultados.
    """
    needle = search_text(query)
    if not needle:
        return []
    matches = []
    for index, entry in enumerate(entries):
        for field in SEARCH_FIELDS:
            if needle in search_text(entry.get(field)):
                matches.append((index, field))
                break
    return matches


def find_match(matches, entries, query):
    """Posicion en `matches` del resultado de Find, o None si no hay.

    Gana el shot que se llama exactamente asi: buscar "PROJA_010_0100" no
    tiene que caer en "PROJA_010_01000" ni en un brief que lo nombre. Si no
    hay nombre exacto, el primer resultado del timeline.
    """
    if not matches:
        return None
    needle = search_text(query)
    for position, (index, _field) in enumerate(matches):
        if search_text(entries[index].get("shot")) == needle:
            return position
    return 0


def next_match(matches, starts, frame, current=None):
    """(posicion en `matches`, dio la vuelta) del resultado de Next.

    `starts` son los IN de todas las marcas. Si el playhead sigue en el IN del
    resultado mostrado (`current`, indice de marca), se avanza desde esa marca:
    dos marcas pueden empezar en el mismo cuadro. Si el usuario movio el
    playhead, desde el playhead. Despues del ultimo vuelve al primero.
    """
    if not matches:
        return None, False
    from_current = current is not None and starts[current] == frame
    for position, (index, _field) in enumerate(matches):
        if (index > current) if from_current else (starts[index] > frame):
            return position, False
    return 0, True


def follow_ends(starts, ends, last_frame):
    """OUT para seguir al playhead: una marca de un cuadro llega hasta la siguiente.

    Una fila con IN = OUT o sin OUT queda como marca de un cuadro (el IN alcanza
    para Previous/Next). Pero la ventana busca la marca que CUBRE el cuadro, y
    al arrastrar el playhead casi nunca se cae justo en ese cuadro: medido en
    un episodio con las 174 marcas de un cuadro, la ventana solo cambiaba al
    pisar el IN exacto. Esas marcas se estiran hasta el cuadro anterior a la
    siguiente que empiece despues (o hasta `last_frame` si es la ultima). Las
    marcas con rango real no se tocan. `starts` va ordenado.
    """
    result = list(ends)
    for index, (start, end) in enumerate(zip(starts, ends)):
        if end > start:
            continue
        following = bisect.bisect_right(starts, start)
        result[index] = starts[following] - 1 if following < len(starts) else max(last_frame, start)
    return result


# -- timecode y plan -------------------------------------------------------

def parse_timecode(text, fps):
    """Cuadros totales de un 'HH:MM:SS:FF' no drop-frame, o None si no es TC."""
    match = TC_RE.match(str(text or "").strip())
    if not match:
        return None
    hours, minutes, seconds, frames = (int(g) for g in match.groups())
    if minutes > 59 or seconds > 59 or frames >= fps:
        return None
    return ((hours * 60 + minutes) * 60 + seconds) * fps + frames


def format_timecode(frames, fps):
    frames = max(0, int(frames))
    seconds, ff = divmod(frames, fps)
    minutes, ss = divmod(seconds, 60)
    hh, mm = divmod(minutes, 60)
    return "%02d:%02d:%02d:%02d" % (hh, mm, ss, ff)


def status_kind(status):
    """'omit', 'maybe_omit' o '' segun el texto del status."""
    norm = normalize_header(status)
    if not any(token in norm for token in OMIT_TOKENS):
        return ""
    return "maybe_omit" if any(token in norm for token in MAYBE_TOKENS) else "omit"


def is_shot_name(text):
    """Falso para los titulos de grupo de una planilla ("PROJA_001_", "PROJA_001-"):
    son filas de seccion, a veces con foto, y no se ubican ni se marcan."""
    text = str(text or "").strip()
    return bool(text) and not text.endswith(("_", "-", "."))


def is_omit(status):
    return status_kind(status) == "omit"


def with_located_timecodes(table, located):
    """Copia de la tabla con las columnas que ubico el motor de thumbnails.

    `located` = {fila: {"tc_in", "tc_out", "thumb", "level", "clip"}}; el
    TC OUT va exclusivo, como en una planilla de montaje. "clip" es el
    texto de clip_text (solo si se ubico con EDL). Las filas sin entrada
    quedan vacias y build_plan las reporta como "No TC IN".
    """
    headers = list(table.headers) + [LOCATED_TC_IN, LOCATED_TC_OUT, LOCATED_THUMB,
                                     LOCATED_LEVEL, LOCATED_CLIP]
    width = len(table.headers)
    rows = []
    for number, values in table.rows:
        entry = located.get(number) or {}
        padded = (list(values) + [""] * width)[:width]
        rows.append((number, padded + [entry.get("tc_in", ""), entry.get("tc_out", ""),
                                       entry.get("thumb", ""), entry.get("level", ""),
                                       entry.get("clip", "")]))
    return Table(table.path, table.sheet, table.header_row, headers, rows)


def clip_text(info):
    """Clip y SRC TC de un plano del EDL en una linea para la planilla y el tag:
    'clip | src in | src out | evento'. Vacio sin info."""
    if not info:
        return ""
    return " | ".join([str(info["clip"]), str(info["src_in"]), str(info["src_out"]),
                       str(info["event"])])


def parse_clip(text):
    """Inversa de clip_text: {clip, src_in, src_out, event}, o {} si no aplica."""
    parts = [p.strip() for p in str(text or "").split("|")]
    if len(parts) != 4 or not parts[0]:
        return {}
    return {"clip": parts[0], "src_in": parts[1], "src_out": parts[2], "event": parts[3]}


def episode_values(table, column):
    """Valores distintos de episodio en orden de aparicion."""
    seen = []
    for value in table.column_values(column):
        value = normalize_episode(value)
        if value and value not in seen:
            seen.append(value)
    return seen


def _value(row, index):
    if index is None or index >= len(row):
        return ""
    return row[index].strip()


def build_plan(table, columns, fps, reference_start, duration,
               episode=None, skip_omit=True):
    """Arma las marcas en cuadros de timeline.

    `reference_start` es el TC (en cuadros) que corresponde al cuadro 0 del
    timeline. `duration` es el largo del timeline en cuadros. El REC TC OUT
    de la planilla es exclusivo (el OUT de un shot es el IN del siguiente),
    asi que la marca termina un cuadro antes.
    """
    plan = Plan()
    shot_col = columns.get("shot")
    in_col = columns.get("tc_in")
    out_col = columns.get("tc_out")
    if shot_col is None or in_col is None:
        raise ValueError("Faltan las columnas de shot o de TC IN.")
    seen_shots = {}
    for number, row in table.rows:
        shot = _value(row, shot_col)
        tc_in_text = _value(row, in_col)
        if not tc_in_text and not is_shot_name(shot):
            continue
        if episode and normalize_episode(_value(row, columns.get("episode"))) != episode:
            plan.skipped_episode += 1
            continue
        status = _value(row, columns.get("status"))
        if skip_omit and status and is_omit(status):
            plan.skipped_omit += 1
            continue
        if not shot:
            plan.issues.append(Issue(number, "", tc_in_text, "Row without shot name", False))
            continue
        tc_in = parse_timecode(tc_in_text, fps)
        if tc_in is None:
            message = "No TC IN" if not tc_in_text else "Invalid TC IN"
            plan.issues.append(Issue(number, shot, tc_in_text, message, False))
            continue
        frame_in = tc_in - reference_start
        if frame_in < 0 or frame_in >= duration:
            plan.issues.append(Issue(number, shot, tc_in_text, "Outside the timeline", False))
            continue
        tc_out_text = _value(row, out_col)
        tc_out = parse_timecode(tc_out_text, fps)
        if tc_out is None or tc_out <= tc_in:
            # Sin OUT valido o con IN = OUT la marca queda de un cuadro: el IN
            # alcanza para navegar y el aviso deja ver que la fila esta mal.
            frame_out = frame_in
            message = "No TC OUT" if tc_out is None else "TC OUT not after TC IN"
            plan.issues.append(Issue(number, shot, tc_in_text, message + ": 1-frame mark", True))
        else:
            frame_out = min(tc_out - 1 - reference_start, duration - 1)
        if shot in seen_shots:
            plan.issues.append(Issue(
                number, shot, tc_in_text,
                "Shot repeated (also row %d)" % seen_shots[shot], True))
        else:
            seen_shots[shot] = number
        note = _value(row, columns.get("note"))
        info = {}
        for role in INFO_ROLES:
            value = _value(row, columns.get(role))
            if value:
                # Episodio y escena: Excel guarda los numeros como float.
                info[role] = normalize_episode(value) if role in ("episode", "scene") else value
        plan.marks.append(Mark(number, shot, frame_in, frame_out,
                               tc_in_text, tc_out_text, note, info))
    plan.marks.sort(key=lambda m: (m.frame_in, m.row))
    for previous, current in zip(plan.marks, plan.marks[1:]):
        if current.frame_in <= previous.frame_out:
            plan.issues.append(Issue(
                current.row, current.shot, current.tc_in,
                "Overlaps %s" % previous.shot, True))
    return plan
