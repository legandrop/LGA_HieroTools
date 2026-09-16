"""
____________________________________________________________________

  LGA_NKS_ReplaceClip v1.00 | Lega

  Usado por runtime activo:
  - LGA_NKS_Edit_Panel.py (boton Replace Clip)

  Reemplaza el media del clip seleccionado por un archivo que elige el
  usuario, aunque tenga otro nombre o este en otra carpeta. Sirve cuando
  Reconnect Media no engancha: ese busca el MISMO nombre de archivo.

  Antes de tocar el timeline arma un MediaSource con el archivo elegido y
  lo compara contra lo que Hiero recuerda del original (primer frame,
  duracion, resolucion). Si algo difiere, pide confirmacion. Despues del
  replace restaura los trims, el color del clip y el bin, igual que
  Self ReplaceClip.

  v1.00: Version inicial.
____________________________________________________________________
"""

import os
import time
import traceback

import hiero.core
import hiero.ui

from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets
from LGA_NKS_Shared.LGA_NKS_MessageBox import ask_question, show_error, show_warning

DEBUG = False  # consola; el .log se escribe siempre

LOG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "logs", "DebugPy_ReplaceClip.log"
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
    debug_print(f"LGA_NKS_ReplaceClip v1.00 - {time.strftime('%Y-%m-%d %H:%M:%S')}")


def _cerrar_log():
    global _log_file
    if _log_file is not None:
        try:
            _log_file.close()
        except Exception:
            pass
    _log_file = None


# ------------------------------------------------------------------
# Lectura de datos
# ------------------------------------------------------------------

def primera_ruta(media_source):
    try:
        infos = media_source.fileinfos()
        return infos[0].filename() if infos else None
    except Exception as e:
        debug_print(f"No se pudo leer fileinfos: {e}")
        return None


def datos_media(media_source):
    """Datos comparables de un MediaSource. Validado con clips offline en NKS 16."""
    datos = {}
    for campo in ("startTime", "duration", "width", "height"):
        try:
            datos[campo] = getattr(media_source, campo)()
        except Exception as e:
            datos[campo] = None
            debug_print(f"  {campo}() fallo: {e}")
    return datos


def carpeta_existente_mas_cercana(ruta):
    carpeta = os.path.dirname(ruta) if ruta else ""
    while carpeta and not os.path.isdir(carpeta):
        padre = os.path.dirname(carpeta)
        if padre == carpeta:
            return ""
        carpeta = padre
    return carpeta


def rango_texto(datos):
    inicio, duracion = datos.get("startTime"), datos.get("duration")
    if inicio is None or duracion is None:
        return "?"
    return f"{inicio}-{inicio + duracion - 1} ({duracion} frames)"


# ------------------------------------------------------------------
# Helpers de color y bin (misma logica que Self ReplaceClip)
# ------------------------------------------------------------------

def get_clip_color(track_item):
    try:
        return track_item.source().binItem().color()
    except Exception as e:
        debug_print(f"No se pudo leer el color del clip: {e}")
        return None


def set_clip_color(track_item, color):
    if not color:
        return
    try:
        track_item.source().binItem().setColor(color)
        debug_print("Color del clip restaurado.")
    except Exception as e:
        debug_print(f"No se pudo restaurar el color: {e}")


def get_full_bin_path(bin_item):
    path = []
    while bin_item:
        if isinstance(bin_item, hiero.core.Bin):
            path.append(bin_item.name())
        bin_item = bin_item.parentBin() if hasattr(bin_item, "parentBin") else None
    return "/".join(reversed(path))


def find_or_create_bin(project, bin_path):
    current_bin = project.clipsBin()
    for bin_name in [b for b in bin_path.split("/") if b]:
        found = None
        for item in current_bin.items():
            if isinstance(item, hiero.core.Bin) and item.name() == bin_name:
                found = item
                break
        if not found:
            found = hiero.core.Bin(bin_name)
            current_bin.addItem(found)
        current_bin = found
    return current_bin


