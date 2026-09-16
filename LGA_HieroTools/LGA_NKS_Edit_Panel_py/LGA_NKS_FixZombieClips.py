"""
____________________________________________________________________

  LGA_NKS_FixZombieClips v1.00 | Lega

  Usado por runtime activo:
  - LGA_NKS_Edit_Panel.py (boton Fix Zombies)

  Busca en todo el timeline los clips "zombie" y los arregla con un self
  replace (replaceClips con su propia ruta), que es lo unico que vuelve a
  armar el enlace.

  Un clip es zombie cuando su BinItem quedo HUERFANO: sigue existiendo
  colgado del clip, pero ya no pertenece a ningun bin ni a ningun
  proyecto. El clip se ve y se reproduce, pero el Properties panel queda
  vacio, no se lee la metadata, Reconnect Media no engancha y Scan for
  Versions tira "Version is null".

  OJO con la deteccion: sobre un BinItem huerfano, activeVersion() tira
  "Model is null" y activeItem() CRASHEA NKS (medido con una sonda). Por
  eso solo se llaman parentBin() y project(), que son seguras.

  v1.00: Version inicial.
____________________________________________________________________
"""

import os
import time
import traceback

import hiero.core
import hiero.ui

from LGA_NKS_Shared.LGA_NKS_MessageBox import show_info, show_warning

DEBUG = False  # consola; el .log se escribe siempre

LOG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "logs", "DebugPy_FixZombieClips.log"
)

_log_file = None


def debug_print(*message):
    """Escribe al log y lo fuerza a disco: si NKS se cae, queda la ultima linea."""
    msg = " ".join(str(m) for m in message)
    if _log_file is not None:
        try:
            _log_file.write(msg + "\n")
            _log_file.flush()
            os.fsync(_log_file.fileno())
        except Exception:
            pass
    if DEBUG:
        print(msg)


def _abrir_log():
    global _log_file
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    _log_file = open(LOG_PATH, "w", newline="\n", encoding="utf-8")
    debug_print(f"LGA_NKS_FixZombieClips v1.00 - {time.strftime('%Y-%m-%d %H:%M:%S')}")


def _cerrar_log():
    global _log_file
    if _log_file is not None:
        try:
            _log_file.close()
        except Exception:
            pass
    _log_file = None


# ------------------------------------------------------------------
# Deteccion
# ------------------------------------------------------------------

def es_zombie(track_item):
    """True si el BinItem del clip quedo huerfano. Solo llamadas seguras."""
    try:
        bin_item = track_item.source().binItem()
    except Exception as e:
        debug_print(f"  no se pudo leer binItem: {e}  -> se trata como zombie")
        return True
    if bin_item is None:
        return True
    try:
        bin_item.parentBin()
    except Exception as e:
        debug_print(f"  sin bin padre ({e})")
        return True
    try:
        if bin_item.project() is None:
            debug_print("  binItem sin proyecto")
            return True
    except Exception as e:
        debug_print(f"  project() fallo ({e})")
        return True
    return False


def ruta_del_clip(track_item):
    try:
        infos = track_item.source().mediaSource().fileinfos()
        return infos[0].filename() if infos else None
    except Exception as e:
        debug_print(f"  no se pudo leer la ruta: {e}")
        return None


# ------------------------------------------------------------------
# Arreglo
# ------------------------------------------------------------------

def get_clip_color(track_item):
    try:
        return track_item.source().binItem().color()
    except Exception as e:
        debug_print(f"  no se pudo leer el color: {e}")
        return None


def set_clip_color(track_item, color):
    if not color:
        return
    try:
        track_item.source().binItem().setColor(color)
    except Exception as e:
        debug_print(f"  no se pudo restaurar el color: {e}")


def arreglar(track_item):
    """Self replace del clip con su propia ruta. Devuelve (ok, motivo)."""
    nombre = track_item.name()
    ruta = ruta_del_clip(track_item)
    debug_print(f"  ruta: {ruta}")
    if not ruta:
        return False, "no se pudo leer la ruta del media"

    try:
        media_presente = track_item.source().mediaSource().isMediaPresent()
    except Exception:
        media_presente = False
    debug_print(f"  media presente: {media_presente}")
    if not media_presente:
        # replaceClips con una ruta sin media deja el clip igual de roto.
        # Esos van con el boton Replace Clip, eligiendo el archivo a mano.
        return False, "el media esta offline"

    source_in, source_out = track_item.sourceIn(), track_item.sourceOut()
    color = get_clip_color(track_item)

    debug_print(f"  -> replaceClips({ruta})")
    track_item.replaceClips(ruta)

    if (track_item.sourceIn(), track_item.sourceOut()) != (source_in, source_out):
        debug_print(
            f"  trims cambiaron ({track_item.sourceIn()}-{track_item.sourceOut()}), "
            f"restaurando {source_in}-{source_out}"
        )
        track_item.setSourceIn(source_in)
        track_item.setSourceOut(source_out)
    set_clip_color(track_item, color)

    if es_zombie(track_item):
        return False, "sigue zombie despues del replace"
    debug_print(f"  '{nombre}' arreglado")
    return True, None


def main():
    _abrir_log()
    try:
        seq = hiero.ui.activeSequence()
        if not seq:
            debug_print("No hay secuencia activa.")
            show_warning(None, "Fix Zombies", "No active sequence.")
            return

        clips = []
        for track in seq.videoTracks():
            for item in track:
                if not isinstance(item, hiero.core.EffectTrackItem):
                    clips.append(item)
        debug_print(f"Secuencia: {seq.name()}  clips a revisar: {len(clips)}")

        zombies = []
        for item in clips:
            debug_print(f"[{item.parentTrack().name()}] {item.name()}")
            if es_zombie(item):
                debug_print("  ZOMBIE")
                zombies.append(item)
        debug_print(f"Zombies encontrados: {len(zombies)}")

        if not zombies:
            show_info(
                None,
                "Fix Zombies",
                f"Checked {len(clips)} clips. No broken clips found.",
            )
            return

        arreglados, fallidos = [], []
        project = seq.project()
        with project.beginUndo("Fix Zombie Clips"):
            for item in zombies:
                nombre = item.name()
                debug_print(f"Arreglando '{nombre}' ({item.parentTrack().name()})")
                try:
                    ok, motivo = arreglar(item)
                except Exception as e:
                    debug_print(traceback.format_exc())
                    ok, motivo = False, str(e)
                if ok:
                    arreglados.append(nombre)
                else:
                    debug_print(f"  NO se pudo: {motivo}")
                    fallidos.append(f"{nombre}: {motivo}")

        debug_print(f"Arreglados: {len(arreglados)}  sin arreglar: {len(fallidos)}")
        texto = f"Checked {len(clips)} clips.\nFixed {len(arreglados)} of {len(zombies)} broken clips."
        if fallidos:
            texto += "\n\nNot fixed:\n" + "\n".join(fallidos)
            texto += "\n\nUse Replace Clip on these, choosing the media by hand."
            show_warning(None, "Fix Zombies", texto)
        else:
            show_info(None, "Fix Zombies", texto)
    except Exception:
        debug_print(traceback.format_exc())
    finally:
        _cerrar_log()
