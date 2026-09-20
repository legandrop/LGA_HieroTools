"""
____________________________________________________________________

  LGA_NKS_CleanProject v2.03 | Lega

  Main automatic cleaning script that combines both objectives:
  1. Removal of unused clips in sequences
  2. Cleaning of offline versions in clips with multiple versions

  v2.03: Movido al Projects Panel; la accion se ejecuta desde su barra lateral.
  v2.02: Translation to English
  v2.01: Added final user message with cleaning summary
         Main script that integrates both cleaning functionalities
         Implements anti-sequence protection with blacklist
         Compatible with all formats (.exr, .mov, .nk)
         Detailed logging with debug_print for output control
  v2.00: Main script that integrates both cleaning functionalities
         Implements anti-sequence protection with blacklist
         Compatible with all formats (.exr, .mov, .nk)
         Detailed logging with debug_print for output control
____________________________________________________________________

"""

import hiero
import hiero.core.find_items
import nuke
import os
import logging
import queue
import time
from logging.handlers import QueueHandler, QueueListener

# Variables globales de logging (valores por defecto)
DEBUG = True
DEBUG_CONSOLE = False
DEBUG_LOG = True
script_start_time = None
debug_log_listener = None


class RelativeTimeFormatter(logging.Formatter):
    """Formatter que incluye tiempo relativo desde el inicio del script."""
    def format(self, record):
        global script_start_time
        if script_start_time is None:
            script_start_time = record.created

        relative_time = record.created - script_start_time
        record.relative_time = f"{relative_time:.3f}s"
        return super().format(record)


