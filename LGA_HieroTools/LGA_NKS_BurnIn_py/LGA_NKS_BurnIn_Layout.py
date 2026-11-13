"""
____________________________________________________________________

  LGA_NKS_BurnIn_Layout v1.02 | Lega

  Modelo del mapa de LGA BurnIn, en Python puro (sin Nuke ni Qt, se
  prueba con el runtime embebido). Lo comparten el panel (que edita el
  mapa) y la logica del render (que convierte el mapa en rectangulos
  de pixeles para los paneles del kernel y las cajas de los Text2).

  El mapa tiene ocho lugares (cuatro esquinas, arriba y abajo al
  centro, los dos costados) y la bandeja Hidden. Cada lugar es una
  lista de LINEAS, de arriba hacia abajo, y cada linea una lista de
  campos, de izquierda a derecha. Hay cinco distribuciones (presets);
  cada una recuerda como la dejo el usuario. Todo viaja en un JSON
  dentro del knob invisible bi_layout del gizmo.

  Es el mismo modelo que el menu Burn-ins de Shot Player (LGA Media
  Tools), del que sale el diseno.

  v1.02: Default de fabrica: Bottom line con la distribucion de Lega
         (clip | fps res | codec y colorspace abajo; TC y Frame arriba a
         la derecha).
  v1.01: Mascara del viewer: mask_inset() y compute(inset=) acomodan los
         campos dentro del area visible (tambien con la mascara al 50%).
  v1.00: Version inicial.
____________________________________________________________________
"""

import copy
import json
import math

# Campos del efecto, en el orden del motor (Text2 y params del kernel).
FIELDS = (
    "clip", "cspace", "res", "frame", "tc", "fps",
    "track", "date", "codec", "custom1", "custom2",
)

# Rotulo corto de cada campo en el mapa del panel.
SHORT = {
    "clip": "Clip", "cspace": "Colorspace", "res": "Res", "frame": "Frame",
    "tc": "TC", "fps": "FPS", "track": "Track", "date": "Date",
    "codec": "Codec", "custom1": "Custom 1", "custom2": "Custom 2",
}

SLOTS = ("tl", "tc", "tr", "ml", "mr", "bl", "bc", "br")

# (clave, nombre visible). El orden es el de los botones del panel.
PRESETS = (
    ("corners", "Corners"),
    ("tb", "Top & bottom"),
    ("bottom", "Bottom line"),
    ("edge", "Edge"),
    ("left", "Left list"),
)
DEFAULT_PRESET = "bottom"

_PRESET_SLOTS = {
    "corners": {"tl": [["clip"]], "tr": [["cspace"]],
                "bl": [["frame"], ["tc"]], "br": [["res", "fps"]]},
    "tb": {"tl": [["clip"]], "tc": [["cspace"]], "tr": [["res"]],
           "bl": [["frame"]], "bc": [["tc"]], "br": [["fps"]]},
    # Bottom line es la de fabrica: la que Lega armo para distribuir
    # (12-11-2026). TC y Frame quedan arriba a la derecha.
    "bottom": {"bl": [["clip"]], "bc": [["fps", "res"]],
               "br": [["codec"], ["cspace"]], "tr": [["tc"], ["frame"]]},
    "edge": {"tl": [["clip"]], "ml": [["tc"]], "mr": [["res", "fps"]],
             "br": [["frame"]]},
    "left": {"tl": [["clip"], ["cspace"], ["res"], ["fps"], ["frame"], ["tc"]]},
}
_PRESET_SIDES = {"edge": "rotated"}

BG_MODES = ("Panels", "Band", "Text")

# Tamano de letra como fraccion del alto del formato (Size S/M/L del panel).
# M = 0.023 es el tamano historico del efecto en 4K (50 px sobre 2160).
SIZE_FRACTIONS = (("S", 0.0185), ("M", 0.023), ("L", 0.029))

# Proporciones del layout, en multiplos del tamano de letra (fs) o del alto.
MARGIN_FRAC = 0.025   # margen a los bordes, fraccion del alto del formato
GAP_FS = 0.35         # separacion entre paneles de una misma linea
LINE_GAP_FS = 0.3     # separacion entre lineas
LINE_HEIGHT_FS = 1.3  # alto del panel = fs * 1.3 + padding (como siempre)


