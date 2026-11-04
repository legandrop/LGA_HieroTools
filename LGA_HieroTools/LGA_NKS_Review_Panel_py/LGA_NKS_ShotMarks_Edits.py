"""
____________________________________________________________________

  LGA_NKS_ShotMarks_Edits v1.00 | Lega

  Cambios a la planilla hechos desde la ventanita de Shot Marks, sin
  salir de NKS: dificultad, Notes, Budget Alternative (rol notes2) y preguntas. Se guardan en un
  archivo local y NO se escriben en la planilla: quedan pendientes hasta
  que se pasen a la planilla (Google Sheets o Excel) revisando cada uno.

  Existe porque al revisar el corte las correcciones aparecen mirando el
  shot, y abrir la planilla para cada una corta la revision. Ademas la
  planilla puede estar siendo editada por otra persona: escribirle desde
  NKS pisaria su trabajo sin que nadie lo vea.

  Cada cambio guarda el valor que tenia la planilla cuando se hizo
  ("before"): al pasarlo, si la planilla ya no tiene ese valor, alguien la
  cambio mientras tanto y hay que decidir a mano. Un cambio que vuelve al
  valor de la planilla se borra solo.

  Archivo: <carpeta del .hrox>/<proyecto sin version>_ShotMarks_Edits.json
  (con el proyecto sin guardar, en la carpeta de respaldo que se pase).
  Sin host ni Qt: lo usan la ventanita y los tests.

  v1.00: Version inicial.
____________________________________________________________________
"""

import csv
import datetime
import getpass
import json
import os
import re
import uuid

FILE_SUFFIX = "_ShotMarks_Edits.json"
FORMAT_VERSION = 1

# Campos que se editan desde la ventanita (roles de Shot Marks).
EDITABLE = ("difficulty", "notes", "notes2")
QUESTION = "question"
FIELD_LABELS = {"difficulty": "Difficulty", "notes": "Notes", "notes2": "Budget Alternative",
                QUESTION: "Question"}

STATE_PENDING = "pending"
# Ya esta en la planilla: lo detecta la ventanita al ver el valor nuevo en
# la marca despues de volver a correr Shot Marks.
STATE_APPLIED = "applied"

EXPORT_HEADERS = ("Shot", "Row", "Field", "Sheet value", "New value", "Sheet now",
                  "Author", "Date", "Timeline", "Sheet", "Id")


def project_base(project_name):
    """Proyecto sin version (como las decisiones de Locate): al pasar de v10 a
    v11 el archivo de cambios sigue siendo el mismo."""
    name = project_name or "project"
    base = re.sub(r"[_ .-]*v\d+$", "", name, flags=re.IGNORECASE) or name
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", base)


def edits_path(hrox_path, project_name, fallback_dir):
    folder = os.path.dirname(hrox_path) if hrox_path else fallback_dir
    return os.path.join(folder, project_base(project_name) + FILE_SUFFIX)


def _same(a, b):
    """Iguales para la planilla: sin diferencias de fin de linea ni espacios
    sobrantes, y la dificultad sin mayusculas ("mid" == "Mid")."""
    norm = lambda t: "\n".join(line.rstrip() for line in
                               str(t or "").replace("\r\n", "\n").replace("\r", "\n").strip().split("\n"))
    return norm(a) == norm(b)


def _same_field(field, a, b):
    if field == "difficulty":
        return str(a or "").strip().lower() == str(b or "").strip().lower()
    return _same(a, b)


def empty():
    return {"version": FORMAT_VERSION, "edits": []}


def load(path):
    """Los cambios del archivo, o vacio si no existe. Un archivo roto no se
    pisa: se avisa con ValueError para no perder cambios."""
    if not path or not os.path.isfile(path):
        return empty()
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or not isinstance(data.get("edits"), list):
        raise ValueError("Not a Shot Marks edits file: %s" % path)
    return data


def save(path, data):
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def _author():
    try:
        return getpass.getuser()
    except Exception:
        return ""


def pending(data, shot=None):
    return [e for e in data.get("edits", [])
            if e.get("state") == STATE_PENDING and (shot is None or e.get("shot") == shot)]


def find(data, shot, field):
    for edit in pending(data, shot):
        if edit.get("field") == field:
            return edit
    return None