def setup_debug_logging(script_name="CleanProject"):
    """Configura el logging para escribir SOLO en archivo."""
    global debug_log_listener

    log_filename = f"debugPy_{script_name}.log"
    log_file_path = os.path.join(
        os.path.dirname(__file__), "..", "logs", log_filename
    )

    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

    try:
        with open(log_file_path, "w", encoding="utf-8") as f:
            f.write(f"Fecha: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    except Exception:
        pass

    logger_name = f"{script_name.lower()}_logger"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    if logger.handlers:
        logger.handlers.clear()

    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    formatter = RelativeTimeFormatter("[%(relative_time)s] %(message)s")
    file_handler.setFormatter(formatter)

    log_queue = queue.Queue()
    queue_handler = QueueHandler(log_queue)
    queue_handler.setLevel(logging.DEBUG)
    logger.addHandler(queue_handler)

    if debug_log_listener:
        try:
            debug_log_listener.stop()
        except Exception:
            pass

    debug_log_listener = QueueListener(
        log_queue, file_handler, respect_handler_level=True
    )
    debug_log_listener.daemon = True
    debug_log_listener.start()

    return logger


debug_logger = setup_debug_logging(script_name="CleanProject")


def debug_print(*message, level="info"):
    global script_start_time

    msg = " ".join(str(arg) for arg in message)

    if DEBUG and DEBUG_LOG:
        if script_start_time is None:
            script_start_time = time.time()
        if level == "debug":
            debug_logger.debug(msg)
        elif level == "warning":
            debug_logger.warning(msg)
        elif level == "error":
            debug_logger.error(msg)
        else:
            debug_logger.info(msg)

    if DEBUG and DEBUG_CONSOLE:
        if script_start_time is None:
            script_start_time = time.time()
        relative_time = time.time() - script_start_time
        print(f"[{relative_time:.3f}s] {msg}")


def get_all_sequences(project):
    """Obtiene todas las secuencias del proyecto para verificar uso de clips"""
    sequences = []
    try:
        sequences = hiero.core.findItems(project, "Sequences")
        debug_print(f"📋 Found {len(sequences)} sequences to verify usage")
    except Exception as e:
        debug_print(f"⚠️ Error getting sequences: {e}")
    return sequences


def is_bin_item_used_in_sequences(bin_item, sequences):
    """
    Verifica si un BinItem está siendo usado en alguna secuencia
    Retorna True si se usa, False si no se usa
    """
    if not sequences:
        return False

    try:
        bin_name = bin_item.name() if hasattr(bin_item, "name") else ""

        # Verificar si el BinItem completo se usa en secuencias
        for sequence in sequences:
            if hasattr(sequence, "videoTracks"):
                for track in sequence.videoTracks():
                    for track_item in track.items():
                        if hasattr(track_item, "source"):
                            source = track_item.source()
                            if source:
                                # Comparar por nombre del BinItem (más confiable)
                                if (
                                    hasattr(source, "name")
                                    and source.name() == bin_name
                                ):
                                    return True

                                # También verificar si es el mismo objeto
                                if source == bin_item:
                                    return True

        # Para BinItems con versiones, verificar si alguna versión se usa
        if hasattr(bin_item, "items"):
            versions = bin_item.items()
            for version in versions:
                if hasattr(version, "name"):
                    version_name = version.name()

                    # Verificar si esta versión aparece en secuencias
                    for sequence in sequences:
                        if hasattr(sequence, "videoTracks"):
                            for track in sequence.videoTracks():
                                for track_item in track.items():
                                    if hasattr(track_item, "source"):
                                        source = track_item.source()
                                        if (
                                            source
                                            and hasattr(source, "name")
                                            and source.name() == version_name
                                        ):
                                            return True

        # Para clips .nk (composiciones), ser más conservador
        if bin_name.endswith(".nk"):
            # Si el archivo existe, asumir que podría estar en uso
            try:
                if hasattr(bin_item, "mediaSource") and bin_item.mediaSource():
                    media_source = bin_item.mediaSource()
                    if (
                        hasattr(media_source, "isMediaPresent")
                        and media_source.isMediaPresent()
                    ):
                        # Ser conservador con .nk - si existe, no eliminar
                        return True
            except:
                pass

    except Exception as e:
        bin_name = bin_item.name() if hasattr(bin_item, "name") else "unknown"
        debug_print(f"⚠️ Error checking BinItem usage {bin_name}: {e}")
        # En caso de error, ser conservador y asumir que se usa
        return True

    return False


def cleanAllUnusedClips():
    """OBJETIVO 1: Elimina TODOS los clips del proyecto que NO se usan en secuencias"""

    projects = hiero.core.projects()
    if not projects:
        debug_print("❌ ERROR: No active project")
        return 0, 0, 0

    proj = projects[0]
    debug_print(f"🧹 DELETING ALL UNUSED CLIPS - PART 1")
    debug_print(f"📂 Project: {proj.name()}")
    debug_print(f"🎯 Processing ALL project clips")
    debug_print(f"📋 Finding BinItems and checking usage in sequences...")
    debug_print()

    # Obtener todas las secuencias para verificación de uso
    sequences = get_all_sequences(proj)

    # DEBUG: Mostrar nombres de secuencias y crear lista negra
    known_sequences = set()
    if sequences:
        debug_print("📋 Found sequence names (blacklist):")
        for seq in sequences:
            if hasattr(seq, "name"):
                seq_name = seq.name()
                known_sequences.add(seq_name)
                debug_print(f"   • '{seq_name}' → IN BLACKLIST")
        debug_print()

    # Find ALL bin items in the project (SOLO BinItems, no Sequences)
    all_bin_items = []

    for item in hiero.core.findItems(proj, "BinItems"):
        if item and hasattr(item, "name"):
            item_name = item.name()
            # Excluir secuencias conocidas Y items con videoTracks
            if item_name not in known_sequences and not hasattr(item, "videoTracks"):
                # Es un BinItem real
                all_bin_items.append(item)

    if not all_bin_items:
        debug_print(f"❌ No BinItems found in the project")
        return 0, 0, 0

    debug_print(
        f"📋 Found {len(all_bin_items)} real BinItem(s) in the project (excluding {len(known_sequences)} sequences):"
    )
    debug_print()

    # Process each BinItem found - DETECTAR Y ELIMINAR SI NO SE USA
    total_processed = 0
    used_clips = 0
    deleted_clips = 0

    for bin_item_index, bin_item in enumerate(all_bin_items):
        try:
            bin_name = bin_item.name()

            # Determinar tipo de archivo
            file_type = "unknown"
            try:
                if hasattr(bin_item, "items"):
                    versions = bin_item.items()
                    if versions and hasattr(versions[0], "item"):
                        clip_item = versions[0].item()
                        if hasattr(clip_item, "mediaSource"):
                            media_source = clip_item.mediaSource()
                            if (
                                hasattr(media_source, "fileinfos")
                                and media_source.fileinfos()
                            ):
                                file_info = media_source.fileinfos()[0]
                                if hasattr(file_info, "filename"):
                                    path = file_info.filename()
                                    if path.endswith(".nk"):
                                        file_type = ".nk"
                                    elif path.endswith(".exr"):
                                        file_type = ".exr"
                                    elif path.endswith(".mov"):
                                        file_type = ".mov"
            except:
                pass

            # VERIFICAR SI EL CLIP SE USA EN SECUENCIAS
            is_used = is_bin_item_used_in_sequences(bin_item, sequences)

            if is_used:
                debug_print(f"✅ {bin_name} ({file_type}): KEPT (used in sequences)")
                used_clips += 1
            else:
                # ELIMINAR CLIP NO UTILIZADO
                try:
                    # Obtener el bin contenedor para eliminar el item
                    parent_bin = None
                    for bin_container in hiero.core.findItems(proj, "Bins"):
                        if (
                            hasattr(bin_container, "items")
                            and bin_item in bin_container.items()
                        ):
                            parent_bin = bin_container
                            break

                    if parent_bin:
                        parent_bin.removeItem(bin_item)
                        debug_print(
                            f"🗑️  {bin_name} ({file_type}): DELETED (not used in sequences)"
                        )
                        deleted_clips += 1
                    else:
                        debug_print(
                            f"⚠️  {bin_name} ({file_type}): Could not delete (container not found)"
                        )

                except Exception as e:
                    debug_print(f"❌ {bin_name} ({file_type}): Error deleting - {e}")

            total_processed += 1

        except Exception as e:
            debug_print(f"❌ Error processing {bin_item.name()}: {e}")
            total_processed += 1

    # Final summary
    debug_print(f"\n📊 CLEANING COMPLETED - PART 1:")
    debug_print(f"   • BinItems processed: {total_processed}")
    debug_print(f"   • Clips kept: {used_clips}")
    debug_print(f"   • Clips deleted: {deleted_clips}")
    debug_print(f"\n✅ Project cleaned - Unused clips removed")

    return total_processed, used_clips, deleted_clips


# Version Cleaner - Process ALL clips in project
# Detects online/offline versions and safely removes offline ones from ALL BinItems

import hiero
import hiero.core.find_items
import os


def cleanOfflineVersions():
    """Detect online/offline versions and remove offline ones safely"""

    projects = hiero.core.projects()
    if not projects:
        debug_print("ERROR: No active project found.")
        return 0, 0

    proj = projects[0]
    debug_print(f"🧽 CLEANING OFFLINE VERSIONS - ENTIRE PROJECT")
    debug_print(f"📂 Project: {proj.name()}")
    debug_print(f"🎯 Processing ALL project clips")
    debug_print(f"🔍 Finding BinItems...")
    debug_print()

    # Find ALL bin items in the project
    all_bin_items = []

    for bin_item in hiero.core.findItems(proj, "BinItems"):
        if bin_item and hasattr(bin_item, "name"):
            if hasattr(bin_item, "items"):
                try:
                    versions = bin_item.items()
                    if len(versions) >= 1:  # Only process BinItems that have versions
                        all_bin_items.append(bin_item)
                except:
                    pass

    if not all_bin_items:
        debug_print(f"⚠️ No BinItems with versions found in the project")
        return 0, 0

    debug_print(f"📋 Found {len(all_bin_items)} BinItem(s) to process:")
    debug_print()

    # Process each BinItem found
    total_processed = 0
    total_versions_removed = 0

    for bin_item_index, main_bin_item in enumerate(all_bin_items):
        try:
            versions = main_bin_item.items()
            total_versions = len(versions)

            # Quick analysis without verbose logging
            online_count = 0
            offline_count = 0
            offline_to_remove = 0

            # Get active version
            active_version = None
            try:
                active_version = main_bin_item.activeVersion()
            except:
                pass

            bin_item_name = main_bin_item.name()

            for version in versions:
                if hasattr(version, "name") and version.name().startswith(
                    bin_item_name
                ):
                    # Check if this version is active
                    is_active = active_version and version == active_version

                    # Check online/offline status
                    try:
                        if hasattr(version, "item"):
                            clip_item = version.item()
                            if clip_item and hasattr(clip_item, "mediaSource"):
                                media_source = clip_item.mediaSource()
                                if media_source and hasattr(
                                    media_source, "isMediaPresent"
                                ):
                                    if media_source.isMediaPresent():
                                        online_count += 1
                                    else:
                                        offline_count += 1
                                        if not is_active:
                                            offline_to_remove += 1
                    except:
                        offline_count += 1

            # Determine file type from first version path
            file_type = "unknown"
            try:
                if versions and hasattr(versions[0], "item"):
                    clip_item = versions[0].item()
                    if hasattr(clip_item, "mediaSource"):
                        media_source = clip_item.mediaSource()
                        if (
                            hasattr(media_source, "fileinfos")
                            and media_source.fileinfos()
                        ):
                            file_info = media_source.fileinfos()[0]
                            if hasattr(file_info, "filename"):
                                path = file_info.filename()
                                if path.endswith(".nk"):
                                    file_type = ".nk"
                                elif path.endswith(".exr"):
                                    file_type = ".exr"
                                elif path.endswith(".mov"):
                                    file_type = ".mov"
            except:
                pass

            # Process based on conditions
            if total_versions <= 1:
                debug_print(
                    f"⏭️  {main_bin_item.name()} ({file_type}): 1 version - Not processed"
                )
            elif online_count == 0:
                debug_print(
                    f"⚠️  {main_bin_item.name()} ({file_type}): {total_versions} offline versions - Not processed (all offline)"
                )
            else:
                # Safe to remove offline versions
                versions_to_remove = []
                for version in versions:
                    if hasattr(version, "name") and version.name().startswith(
                        bin_item_name
                    ):
                        is_active = active_version and version == active_version
                        if not is_active:
                            try:
                                clip_item = version.item()
                                if clip_item and hasattr(clip_item, "mediaSource"):
                                    media_source = clip_item.mediaSource()
                                    if (
                                        media_source
                                        and hasattr(media_source, "isMediaPresent")
                                        and not media_source.isMediaPresent()
                                    ):
                                        versions_to_remove.append(version)
                            except:
                                pass

                if versions_to_remove:
                    # Remove offline versions
                    removed_count = 0
                    for version in versions_to_remove:
                        try:
                            main_bin_item.removeVersion(version)
                            removed_count += 1
                        except:
                            pass

                    remaining = total_versions - removed_count
                    debug_print(
                        f"🗑️  {main_bin_item.name()} ({file_type}): Removed {removed_count} offline, kept {remaining} online"
                    )
                    total_versions_removed += removed_count
                else:
                    debug_print(
                        f"✅ {main_bin_item.name()} ({file_type}): {total_versions} versions - No offline to remove"
                    )

            total_processed += 1

        except Exception as e:
            debug_print(f"❌ Error processing {main_bin_item.name()}: {e}")
            total_processed += 1

    # Final summary
    debug_print(f"\ CLEANING COMPLETED - ENTIRE PROJECT:")
    debug_print(f"   • BinItems processed: {total_processed}")
    debug_print(f"   • Offline versions removed: {total_versions_removed}")
    debug_print(f"   • Project cleaned ✅")

    return total_processed, total_versions_removed


def main():
    """Ejecuta la limpieza completa del proyecto: clips no utilizados + versiones offline"""

    debug_print("🚀 STARTING COMPLETE PROJECT CLEANING")
    debug_print("=" * 60)

    # Ejecutar limpieza de clips no utilizados
    processed_clips, used_clips, deleted_clips = cleanAllUnusedClips()

    debug_print()
    debug_print("-" * 60)
    debug_print()

    # Ejecutar limpieza de versiones offline
    processed_versions, deleted_versions = cleanOfflineVersions()

    debug_print()
    debug_print("=" * 60)
    debug_print("🎉 COMPLETE CLEANING FINISHED")
    debug_print()

    # Show results message to user
    message = f"""COMPLETE PROJECT CLEANING FINISHED

RESULTS:

• Clips processed: {processed_clips}
• Clips deleted (unused): {deleted_clips}

• BinItems processed (versions): {processed_versions}
• Offline versions removed: {deleted_versions}

✅ Project successfully cleaned"""

    try:
        nuke.message(message)
    except:
        # Fallback si nuke.message no está disponible
        print(message)


# Execute the cleaning
if __name__ == "__main__":
    main()