def mover_clip_desde_conform(project, clip_name, target_bin_path):
    """replaceClips deja el clip nuevo en el bin 'Conform': se lo lleva al bin original."""
    conform = None
    for item in project.clipsBin().items():
        if isinstance(item, hiero.core.Bin) and item.name() == "Conform":
            conform = item
            break
    if conform is None:
        debug_print("No hay bin 'Conform'; el clip queda donde lo dejo Hiero.")
        return
    for item in conform.items():
        if item.name() == clip_name:
            target = find_or_create_bin(project, target_bin_path)
            conform.removeItem(item)
            target.addItem(item)
            debug_print(f"Clip '{clip_name}' movido de 'Conform' a '{target_bin_path}'.")
            return
    debug_print(f"No se encontro '{clip_name}' en 'Conform'.")


# ------------------------------------------------------------------
# Flujo
# ------------------------------------------------------------------

def pedir_archivo(clip_name, carpeta_inicial):
    ruta, _ = QtWidgets.QFileDialog.getOpenFileName(
        hiero.ui.mainWindow(),
        f"Replace Clip: choose media for '{clip_name}'",
        carpeta_inicial or "",
    )
    return ruta.replace("\\", "/") if ruta else None


def comparar(original, candidato):
    """Devuelve lista de diferencias legibles (vacia si todo coincide)."""
    diferencias = []
    if (original.get("startTime"), original.get("duration")) != (
        candidato.get("startTime"),
        candidato.get("duration"),
    ):
        diferencias.append(
            f"Frame range: {rango_texto(original)}  ->  {rango_texto(candidato)}"
        )
    if (original.get("width"), original.get("height")) != (
        candidato.get("width"),
        candidato.get("height"),
    ):
        diferencias.append(
            f"Resolution: {original.get('width')}x{original.get('height')}  ->  "
            f"{candidato.get('width')}x{candidato.get('height')}"
        )
    return diferencias


