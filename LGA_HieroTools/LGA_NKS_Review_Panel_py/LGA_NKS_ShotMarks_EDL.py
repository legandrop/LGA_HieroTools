"""
____________________________________________________________________

  LGA_NKS_ShotMarks_EDL v1.00 | Lega

  Nucleo sin host: lee un EDL CMX 3600 del armado y da los cortes del
  video en cuadros, mas el clip de camara y el SRC TC de cada plano.

  Existe porque el detector de cortes por imagen (scdet) del motor de
  thumbnails no alcanza para un largo: medido contra el EDL de un
  armado de 2,6 h, acerto 1460 de 1587 cortes al cuadro, pero perdio
  125 (cortes entre planos de la misma escena y luz, con puntaje 2-6
  contra un umbral de 6) y marco 32 que no existen (flashes,
  relampagos, movimientos rapidos). Cambiar el umbral solo cambia un
  error por el otro. El EDL del mismo armado trae los cortes exactos.

  No importa hiero ni Qt: lo usan el dialogo de Shot Marks, el motor
  (proceso aparte con el Python embebido) y los tests.

  v1.00: Version inicial.
____________________________________________________________________
"""

import bisect
import re

TC = r"(\d{1,2}[:;.]\d{2}[:;.]\d{2}[:;.]\d{2})"
# Numero, reel (puede tener espacios: "Universal Counting Leader"), pista,
# transicion (C, D, W001, K...), duracion opcional y los cuatro TC.
EVENT_RE = re.compile(
    r"^\s*(\d+)\s+(.+?)\s+(\S+)\s+(C|D|W\d+|K[BO]?\d*)\s+(?:(\d+)\s+)?"
    + TC + r"\s+" + TC + r"\s+" + TC + r"\s+" + TC + r"\s*$")
CLIP_RE = re.compile(r"^\*\s*(FROM|TO) CLIP NAME:\s*(.*)$", re.IGNORECASE)
SPEED_RE = re.compile(r"^M2\s")
MEDIA_EXT_RE = re.compile(r"\.(mov|mxf|mp4|ari|r3d|braw|dng|exr|dpx|wav)$", re.IGNORECASE)

# Alineacion contra los cortes detectados en la imagen: desfasajes que se
# prueban (10 s de cola a 24/25/30 fps entran) y cuantos cortes del EDL
# tienen que coincidir al cuadro para confiar en el EDL.
ALIGN_RADIUS = 400
ALIGN_MIN_RATIO = 0.5


class Event(object):
    """Un plano del EDL. rec_* y src_* en cuadros de TC; rec_out exclusivo."""

    def __init__(self, number, reel, track, transition, src_in, src_out, rec_in, rec_out):
        self.number = number
        self.reel = reel
        self.track = track
        self.transition = transition
        self.src_in = src_in
        self.src_out = src_out
        self.rec_in = rec_in
        self.rec_out = rec_out
        self.clip = ""
        self.speed = False  # M2: cambio de velocidad, el SRC no avanza 1 a 1

    def name(self):
        """Clip sin extension de media; sin clip (negro, titulos), el reel."""
        return MEDIA_EXT_RE.sub("", self.clip) or self.reel


class Edl(object):
    def __init__(self, title, drop_frame, events):
        self.title = title
        self.drop_frame = drop_frame
        self.events = events  # solo video, con duracion, en orden de REC

    def rec_range(self):
        if not self.events:
            return None
        return self.events[0].rec_in, max(e.rec_out for e in self.events)


