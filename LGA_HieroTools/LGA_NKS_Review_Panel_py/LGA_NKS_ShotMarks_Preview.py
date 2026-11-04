"""
____________________________________________________________________

  LGA_NKS_ShotMarks_Preview v1.00 | Lega

  Vista previa del dialogo de Shot Marks, sin host ni Qt: arma las
  filas de la tabla a partir del plan, las filtra (All / Changes /
  Problems) y dice que columnas imprescindibles faltan. Se prueba con
  unittest.

  Existe porque el filtro de la vista previa decide que filas ve el
  usuario antes de escribir cientos de tags: es logica, no dibujo, y
  tiene que poder probarse sin abrir NKS. El dialogo solo traduce
  cada "kind" a su color.

  Filas: dict con order, row, shot, tc_in, frames, change, change_kind,
  result, result_kind, is_change, is_problem.
    change_kind: "unchanged" | "changed" | "new" | "removed" | ""
    result_kind: "ok" | "warning" | "error" | "dim"

  v1.00: Version inicial (rediseno del dialogo en panel + vista previa).
____________________________________________________________________
"""

FILTER_ALL = "all"
FILTER_CHANGES = "changes"
FILTER_PROBLEMS = "problems"
FILTERS = (FILTER_ALL, FILTER_CHANGES, FILTER_PROBLEMS)

# Columnas sin las que no hay plan. TC Out no: sin ella la marca dura un cuadro.
REQUIRED_ROLES = ("shot", "tc_in")
# Columnas de datos que van a la ventana de la marca, en el orden del dialogo.
DATA_ROLES = ("episode", "status", "note", "notes", "notes2", "description", "scene",
              "vendor", "category", "difficulty")

CHANGE_LABELS = {
    "unchanged": "unchanged",
    "changed": "changed",
    "new": "new",
    "removed": "no longer in the sheet",
}


def change_text(change, changed, fields):
    """Texto de la columna Change. `fields` fija el orden de los campos."""
    if not change:
        return ""
    if change == "changed":
        return "Changed: %s" % ", ".join(f for f in fields if f in changed)
    return CHANGE_LABELS[change].capitalize()


def preview_entries(plan, removed, fields, tc_key):
    """Filas de la vista previa, ya ordenadas.

    Arriba las rojas (lo que se fue), despues lo que cambio contra la
    corrida anterior, lo que no se escribe y lo que se escribe con aviso:
    es lo que hay que revisar. Un shot que ya figura como marca roja no se
    repite como error suelto.
    """
    notes = {}
    for issue in plan.issues:
        notes.setdefault((issue.row, issue.shot), []).append(issue)
    entries = []
    for mark in plan.marks:
        issues = notes.pop((mark.row, mark.shot), [])
        order = {"changed": 1, "new": 2}.get(mark.change, 4 if issues else 5)
        entries.append(_entry(order, mark.row, mark.shot, mark.tc_in,
                              "%d-%d" % (mark.frame_in, mark.frame_out),
                              change_text(mark.change, mark.changed, fields), mark.change or "",
                              "; ".join(i.message for i in issues) or "Mark",
                              "warning" if issues else "ok"))
    for old in removed:
        reason = old.get("reason") or ""
        entries.append(_entry(0, 0, old["shot"], old["metadata"].get(tc_key, ""),
                              "%d-%d" % (old["frame_in"], old["frame_out"]),
                              "Not placed" if reason else change_text("removed", {}, fields),
                              "removed",
                              "Red mark where it was" + (": %s" % reason if reason else ""),
                              "dim", unplaced=bool(reason)))
    red = {old["shot"] for old in removed}
    for (row, shot), issues in notes.items():
        if shot in red:
            continue
        entries.append(_entry(3, row, shot, issues[0].tc_in, "", "", "",
                              "; ".join(i.message for i in issues), "error"))
    entries.sort(key=lambda e: (e["order"], e["row"]))
    return entries


def _entry(order, row, shot, tc_in, frames, change, change_kind, result, result_kind,
           unplaced=False):
    return {
        "order": order, "row": row, "shot": shot, "tc_in": tc_in, "frames": frames,
        "change": change, "change_kind": change_kind, "result": result,
        "result_kind": result_kind,
        "is_change": change_kind in ("changed", "new", "removed"),
        # Una roja cuyo shot sigue en la planilla pero no se ubico tambien es
        # un problema: hay que mirar por que.
        "is_problem": result_kind in ("warning", "error") or unplaced,
    }


def filter_entries(entries, mode):
    if mode == FILTER_CHANGES:
        return [e for e in entries if e["is_change"]]
    if mode == FILTER_PROBLEMS:
        return [e for e in entries if e["is_problem"]]
    return list(entries)


def filter_counts(entries):
    """{filtro: cantidad de filas}, para los rotulos del filtro."""
    return {mode: len(filter_entries(entries, mode)) for mode in FILTERS}


def missing_required(columns, thumb_mode):
    """Roles imprescindibles sin columna. En modo thumbnails el TC no hace falta:
    sale de ubicar las fotos."""
    roles = ("shot",) if thumb_mode else REQUIRED_ROLES
    return [role for role in roles if columns.get(role) is None]


def data_column_count(columns):
    """Cuantas columnas de datos van a la ventana de la marca."""
    return sum(1 for role in DATA_ROLES if columns.get(role) is not None)


def grid_rows(rows, limit):
    """(filas a mostrar, cuantas quedan afuera) de la grilla de fotos."""
    rows = list(rows)
    shown = rows[:limit] if len(rows) <= limit else rows[:limit - 1]
    return shown, len(rows) - len(shown)
