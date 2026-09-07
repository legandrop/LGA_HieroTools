"""
Tests de LGA_NKS_ColorManagement_Config, sin depender de Nuke/Hiero.

Arma una pipesync_stats.db sintetica en un temp dir y apunta ahi el modulo
bajo prueba, mismo patron que test_vendor_naming.py. Cada test_* es
autocontenido (arma su propia DB temporal) para poder correr con pytest o
de forma directa via `if __name__ == "__main__"`.
"""

import json
import os
import sqlite3
import sys
from tempfile import TemporaryDirectory

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED_DIR = os.path.dirname(CURRENT_DIR)
if SHARED_DIR not in sys.path:
    sys.path.insert(0, SHARED_DIR)

import LGA_NKS_ColorManagement_Config as cm_config  # noqa: E402


def _build_db(db_path, proyectos):
    """
    proyectos: {nombre: envelope_dict | None}.

    `envelope_dict` es el envelope COMPLETO de Project Settings, tal cual lo
    guarda PipeSync (con o sin la clave "color_management" - el caller decide
    que forma probar). `None` significa que el proyecto esta en `projects`
    pero nunca llego a tener fila en `project_settings_cache` (PipeSync
    nunca le sincronizo settings).
    """
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE projects (id INTEGER PRIMARY KEY, project_name TEXT)")
    conn.execute(
        "CREATE TABLE project_settings_cache (project_id INTEGER, settings_json TEXT)"
    )
    for idx, (nombre, envelope_dict) in enumerate(proyectos.items(), start=1):
        conn.execute("INSERT INTO projects VALUES (?, ?)", (idx, nombre))
        if envelope_dict is None:
            continue
        envelope = json.dumps(envelope_dict)
        conn.execute(
            "INSERT INTO project_settings_cache VALUES (?, ?)", (idx, envelope)
        )
    conn.commit()
    conn.close()


def _envelope_color_management(color_management):
    """Envelope con SOLO la clave color_management, para los casos que la traen."""
    return {"color_management": color_management}


def _con_db_sintetica(proyectos):
    """
    Context manager casero: arma una DB sintetica, apunta el modulo ahi,
    corre el bloque, y restaura todo (incluido el cache) al salir.

    Devuelve el path de la DB por si algun test lo necesita.
    """

    class _Ctx:
        def __enter__(self):
            self._tmp = TemporaryDirectory()
            db_path = os.path.join(self._tmp.name, "pipesync_stats.db")
            _build_db(db_path, proyectos)
            self._original_path_fn = cm_config.get_color_management_db_path
            cm_config.get_color_management_db_path = lambda: db_path
            cm_config.refresh_cache()
            return db_path

        def __exit__(self, *exc_info):
            cm_config.get_color_management_db_path = self._original_path_fn
            cm_config.refresh_cache()
            self._tmp.cleanup()
            return False

    return _Ctx()


# ============================
# Caso 1: color_management completo y enabled=true
# ============================


def test_proyecto_managed_completo():
    with _con_db_sintetica(
        {
            "PROJA": _envelope_color_management(
                {
                    "enabled": True,
                    "workspace": "acescg",
                    "plates": "acescg",
                    "exr_publish": "aces2065-1",
                }
            )
        }
    ):
        assert cm_config.is_color_managed("PROJA") is True

        config = cm_config.get_color_management("PROJA")
        assert config is not None
        assert config["workspace"] == "acescg"
        assert config["plates"] == "acescg"
        assert config["exr_publish"] == "aces2065-1"

        # Lookup case-insensitive del nombre de proyecto.
        assert cm_config.is_color_managed("proja") is True


# ============================
# Caso 2: proyecto sin la clave color_management
# ============================


def test_proyecto_sin_clave_color_management():
    # PROJB tiene un envelope real (por ejemplo, vendors cargados) pero
    # JAMAS configuro color management: la clave "color_management" no
    # esta en el envelope. PROJA ni siquiera tiene fila de settings.
    with _con_db_sintetica({"PROJB": {"vendors": ["VEN"]}, "PROJA": None}):
        # PROJB esta en la DB, con un envelope, pero SIN la clave
        # "color_management": _extraer_color_management debe dar None.
        assert cm_config.get_color_management("PROJB") is None
        assert cm_config.is_color_managed("PROJB") is False

        # PROJA esta en la DB pero ni siquiera tiene fila de settings.
        assert cm_config.get_color_management("PROJA") is None
        assert cm_config.is_color_managed("PROJA") is False

        # Proyecto que directamente no esta en la DB.
        assert cm_config.get_color_management("DESCONOCIDO") is None
        assert cm_config.is_color_managed("DESCONOCIDO") is False