def tc_frames(text, fps, drop_frame=False):
    """Cuadros de un TC. Drop-frame solo para 30/60 nominal (29,97/59,94)."""
    hh, mm, ss, ff = (int(v) for v in re.split(r"[:;.]", text))
    frames = ((hh * 60 + mm) * 60 + ss) * fps + ff
    if drop_frame and fps in (30, 60):
        drop = fps // 15
        minutes = hh * 60 + mm
        frames -= drop * (minutes - minutes // 10)
    return frames


def frames_tc(frames, fps):
    frames = max(0, int(frames))
    seconds, ff = divmod(frames, fps)
    minutes, ss = divmod(seconds, 60)
    hh, mm = divmod(minutes, 60)
    return "%02d:%02d:%02d:%02d" % (hh, mm, ss, ff)


def _is_video(track):
    track = track.upper()
    return track == "B" or "V" in track


def parse_edl(text, fps):
    """Edl con los eventos de video con duracion.

    - Los eventos de largo cero (el lado "desde" de una disolvencia en CMX)
      se descartan: el plano entrante empieza en el REC IN del evento D.
    - "* FROM CLIP NAME:" da el nombre del clip; si sigue en lineas sueltas
      (los titulos traen el texto entero), vale solo la primera.
    - M2 marca cambio de velocidad.
    """
    title, drop_frame = "", False
    events = []
    current = None
    for raw in text.splitlines():
        line = raw.rstrip()
        upper = line.strip().upper()
        if upper.startswith("TITLE:"):
            title = line.split(":", 1)[1].strip()
            continue
        if upper.startswith("FCM:"):
            drop_frame = "NON" not in upper and "DROP" in upper
            continue
        match = EVENT_RE.match(line)
        if match:
            number, reel, track, transition = match.group(1, 2, 3, 4)
            tcs = [tc_frames(t, fps, drop_frame) for t in match.group(6, 7, 8, 9)]
            current = None
            if not _is_video(track) or tcs[3] <= tcs[2]:
                continue
            current = Event(int(number), reel.strip(), track, transition, *tcs)
            events.append(current)
            continue
        if current is None:
            continue
        clip = CLIP_RE.match(line.strip())
        if clip:
            # TO CLIP NAME es el entrante de una disolvencia: es este evento.
            if clip.group(1).upper() == "TO" or not current.clip:
                current.clip = clip.group(2).strip()
            continue
        if SPEED_RE.match(line):
            current.speed = True
    events.sort(key=lambda e: (e.rec_in, e.number))
    return Edl(title, drop_frame, events)


def read_edl(path, fps):
    with open(str(path), "rb") as handle:
        data = handle.read()
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            return parse_edl(data.decode(encoding), fps)
        except UnicodeDecodeError:
            continue
    return parse_edl(data.decode("latin-1", "replace"), fps)


def cut_frames(edl, offset, total):
    """Cuadros del video donde empieza un plano (REC IN y REC OUT de cada
    evento, con offset = TC del cuadro 0 del video), dentro de (0, total)."""
    points = set()
    for event in edl.events:
        for value in (event.rec_in - offset, event.rec_out - offset):
            if 0 < value < total:
                points.add(value)
    return sorted(points)


def align(edl, offset, detected, total):
    """Desfasaje y coincidencias de los cortes del EDL contra los detectados.

    Devuelve (desfasaje, coincidencias, cortes del EDL). El desfasaje es lo
    que hay que sumarle a `offset` para que el EDL caiga sobre la imagen: 0
    si el EDL y el MOV son del mismo armado y el TC del MOV es el del EDL. Se elige el que hace
    coincidir mas cortes al cuadro, y ante empate el mas chico.
    """
    cuts = cut_frames(edl, offset, total)
    if not cuts or not detected:
        return 0, 0, len(cuts)
    votes = {}
    for cut in cuts:
        lo = bisect.bisect_left(detected, cut - ALIGN_RADIUS)
        hi = bisect.bisect_right(detected, cut + ALIGN_RADIUS)
        for value in detected[lo:hi]:
            delta = cut - value
            votes[delta] = votes.get(delta, 0) + 1
    if not votes:
        return 0, 0, len(cuts)
    best = max(votes.items(), key=lambda kv: (kv[1], -abs(kv[0])))
    # Ante una diferencia chica se prefiere 0: el TC del MOV manda.
    if votes.get(0, 0) >= best[1] * 0.9:
        return 0, votes.get(0, 0), len(cuts)
    return best[0], best[1], len(cuts)


def is_aligned(matched, total):
    return total > 0 and matched >= total * ALIGN_MIN_RATIO


def segments(edl, offset, total):
    """Planos del EDL en cuadros del video, listos para JSON.

    [{"in", "out" (inclusivo), "event", "clip", "src_in", "src_out" (cuadros
    de TC), "speed"}], en orden. Los que caen fuera del video se descartan.
    El motor los pasa en el resultado: la ventana de revision los usa sin
    volver a leer el EDL.
    """
    out = []
    for event in edl.events:
        start = max(0, event.rec_in - offset)
        end = min(total, event.rec_out - offset) - 1
        if end < start:
            continue
        # Si el video empieza adentro del plano, el SRC arranca igual de corrido.
        src_in = event.src_in + start - (event.rec_in - offset)
        out.append({"in": start, "out": end, "event": event.number, "clip": event.name(),
                    "src_in": src_in, "src_out": event.src_out, "speed": event.speed})
    return out


def segment_at(segs, frame, starts=None):
    """Plano que cubre el cuadro `frame`, o None (hueco de la pista).

    Los eventos de una pista no se pisan: alcanza con el ultimo que empieza
    antes. `starts` (los "in" ya armados) evita rearmarlos en cada llamada.
    """
    if starts is None:
        starts = [s["in"] for s in segs]
    index = bisect.bisect_right(starts, frame) - 1
    if index >= 0 and segs[index]["out"] >= frame:
        return segs[index]
    return None


def source_info(seg, frame, fps):
    """{clip, src_in, src_out, src_frame, event} de un plano, en texto.

    src_frame es el SRC TC del cuadro pedido; con cambio de velocidad (M2)
    queda vacio porque el SRC no avanza 1 a 1. src_out es exclusivo, como
    en el EDL.
    """
    src_frame = ""
    if not seg.get("speed"):
        src_frame = frames_tc(seg["src_in"] + frame - seg["in"], fps)
    return {"clip": seg["clip"], "src_in": frames_tc(seg["src_in"], fps),
            "src_out": frames_tc(seg["src_out"], fps), "src_frame": src_frame,
            "event": seg["event"]}
