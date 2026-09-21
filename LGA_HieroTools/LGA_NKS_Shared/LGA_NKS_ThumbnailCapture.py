"""
____________________________________________________________________

  LGA_NKS_ThumbnailCapture v1.00 | Lega

  Captura imagenes del viewer sin incluir el track de burn-in y restaura
  exactamente el estado previo del timeline al terminar.

  v1.00: Proteccion compartida para Thumbnail y Create Shot. Reconoce
         BurnIn, burn-in, burn_in y variantes de mayusculas/espaciado.
____________________________________________________________________
"""

from contextlib import contextmanager


class BurnInTrackError(RuntimeError):
    """Impide capturar si no se puede garantizar que el burn-in quede oculto."""


def _normalized_track_name(name):
    """Normaliza separadores y capitalizacion sin aceptar sufijos adicionales."""
    return "".join(char for char in str(name).casefold() if char.isalnum())


def _log(logger, message):
    if logger is not None:
        try:
            logger(message)
        except Exception:
            pass


def _set_track_state(track, enabled, process_events):
    """Aplica y verifica el estado; reintenta una vez tras refrescar eventos."""
    last_error = None
    for attempt in range(2):
        try:
            track.setEnabled(enabled)
        except Exception as exc:
            last_error = exc

        try:
            if bool(track.isEnabled()) == enabled:
                return
        except Exception as exc:
            last_error = exc

        if attempt == 0 and process_events is not None:
            try:
                process_events()
            except Exception as exc:
                last_error = exc

    detail = f": {last_error}" if last_error is not None else ""
    raise RuntimeError(f"el estado no cambio{detail}")


def _restore_tracks(changed_tracks, process_events, logger):
    errors = []
    for track, original_state, track_name in reversed(changed_tracks):
        try:
            _set_track_state(track, original_state, process_events)
            _log(logger, f"Track '{track_name}' restaurado a su estado original")
        except Exception as exc:
            errors.append(f"{track_name}: {exc}")

    if changed_tracks and process_events is not None:
        try:
            process_events()
        except Exception as exc:
            errors.append(f"refresh del viewer: {exc}")
    return errors


@contextmanager
def temporarily_disable_burnin_tracks(sequence, process_events=None, logger=None):
    """Deshabilita todos los tracks burn-in y restaura su estado al salir.

    La captura falla de forma explicita si encuentra un burn-in que no puede
    deshabilitar. Asi nunca se genera silenciosamente un thumbnail con overlay.
    """
    changed_tracks = []
    matched_count = 0

    try:
        tracks = list(sequence.videoTracks()) if sequence is not None else []
        for track in tracks:
            track_name = track.name()
            if _normalized_track_name(track_name) != "burnin":
                continue

            matched_count += 1
            original_state = bool(track.isEnabled())
            if not original_state:
                _log(logger, f"Track '{track_name}' ya estaba deshabilitado")
                continue

            changed_tracks.append((track, original_state, track_name))
            _set_track_state(track, False, process_events)
            _log(logger, f"Track '{track_name}' deshabilitado para el thumbnail")

        if changed_tracks and process_events is not None:
            process_events()
    except Exception as exc:
        restore_errors = _restore_tracks(changed_tracks, process_events, logger)
        detail = f": {'; '.join(restore_errors)}" if restore_errors else ""
        raise BurnInTrackError(
            f"No se pudo deshabilitar el track burn-in antes de capturar{detail}"
        ) from exc

    body_error = None
    try:
        yield matched_count
    except BaseException as exc:
        body_error = exc
        raise
    finally:
        restore_errors = _restore_tracks(changed_tracks, process_events, logger)
        if restore_errors:
            message = "No se pudo restaurar el track burn-in: " + "; ".join(
                restore_errors
            )
            error = BurnInTrackError(message)
            if body_error is not None:
                raise error from body_error
            raise error


def capture_viewer_image_without_burnin(
    sequence, capture_image, process_events=None, logger=None
):
    """Ejecuta la lectura del viewer mientras todos los burn-in estan apagados."""
    with temporarily_disable_burnin_tracks(
        sequence,
        process_events=process_events,
        logger=logger,
    ):
        return capture_image()
