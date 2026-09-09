# -*- coding: utf-8 -*-
"""
Tests de LGA_NKS_CG_Versions.

Lo que fija este archivo es la regla que distingue a CG del resto:

  comp / roto / cleanup -> la ultima es la de NUMERO mas alto.
  CG                    -> la ultima es la ULTIMA SUBIDA, por fecha.

CG es una sola task de Flow que junta entregas de varias disciplinas, y cada
disciplina lleva su propio contador. Por eso el numero no ordena: un
`lighting_v004` puede ser mas nuevo que un `animation_v013`. El test del caso
maestro es exactamente ese, porque es el que el criterio viejo resolvia mal.

Corre sin Hiero, sin PipeSync instalado y sin red: la DB se arma sintetica.
"""

import os
import sqlite3
import sys
from tempfile import TemporaryDirectory


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED_DIR = os.path.dirname(CURRENT_DIR)
if SHARED_DIR not in sys.path:
    sys.path.insert(0, SHARED_DIR)

from LGA_NKS_CG_Versions import (  # noqa: E402
    fecha_de_subida,
    orden_por_subida,
    ultima_version_cg,
    ultima_version_cg_de_shot,
)


class TestFailure(AssertionError):
    pass


def _expect(condition, message):
    if not condition:
        raise TestFailure(message)


def _v(code, numero, fecha):
    return {"version_code": code, "version_number": numero, "created_on": fecha}


def check_caso_maestro():
    """El caso que el criterio viejo resolvia mal: numero alto pero vieja."""
    versiones = [
        _v("PROJA_1013_0800_animation_v013", 13, "2026-09-01 10:00:00-03:00"),
        _v("PROJA_1013_0800_lighting_v004", 4, "2026-09-07 18:41:51-03:00"),
    ]
    ultima = ultima_version_cg(versiones)
    _expect(
        ultima["version_code"] == "PROJA_1013_0800_lighting_v004",
        "En CG manda la fecha: lighting_v004 es posterior a animation_v013, "
        "aunque su numero sea menor. Dio: %r" % (ultima["version_code"],),
    )
    # Y el criterio viejo, por numero, daba la otra: si alguien lo reintroduce
    # este test tiene que fallar.
    por_numero = max(versiones, key=lambda v: v["version_number"])
    _expect(
        por_numero["version_code"] != ultima["version_code"],
        "El caso maestro dejo de discriminar entre los dos criterios",
    )


def check_orden_completo():
    versiones = [
        _v("A_v001", 1, "2026-01-01 00:00:00-03:00"),
        _v("B_v050", 50, "2026-02-01 00:00:00-03:00"),
        _v("C_v002", 2, "2026-03-01 00:00:00-03:00"),
    ]
    ordenadas = sorted(versiones, key=orden_por_subida)
    _expect(
        [v["version_code"] for v in ordenadas] == ["A_v001", "B_v050", "C_v002"],
        "El orden por subida ignora el numero: %r" % (ordenadas,),
    )


def check_filas_sin_fecha():
    """Una fila legacy sin fecha no puede ganar por tener numero alto."""
    versiones = [
        _v("LEGACY_v099", 99, None),
        _v("NUEVA_v001", 1, "2026-09-07 18:41:51-03:00"),
    ]
    _expect(
        ultima_version_cg(versiones)["version_code"] == "NUEVA_v001",
        "Una fila sin created_on no puede ganarle a una con fecha",
    )
    # Si NINGUNA tiene fecha, se desempata por numero.
    solo_legacy = [_v("A_v2", 2, None), _v("B_v9", 9, "")]
    _expect(
        ultima_version_cg(solo_legacy)["version_code"] == "B_v9",
        "Sin ninguna fecha, desempata el numero",
    )


def check_fechas_raras():
    _expect(fecha_de_subida(_v("A_v1", 1, "no-es-fecha")) is None,
            "Una fecha invalida devuelve None, no revienta")
    _expect(fecha_de_subida(_v("A_v1", 1, None)) is None, "None devuelve None")
    _expect(fecha_de_subida({}) is None, "Un dict sin la clave devuelve None")
    _expect(fecha_de_subida(None) is None, "None como version devuelve None")

    # Naive contra aware: comparar los dos sin normalizar levanta TypeError.
    mezcla = [
        _v("NAIVE_v1", 1, "2026-09-08 12:00:00"),
        _v("AWARE_v1", 1, "2026-09-07 12:00:00-03:00"),
    ]
    _expect(
        ultima_version_cg(mezcla) is not None,
        "Mezclar fechas con y sin offset no puede levantar TypeError",
    )