def set_value(data, shot, row, field, sheet_value, new_value, timeline="", source="",
              author=None, when=None):
    """Cambia un campo editable. Un solo cambio pendiente por shot y campo: el
    segundo actualiza el primero y conserva el valor de la planilla de cuando
    se empezo. Si vuelve al valor de la planilla, el cambio se borra.
    Devuelve el cambio, o None si se borro."""
    if field not in EDITABLE:
        raise ValueError("Field not editable: %s" % field)
    edit = find(data, shot, field)
    before = edit["before"] if edit is not None else (sheet_value or "")
    if _same_field(field, before, new_value):
        if edit is not None:
            data["edits"].remove(edit)
        return None
    if edit is None:
        edit = {"id": uuid.uuid4().hex[:12], "shot": shot, "row": str(row or ""), "field": field,
                "before": before, "state": STATE_PENDING, "created": when or _now()}
        data["edits"].append(edit)
    edit.update({"after": new_value or "", "author": author if author is not None else _author(),
                 "when": when or _now(), "timeline": timeline, "source": source})
    return edit


def add_question(data, shot, row, text, timeline="", source="", author=None, when=None):
    """Pregunta sobre el shot: no reemplaza nada, se suma."""
    text = str(text or "").strip()
    if not text:
        return None
    edit = {"id": uuid.uuid4().hex[:12], "shot": shot, "row": str(row or ""), "field": QUESTION,
            "before": "", "after": text, "state": STATE_PENDING, "created": when or _now(),
            "when": when or _now(), "author": author if author is not None else _author(),
            "timeline": timeline, "source": source}
    data["edits"].append(edit)
    return edit


def remove(data, edit_id):
    for edit in list(data.get("edits", [])):
        if edit.get("id") == edit_id:
            data["edits"].remove(edit)
            return edit
    return None


def overlay(info, data):
    """Info de la marca con los cambios pendientes encima.

    Agrega a `info`:
      edited:   {campo: valor de la planilla} de lo que se cambio aca.
      conflict: {campo: valor de la planilla de cuando se cambio} si la
                planilla ya no tiene ese valor (alguien la cambio despues).
      questions: preguntas pendientes del shot.
      applied:  ids de los cambios cuyo valor nuevo ya esta en la planilla
                (se pasaron): no se muestran como cambio y se pueden cerrar
                con mark_applied.
    """
    info = dict(info)
    info["edited"] = {}
    info["conflict"] = {}
    info["questions"] = []
    info["applied"] = []
    shot = info.get("shot")
    for edit in pending(data, shot):
        field = edit.get("field")
        if field == QUESTION:
            info["questions"].append(edit)
            continue
        if field not in EDITABLE:
            continue
        current = info.get(field) or ""
        if _same_field(field, current, edit.get("after")):
            info["applied"].append(edit.get("id"))
            continue
        info["edited"][field] = current
        if not _same_field(field, current, edit.get("before")):
            info["conflict"][field] = edit.get("before") or ""
        info[field] = edit.get("after") or ""
    return info


def mark_applied(data, ids, when=None):
    """Cierra los cambios que ya estan en la planilla (quedan en el archivo
    como historial, fuera de los pendientes). Devuelve cuantos cerro."""
    count = 0
    for edit in data.get("edits", []):
        if edit.get("id") in ids and edit.get("state") == STATE_PENDING:
            edit["state"] = STATE_APPLIED
            edit["applied"] = when or _now()
            count += 1
    return count


def export_rows(data, sheet_now=None):
    """Filas para la planilla de revision. `sheet_now(shot, field)` da el
    valor actual de la planilla (o None si no se sabe)."""
    rows = []
    for edit in sorted(pending(data), key=lambda e: (e.get("shot", ""), e.get("field", ""),
                                                     e.get("when", ""))):
        now = sheet_now(edit["shot"], edit["field"]) if sheet_now and edit["field"] != QUESTION else None
        rows.append([edit.get("shot", ""), edit.get("row", ""),
                     FIELD_LABELS.get(edit.get("field"), edit.get("field")),
                     edit.get("before", ""), edit.get("after", ""),
                     "" if now is None else now, edit.get("author", ""), edit.get("when", ""),
                     edit.get("timeline", ""), edit.get("source", ""), edit.get("id", "")])
    return rows


def export_csv(path, data, sheet_now=None):
    """CSV en UTF-8 con BOM (Excel lo abre con los acentos bien; Google Sheets
    lo importa igual). Devuelve cuantas filas escribio."""
    rows = export_rows(data, sheet_now)
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(EXPORT_HEADERS)
        writer.writerows(rows)
    return len(rows)
