"""
____________________________________________________________________

  LGA_NKS_InOut_Editref v1.43 | Lega

  Establece los puntos In y Out de la secuencia activa
  basándose en el clip más cercano del track "EditRef".
   1. Obtiene la secuencia activa y la posición del playhead.
   2. Encuentra el clip más cercano en el track "EditRef".
   3. Establece los puntos In y Out basados en ese clip.
   4. Selecciona el clip, mueve el playhead al inicio y ajusta
      la vista para que se ajuste al clip seleccionado.

  v1.43: Corrige el callback diferido de Zoom to Fit para usar QtCore.QTimer.
  v1.42: Usa módulo centralizado LGA_NKS_GetClip con método híbrido para buscar clips en track EditRef o EditRefClean (playhead primero, luego selección como fallback)
____________________________________________________________________
"""

import hiero.core
import hiero.ui
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtCore
from pathlib import Path
import sys

DEBUG = False

# Importar métodos de selección híbrida
utils_path = Path(__file__).parent.parent / "LGA_NKS_Shared"
if utils_path.exists():
    sys.path.insert(0, str(utils_path))
    try:
        from LGA_NKS_Shared import LGA_NKS_GetClip as clip_utils
        find_clip_at_playhead_in_track = clip_utils.find_clip_at_playhead_in_track
        get_clip_to_process = clip_utils.get_clip_to_process
    except ImportError:
        find_clip_at_playhead_in_track = None
        get_clip_to_process = None
else:
    find_clip_at_playhead_in_track = None
    get_clip_to_process = None


def debug_print(*message):
    if DEBUG:
        print(*message)


def set_in_out_from_edit_ref_track():
    """
    Establece los puntos In y Out basándose en el clip más cercano del track EditRef.
    """
    # Obtener la secuencia activa
    seq = hiero.ui.activeSequence()
    if not seq:
        debug_print("No hay una secuencia activa.")
        return None

    # Obtener la posicion del playhead
    te = hiero.ui.getTimelineEditor(seq)
    current_viewer = hiero.ui.currentViewer()
    player = current_viewer.player() if current_viewer else None
    playhead_frame = player.time() if player else None

    if playhead_frame is None:
        debug_print("No se pudo obtener la posicion del playhead.")
        return None

    # Buscar el track llamado "EditRef" o "EditRefClean"
    edit_ref_track = None
    track_name = None
    for track in seq.videoTracks():
        if track.name() == "EditRef":
            edit_ref_track = track
            track_name = "EditRef"
            break
    if not edit_ref_track:
        for track in seq.videoTracks():
            if track.name() == "EditRefClean":
                edit_ref_track = track
                track_name = "EditRefClean"
                break

    if not edit_ref_track:
        debug_print("No se encontro un track llamado 'EditRef' ni 'EditRefClean'.")
        return None

    # Usar método híbrido de selección: primero intentar con playhead
    edit_ref_clip = None
    if find_clip_at_playhead_in_track:
        edit_ref_clip = find_clip_at_playhead_in_track(seq, track_name=track_name)
        if edit_ref_clip:
            debug_print(f"Clip encontrado usando método híbrido en playhead: {edit_ref_clip.name()}")
    
    # Si no se encontró por playhead, intentar con método híbrido completo (incluye selección)
    if not edit_ref_clip and get_clip_to_process:
        edit_ref_clip = get_clip_to_process(track_name=track_name, prioritize_multiple_selection=False)
        if edit_ref_clip:
            debug_print(f"Clip encontrado usando método híbrido (selección): {edit_ref_clip.name()}")
    
    # Si aún no se encontró, buscar el clip más cercano (fallback)
    if not edit_ref_clip:
        min_distance = float("inf")
        for item in edit_ref_track.items():
            if item.timelineIn() <= playhead_frame < item.timelineOut():
                edit_ref_clip = item
                break
            else:
                # Calcular la distancia al playhead
                if playhead_frame < item.timelineIn():
                    distance = item.timelineIn() - playhead_frame
                else:
                    distance = playhead_frame - item.timelineOut()
                if distance < min_distance:
                    min_distance = distance
                    edit_ref_clip = item

    if not edit_ref_clip:
        debug_print("No se encontro ningun clip en el track EditRef.")
        return None

    # Obtener el in y out del clip de referencia
    ref_in = edit_ref_clip.timelineIn()
    ref_out = edit_ref_clip.timelineOut()

    # Establecer el in y out de la secuencia
    seq.setInTime(ref_in)
    seq.setOutTime(ref_out)

    debug_print(
        f"Se ha establecido el in/out de la secuencia a [{ref_in}, {ref_out}] basado en el clip de EditRef mas cercano."
    )

    return edit_ref_clip, edit_ref_track.name()


def seleccionar_y_ajustar_clip(clip, track_name):
    """
    Selecciona el clip y ajusta la vista para que se ajuste al clip seleccionado.
    """
    if not clip:
        return

    try:
        # Seleccionar el clip
        timeline_editor = hiero.ui.getTimelineEditor(hiero.ui.activeSequence())
        if timeline_editor:
            timeline_editor.setSelection([clip])
            debug_print(f"Clip seleccionado: {clip.name()}")

            # Mover el playhead al inicio del clip
            viewer = hiero.ui.currentViewer()
            if viewer:
                new_time = clip.timelineIn()
                debug_print(f"Moviendo playhead al inicio del clip: {new_time}")
                viewer.setTime(new_time)
            else:
                debug_print("No se pudo obtener el viewer")

            # Obtener y activar la ventana del timeline
            window = timeline_editor.window()
            window.activateWindow()
            window.setFocus()

            # Ejecutar el comando Zoom to Fit después de que la UI se actualice
            QtCore.QTimer.singleShot(
                0, lambda: hiero.ui.findMenuAction("Zoom to Fit").trigger()
            )
            debug_print("Ejecutando comando Zoom to Fit")
        else:
            debug_print("No se pudo obtener el timeline editor.")
    except Exception as e:
        debug_print(f"Error al seleccionar y ajustar el clip: {e}")


def main():
    """
    Función principal que establece los puntos In/Out y ajusta la vista.
    """
    result = set_in_out_from_edit_ref_track()
    if result:
        clip, track_name = result
        if track_name == "EditRefClean":
            seleccionar_y_ajustar_clip(clip, track_name)


if __name__ == "__main__":
    main()
