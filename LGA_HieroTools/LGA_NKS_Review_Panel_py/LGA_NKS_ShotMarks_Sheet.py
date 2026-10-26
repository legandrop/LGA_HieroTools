"""
____________________________________________________________________

  LGA_NKS_ShotMarks_Sheet v1.00 | Lega

  Nucleo sin host de Shot Marks: lee una planilla (xlsx o csv),
  detecta la fila de encabezado y las columnas de shot y timecode,
  y arma el plan de marcas (cuadro de timeline por shot) con la
  lista de problemas de cada fila. No importa hiero ni Qt: se
  prueba con unittest y corre fuera del hilo de UI.

  El xlsx se lee con zipfile + iterparse (solo el XML de la hoja y
  los sharedStrings), sin openpyxl: NKS no lo trae, y asi una
  planilla de cientos de MB por las imagenes se lee en segundos.

  v1.00: Version inicial.
____________________________________________________________________
"""

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
    "timecodein", "mastertc", "start",
)
TC_OUT_HEADERS = (
    "rectcout", "recordtcout", "recout", "recordout", "tcout",
    "timecodeout", "end",
)
EPISODE_HEADERS = ("ep", "episode", "episodio", "epi", "reel")
STATUS_HEADERS = ("status", "estado", "shotstatus")
NOTE_HEADERS = ("brief", "description", "descripcion", "notes", "notas")

OMIT_TOKENS = ("omit", "omitted", "cbb", "removed")

ROLES = ("shot", "tc_in", "tc_out", "episode", "status", "note")
_ROLE_HEADERS = {
    "shot": SHOT_HEADERS,
    "tc_in": TC_IN_HEADERS,
    "tc_out": TC_OUT_HEADERS,
    "episode": EPISODE_HEADERS,
    "status": STATUS_HEADERS,
    "note": NOTE_HEADERS,
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
    def __init__(self, row, shot, frame_in, frame_out, tc_in, tc_out, note):
        self.row = row
        self.shot = shot
        self.frame_in = frame_in
        self.frame_out = frame_out  # inclusivo
        self.tc_in = tc_in
        self.tc_out = tc_out
        self.note = note


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
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel
            rows = []
            for number, values in enumerate(csv.reader(handle, dialect), start=1):
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

def _header_score(values):
    """Cuanto se parece una fila a un encabezado de breakdown con timecode."""
    norm = [normalize_header(v) for v in values]
    score = 0
    if any(n in SHOT_HEADERS for n in norm):
        score += 2
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


def detect_header_row(rows):
    """Indice en `rows` de la fila de encabezado, o None si ninguna sirve."""
    best_index, best_score = None, 0
    for index, (_number, values) in enumerate(rows[:HEADER_SEARCH_ROWS]):
        score = _header_score(values)
        if score > best_score:
            best_index, best_score = index, score
    # Hace falta al menos shot + tc in para que la hoja sirva.
    return best_index if best_score >= 4 else None


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


def _rows_score(rows):
    index = detect_header_row(rows)
    return _header_score(rows[index][1]) if index is not None else 0


def suggest_sheet(path, sheets=None):
    """La hoja con mejor encabezado de shot + timecode, o None.

    El zip y los sharedStrings se abren una sola vez: releerlos por hoja
    costaba 14 s en una planilla real de 55 hojas.
    """
    path = Path(path)
    if path.suffix.lower() == ".csv":
        return "" if _rows_score(_read_rows(path, "", HEADER_SEARCH_ROWS)) else None
    best, best_score = None, 0
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
    return best


def load_table(path, sheet):
    rows = _read_rows(path, sheet)
    if not rows:
        raise ValueError("La hoja esta vacia.")
    index = detect_header_row(rows)
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


def is_omit(status):
    norm = normalize_header(status)
    return any(token in norm for token in OMIT_TOKENS)


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
        if not shot and not tc_in_text:
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
        plan.marks.append(Mark(number, shot, frame_in, frame_out,
                               tc_in_text, tc_out_text, note))
    plan.marks.sort(key=lambda m: (m.frame_in, m.row))
    for previous, current in zip(plan.marks, plan.marks[1:]):
        if current.frame_in <= previous.frame_out:
            plan.issues.append(Issue(
                current.row, current.shot, current.tc_in,
                "Overlaps %s" % previous.shot, True))
    return plan