# ── Estado ────────────────────────────────────────────────────────────────────


def fresh_arrangement(preset):
    """Distribucion de fabrica de un preset: los lugares de su regla y el
    resto de los campos en Hidden."""
    base = _PRESET_SLOTS.get(preset, _PRESET_SLOTS[DEFAULT_PRESET])
    slots = {s: copy.deepcopy(base.get(s, [])) for s in SLOTS}
    used = set(f for lines in slots.values() for line in lines for f in line)
    return {
        "slots": slots,
        "hidden": [f for f in FIELDS if f not in used],
        "sides": _PRESET_SIDES.get(preset, "upright"),
    }


def default_state():
    return {
        "v": 1,
        "preset": DEFAULT_PRESET,
        "arr": {key: fresh_arrangement(key) for key, _name in PRESETS},
    }


def _clean_arrangement(arr, preset):
    """Normaliza una distribucion leida del JSON: lugares conocidos, campos
    conocidos sin repetir, y todo campo faltante a Hidden."""
    if not isinstance(arr, dict):
        return fresh_arrangement(preset)
    seen = set()
    slots = {}
    raw_slots = arr.get("slots") if isinstance(arr.get("slots"), dict) else {}
    for s in SLOTS:
        lines = []
        for line in raw_slots.get(s) or []:
            if not isinstance(line, list):
                continue
            clean = [f for f in line if f in FIELDS and f not in seen]
            seen.update(clean)
            if clean:
                lines.append(clean)
        slots[s] = lines
    hidden = [f for f in (arr.get("hidden") or []) if f in FIELDS and f not in seen]
    seen.update(hidden)
    hidden += [f for f in FIELDS if f not in seen]
    sides = arr.get("sides") if arr.get("sides") in ("upright", "rotated") else "upright"
    return {"slots": slots, "hidden": hidden, "sides": sides}


def parse(text):
    """Estado desde el JSON del knob. Vacio o roto -> estado de fabrica."""
    state = default_state()
    try:
        data = json.loads(text) if text else None
    except (TypeError, ValueError):
        data = None
    if not isinstance(data, dict):
        return state
    preset = data.get("preset")
    if preset in dict(PRESETS):
        state["preset"] = preset
    arrs = data.get("arr") if isinstance(data.get("arr"), dict) else {}
    for key, _name in PRESETS:
        if key in arrs:
            state["arr"][key] = _clean_arrangement(arrs[key], key)
    return state


def dump(state):
    return json.dumps(state, sort_keys=True, separators=(",", ":"))


def active(state):
    return state["arr"][state["preset"]]


def slot_of(arr, field):
    for s in SLOTS:
        for line in arr["slots"][s]:
            if field in line:
                return s
    return "hidden"


def visible_fields(arr):
    return [f for s in SLOTS for line in arr["slots"][s] for f in line]


def _detach(arr, field):
    arr["hidden"] = [f for f in arr["hidden"] if f != field]
    for s in SLOTS:
        lines = [[f for f in line if f != field] for line in arr["slots"][s]]
        arr["slots"][s] = [line for line in lines if line]


def move_to(arr, field, slot):
    """Lleva un campo a un lugar (en una linea nueva al final) o a Hidden."""
    if field not in FIELDS:
        return
    _detach(arr, field)
    if slot == "hidden":
        arr["hidden"].append(field)
    elif slot in SLOTS:
        arr["slots"][slot].append([field])


def move_next_to(arr, field, target, side):
    """Suelta un campo junto a otro: 'l'/'r' en la misma linea, 't'/'b' en
    una linea nueva arriba o abajo de la del otro."""
    if field == target or field not in FIELDS:
        return
    slot = slot_of(arr, target)
    if slot == "hidden":
        move_to(arr, field, "hidden")
        return
    _detach(arr, field)
    lines = arr["slots"][slot]
    li = next(i for i, line in enumerate(lines) if target in line)
    ci = lines[li].index(target)
    if side == "l":
        lines[li].insert(ci, field)
    elif side == "r":
        lines[li].insert(ci + 1, field)
    elif side == "t":
        lines.insert(li, [field])
    else:
        lines.insert(li + 1, [field])


