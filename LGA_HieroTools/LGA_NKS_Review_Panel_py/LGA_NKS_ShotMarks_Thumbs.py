"""
____________________________________________________________________

  LGA_NKS_ShotMarks_Thumbs v1.00 | Lega

  Lee los thumbnails de una hoja de xlsx: que imagen esta anclada en
  que fila. Sin host ni Qt (zipfile + ElementTree): se prueba con
  unittest y corre fuera del hilo de UI.

  Existe para las planillas de breakdown que no traen timecode y solo
  tienen la foto del shot: Shot Marks la ubica en el video del corte
  (LGA_NKS_ShotMarks_Locate_Engine).

  Las imagenes de Excel "flotantes" viven en xl/drawings/drawingN.xml,
  ancladas a una celda (twoCellAnchor / oneCellAnchor). Las imagenes
  "en celda" (richData) son otro formato y no se leen todavia.

  v1.00: Version inicial.
____________________________________________________________________
"""

import hashlib
import os
import posixpath
import xml.etree.ElementTree as ET
import zipfile

XDR = "{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG = "{http://schemas.openxmlformats.org/package/2006/relationships}"
MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")


def _rels(archive, part):
    """{Id: ruta en el zip} de las relaciones de una parte."""
    folder, name = posixpath.split(part)
    rels_path = posixpath.join(folder, "_rels", name + ".rels")
    if rels_path not in archive.namelist():
        return {}
    result = {}
    for node in ET.fromstring(archive.read(rels_path)).iter(PKG + "Relationship"):
        target = str(node.get("Target") or "")
        if target.startswith("/"):
            path = target.lstrip("/")
        else:
            path = posixpath.normpath(posixpath.join(folder, target))
        result[str(node.get("Id") or "")] = path
    return result


def _sheet_part(archive, sheet_name):
    root = ET.fromstring(archive.read("xl/workbook.xml"))
    for node in root.iter(MAIN + "sheet"):
        if str(node.get("name") or "") == sheet_name:
            return _rels(archive, "xl/workbook.xml").get(str(node.get(R + "id") or ""))
    return None


def _anchor_row(anchor):
    """Fila (0-based) a la que pertenece una imagen anclada.

    Una foto que ocupa una sola fila puede terminar en el borde de la
    siguiente (to.row = from.row + 1): pertenece a la primera. Si cruza
    varias filas, a la del medio.
    """
    start = anchor.find(XDR + "from")
    end = anchor.find(XDR + "to")
    row0 = int(start.findtext(XDR + "row") or 0)
    if end is None:
        return row0
    row1 = int(end.findtext(XDR + "row") or row0)
    return row0 if row1 - row0 <= 1 else (row0 + row1) // 2


def sheet_images(path, sheet_name):
    """[{row (1-based), col (0-based), part (ruta en el zip)}] de la hoja."""
    with zipfile.ZipFile(str(path)) as archive:
        sheet = _sheet_part(archive, sheet_name)
        if not sheet:
            return []
        images = []
        for drawing in _rels(archive, sheet).values():
            if "/drawings/" not in drawing or not drawing.endswith(".xml"):
                continue
            media = _rels(archive, drawing)
            root = ET.fromstring(archive.read(drawing))
            for tag in ("twoCellAnchor", "oneCellAnchor"):
                for anchor in root.iter(XDR + tag):
                    blip = anchor.find(".//" + A + "blip")
                    if blip is None:
                        continue
                    part = media.get(str(blip.get(R + "embed") or ""))
                    if not part or not part.lower().endswith(IMAGE_EXTENSIONS):
                        continue
                    col = int(anchor.find(XDR + "from").findtext(XDR + "col") or 0)
                    images.append({"row": _anchor_row(anchor) + 1, "col": col, "part": part})
        return images


def has_cell_images(path):
    """Imagenes "en celda" (richData): todavia no se leen."""
    with zipfile.ZipFile(str(path)) as archive:
        return any(n.startswith("xl/richData/") for n in archive.namelist())


def extract_thumbs(path, sheet_name, rows, out_dir):
    """{fila: {"sha1", "file"}} de las filas pedidas que tienen imagen.

    Si una fila tiene varias, gana la de la columna mas a la izquierda.
    Cada imagen se guarda una vez con su sha1 de nombre: dos filas con la
    misma foto la comparten y una planilla nueva reusa lo ya extraido.
    """
    wanted = set(rows)
    best = {}
    for image in sheet_images(path, sheet_name):
        if image["row"] in wanted:
            current = best.get(image["row"])
            if current is None or image["col"] < current["col"]:
                best[image["row"]] = image
    os.makedirs(out_dir, exist_ok=True)
    result = {}
    with zipfile.ZipFile(str(path)) as archive:
        for row, image in best.items():
            data = archive.read(image["part"])
            sha1 = hashlib.sha1(data).hexdigest()
            ext = os.path.splitext(image["part"])[1].lower()
            target = os.path.join(out_dir, sha1 + ext)
            if not os.path.isfile(target):
                with open(target + ".tmp", "wb") as handle:
                    handle.write(data)
                os.replace(target + ".tmp", target)
            result[row] = {"sha1": sha1, "file": target}
    return result