def check_lista_vacia():
    _expect(ultima_version_cg([]) is None, "Lista vacia devuelve None")
    _expect(ultima_version_cg(None) is None, "None devuelve None")


def _armar_db(ruta, filas):
    """DB sintetica con el esquema minimo que usa la consulta."""
    con = sqlite3.connect(ruta)
    cur = con.cursor()
    cur.execute("CREATE TABLE shots (id INTEGER PRIMARY KEY, shot_name TEXT)")
    cur.execute(
        "CREATE TABLE tasks (id INTEGER PRIMARY KEY, shot_id INTEGER, task_type TEXT)"
    )
    cur.execute(
        "CREATE TABLE versions (id INTEGER PRIMARY KEY, task_id INTEGER, "
        "version_code TEXT, version_number INTEGER, created_on TIMESTAMP)"
    )
    cur.execute("INSERT INTO shots VALUES (1, 'PROJA_1013_0800')")
    cur.execute("INSERT INTO tasks VALUES (10, 1, 'Comp')")
    cur.execute("INSERT INTO tasks VALUES (11, 1, 'CG')")
    for i, (task_id, code, numero, fecha) in enumerate(filas, start=100):
        cur.execute(
            "INSERT INTO versions VALUES (?, ?, ?, ?, ?)",
            (i, task_id, code, numero, fecha),
        )
    con.commit()
    con.close()


def check_lectura_de_db():
    with TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "pipesync.db")
        _armar_db(
            db,
            [
                # La task Comp no tiene que entrar en el calculo de CG.
                (10, "PROJA_1013_0800_comp_v099", 99, "2026-12-01 00:00:00-03:00"),
                (11, "PROJA_1013_0800_animation_v013", 13, "2026-09-01 10:00:00-03:00"),
                (11, "PROJA_1013_0800_lighting_v004", 4, "2026-09-07 18:41:51-03:00"),
            ],
        )
        codigo = ultima_version_cg_de_shot("PROJA_1013_0800", db_path=db)
        _expect(
            codigo == "PROJA_1013_0800_lighting_v004",
            "La consulta tiene que devolver la ultima de CG por fecha, y NO "
            "mirar la task Comp. Dio: %r" % (codigo,),
        )
        _expect(
            ultima_version_cg_de_shot("PROJA_9999_9999", db_path=db) is None,
            "Un shot que no esta devuelve None",
        )
        _expect(
            ultima_version_cg_de_shot("", db_path=db) is None,
            "Un shot vacio devuelve None",
        )
        _expect(
            ultima_version_cg_de_shot("PROJA_1013_0800", db_path=db + ".noexiste")
            is None,
            "Una DB inexistente devuelve None en vez de reventar",
        )


def check_shot_sin_task_cg():
    with TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "pipesync.db")
        _armar_db(
            db,
            [(10, "PROJA_1013_0800_comp_v001", 1, "2026-09-01 00:00:00-03:00")],
        )
        _expect(
            ultima_version_cg_de_shot("PROJA_1013_0800", db_path=db) is None,
            "Un shot con task CG sin versiones devuelve None",
        )


def check_matcheo_carpeta_contra_flow():
    """El `version_code` de Flow trae sufijos que la carpeta de publish no tiene.

    Es el caso que una auditoria demostro roto: comparar los nombres enteros
    no matchea NUNCA contra un codigo como `..._lighting_v010_SeqRef_b`, y CG
    quedaba sin ninguna version marcada como ultima, en silencio.
    """
    from LGA_NKS_CG_Versions import clave_de_version, misma_entrega

    code = "PROJA_1005_0500_WAN_lighting_v010_SeqRef_b"
    _expect(
        misma_entrega("PROJA_1005_0500_WAN_lighting_v010", code),
        "La carpeta sin sufijo tiene que matchear el version_code con sufijo",
    )
    _expect(
        misma_entrega(code, code),
        "Un nombre identico obviamente matchea",
    )
    _expect(
        not misma_entrega("PROJA_1005_0500_WAN_lighting_v011", code),
        "Otro numero NO matchea",
    )
    _expect(
        not misma_entrega("PROJA_1005_0500_WAN_animation_v010", code),
        "Otra disciplina con el mismo numero NO matchea",
    )
    # La igualdad exacta, que era el criterio roto, tiene que seguir fallando:
    # si alguien la reintroduce, este test lo delata.
    _expect(
        "PROJA_1005_0500_WAN_lighting_v010".lower() != code.lower(),
        "El caso dejo de discriminar entre matcheo exacto y por clave",
    )

    _expect(
        clave_de_version(code) == ("proja_1005_0500_wan_lighting", 10),
        "La clave es (lo de antes de la version, numero): %r"
        % (clave_de_version(code),),
    )
    _expect(clave_de_version("SinVersion") is None, "Sin _vNNN devuelve None")

    # Un shot cuyo NOMBRE ya trae un token con forma de version. Tomando el
    # primer `_vNNN` el `_v2` se comia el nombre entero y dos disciplinas
    # distintas colapsaban a la misma clave: se daban por la misma entrega, y
    # con replace_cg_clip eso reemplaza la media por la carpeta equivocada.
    a = "PROJA_v2_1013_0800_lighting_v010"
    b = "PROJA_v2_1013_0800_animation_v013"
    _expect(
        clave_de_version(a) == ("proja_v2_1013_0800_lighting", 10),
        "La clave sale del ULTIMO _vNNN: %r" % (clave_de_version(a),),
    )
    _expect(
        not misma_entrega(a, b),
        "Dos disciplinas distintas NO son la misma entrega aunque el nombre "
        "del shot traiga un _vN adentro",
    )
    _expect(
        misma_entrega(a, a + "_SeqRef"),
        "La misma entrega con sufijo sigue matcheando con el shot con _vN",
    )
    _expect(not misma_entrega(None, code), "None no matchea")
    _expect(not misma_entrega("x", None), "None como codigo no matchea")
    _expect(
        misma_entrega("ABC", "ABC"),
        "Sin version reconocible se cae a comparar los nombres completos",
    )


