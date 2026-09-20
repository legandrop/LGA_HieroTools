"""
____________________________________________________________________

  LGA_NKS_ON_Clips_OFF_v00-Clips v1.22 | Lega

  Activa todos los clips y desactiva clips v00/v000, contemplando todas las tasks.

  Logica por tipo de track (nombres centralizados en LGA_NKS_GetClip):
  - Track EXR de task (_comp_, _roto_, _cleanup_ -> TASK_EXR_TRACKS):
      v00/v000 -> OFF; cualquier otra version (o sin version) -> ON.
  - Track Rev de task (_compRev_, _rotoRev_, _cleanupRev_ -> TASK_REV_TRACKS):
      SIEMPRE OFF, sin importar el numero de version.
  - Otros tracks (EditRef, aPlate, BurnIn, etc.): ON (comportamiento historico).

  v1.22: Movido de Review al ViewerTL Panel junto con los controles de estado
         de clips; la logica no cambia.
  v1.21: Reescrito para identificar el clip por su track (TASK_EXR_TRACKS / TASK_REV_TRACKS)
         en lugar del regex hardcodeado "_comp_v". Ahora contempla roto y cleanup, y apaga
         siempre los tracks Rev. La deteccion de version es generica (_v\\d{2,3}) y solo se
         aplica a los tracks EXR de task.
  v1.20: Soporta versiones de 2 y 3 dígitos
____________________________________________________________________

"""

import hiero.core
import hiero.ui
import os
import re
import sys
from pathlib import Path

DEBUG = False


def debug_print(*message):
    if DEBUG:
        print(*message)


# Importar las listas centralizadas de tracks por task
utils_path = Path(__file__).parent.parent / "LGA_NKS_Shared"
if utils_path.exists():
    sys.path.insert(0, str(utils_path))
    from LGA_NKS_Shared.LGA_NKS_GetClip import TASK_EXR_TRACKS, TASK_REV_TRACKS
else:
    debug_print("ERROR: No se encontró el módulo LGA_NKS_GetClip, usando defaults")
    TASK_EXR_TRACKS = ["_comp_", "_roto_", "_cleanup_"]
    TASK_REV_TRACKS = ["_compRev_", "_rotoRev_", "_cleanupRev_"]

# Sets en minúscula para comparar nombres de track case-insensitive
_EXR_TRACKS_LOWER = {t.lower() for t in TASK_EXR_TRACKS}
_REV_TRACKS_LOWER = {t.lower() for t in TASK_REV_TRACKS}

# Patrón de versión genérico: _v00, _v000, _v01, _v001, etc. (no atado a la task)
_VERSION_PATTERN = re.compile(r"_v(\d{2,3})", re.IGNORECASE)


def _get_version_number(item):
    """Devuelve el número de versión (str) detectado en el filename del clip, o None."""
    try:
        fileinfos = item.source().mediaSource().fileinfos()
        if not fileinfos:
            return None
        file_path = fileinfos[0].filename()
        if not file_path:
            return None
        filename = os.path.basename(file_path)
        m = _VERSION_PATTERN.search(filename.lower())
        return m.group(1) if m else None
    except Exception as e:
        debug_print(f"Error obteniendo versión del clip '{item.name()}': {e}")
        return None


def main(force_all_clips=False):
    """
    Activa todos los clips y desactiva clips v00/v000 según el track de cada clip.

    Args:
        force_all_clips (bool): Si es True, procesa todos los clips de todos los tracks
                               del timeline, no solo los seleccionados.
    """
    if force_all_clips:
        debug_print("Ejecutando sobre todos los clips del timeline")
    else:
        debug_print("Ejecutando solo en los clips seleccionados")

    try:
        seq = hiero.ui.activeSequence()
        if not seq:
            debug_print("No se encontro una secuencia activa en Hiero.")
            return

        te = hiero.ui.getTimelineEditor(seq)

        # Determinar qué clips procesar
        if force_all_clips:
            selected_items = []
            for track in seq.videoTracks():
                selected_items.extend(track.items())
            debug_print(
                f"Procesando todos los clips del timeline ({len(selected_items)} clips)"
            )
        else:
            selected_items = te.selection()
            debug_print(
                f"Procesando clips seleccionados ({len(selected_items)} clips)"
            )

        if not selected_items:
            debug_print("No hay clips para procesar en la linea de tiempo.")
            return

        for item in selected_items:
            if isinstance(item, hiero.core.EffectTrackItem):
                continue

            track = item.parentTrack() if hasattr(item, "parentTrack") else None
            track_name = track.name().lower() if track else ""

            # Tracks Rev de task: SIEMPRE OFF, sin importar la versión
            if track_name in _REV_TRACKS_LOWER:
                item.setEnabled(False)
                debug_print(f"Clip '{item.name()}' (track Rev '{track_name}') desactivado.")
                continue

            # Tracks EXR de task: v00/v000 OFF, resto ON
            if track_name in _EXR_TRACKS_LOWER:
                version_number = _get_version_number(item)
                if version_number in ("00", "000"):
                    item.setEnabled(False)
                    debug_print(
                        f"Clip '{item.name()}' (track '{track_name}') desactivado (versión v{version_number})."
                    )
                else:
                    item.setEnabled(True)
                    debug_print(
                        f"Clip '{item.name()}' (track '{track_name}') activado (versión v{version_number})."
                    )
                continue

            # Otros tracks (no-task): activar (comportamiento histórico)
            item.setEnabled(True)
            debug_print(f"Clip '{item.name()}' (track '{track_name}') activado (track no-task).")

    except Exception as e:
        debug_print(f"Error durante la operacion: {e}")
