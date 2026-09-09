# -*- coding: utf-8 -*-
"""
____________________________________________________________________

  LGA_NKS_CG_Versions v1.02 | Lega

  Cual es la ULTIMA version de la task CG, y por que se decide distinto que
  en el resto de las tasks.

  comp, roto y cleanup son cada una su propia task de Flow, con su propio
  contador: ahi la ultima es la de NUMERO mas alto, como siempre.

  CG es una sola task de Flow que junta las entregas de varias disciplinas
  (animation, lighting, layout, ...), y cada disciplina lleva su PROPIO
  contador. Por eso el numero no ordena: un `lighting_v004` puede haberse
  entregado despues que un `animation_v013`. Dentro de CG la ultima version
  es la ULTIMA SUBIDA, por fecha. El nombre de la version no decide nada:
  cualquier nombre dentro de la task CG es valido.

  Este modulo NO importa hiero, asi que lo pueden usar los tests y las tools
  que corren fuera de NKS.

  v1.02: carpeta_de_version_cg() resuelve que carpeta de 4_publish es una
         version de Flow. Busca primero por (disciplina, numero) y, si no
         hay ninguna, SOLO por numero y solo si hay una unica candidata:
         cubre el caso de que la DB haya quedado vieja respecto del disco
         tras un rename en Flow. Con dos candidatas no elige ninguna.
         Ademas, la clave sale del ULTIMO `_vNNN` del nombre y no del
         primero: un shot que traiga un token con forma de version adentro
         (`PROJA_v2_1013_0800_lighting_v010`) hacia colapsar dos disciplinas
         distintas a la misma clave, y con el reemplazo de media eso deja el
         clip apuntando a la carpeta equivocada.
  v1.01: misma_entrega() compara por (disciplina, numero) y no por nombre
         completo: el version_code de Flow trae sufijos que la carpeta de
         publish no tiene -se vieron `_SeqRef` y `_SeqRef_b`- y una igualdad
         exacta no matchea nunca, dejando a CG sin ninguna version marcada
         como ultima, en silencio.
  v1.00: Version inicial.
____________________________________________________________________

"""

import os
import re
import sqlite3
from datetime import datetime, timezone


# Sufijo de version de un nombre: el `_v010` de `SHOT_lighting_v010`.
#
# Se toma el ULTIMO y no el primero: el nombre de un shot puede tener un token
# con forma de version adentro -`PROJA_v2_1013_0800_lighting_v010`-, y tomando
# el primero ese `_v2` se come el nombre entero. Ahi dos disciplinas distintas
# colapsan a la misma clave y se dan por la misma entrega, que con
# `replace_cg_clip` significa reemplazar la media del clip por la carpeta
# equivocada. El sufijo real es siempre el que esta mas cerca del final.
_RE_VERSION = re.compile(r"[_\-]v(\d+)", re.IGNORECASE)


def clave_de_version(nombre):
    """Identidad de una entrega: (lo que va antes de la version, numero).

    `SHOT_lighting_v010_SeqRef_b`  ->  ("shot_lighting", 10)
    `SHOT_lighting_v010`           ->  ("shot_lighting", 10)

    Sirve para decidir si una carpeta de publish corresponde a una version de
    Flow. NO se comparan los nombres enteros a proposito: el `version_code`
    que Flow devuelve trae sufijos que la carpeta no tiene -se vieron
    `_SeqRef` y `_SeqRef_b`, que es la convencion de los .mov de review- y una
    igualdad exacta no matchea NUNCA. Como esos sufijos los escribe otra
    herramienta y no hay lista de cuales son, se ignora todo lo que venga
    despues del numero de version en vez de recortar sufijos conocidos.

    Devuelve None si el nombre no tiene un `_vNNN` reconocible.
    """
    if not nombre:
        return None
    texto = str(nombre)
    matches = list(_RE_VERSION.finditer(texto))
    if not matches:
        return None
    match = matches[-1]
    return (texto[: match.start()].strip().lower(), int(match.group(1)))


def misma_entrega(nombre_carpeta, version_code):
    """True si una carpeta de publish corresponde a ese `version_code`.

    Compara por (disciplina, numero). Si alguno de los dos no tiene version
    reconocible se cae a comparar los nombres completos, que es lo unico que
    queda.
    """
    if not nombre_carpeta or not version_code:
        return False
    clave_carpeta = clave_de_version(nombre_carpeta)
    clave_codigo = clave_de_version(version_code)
    if clave_carpeta is None or clave_codigo is None:
        return str(nombre_carpeta).strip().lower() == str(version_code).strip().lower()
    return clave_carpeta == clave_codigo


