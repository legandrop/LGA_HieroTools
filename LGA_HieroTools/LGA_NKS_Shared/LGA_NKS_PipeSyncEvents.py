"""
____________________________________________________________________

  LGA_NKS_PipeSyncEvents v1.00 | Lega

  Avisa a PipeSync abierto de un cambio que HieroTools ya hizo en Flow,
  para que se vea al instante en todos sus tabs (Shots, Review, Prod,
  Gantt) sin esperar al proximo sync.

  Por que existe: Push escribe Flow y despues pipesync.db, pero PipeSync
  tiene sus vistas armadas en memoria y no se entera de una escritura
  externa a la base. Este modulo le manda UNA linea JSON por el canal
  local de eventos de PipeSync (QLocalServer "PipeSync_Events", o
  "PipeSync_Events_Client" en contexto client). PipeSync actualiza su
  cache local y repinta con el mismo aviso que usa un cambio hecho
  adentro de la app. Nunca vuelve a escribir Flow por este aviso.

  Es fuego y olvido: si PipeSync no esta abierto (o es una version
  vieja sin el canal), no pasa nada; al abrirlo lee la base, que ya
  tiene el estado nuevo. Nunca lanza excepciones al llamador.

  Canal local (named pipe en Windows, socket Unix en macOS): no es red,
  no pasa por el firewall. Contrato del lado de PipeSync:
  include/pipesync/ExternalEventProtocol.h (repo LGA_PipeSync_2).

  v1.00: Primera version. Evento task_status.
____________________________________________________________________
"""

import json
import os
import socket
import sys
import tempfile
import time

PROTOCOL_VERSION = 1
_SERVER_STUDIO = "PipeSync_Events"
_SERVER_CLIENT = "PipeSync_Events_Client"
_TIMEOUT_S = 1.0
# Windows: ERROR_PIPE_BUSY. Qt deja una sola instancia del pipe escuchando y crea la
# siguiente apenas acepta una conexion: un segundo intento casi siempre entra.
_ERROR_PIPE_BUSY = 231
_BUSY_RETRIES = 3


def _noop(*_args, **_kwargs):
    pass


def _context_mode():
    """'studio' o 'client', el mismo contexto que decide que pipesync.db se escribio."""
    try:
        from LGA_NKS_Shared.LGA_NKS_ContextProfile import get_context_mode

        return get_context_mode()
    except Exception:
        try:
            from LGA_NKS_ContextProfile import get_context_mode

            return get_context_mode()
        except Exception:
            return "studio"


def server_name(context_mode):
    return _SERVER_CLIENT if context_mode == "client" else _SERVER_STUDIO


def _send_windows(name, data):
    path = "\\\\.\\pipe\\" + name
    for attempt in range(_BUSY_RETRIES):
        try:
            with open(path, "wb", buffering=0) as pipe:
                pipe.write(data)
            return True, ""
        except FileNotFoundError:
            return False, "PipeSync no esta abierto (no existe el canal %s)" % name
        except OSError as e:
            if getattr(e, "winerror", None) == _ERROR_PIPE_BUSY and attempt + 1 < _BUSY_RETRIES:
                time.sleep(0.1)
                continue
            return False, "no se pudo escribir en %s: %s" % (name, e)
    return False, "canal %s ocupado" % name


def _send_unix(name, data):
    # Qt arma la ruta del QLocalServer como QDir::tempPath() + "/" + nombre, y
    # QDir::tempPath() sale de TMPDIR, igual que tempfile.gettempdir().
    path = os.path.join(tempfile.gettempdir(), name)
    if not os.path.exists(path):
        return False, "PipeSync no esta abierto (no existe %s)" % path
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(_TIMEOUT_S)
    try:
        sock.connect(path)
        sock.sendall(data)
        return True, ""
    except OSError as e:
        return False, "no se pudo escribir en %s: %s" % (path, e)
    finally:
        try:
            sock.close()
        except Exception:
            pass


def build_task_status_line(context_mode, task_sg_id, status, task_local_id=None, source="hiero_push"):
    """La linea que se manda, terminada en '\\n'. Separada para poder probarla."""
    payload = {
        "v": PROTOCOL_VERSION,
        "event": "task_status",
        "context": context_mode,
        "task_sg_id": int(task_sg_id),
        "status": str(status),
        "source": source,
    }
    if task_local_id:
        payload["task_id"] = int(task_local_id)
    return (json.dumps(payload) + "\n").encode("utf-8")


def notify_task_status_changed(task_sg_id, status, task_local_id=None, source="hiero_push", log=None):
    """Avisa a PipeSync que la task (id de Flow) ya quedo en `status` (codigo de Flow).

    Llamar SOLO despues de que Flow confirmo el cambio, y fuera del hilo principal
    (puede tardar hasta ~1 s si el canal esta ocupado). Devuelve True si el aviso se
    entrego; False si PipeSync no esta abierto o fallo, sin lanzar nunca.
    """
    log = log or _noop
    try:
        if not task_sg_id or not status:
            log("PipeSyncEvents: aviso omitido, falta task_sg_id o status")
            return False
        context_mode = _context_mode()
        name = server_name(context_mode)
        data = build_task_status_line(context_mode, task_sg_id, status, task_local_id, source)
        if sys.platform == "win32":
            ok, reason = _send_windows(name, data)
        else:
            ok, reason = _send_unix(name, data)
        if ok:
            log("PipeSyncEvents: aviso entregado a %s (task Flow %s -> %s)" % (name, task_sg_id, status))
        else:
            log("PipeSyncEvents: aviso no entregado: %s" % reason)
        return ok
    except Exception as e:
        log("PipeSyncEvents: error inesperado avisando a PipeSync: %s" % e)
        return False