def stack_state(arr):
    """'row' si cada lugar tiene una sola linea, 'column' si cada linea tiene
    un solo campo (y no es row), 'mixed' si no es ninguna."""
    used = [arr["slots"][s] for s in SLOTS if arr["slots"][s]]
    if all(len(lines) == 1 for lines in used):
        return "row"
    if all(len(line) == 1 for lines in used for line in lines):
        return "column"
    return "mixed"


def set_stack(arr, mode):
    for s in SLOTS:
        flat = [f for line in arr["slots"][s] for f in line]
        if not flat:
            arr["slots"][s] = []
        elif mode == "row":
            arr["slots"][s] = [flat]
        else:
            arr["slots"][s] = [[f] for f in flat]


def is_default(state):
    preset = state["preset"]
    return active(state) == fresh_arrangement(preset)


# ── Geometria ─────────────────────────────────────────────────────────────────
#
# Coordenadas de Nuke: origen abajo a la izquierda, y hacia arriba. Cada
# campo visible devuelve su panel SIN ROTAR (x, y, w, h) y su rotacion en
# grados y su pivote. Los campos de un costado girado (Sides: Rotated) rotan
# alrededor de un pivote FIJO por costado (side_pivot): asi el pivote literal
# que exige el Text2 (animation_layers) no depende del ancho del texto, que
# cambia de clip a clip; solo cambia con el formato, el tamano de letra y el
# padding. El rectangulo sin rotar se calcula para que, al rotar alrededor de
# ese pivote, el panel caiga donde tiene que estar.
#
# El pivote se elige para que el rectangulo SIN ROTAR de la primera linea
# quede en el CENTRO del formato. Con el pivote en el propio panel (lo
# primero que se probo) la caja sin rotar del costado izquierdo quedaba con x
# negativa, y un Text2 con la caja fuera del formato rompe el render del
# efecto entero en el timeline: desaparecian los paneles de varios campos y
# otros se corrian (medido en NKS 17). Con costados derechos no pasaba.


def mask_inset(aspect, fmt_w, fmt_h):
    """(ix, iy): lo que tapa la mascara del viewer en cada borde, en px.

    aspect es el de la mascara (3:2 = 1.5); 0 o None = sin mascara. Una
    mascara mas angosta que el formato deja barras a los costados (ix); una
    mas ancha, arriba y abajo (iy). Los burn-ins se acomodan dentro de lo que
    queda visible, tambien con la mascara al 50% (Half)."""
    try:
        a = float(aspect or 0.0)
        W, H = float(fmt_w), float(fmt_h)
    except (TypeError, ValueError):
        return (0.0, 0.0)
    if a <= 0.0 or W <= 0.0 or H <= 0.0:
        return (0.0, 0.0)
    if a < W / H:
        return (max(0.0, (W - H * a) / 2.0), 0.0)
    return (0.0, max(0.0, (H - W / a) / 2.0))


def side_pivot(edge, fmt_w, fmt_h, h, inset_x=0.0):
    """Pivote fijo del costado 'l' (gira 90) o 'r' (gira 270): el punto
    que lleva el centro del formato al centro de la primera linea del
    costado (a media altura, a margen + h/2 del borde visible; inset_x es
    la barra de la mascara)."""
    W, H = float(fmt_w), float(fmt_h)
    d = float(inset_x) + MARGIN_FRAC * H + h / 2.0
    if edge == "l":
        return ((W / 2.0 + d) / 2.0, (H + d - W / 2.0) / 2.0)
    return ((1.5 * W - d) / 2.0, (H - W / 2.0 + d) / 2.0)


def line_height(fs, pad):
    return fs * LINE_HEIGHT_FS + pad


def _unrotate(cx, cy, w, h, rot, pivot):
    """Panel sin rotar cuyo centro, rotado `rot` grados (antihorario, y
    hacia arriba) alrededor de `pivot`, cae en (cx, cy)."""
    px, py = pivot
    a = math.radians(-rot)
    dx, dy = cx - px, cy - py
    ux = px + dx * math.cos(a) - dy * math.sin(a)
    uy = py + dx * math.sin(a) + dy * math.cos(a)
    return (ux - w / 2.0, uy - h / 2.0, w, h)