def fecha_de_subida(version):
    """Fecha de subida de una version, o None si la fila no la trae.

    Se lee `created_on`, que es la fecha que viene de Flow, y NO `created_at`,
    que es cuando PipeSync escribio la fila local: dos versiones sincronizadas
    en la misma pasada comparten `created_at` y no se podrian ordenar.

    Formato tipico: "2026-09-09 10:45:05-03:00".
    """
    if not version:
        return None
    crudo = str(version.get("created_on") or "").strip()
    if not crudo:
        return None
    try:
        fecha = datetime.fromisoformat(crudo)
    except (ValueError, TypeError):
        return None
    # Sin offset se asume UTC, para poder comparar contra las que si lo traen:
    # comparar una fecha naive con una aware levanta TypeError.
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=timezone.utc)
    return fecha


def orden_por_subida(version):
    """Clave de orden de las versiones de la task CG: manda la fecha.

    Las filas sin fecha van al fondo y desempatan por numero, para que una
    fila legacy sin `created_on` no se lleve puesto el calculo (con `max()`
    quedaria arriba si su numero fuera alto).
    """
    fecha = fecha_de_subida(version)
    numero = (version or {}).get("version_number") or 0
    if fecha is None:
        return (0, 0.0, numero)
    return (1, fecha.timestamp(), numero)


def ultima_version_cg(versiones):
    """La version mas nueva de una lista de versiones de la task CG.

    `versiones` son dicts con al menos `created_on` y `version_number`.
    Devuelve None si la lista viene vacia.
    """
    if not versiones:
        return None
    return max(versiones, key=orden_por_subida)


def _db_path():
    try:
        from LGA_NKS_PipeSyncPaths import get_pipesync_db_path
    except ImportError:
        from LGA_NKS_Shared.LGA_NKS_PipeSyncPaths import get_pipesync_db_path
    return get_pipesync_db_path()


def ultima_version_cg_de_shot(shot_name, db_path=None):
    """`version_code` de la ultima version de la task CG de un shot.

    Lee la DB de PipeSync del contexto activo en modo SOLO LECTURA. Devuelve
    None si no hay DB, si el shot no esta, si no tiene task CG o si esa task
    no tiene versiones: en todos esos casos el caller se queda con su
    comportamiento historico en vez de recibir un dato inventado.

    `db_path` existe para los tests.
    """
    if not shot_name:
        return None
    ruta = db_path or _db_path()
    if not ruta or not os.path.exists(str(ruta)):
        return None

    try:
        con = sqlite3.connect("file:%s?mode=ro" % str(ruta), uri=True)
    except sqlite3.Error:
        return None
    try:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        filas = cur.execute(
            """
            SELECT v.version_code, v.version_number, v.created_on
            FROM versions v
            JOIN tasks t ON t.id = v.task_id
            JOIN shots s ON s.id = t.shot_id
            WHERE s.shot_name = ? AND LOWER(t.task_type) = 'cg'
            """,
            (str(shot_name),),
        ).fetchall()
    except sqlite3.Error:
        return None
    finally:
        con.close()

    ultima = ultima_version_cg([dict(f) for f in filas])
    return (ultima or {}).get("version_code") or None


def carpeta_de_version_cg(publish_dir, version_code):
    """Carpeta de `publish_dir` que corresponde a esa version de Flow.

    Devuelve la ruta completa, o None si no hay ninguna que corresponda.

    Se busca en dos pasadas:

    1. Por (disciplina, numero), que es la identidad de la entrega.
    2. Si ninguna coincide, SOLO por numero, y unicamente si hay UNA sola
       candidata. Esto cubre el caso real de que el `version_code` de la DB
       haya quedado viejo respecto del disco -por ejemplo si alguien renombro
       la version en Flow y la DB todavia no lo sincronizo-. Si hay dos
       carpetas con el mismo numero no se elige ninguna: adivinar cual es
       peor que no hacer nada.
    """
    if not publish_dir or not version_code:
        return None
    clave = clave_de_version(version_code)
    try:
        entradas = [
            nombre
            for nombre in os.listdir(str(publish_dir))
            if os.path.isdir(os.path.join(str(publish_dir), nombre))
        ]
    except (OSError, ValueError):
        return None

    for nombre in sorted(entradas):
        if misma_entrega(nombre, version_code):
            return os.path.join(str(publish_dir), nombre)

    if clave is None:
        return None
    numero = clave[1]
    por_numero = [
        nombre
        for nombre in sorted(entradas)
        if (clave_de_version(nombre) or (None, None))[1] == numero
    ]
    if len(por_numero) == 1:
        return os.path.join(str(publish_dir), por_numero[0])
    return None


__all__ = [
    "clave_de_version",
    "misma_entrega",
    "carpeta_de_version_cg",
    "fecha_de_subida",
    "orden_por_subida",
    "ultima_version_cg",
    "ultima_version_cg_de_shot",
]