# ============================
# Caso 3: enabled=false pero con valores
# ============================


def test_enabled_false_conserva_valores():
    with _con_db_sintetica(
        {
            "PROJA": _envelope_color_management(
                {
                    "enabled": False,
                    "workspace": "acescg",
                    "plates": "acescg",
                    "exr_publish": "aces2065-1",
                }
            )
        }
    ):
        assert cm_config.is_color_managed("PROJA") is False

        config = cm_config.get_color_management("PROJA")
        assert config is not None
        assert config["enabled"] is False
        assert config["workspace"] == "acescg"
        assert config["plates"] == "acescg"
        assert config["exr_publish"] == "aces2065-1"


# ============================
# Caso 4: token desconocido se devuelve tal cual
# ============================


def test_token_desconocido_no_se_normaliza():
    with _con_db_sintetica(
        {
            "PROJA": _envelope_color_management(
                {
                    "enabled": True,
                    "workspace": "cineon",
                    "plates": "cineon",
                    "exr_publish": "aces2065-1",
                }
            )
        }
    ):
        config = cm_config.get_color_management("PROJA")
        assert config is not None
        assert config["workspace"] == "cineon"
        assert config["plates"] == "cineon"
        # Sigue siendo managed: enabled no depende de que los tokens sean
        # conocidos.
        assert cm_config.is_color_managed("PROJA") is True


# ============================
# Caso 5: DB inexistente -> {} sin excepcion
# ============================


def test_db_inexistente_no_explota():
    with TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "no_existe.db")
        original_path_fn = cm_config.get_color_management_db_path
        cm_config.get_color_management_db_path = lambda: db_path
        cm_config.refresh_cache()
        try:
            assert cm_config.load_project_color_management() == {}
            assert cm_config.get_color_management("PROJA") is None
            assert cm_config.is_color_managed("PROJA") is False
        finally:
            cm_config.get_color_management_db_path = original_path_fn
            cm_config.refresh_cache()


# ============================
# Caso 6: resolve_ocio_name contra una lista tipo config aces_1.2
# ============================

ACES_1_2_TRANSFORMS = [
    "ACES - ACEScg",
    "ACES - ACES2065-1",
    "Output - Rec.709",
    "scene_linear (ACES - ACEScg)",
    "Input - ARRI - V3 LogC (EI160) - Wide Gamut",
]


def test_resolve_ocio_name_acescg_no_matchea_el_rol():
    resultado = cm_config.resolve_ocio_name("acescg", ACES_1_2_TRANSFORMS)
    assert resultado == "ACES - ACEScg"


def test_resolve_ocio_name_aces2065_1():
    resultado = cm_config.resolve_ocio_name("aces2065-1", ACES_1_2_TRANSFORMS)
    assert resultado == "ACES - ACES2065-1"


# ============================
# Caso 7: token que no esta en la lista -> None
# ============================


def test_resolve_ocio_name_token_sin_match():
    resultado = cm_config.resolve_ocio_name("cineon", ACES_1_2_TRANSFORMS)
    assert resultado is None


def _expect(condition, message):
    if not condition:
        raise AssertionError(message)


def run():
    """
    Corre todos los test_* del modulo, en orden, para uso sin pytest.

    Son 8 funciones test_* para los 7 casos del encargo: el caso 6
    (resolve_ocio_name contra la lista tipo aces_1.2) se separo en dos
    funciones -acescg y aces2065-1- para que un fallo puntual se reporte
    solo.
    """
    tests = [
        (nombre, funcion)
        for nombre, funcion in sorted(globals().items())
        if nombre.startswith("test_") and callable(funcion)
    ]
    _expect(len(tests) == 8, "Se esperaban 8 funciones test_*, se encontraron {0}".format(len(tests)))

    for nombre, funcion in tests:
        funcion()
        print("  [OK] {0}".format(nombre))


if __name__ == "__main__":
    run()
    print("test_color_management_config: OK")
