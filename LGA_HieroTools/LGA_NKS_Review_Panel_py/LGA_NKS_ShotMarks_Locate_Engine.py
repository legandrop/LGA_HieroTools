"""
____________________________________________________________________

  LGA_NKS_ShotMarks_Locate_Engine v1.01 | Lega

  Motor de Shot Marks sin columna de timecode: ubica cada thumbnail de
  la planilla en el video del corte y devuelve el plano (corte a corte)
  que lo contiene. Corre como PROCESO APARTE con el Python embebido del
  pack, no dentro de NKS: es un minuto de Python puro que en un hilo de
  NKS se pelearia el GIL con la UI. Solo libreria estandar.

  Uso: python -I LGA_NKS_ShotMarks_Locate_Engine.py <job.json>
  Escribe progreso como una linea JSON por evento en stdout y el
  resultado en el JSON que pide el job.

  Pasos:
  1. Indice del video (una vez por video, cacheado por ruta+tamano+fecha):
     ffmpeg recorre la pelicula y guarda por cuadro una huella 9x8 gris
     (dHash) y otra 32x18 gris, mas el puntaje de cambio de escena de
     scdet. ~3,5 min para 2,6 h de ProRes LT en HD.
  2. Thumbs: detecta el area de imagen (sin barras ni UI de un player),
     recorta igual que el video y saca las mismas huellas.
  3. Matcheo: dHash contra todos los cuadros -> mejores planos -> NCC en
     gris (tolera grade distinto) -> anclas seguras -> el resto se busca
     entre anclas vecinas en orden de planilla.
  4. Cuadro exacto: refinado a 192x104 decodificando +-24 cuadros.
  5. IN/OUT: el plano del EDL que contiene el cuadro, o sin EDL el
     plano entre los cortes de scdet que lo rodean.

  Log: logs/DebugPy_LGA_NKS_ShotMarks_Locate_Engine.log.

  v1.01: EDL del armado opcional (job["edl"]). Si sus cortes caen sobre
         la imagen (la mitad al cuadro contra scdet, probando desfasajes),
         reemplaza a scdet como unidad de busqueda y para el IN/OUT, sin
         el tope de 60 s, y cada fila lleva el clip y el SRC TC de su
         plano. Medido en un armado de 2,6 h: scdet perdia 125 de 1587
         cortes y marcaba 32 de mas.
  v1.00: Version inicial.
____________________________________________________________________
"""

import array
import bisect
import concurrent.futures
import hashlib
import json
import logging
import math
import mmap
import operator
import os
import struct
import subprocess
import sys
import time
from collections import Counter

DEBUG = False

INDEX_VERSION = "1"
# Cadena de escalado comun al video y a los thumbs: mismo recorte central y
# mismo paso por 160x86 antes de las huellas, para que comparen igual.
INNER = 0.92
BASE_W, BASE_H = 160, 86
D8 = 72          # 9x8 gris
G32 = 576        # 32x18 gris
FINE_W, FINE_H = 192, 104
FINE_RADIUS = 24

CUT_SCORE = 6.0          # scdet: puntaje minimo de un corte
CUT_PEAK_RADIUS = 3      # dos detecciones a menos de esto: queda la mas fuerte
MAX_SHOT_FRAMES = 60 * 24  # un "plano" mas largo: no hay corte claro

HAMMING_MAX = 28
CANDIDATE_SEGMENTS = 30
AUTO_SCORE = 0.90
AUTO_MARGIN = 0.10
REVIEW_SCORE = 0.60
LOCAL_RADIUS = 2400      # cuadros: margen contra planos de la misma zona
DARK_MEDIAN = 14         # mediana de fila/columna por debajo: barra o UI

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

_log = logging.getLogger("LGA_NKS_ShotMarks_Locate_Engine")