def compute(arr, widths, fmt_w, fmt_h, fs, pad, inset=(0.0, 0.0)):
    """Rectangulos de todos los campos visibles con texto.

    widths: {campo: ancho del panel en px} SOLO de los campos con texto (un
    campo sin texto no ocupa lugar ni dibuja panel).
    Devuelve ({campo: (x, y, w, h, rot, pivot_x, pivot_y)}, bandas), donde bandas es
    {'t': grosor, 'b': grosor, 'l': grosor, 'r': grosor} en px (0 = sin
    banda) para el modo Band.

    inset = (ix, iy): barras de la mascara del viewer (mask_inset). Los
    campos se ubican dentro del area visible; las bandas suman la barra a su
    grosor para empezar donde termina la mascara.
    """
    W, H = float(fmt_w), float(fmt_h)
    ix, iy = float(inset[0]), float(inset[1])
    m = MARGIN_FRAC * H
    g = GAP_FS * fs
    vg = LINE_GAP_FS * fs
    h = line_height(fs, pad)
    center = (W / 2.0, H / 2.0)
    rotated = arr.get("sides") == "rotated"
    rects = {}
    bands = {"t": 0.0, "b": 0.0, "l": 0.0, "r": 0.0}

    def lines_of(slot):
        out = []
        for line in arr["slots"].get(slot) or []:
            live = [f for f in line if widths.get(f, 0.0) > 0.0]
            if live:
                out.append(live)
        return out

    def line_len(line):
        return sum(widths[f] for f in line) + g * (len(line) - 1)

    def block(n):
        return n * h + max(0, n - 1) * vg

    # Arriba y abajo: las lineas se apilan desde el borde hacia adentro.
    for slot in ("tl", "tc", "tr", "bl", "bc", "br"):
        lines = lines_of(slot)
        n = len(lines)
        if not n:
            continue
        edge = "t" if slot[0] == "t" else "b"
        bands[edge] = max(bands[edge], block(n) + 2.0 * m + iy)
        for i, line in enumerate(lines):
            if edge == "t":
                y = H - iy - m - h - i * (h + vg)
            else:
                y = iy + m + (n - 1 - i) * (h + vg)
            total = line_len(line)
            if slot[1] == "l":
                x = ix + m
            elif slot[1] == "r":
                x = W - ix - m - total
            else:
                x = (W - total) / 2.0
            for f in line:
                rects[f] = (x, y, widths[f], h, 0.0) + center
                x += widths[f] + g

    # Costados.
    for slot in ("ml", "mr"):
        lines = lines_of(slot)
        n = len(lines)
        if not n:
            continue
        edge = "l" if slot == "ml" else "r"
        if not rotated:
            # Derechos: bloque de lineas centrado en vertical.
            bands[edge] = max(bands[edge], max(line_len(l) for l in lines) + 2.0 * m + ix)
            top = H / 2.0 + block(n) / 2.0
            for i, line in enumerate(lines):
                y = top - h - i * (h + vg)
                total = line_len(line)
                x = ix + m if edge == "l" else W - ix - m - total
                for f in line:
                    rects[f] = (x, y, widths[f], h, 0.0) + center
                    x += widths[f] + g
            continue
        # Girados a lo largo del borde: el izquierdo se lee de abajo hacia
        # arriba (90), el derecho de arriba hacia abajo (270). Cada linea
        # corre paralela al borde; la primera es la mas cercana a el.
        bands[edge] = max(bands[edge], block(n) + 2.0 * m + ix)
        rot = 90.0 if edge == "l" else 270.0
        pivot = side_pivot(edge, W, H, h, ix)
        for i, line in enumerate(lines):
            dist = ix + m + i * (h + vg) + h / 2.0
            cx = dist if edge == "l" else W - dist
            total = line_len(line)
            along = (H - total) / 2.0
            for f in line:
                center_along = along + widths[f] / 2.0
                cy = center_along if edge == "l" else H - center_along
                rects[f] = _unrotate(cx, cy, widths[f], h, rot, pivot) + (rot,) + pivot
                along += widths[f] + g
    return rects, bands
