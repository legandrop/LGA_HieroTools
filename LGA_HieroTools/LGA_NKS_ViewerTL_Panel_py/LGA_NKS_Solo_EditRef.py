"""
____________________________________________________________________

  LGA_NKS_Solo_EditRef v1.00 | Lega

  Toggle para mirar el EditRef solo: apaga todos los tracks de video
  menos EditRef / EditRefClean y BurnIn, y el segundo toque prende
  todo de nuevo.

  Existe porque para revisar el corte la gente apagaba a mano track por
  track, y despues tenia que volver a prenderlos uno por uno.

  Como decide que hacer (sin guardar estado entre toques):
  - Esta en "solo" si ningun otro track de video prendido tiene un clip
    o un soft effect bajo el playhead, y ademas hay al menos un track
    apagado. Ahi PRENDE todos los tracks de video.
  - Si no, APAGA todos los tracks de video salvo EditRef/EditRefClean
    (puede haber mas de uno con ese nombre) y BurnIn, y prende EditRef
    si estaba apagado.
  - BurnIn y los tracks de audio no se tocan nunca.
  - Trabaja a nivel TRACK: el enable de cada clip queda como estaba.

  La segunda condicion evita un toque que no hace nada: con todo
  prendido y solo EditRef bajo el playhead, el toque apaga el resto
  en vez de "prender todo" sobre algo que ya esta prendido.

  v1.00: Version inicial.
____________________________________________________________________
"""

import os
import time
import traceback

EDITREF_TRACK_NAMES = {"editref", "editrefclean"}
BURNIN_TRACK_NAMES = {"burnin", "burn in", "burn_in"}

DEBUG = False

LOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "logs",
    "DebugPy_LGA_NKS_Solo_EditRef.log",
)
_log_lines = []


def debug_print(*message):
    msg = " ".join(str(arg) for arg in message)
    _log_lines.append(msg)
    if DEBUG:
        print(msg)


def _write_log():
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "w", encoding="utf-8", newline="\n") as f:
            f.write("Fecha: %s\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
            f.write("\n".join(_log_lines) + "\n")
    except Exception:
        pass


def _norm(name):
    return (name or "").strip().lower()


def is_editref_track(track):
    return _norm(track.name()) in EDITREF_TRACK_NAMES


def is_burnin_track(track):
    return _norm(track.name()) in BURNIN_TRACK_NAMES


def _covers(item, frame):
    return item.timelineIn() <= frame <= item.timelineOut()


def has_content_at(track, frame):
    """True si el track tiene un clip o un soft effect bajo el frame."""
    for item in track.items():
        if _covers(item, frame):
            return True
    for row in track.subTrackItems() or []:
        for effect in row:
            if _covers(effect, frame):
                return True
    return False


def decide_action(tracks, frame):
    """Devuelve "restore" o "solo" segun el estado de los tracks de video."""
    others = [t for t in tracks if not is_editref_track(t) and not is_burnin_track(t)]
    visible_at_playhead = [
        t for t in others if t.isEnabled() and has_content_at(t, frame)
    ]
    any_disabled = any(not t.isEnabled() for t in others)
    debug_print(
        "Otros tracks: %d | prendidos con contenido en el playhead: %s | alguno apagado: %s"
        % (len(others), [t.name() for t in visible_at_playhead], any_disabled)
    )
    if not visible_at_playhead and any_disabled:
        return "restore"
    return "solo"


def apply_action(tracks, action):
    """Aplica la accion y devuelve la cantidad de tracks que cambiaron."""
    changed = 0
    for track in tracks:
        if is_burnin_track(track):
            continue
        if action == "solo":
            wanted = is_editref_track(track)
        else:
            wanted = True
        if track.isEnabled() != wanted:
            track.setEnabled(wanted)
            changed += 1
            debug_print("  %s -> %s" % (track.name(), "ON" if wanted else "OFF"))
    return changed


def main():
    try:
        import hiero.core
        import hiero.ui

        seq = hiero.ui.activeSequence()
        if not seq:
            debug_print("No hay secuencia activa.")
            return
        viewer = hiero.ui.currentViewer()
        if not viewer:
            debug_print("No hay viewer activo.")
            return
        frame = viewer.time()
        tracks = list(seq.videoTracks())
        debug_print("Secuencia: %s | playhead: %s | tracks de video: %d"
                    % (seq.name(), frame, len(tracks)))

        if not any(is_editref_track(t) for t in tracks):
            debug_print("No hay track EditRef ni EditRefClean: no se toca nada.")
            from LGA_NKS_Shared.LGA_NKS_MessageBox import show_warning

            show_warning(
                None,
                "Solo EditRef",
                "The active sequence has no <b>EditRef</b> or <b>EditRefClean</b> track.",
            )
            return

        action = decide_action(tracks, frame)
        debug_print("Accion: %s" % action)

        project = seq.project()
        if project:
            project.beginUndo("Solo EditRef")
        try:
            changed = apply_action(tracks, action)
        finally:
            if project:
                project.endUndo()
        debug_print("Tracks cambiados: %d" % changed)
    except Exception:
        debug_print("ERROR:\n" + traceback.format_exc())
    finally:
        _write_log()


if __name__ == "__main__":
    main()