def _setup_log():
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)
    _log.setLevel(logging.DEBUG)
    for handler in list(_log.handlers):
        handler.close()
        _log.removeHandler(handler)
    handler = logging.FileHandler(
        os.path.join(log_dir, "DebugPy_LGA_NKS_ShotMarks_Locate_Engine.log"),
        mode="w", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    _log.addHandler(handler)
    if DEBUG:
        _log.addHandler(logging.StreamHandler(sys.stderr))


def emit(event, **data):
    """Una linea JSON por evento: el dialogo de NKS la lee por el pipe."""
    data["event"] = event
    sys.stdout.write(json.dumps(data) + "\n")
    sys.stdout.flush()


def run(args, cwd=None):
    return subprocess.run(args, cwd=cwd, capture_output=True, check=True,
                          creationflags=CREATE_NO_WINDOW).stdout


# -- huellas ---------------------------------------------------------------

def dhash(b):
    """9x8 gris -> 64 bits (gradiente horizontal)."""
    h = 0
    for y in range(8):
        r = b[y * 9:(y + 1) * 9]
        for x in range(8):
            h = (h << 1) | (r[x + 1] > r[x])
    return h


def normalized(values):
    """Media 0 y desvio 1: la NCC no depende de exposicion ni contraste."""
    n = len(values)
    mean = sum(values) / n
    sd = math.sqrt(max(sum(map(operator.mul, values, values)) / n - mean * mean, 1e-9))
    return [(v - mean) / sd for v in values]


def ncc(norm_ref, raw):
    """Correlacion de una huella normalizada contra bytes crudos.

    Como norm_ref tiene media 0, alcanza con dividir el producto por el
    desvio de raw: no hace falta normalizar raw (se ahorra una lista).
    """
    n = len(raw)
    total = sum(raw)
    mean = total / n
    var = sum(map(operator.mul, raw, raw)) / n - mean * mean
    if var <= 1e-9:
        return 0.0
    return sum(map(operator.mul, norm_ref, raw)) / (n * math.sqrt(var))


# -- cortes ----------------------------------------------------------------

def cut_frames(scores, threshold=CUT_SCORE, radius=CUT_PEAK_RADIUS):
    """Cuadros donde empieza un plano: picos locales de scdet.

    scdet a veces marca dos cuadros seguidos (flash, montaje rapido) y el
    corte real es el primero o el mas fuerte: entre detecciones a menos de
    `radius` cuadros queda la de mayor puntaje.
    """
    cuts = []
    for i, score in enumerate(scores):
        if i == 0 or score <= threshold:
            continue
        if cuts and i - cuts[-1] < radius:
            if score > scores[cuts[-1]]:
                cuts[-1] = i
            continue
        cuts.append(i)
    return cuts


_EDL_MODULE = None


def _edl():
    """LGA_NKS_ShotMarks_EDL, cargado por ruta: el motor corre con -I y la
    carpeta del script no esta en sys.path."""
    global _EDL_MODULE
    if _EDL_MODULE is None:
        import importlib.util
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "LGA_NKS_ShotMarks_EDL.py")
        spec = importlib.util.spec_from_file_location("LGA_NKS_ShotMarks_EDL", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _EDL_MODULE = module
    return _EDL_MODULE


def load_edl(path, info, total, detected):
    """({estado del EDL}, planos) para un video.

    El EDL se usa solo si sus cortes caen sobre la imagen: se cruzan con los
    de scdet y tiene que coincidir al menos la mitad al cuadro. Si el TC del
    MOV no es el del EDL se prueba un desfasaje. Un EDL de otro armado o de
    otra pelicula no pasa y se sigue con scdet, avisando.
    """
    if not path:
        return {"used": False, "path": ""}, []
    state = {"used": False, "path": path}
    if not os.path.isfile(path):
        state["reason"] = "EDL not found"
        _log.warning("EDL no encontrado: %s", path)
        return state, []
    edl = _edl()
    fps = int(round(info["fps"]))
    parsed = edl.read_edl(path, fps)
    if not parsed.events:
        state["reason"] = "The EDL has no video events"
        _log.warning("EDL sin eventos de video: %s", path)
        return state, []
    if info.get("timecode"):
        offset = edl.tc_frames(info["timecode"], fps)
    else:
        offset = parsed.rec_range()[0]
    delta, matched, count = edl.align(parsed, offset, detected, total)
    state.update({"title": parsed.title, "events": len(parsed.events), "edl_cuts": count,
                  "matched": matched, "picture_cuts": len(detected), "offset": delta})
    if not edl.is_aligned(matched, count):
        state["reason"] = "Only %d of %d cuts of the EDL match the movie" % (matched, count)
        _log.warning("EDL descartado: coinciden %d de %d cortes (desfasaje %d)",
                     matched, count, delta)
        return state, []
    offset += delta
    cuts = edl.cut_frames(parsed, offset, total)
    segs = edl.segments(parsed, offset, total)
    state.update({"used": True, "cuts": cuts,
                  "missed": count - matched, "extra": len(detected) - matched})
    _log.info("EDL %s: %d planos, %d cortes; coinciden %d al cuadro con los de la imagen "
              "(desfasaje %d); scdet perdio %d y marco %d de mas",
              parsed.title, len(parsed.events), count, matched, delta,
              count - matched, len(detected) - matched)
    return state, segs


def shot_range(cuts, frame, total):
    """(in, out) inclusivos del plano que contiene `frame`."""
    k = bisect.bisect_right(cuts, frame)
    start = cuts[k - 1] if k > 0 else 0
    end = (cuts[k] - 1) if k < len(cuts) else total - 1
    return start, end


# -- imagen de los thumbs ----------------------------------------------------

def image_size(data):
    """(ancho, alto) de un JPG o PNG leyendo solo la cabecera, o None."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
    if data[:2] != b"\xff\xd8":
        return None
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            height, width = struct.unpack(">HH", data[i + 5:i + 9])
            return width, height
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    return None


def _longest_run(values, threshold):
    best, start = (0, 0), None
    for i, v in enumerate(list(values) + [0]):
        if v > threshold and start is None:
            start = i
        elif v <= threshold and start is not None:
            if i - start > best[1] - best[0]:
                best = (start, i)
            start = None
    return best


def picture_rect(gray, w, h, aspect):
    """(x, y, ancho, alto) del area de imagen dentro de un thumb.

    Saca barras negras y la UI de un player (bandas oscuras con texto): la
    mediana de una fila de banda es oscura aunque tenga letras. Despues
    fuerza el aspecto del video: una escena oscura de un lado hacia que la
    deteccion se comiera media imagen (aspectos de 0,99 a 2,86 medidos).
    """
    rows = [sorted(gray[y * w:(y + 1) * w])[w // 2] for y in range(h)]
    y0, y1 = _longest_run(rows, DARK_MEDIAN)
    if y1 - y0 < h * 0.4:
        y0, y1 = 0, h
    sample = list(range(y0, y1, max(1, (y1 - y0) // 64)))
    cols = [sorted(gray[x + y * w] for y in sample)[len(sample) // 2] for x in range(w)]
    x0, x1 = _longest_run(cols, DARK_MEDIAN)
    if x1 - x0 < w * 0.5:
        x0, x1 = 0, w
    pw, ph = x1 - x0, y1 - y0
    if aspect and abs(pw / float(ph) / aspect - 1.0) > 0.06:
        if pw / float(ph) < aspect:
            # Demasiado angosto: se perdio un costado oscuro. Ancho por aspecto.
            new_w = min(w, int(round(ph * aspect)))
            cx = (x0 + x1) / 2.0
            x0 = int(round(min(max(cx - new_w / 2.0, 0), w - new_w)))
            pw = new_w
        else:
            new_h = min(h, int(round(pw / aspect)))
            cy = (y0 + y1) / 2.0
            y0 = int(round(min(max(cy - new_h / 2.0, 0), h - new_h)))
            ph = new_h
    return x0, y0, pw, ph


def batch_rects(rects_by_size, aspect):
    """Un recorte por lote: todos los thumbs del mismo tamano salen del mismo
    lugar (un screener exportado igual). La moda de las detecciones con buen
    aspecto le gana al recorte de cada uno, que falla en escenas oscuras."""
    result = {}
    for size, rects in rects_by_size.items():
        if len(rects) < 5:
            continue
        good = [r for r in rects if aspect and abs(r[2] / float(r[3]) / aspect - 1.0) <= 0.03]
        pool = good or rects
        rounded = Counter(tuple(2 * (v // 2) for v in r) for r in pool)
        result[size] = rounded.most_common(1)[0][0]
    return result


def inner_crop(rect):
    x, y, w, h = rect
    mx, my = int(w * (1 - INNER) / 2), int(h * (1 - INNER) / 2)
    return x + mx, y + my, w - 2 * mx, h - 2 * my


# -- video -------------------------------------------------------------------

def probe_video(ffprobe, path):
    out = run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_streams",
               "-show_format", "-of", "json", path])
    data = json.loads(out.decode("utf-8", "replace"))
    stream = data["streams"][0]
    num, den = (stream.get("r_frame_rate") or "24/1").split("/")
    fps = float(num) / float(den or 1)
    timecode = (stream.get("tags") or {}).get("timecode") or ""
    if not timecode:
        for other in data.get("streams", []):
            timecode = (other.get("tags") or {}).get("timecode") or timecode
    frames = int(stream.get("nb_frames") or 0)
    if not frames:
        duration = float(stream.get("duration") or data.get("format", {}).get("duration") or 0)
        frames = int(round(duration * fps))
    return {"width": int(stream["width"]), "height": int(stream["height"]),
            "fps": fps, "frames": frames, "timecode": timecode}


def video_key(path):
    st = os.stat(path)
    text = "%s|%d|%d|%s" % (os.path.abspath(path).lower(), st.st_size, int(st.st_mtime), INDEX_VERSION)
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def build_index(job, info, folder):
    """Recorre el video una vez. Archivos .tmp y renombre al final: un
    indice cortado a la mitad no se confunde con uno completo."""
    os.makedirs(folder, exist_ok=True)
    chain = ("[0:v:0]scale=320:-2:flags=area,crop=iw*%.2f:ih*%.2f,scale=%d:%d:flags=area,"
             "split=2[a][b];[a]scale=9:8:flags=area,format=gray[d8];"
             "[b]scdet=threshold=0.1,metadata=mode=print:file=scd.tmp,"
             "scale=32:18:flags=area,format=gray[g32]") % (INNER, INNER, BASE_W, BASE_H)
    args = [job["ffmpeg"], "-nostdin", "-v", "error", "-i", job["video"], "-an", "-sn", "-dn",
            "-filter_complex", chain,
            "-map", "[d8]", "-f", "rawvideo", "-y", "d8.tmp",
            "-map", "[g32]", "-f", "rawvideo", "-y", "g32.tmp",
            "-progress", "pipe:1", "-nostats"]
    _log.info("Indice: %s", " ".join(args))
    t0 = time.time()
    proc = subprocess.Popen(args, cwd=folder, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            creationflags=CREATE_NO_WINDOW, text=True)
    total = info["frames"]
    last = 0.0
    for line in proc.stdout:
        if line.startswith("frame="):
            try:
                done = int(line.split("=", 1)[1])
            except ValueError:
                continue
            now = time.time()
            if now - last > 0.5:
                last = now
                emit("progress", stage="index", done=done, total=total,
                     elapsed=round(now - t0, 1))
    err = proc.stderr.read()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg fallo al indexar el video: %s" % err.strip()[-400:])
    frames = os.path.getsize(os.path.join(folder, "d8.tmp")) // D8
    scores = array.array("f", [0.0]) * frames
    current = 0
    with open(os.path.join(folder, "scd.tmp"), encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith("frame:"):
                current = int(line.split()[0][6:])
            elif line.startswith("lavfi.scd.score=") and current < frames:
                scores[current] = float(line.split("=", 1)[1])
    with open(os.path.join(folder, "scd.bin"), "wb") as handle:
        scores.tofile(handle)
    os.replace(os.path.join(folder, "d8.tmp"), os.path.join(folder, "d8.bin"))
    os.replace(os.path.join(folder, "g32.tmp"), os.path.join(folder, "g32.bin"))
    os.remove(os.path.join(folder, "scd.tmp"))
    meta = dict(info, frames=frames, video=job["video"], seconds=round(time.time() - t0, 1))
    with open(os.path.join(folder, "meta.json"), "w", encoding="utf-8", newline="\n") as handle:
        json.dump(meta, handle, indent=1)
    _log.info("Indice listo: %d cuadros en %.1f s", frames, time.time() - t0)
    return meta


def ensure_index(job, info):
    folder = os.path.join(job["cache_dir"], "index", video_key(job["video"]))
    meta_path = os.path.join(folder, "meta.json")
    if os.path.isfile(meta_path):
        with open(meta_path, encoding="utf-8") as handle:
            meta = json.load(handle)
        _log.info("Indice en cache: %s (%d cuadros)", folder, meta["frames"])
        emit("progress", stage="index", done=meta["frames"], total=meta["frames"], cached=True)
        return folder, meta
    return folder, build_index(job, info, folder)


# -- thumbs -------------------------------------------------------------------

def _decode_gray(ffmpeg, path, width, height, scale_w):
    w = min(width, scale_w)
    h = max(2, int(round(height * w / float(width))))
    data = run([ffmpeg, "-v", "error", "-i", path, "-vf", "scale=%d:%d:flags=area,format=gray" % (w, h),
                "-f", "rawvideo", "-"])
    return data, w, h


def thumb_rect(ffmpeg, thumb, aspect):
    width, height = thumb["size"]
    gray, w, h = _decode_gray(ffmpeg, thumb["path"], width, height, 640)
    x, y, pw, ph = picture_rect(gray, w, h, aspect)
    k = width / float(w)
    return int(x * k), int(y * k), int(pw * k), int(ph * k)


def thumb_prints(ffmpeg, thumb, rect, folder):
    """Huellas del thumb con el mismo recorte que el video, y el JPG chico
    para la ventana de info. Cacheadas por contenido + recorte."""
    x, y, w, h = inner_crop(rect)
    tag = "%s_%d_%d_%d_%d" % (thumb["sha1"], x, y, w, h)
    paths = {k: os.path.join(folder, "%s.%s" % (tag, k)) for k in ("d8", "g32", "fine")}
    small = os.path.join(folder, "%s_480.jpg" % thumb["sha1"])
    if not all(os.path.isfile(p) for p in paths.values()) or not os.path.isfile(small):
        chain = ("[0:v]split=2[o][s];[o]crop=%d:%d:%d:%d,split=2[c][f];"
                 "[c]scale=%d:%d:flags=area,split=2[a][b];"
                 "[a]scale=9:8:flags=area,format=gray[d8];[b]scale=32:18:flags=area,format=gray[g32];"
                 "[f]scale=%d:%d:flags=area,format=gray[fine];"
                 "[s]scale=480:-2:flags=area,format=yuvj420p[small]") % (
                     w, h, x, y, BASE_W, BASE_H, FINE_W, FINE_H)
        run([ffmpeg, "-v", "error", "-i", thumb["path"], "-filter_complex", chain,
             "-map", "[d8]", "-f", "rawvideo", "-y", paths["d8"] + ".tmp",
             "-map", "[g32]", "-f", "rawvideo", "-y", paths["g32"] + ".tmp",
             "-map", "[fine]", "-f", "rawvideo", "-y", paths["fine"] + ".tmp",
             "-map", "[small]", "-frames:v", "1", "-q:v", "4", "-f", "image2", "-y", small + ".tmp"])
        for p in paths.values():
            os.replace(p + ".tmp", p)
        os.replace(small + ".tmp", small)
    result = {}
    for key, p in paths.items():
        with open(p, "rb") as handle:
            result[key] = handle.read()
    result["small"] = small
    return result


# -- matcheo (procesos) -------------------------------------------------------

_W = {}


def _worker_init(index_folder, cuts):
    """Cada proceso carga el indice una vez (dHash en ints, g32 por mmap).

    `cuts` llega armado (del EDL o de scdet): los planos son la unidad de
    busqueda, y con los del EDL dos planos parecidos pegados ya no se
    funden en uno.
    """
    with open(os.path.join(index_folder, "d8.bin"), "rb") as handle:
        raw = handle.read()
    frames = len(raw) // D8
    _W["d8"] = [dhash(raw[i * D8:(i + 1) * D8]) for i in range(frames)]
    handle = open(os.path.join(index_folder, "g32.bin"), "rb")
    _W["g32"] = mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ)
    _W["g32_handle"] = handle
    _W["cuts"] = cuts
    _W["frames"] = frames
    seg = array.array("i", [0]) * frames
    bounds = [0] + cuts + [frames]
    for s in range(len(bounds) - 1):
        for i in range(bounds[s], bounds[s + 1]):
            seg[i] = s
    _W["seg"] = seg
    _W["bounds"] = bounds


def _frame_g32(i):
    return _W["g32"][i * G32:(i + 1) * G32]


def _best_in_segment(norm, s, around=None, lo=None, hi=None):
    bounds = _W["bounds"]
    a, b = bounds[s], bounds[s + 1]
    if lo is not None:
        a, b = max(a, lo), min(b, hi)
    if b <= a:
        return -1.0, a
    best = (-1.0, a)
    step = 3 if b - a > 12 else 1
    for i in range(a, b, step):
        score = ncc(norm, _frame_g32(i))
        if score > best[0]:
            best = (score, i)
    if step > 1:
        center = best[1]
        for i in range(max(a, center - step + 1), min(b, center + step)):
            score = ncc(norm, _frame_g32(i))
            if score > best[0]:
                best = (score, i)
    return best


def search(task):
    """Candidatos de un thumb: [(score, frame, segmento, hamming)], mejor primero.

    `lo`/`hi` acotan la busqueda a una ventana de cuadros (entre anclas).
    """
    key, d8, g32, lo, hi, max_d, k = task
    target = dhash(d8)
    norm = normalized(list(g32))
    hashes, seg = _W["d8"], _W["seg"]
    lo = 0 if lo is None else max(0, lo)
    hi = _W["frames"] if hi is None else min(_W["frames"], hi)
    best = {}
    for i in range(lo, hi):
        d = (target ^ hashes[i]).bit_count()
        if d <= max_d:
            s = seg[i]
            if s not in best or d < best[s][0]:
                best[s] = (d, i)
    out = []
    for s, (d, i) in sorted(best.items(), key=lambda kv: kv[1][0])[:k]:
        score, frame = _best_in_segment(norm, s, lo=lo, hi=hi)
        out.append((round(score, 4), frame, s, d))
    out.sort(reverse=True)
    return key, out


# -- decision ------------------------------------------------------------------

def margins(cands):
    """(margen global, margen local) del mejor contra otros planos."""
    if not cands:
        return 0.0, 0.0
    best = cands[0]
    others = [c for c in cands[1:] if c[2] != best[2]]
    local = [c for c in others if abs(c[1] - best[1]) <= LOCAL_RADIUS]
    glob = best[0] - (others[0][0] if others else 0.0)
    loc = best[0] - (local[0][0] if local else 0.0)
    return round(glob, 4), round(loc, 4)


def order_breaks(positions, neighbors=3):
    """Indices (en orden de planilla) de anclas que caen antes o despues de
    TODAS sus vecinas: la escena se movio en el montaje."""
    moved = set()
    for idx in range(len(positions)):
        prev = positions[max(0, idx - neighbors):idx]
        nxt = positions[idx + 1:idx + 1 + neighbors]
        p = positions[idx]
        if prev and nxt and ((p < min(prev) and p < min(nxt)) or (p > max(prev) and p > max(nxt))):
            moved.add(idx)
    return moved


def classify(score, margin_local, in_order):
    if score >= AUTO_SCORE and margin_local >= AUTO_MARGIN and in_order:
        return "auto"
    if score >= REVIEW_SCORE:
        return "review"
    return "not_found"


# -- refinado al cuadro exacto -----------------------------------------------

def refine(ffmpeg, video, fine_thumb, frame, fps, total):
    start = max(0, frame - FINE_RADIUS)
    count = min(total, frame + FINE_RADIUS + 1) - start
    data = run([ffmpeg, "-v", "error", "-ss", "%.6f" % (start / fps), "-i", video,
                "-frames:v", str(count), "-an",
                "-vf", "crop=iw*%.2f:ih*%.2f,scale=%d:%d:flags=area,format=gray" % (INNER, INNER, FINE_W, FINE_H),
                "-f", "rawvideo", "-"])
    norm = normalized(list(fine_thumb))
    n = FINE_W * FINE_H
    best = (-1.0, frame)
    for k in range(len(data) // n):
        score = ncc(norm, data[k * n:(k + 1) * n])
        if score > best[0]:
            best = (score, start + k)
    return best


# -- principal -----------------------------------------------------------------

def main(job_path):
    _setup_log()
    t0 = time.time()
    with open(job_path, encoding="utf-8") as handle:
        job = json.load(handle)
    for key in ("ffmpeg", "ffprobe", "video"):
        if not os.path.isfile(job[key]):
            raise RuntimeError("No existe %s: %s" % (key, job[key]))
    workers = max(1, int(job.get("workers") or min(8, os.cpu_count() or 2)))
    _log.info("Job %s | video %s | %d thumbs | %d procesos", job_path, job["video"],
              len(job["rows"]), workers)

    info = probe_video(job["ffprobe"], job["video"])
    aspect = info["width"] / float(info["height"])
    _log.info("Video: %dx%d %.3f fps %d cuadros TC %s", info["width"], info["height"],
              info["fps"], info["frames"], info["timecode"])
    index_folder, meta = ensure_index(job, info)
    frames = meta["frames"]
    vkey = video_key(job["video"])

    # Thumbs: tamano, area de imagen por lote, huellas.
    rows = job["rows"]
    thumbs = {}
    for row in rows:
        if row["sha1"] in thumbs:
            continue
        with open(row["file"], "rb") as handle:
            head = handle.read(65536)
        size = image_size(head)
        if size is None:
            _log.warning("Thumb ilegible: fila %s %s", row["row"], row["file"])
            continue
        thumbs[row["sha1"]] = {"sha1": row["sha1"], "path": row["file"], "size": size}
    emit("progress", stage="thumbs", done=0, total=len(thumbs))
    rects = {}
    with concurrent.futures.ThreadPoolExecutor(workers) as pool:
        futures = {pool.submit(thumb_rect, job["ffmpeg"], t, aspect): key for key, t in thumbs.items()}
        for n, future in enumerate(concurrent.futures.as_completed(futures), 1):
            rects[futures[future]] = future.result()
            if n % 20 == 0:
                emit("progress", stage="thumbs", done=n // 2, total=len(thumbs))
    by_size = {}
    for key, rect in rects.items():
        by_size.setdefault(tuple(thumbs[key]["size"]), []).append(rect)
    lots = batch_rects(by_size, aspect)
    for key in rects:
        size = tuple(thumbs[key]["size"])
        if size in lots:
            rects[key] = lots[size]
            thumbs[key]["lot"] = True
    _log.info("Lotes de recorte: %s", {"%dx%d" % k: v for k, v in lots.items()})
    fp_dir = os.path.join(job["cache_dir"], "thumbs")
    os.makedirs(fp_dir, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(workers) as pool:
        futures = {pool.submit(thumb_prints, job["ffmpeg"], thumbs[key], rects[key], fp_dir): key
                   for key in rects}
        for n, future in enumerate(concurrent.futures.as_completed(futures), 1):
            thumbs[futures[future]]["prints"] = future.result()
            if n % 20 == 0:
                emit("progress", stage="thumbs", done=len(thumbs) // 2 + n // 2, total=len(thumbs))
    emit("progress", stage="thumbs", done=len(thumbs), total=len(thumbs))

    # Decisiones previas: confirmadas en este mismo video se respetan tal cual;
    # de otro video (corte nuevo) se busca con la huella del cuadro confirmado.
    decisions = job.get("decisions") or {}

    def prints_for(sha1):
        decision = decisions.get(sha1) or {}
        if decision.get("video") != vkey and decision.get("d8") and decision.get("g32"):
            return bytes.fromhex(decision["d8"]), bytes.fromhex(decision["g32"])
        p = thumbs[sha1]["prints"]
        return p["d8"], p["g32"]

    # Cortes: los del EDL si hay uno que coincide con la imagen; si no, scdet.
    with open(os.path.join(index_folder, "scd.bin"), "rb") as handle:
        scores = array.array("f")
        scores.frombytes(handle.read())
    detected = cut_frames(scores)
    edl_info, segs = load_edl(job.get("edl"), info, frames, detected)
    cuts = edl_info.pop("cuts") if edl_info.get("used") else detected
    seg_starts = [s["in"] for s in segs]

    keys = [s for s in thumbs if "prints" in thumbs[s]]
    t1 = time.time()
    cands = {}
    with concurrent.futures.ProcessPoolExecutor(workers, initializer=_worker_init,
                                                initargs=(index_folder, cuts)) as pool:
        tasks = []
        for sha1 in keys:
            d8, g32 = prints_for(sha1)
            tasks.append((sha1, d8, g32, None, None, HAMMING_MAX, CANDIDATE_SEGMENTS))
        for n, (sha1, out) in enumerate(pool.map(search, tasks, chunksize=4), 1):
            cands[sha1] = out
            if n % 10 == 0:
                emit("progress", stage="match", done=n, total=len(tasks))
        _log.info("Busqueda global: %.1f s", time.time() - t1)

        # Anclas en orden de planilla (filas, no shots: un shot se repite).
        ordered = [r for r in rows if r["sha1"] in cands]
        anchors = []
        for idx, row in enumerate(ordered):
            c = cands[row["sha1"]]
            if c and c[0][0] >= AUTO_SCORE and margins(c)[1] >= AUTO_MARGIN:
                anchors.append(idx)
        moved = order_breaks([cands[ordered[i]["sha1"]][0][1] for i in anchors])
        moved_rows = {anchors[i] for i in moved}
        clean = [i for i in anchors if i not in moved_rows]
        clean_pos = [cands[ordered[i]["sha1"]][0][1] for i in clean]

        # El resto: buscar entre el ancla anterior y la siguiente.
        window_tasks = []
        for idx, row in enumerate(ordered):
            if idx in anchors:
                continue
            k = bisect.bisect_left(clean, idx)
            lo = clean_pos[k - 1] if k > 0 else 0
            hi = clean_pos[k] + 1 if k < len(clean) else frames
            if hi <= lo:
                lo, hi = 0, frames
            d8, g32 = prints_for(row["sha1"])
            window_tasks.append(((row["sha1"], idx), d8, g32, lo, hi, HAMMING_MAX + 4, 15))
        windowed = {}
        for n, (key, out) in enumerate(pool.map(search, window_tasks, chunksize=4), 1):
            windowed[key] = out
            if n % 10 == 0:
                emit("progress", stage="window", done=n, total=len(window_tasks))
        _log.info("Busqueda entre anclas: %.1f s", time.time() - t1)

    # Resultado por fila.
    results = []
    for idx, row in enumerate(ordered):
        sha1 = row["sha1"]
        global_c = cands[sha1]
        if idx in anchors:
            chosen_c, in_order = global_c, idx not in moved_rows
        else:
            local_c = windowed.get((sha1, idx)) or []
            # Si la ventana no encuentra nada y el global es fuerte, se ofrece
            # el global (escena movida fuera de las anclas).
            if local_c and (not global_c or local_c[0][0] >= global_c[0][0] - 0.05):
                chosen_c, in_order = local_c, True
            else:
                chosen_c, in_order = global_c, False
        best = chosen_c[0] if chosen_c else None
        glob_m, loc_m = margins(chosen_c)
        level = classify(best[0], loc_m, in_order) if best else "not_found"
        note = ""
        if best and not in_order:
            note = "Out of sheet order: the scene may have moved in the cut"
        decision = decisions.get(sha1) or {}
        if decision.get("video") == vkey and decision.get("state") in ("confirmed", "not_in_cut"):
            level = decision["state"]
            if level == "confirmed":
                best = (best[0] if best else 1.0, int(decision["frame"]), -1, 0)
        results.append({
            "row": row["row"], "shot": row["shot"], "sha1": sha1, "level": level,
            "frame": best[1] if best else None, "score": best[0] if best else 0.0,
            "margin": loc_m, "margin_global": glob_m, "in_order": in_order, "note": note,
            "lot": bool(thumbs[sha1].get("lot")),
            "thumb": thumbs[sha1]["prints"]["small"],
            # Area de imagen en pixeles del thumb original: la ventana de
            # revision la usa para mezclar o restar el thumb con el visor.
            "rect": list(rects[sha1]), "size": list(thumbs[sha1]["size"]),
            "candidates": [[c[1], c[0]] for c in chosen_c[:5]],
        })

    # Planos compartidos: dos filas de shots DISTINTOS no pueden caer en el
    # mismo plano. Gana la de mayor puntaje; la otra va a revision.
    by_shot_range = {}
    for r in results:
        if r["frame"] is None or r["level"] in ("not_found", "not_in_cut"):
            continue
        by_shot_range.setdefault(shot_range(cuts, r["frame"], frames), []).append(r)
    for group in by_shot_range.values():
        names = {r["shot"] for r in group}
        if len(names) < 2:
            continue
        group.sort(key=lambda r: -r["score"])
        for r in group[1:]:
            if r["shot"] != group[0]["shot"] and r["level"] in ("auto",):
                r["level"] = "review"
                r["note"] = "Same shot as %s" % group[0]["shot"]

    # Cuadro exacto (en paralelo: cada uno es un ffmpeg corto).
    to_refine = [r for r in results if r["frame"] is not None and r["level"] in ("auto", "review")]
    emit("progress", stage="refine", done=0, total=len(to_refine))
    with concurrent.futures.ThreadPoolExecutor(workers) as pool:
        futures = {pool.submit(refine, job["ffmpeg"], job["video"],
                               thumbs[r["sha1"]]["prints"]["fine"], r["frame"], info["fps"], frames): r
                   for r in to_refine}
        for n, future in enumerate(concurrent.futures.as_completed(futures), 1):
            r = futures[future]
            try:
                score, frame = future.result()
                r["frame"], r["fine_score"] = frame, round(score, 4)
            except Exception as exc:
                _log.warning("Refinado fallo en fila %s: %s", r["row"], exc)
            if n % 20 == 0:
                emit("progress", stage="refine", done=n, total=len(to_refine))

    # IN/OUT: el plano del EDL, o el plano entre cortes de scdet. Sin corte
    # claro, solo el cuadro. Con EDL, el clip y el SRC TC del plano.
    fps_int = int(round(info["fps"]))
    for r in results:
        if r["frame"] is None:
            r["in"] = r["out"] = None
            continue
        seg = _edl().segment_at(segs, r["frame"], seg_starts) if segs else None
        if seg is not None:
            r["cut_ok"], (r["in"], r["out"]) = True, (seg["in"], seg["out"])
            r["edl"] = _edl().source_info(seg, r["frame"], fps_int)
        else:
            start, end = shot_range(cuts, r["frame"], frames)
            r["cut_ok"] = end - start + 1 <= MAX_SHOT_FRAMES
            r["in"], r["out"] = (start, end) if r["cut_ok"] else (r["frame"], r["frame"])
        g = _frame_print_hex(index_folder, r["frame"])
        r["frame_d8"], r["frame_g32"] = g
        # Plano que vuelve en el montaje (A-B-A): el segundo candidato es el
        # mismo clip en otro evento. El thumb puede ser de cualquiera de los
        # dos; se avisa para que la revision mire ambos. Solo en los dudosos:
        # en los aceptados el segundo ya quedo 0,10 por debajo.
        if seg is not None and r["level"] == "review" and not r["note"] and len(r["candidates"]) > 1 \
                and r["candidates"][1][1] >= REVIEW_SCORE:
            other = _edl().segment_at(segs, r["candidates"][1][0], seg_starts)
            if other is not None and other["event"] != seg["event"] and other["clip"] == seg["clip"]:
                r["note"] = "Same clip also at candidate 2 (EDL event %d)" % other["event"]

    result = {"video": job["video"], "video_key": vkey, "fps": info["fps"],
              "index_folder": index_folder, "cuts": cuts,
              "timecode": info["timecode"], "frames": frames, "rows": results,
              "width": info["width"], "height": info["height"],
              "edl": edl_info, "segments": segs,
              "seconds": round(time.time() - t0, 1),
              "levels": dict(Counter(r["level"] for r in results))}
    with open(job["out"], "w", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, indent=1)
    _log.info("Listo en %.1f s: %s", time.time() - t0, result["levels"])
    for r in results:
        _log.info("  fila %-5s %-16s %-10s cuadro %-7s score %.3f margen %.3f %s", r["row"], r["shot"],
                  r["level"], r["frame"], r["score"], r["margin"], r["note"])
    emit("done", result=job["out"], levels=result["levels"], seconds=result["seconds"])


def _frame_print_hex(index_folder, frame):
    """Huellas del cuadro elegido: con un corte nuevo, la confirmacion se
    re-ubica buscando este cuadro en vez del thumb."""
    with open(os.path.join(index_folder, "d8.bin"), "rb") as handle:
        handle.seek(frame * D8)
        d8 = handle.read(D8)
    with open(os.path.join(index_folder, "g32.bin"), "rb") as handle:
        handle.seek(frame * G32)
        g32 = handle.read(G32)
    return d8.hex(), g32.hex()


if __name__ == "__main__":
    try:
        main(sys.argv[1])
    except Exception as exc:
        _log.exception("Fallo el motor")
        emit("error", message=str(exc))
        sys.exit(1)