def check_carpeta_en_disco():
    """Resolver que carpeta de publish corresponde a la version de Flow."""
    from LGA_NKS_CG_Versions import carpeta_de_version_cg

    with TemporaryDirectory() as tmp:
        pub = os.path.join(tmp, "4_publish")
        os.makedirs(os.path.join(pub, "PROJA_1013_0800_lighting_v011_SeqRef"))
        os.makedirs(os.path.join(pub, "PROJA_1013_0800_animation_v013"))
        # Un archivo suelto no es una carpeta de version.
        open(os.path.join(pub, "notas.txt"), "w").close()

        exacta = carpeta_de_version_cg(pub, "PROJA_1013_0800_lighting_v011_SeqRef")
        _expect(
            exacta and os.path.basename(exacta) == "PROJA_1013_0800_lighting_v011_SeqRef",
            "Match exacto por (disciplina, numero): %r" % (exacta,),
        )

        # Caso real: la DB quedo vieja (dice "comp") y el disco dice "lighting".
        # Con una sola carpeta de ese numero, se resuelve igual.
        vieja = carpeta_de_version_cg(pub, "PROJA_1013_0800_comp_v011_SeqRef")
        _expect(
            vieja and os.path.basename(vieja) == "PROJA_1013_0800_lighting_v011_SeqRef",
            "Con la DB desincronizada, el respaldo por numero resuelve: %r" % (vieja,),
        )

        _expect(
            carpeta_de_version_cg(pub, "PROJA_1013_0800_lighting_v099") is None,
            "Una version que no esta en disco devuelve None",
        )
        _expect(
            carpeta_de_version_cg(pub, None) is None
            and carpeta_de_version_cg(None, "X_v001") is None,
            "Entradas vacias devuelven None",
        )
        _expect(
            carpeta_de_version_cg(os.path.join(tmp, "no_existe"), "X_v001") is None,
            "Un publish inexistente devuelve None, no revienta",
        )

    # Ambiguedad: dos disciplinas con el MISMO numero y la DB con un tercer
    # nombre. No se adivina.
    with TemporaryDirectory() as tmp:
        pub = os.path.join(tmp, "4_publish")
        os.makedirs(os.path.join(pub, "PROJA_1013_0800_lighting_v011"))
        os.makedirs(os.path.join(pub, "PROJA_1013_0800_animation_v011"))
        _expect(
            carpeta_de_version_cg(pub, "PROJA_1013_0800_comp_v011") is None,
            "Con dos carpetas del mismo numero no se elige ninguna",
        )
        # Pero si el nombre SI coincide, gana el match exacto sobre la ambiguedad.
        elegida = carpeta_de_version_cg(pub, "PROJA_1013_0800_animation_v011")
        _expect(
            elegida and os.path.basename(elegida) == "PROJA_1013_0800_animation_v011",
            "El match por disciplina desempata: %r" % (elegida,),
        )


def run():
    check_caso_maestro()
    check_matcheo_carpeta_contra_flow()
    check_carpeta_en_disco()
    check_orden_completo()
    check_filas_sin_fecha()
    check_fechas_raras()
    check_lista_vacia()
    check_lectura_de_db()
    check_shot_sin_task_cg()


if __name__ == "__main__":
    run()
    print("test_cg_versions: OK")