def reemplazar_clip(project, track_item):
    nombre = track_item.name()
    debug_print("=" * 70)
    debug_print(f"Clip: {nombre}  track: {track_item.parentTrack().name()}")

    # Estado original
    source_in, source_out = track_item.sourceIn(), track_item.sourceOut()
    timeline_in, timeline_out = track_item.timelineIn(), track_item.timelineOut()
    clip = track_item.source()
    ms_original = clip.mediaSource()
    ruta_original = primera_ruta(ms_original)
    datos_original = datos_media(ms_original)
    try:
        fps_original = clip.framerate().toFloat()
    except Exception:
        fps_original = None
    debug_print(f"Ruta original: {ruta_original}")
    debug_print(f"Media presente: {ms_original.isMediaPresent()}")
    debug_print(f"Original: {datos_original}  fps={fps_original}")
    debug_print(f"Trims: source {source_in}-{source_out}  timeline {timeline_in}-{timeline_out}")

    debug_print("-> leyendo color y bin del clip")
    color = get_clip_color(track_item)
    try:
        bin_path = get_full_bin_path(clip.binItem()).replace("Sequences/", "")
    except Exception as e:
        bin_path = None
        debug_print(f"No se pudo leer el bin del clip: {e}")
    debug_print(f"Bin original: {bin_path}")

    # Eleccion y validacion del archivo nuevo
    elegido = pedir_archivo(nombre, carpeta_existente_mas_cercana(ruta_original))
    if not elegido:
        debug_print("Cancelado por el usuario en el browser.")
        return False
    debug_print(f"Archivo elegido: {elegido}")

    debug_print("-> construyendo MediaSource del archivo elegido")
    try:
        ms_nuevo = hiero.core.MediaSource(elegido)
    except Exception as e:
        debug_print(f"MediaSource del archivo elegido fallo: {e}")
        show_error(None, "Replace Clip", f"Hiero could not read the selected file:\n{elegido}")
        return False
    ruta_nueva = primera_ruta(ms_nuevo) or elegido
    datos_nuevo = datos_media(ms_nuevo)
    debug_print(f"Ruta nueva (secuencia detectada): {ruta_nueva}")
    debug_print(f"Nuevo: {datos_nuevo}  presente={ms_nuevo.isMediaPresent()}")

    if not ms_nuevo.isMediaPresent():
        show_error(None, "Replace Clip", f"The selected media is not available:\n{ruta_nueva}")
        return False

    diferencias = comparar(datos_original, datos_nuevo)
    if diferencias:
        debug_print(f"Diferencias: {diferencias}")
        texto = (
            f"The selected media does not match '{nombre}':\n\n"
            + "\n".join(diferencias)
            + f"\n\nNew: {os.path.basename(ruta_nueva)}\n\nReplace anyway?"
        )
        if not ask_question(None, "Replace Clip", texto, yes_text="Replace", no_text="Cancel", recommended=False):
            debug_print("Cancelado por el usuario por diferencias.")
            return False
    else:
        debug_print("Frame range y resolucion coinciden.")

    # Replace
    debug_print(f"-> replaceClips({ruta_nueva})")
    track_item.replaceClips(ruta_nueva)

    ruta_final = primera_ruta(track_item.source().mediaSource())
    debug_print(f"Ruta despues del replace: {ruta_final}")
    if not ruta_final or ruta_final.replace("\\", "/").lower() != ruta_nueva.replace("\\", "/").lower():
        show_error(
            None,
            "Replace Clip",
            f"Hiero did not replace '{nombre}'.\n\nExpected:\n{ruta_nueva}\n\nGot:\n{ruta_final}",
        )
        return False

    if (track_item.sourceIn(), track_item.sourceOut()) != (source_in, source_out):
        debug_print(
            f"Trims cambiaron ({track_item.sourceIn()}-{track_item.sourceOut()}), "
            f"restaurando {source_in}-{source_out}"
        )
        track_item.setSourceIn(source_in)
        track_item.setSourceOut(source_out)

    avisos = []
    if (track_item.timelineIn(), track_item.timelineOut()) != (timeline_in, timeline_out):
        avisos.append(
            f"Timeline position changed: {timeline_in}-{timeline_out} -> "
            f"{track_item.timelineIn()}-{track_item.timelineOut()}"
        )
    try:
        fps_nuevo = track_item.source().framerate().toFloat()
    except Exception:
        fps_nuevo = None
    if fps_original and fps_nuevo and abs(fps_original - fps_nuevo) > 0.001:
        avisos.append(f"Frame rate changed: {fps_original} -> {fps_nuevo}")

    set_clip_color(track_item, color)
    if bin_path:
        mover_clip_desde_conform(project, track_item.source().name(), bin_path)

    debug_print(
        f"Final: source {track_item.sourceIn()}-{track_item.sourceOut()}  "
        f"timeline {track_item.timelineIn()}-{track_item.timelineOut()}  fps={fps_nuevo}"
    )
    if avisos:
        debug_print(f"Avisos: {avisos}")
        show_warning(None, "Replace Clip", f"'{nombre}' was replaced, but:\n\n" + "\n".join(avisos))
    debug_print("Replace completado.")
    return True


def main():
    _abrir_log()
    try:
        seq = hiero.ui.activeSequence()
        if not seq:
            debug_print("No hay secuencia activa.")
            show_warning(None, "Replace Clip", "No active sequence.")
            return
        te = hiero.ui.getTimelineEditor(seq)
        clips = [i for i in te.selection() if isinstance(i, hiero.core.TrackItem)]
        debug_print(f"Secuencia: {seq.name()}  clips seleccionados: {len(clips)}")
        if not clips:
            show_warning(None, "Replace Clip", "Select a clip in the timeline.")
            return

        project = seq.project()
        with project.beginUndo("Replace Clip"):
            for track_item in clips:
                try:
                    reemplazar_clip(project, track_item)
                except Exception as e:
                    debug_print(traceback.format_exc())
                    show_error(None, "Replace Clip", f"Error replacing '{track_item.name()}':\n{e}")
    except Exception:
        debug_print(traceback.format_exc())
    finally:
        _cerrar_log()
