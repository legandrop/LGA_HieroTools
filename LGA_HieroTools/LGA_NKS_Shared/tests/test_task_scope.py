# -*- coding: utf-8 -*-
"""
Tests de LGA_NKS_TaskScope.

Lo importante de este archivo no son las funciones sueltas: es el chequeo de
consistencia contra LGA_NKS_GetClip.py. TaskScope no puede importar GetClip
(ese modulo importa hiero y solo levanta dentro de NKS), asi que la unica
forma de comparar las dos tablas es leer GetClip.py como TEXTO.

Que cubre el chequeo: sumar o sacar una task en un solo lado, renombrar el
valor de un track en un solo lado, y desacoplar CG_TASK_NAME de su
derivacion. Lo que NO cubre: cualquier cosa que GetClip resuelva en runtime
en vez de declarar como literal, porque aca se lee el fuente y no se ejecuta.

Corre sin Hiero, sin PipeSync y sin red.
"""

import os
import re
import sys


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED_DIR = os.path.dirname(CURRENT_DIR)
if SHARED_DIR not in sys.path:
    sys.path.insert(0, SHARED_DIR)

import LGA_NKS_TaskScope as scope  # noqa: E402


GETCLIP_PATH = os.path.join(SHARED_DIR, "LGA_NKS_GetClip.py")


class TestFailure(AssertionError):
    pass


def _expect(condition, message):
    if not condition:
        raise TestFailure(message)


def _read_getclip_source():
    with open(GETCLIP_PATH, "r", encoding="utf-8") as handle:
        return handle.read()


def _getclip_track_constants(source, suffix):
    """Devuelve {task: valor} de las constantes TRACK_<task>_<suffix>."""
    pattern = re.compile(
        r"^TRACK_(?P<task>\w+)_%s\s*=\s*[\"'](?P<value>[^\"']+)[\"']" % suffix,
        re.MULTILINE,
    )
    return {m.group("task").lower(): m.group("value") for m in pattern.finditer(source)}


def _getclip_list_members(source, list_name):
    """Devuelve los nombres de constante que forman una lista de GetClip."""
    match = re.search(
        r"^%s\s*=\s*\[(?P<body>[^\]]*)\]" % re.escape(list_name),
        source,
        re.MULTILINE,
    )
    _expect(match is not None, "No se encontro la lista %s en GetClip.py" % list_name)
    return [item.strip() for item in match.group("body").split(",") if item.strip()]


def check_consistencia_con_getclip():
    """Las tasks de TaskScope y los tracks de GetClip tienen que coincidir."""
    source = _read_getclip_source()

    exr_members = _getclip_list_members(source, "TASK_EXR_TRACKS")
    rev_members = _getclip_list_members(source, "TASK_REV_TRACKS")
    exr_constants = _getclip_track_constants(source, "EXR")
    rev_constants = _getclip_track_constants(source, "REV")

    # Las tasks que GetClip declara como registradas, en el orden de la lista.
    getclip_tasks = []
    for member in exr_members:
        match = re.match(r"^TRACK_(\w+)_EXR$", member)
        _expect(
            match is not None,
            "Miembro inesperado en TASK_EXR_TRACKS de GetClip.py: %s" % member,
        )
        getclip_tasks.append(match.group(1).lower())

    _expect(
        tuple(getclip_tasks) == scope.all_track_task_names(),
        "TaskScope.TRACK_TASKS %s no coincide con TASK_EXR_TRACKS de GetClip.py %s"
        % (scope.all_track_task_names(), tuple(getclip_tasks)),
    )

    _expect(
        len(rev_members) == len(exr_members),
        "TASK_REV_TRACKS y TASK_EXR_TRACKS de GetClip.py tienen distinta longitud",
    )

    # CG_TASK_NAME aparte: GetClip lo DERIVA de TRACK_cg_EXR y TaskScope lo
    # tiene hardcodeado, asi que comparar solo los tracks deja pasar el caso
    # de que alguien desacople esa derivacion y escriba el nombre a mano.
    cg_declarado = re.search(
        r"^CG_TASK_NAME\s*=\s*(?P<expr>.+)$", source, re.MULTILINE
    )
    _expect(
        cg_declarado is not None, "No se encontro CG_TASK_NAME en GetClip.py"
    )
    expr = cg_declarado.group("expr").split("#")[0].strip()
    literal = re.match(r"^[\"'](?P<valor>[^\"']*)[\"']$", expr)
    if literal is not None:
        # Lo escribieron a mano: vale el literal tal cual.
        cg_en_getclip = literal.group("valor").lower()
    else:
        _expect(
            expr == 'TRACK_cg_EXR.strip("_").lower()',
            "CG_TASK_NAME de GetClip.py ya no se deriva de TRACK_cg_EXR ni es "
            "un literal reconocible: %r. Revisar a mano contra TaskScope." % expr,
        )
        cg_en_getclip = exr_constants.get("cg", "").strip("_").lower()
    _expect(
        cg_en_getclip == scope.CG_TASK_NAME,
        "CG_TASK_NAME: GetClip resuelve %r y TaskScope declara %r"
        % (cg_en_getclip, scope.CG_TASK_NAME),
    )

    # Y los VALORES de los tracks tienen que ser los que TaskScope deriva.
    for task in scope.all_track_task_names():
        _expect(
            exr_constants.get(task) == scope.exr_track_for_task(task),
            "Track EXR de '%s': GetClip dice %r y TaskScope deriva %r"
            % (task, exr_constants.get(task), scope.exr_track_for_task(task)),
        )
        _expect(
            rev_constants.get(task) == scope.rev_track_for_task(task),
            "Track REV de '%s': GetClip dice %r y TaskScope deriva %r"
            % (task, rev_constants.get(task), scope.rev_track_for_task(task)),
        )


def check_scope_por_contexto():
    _expect(
        scope.active_track_tasks("studio") == ("comp", "roto", "cleanup"),
        "En studio las tasks con track son comp, roto y cleanup: %r"
        % (scope.active_track_tasks("studio"),),
    )
    _expect(
        scope.active_track_tasks("client") == ("comp", "cg"),
        "En client las tasks con track son comp y cg: %r"
        % (scope.active_track_tasks("client"),),
    )
    _expect(
        not scope.is_track_task_active("cg", "studio"),
        "CG no existe en studio",
    )
    _expect(
        scope.is_track_task_active("CG", "client"),
        "CG existe en client y el lookup es case-insensitive",
    )
    _expect(
        not scope.is_track_task_active("roto", "client"),
        "Roto no existe en client",
    )
    _expect(
        scope.is_track_task_active("comp", "client")
        and scope.is_track_task_active("comp", "studio"),
        "Comp existe en los dos contextos",
    )


def check_orden_del_stack():
    """El orden importa: decide donde se inserta un track nuevo en el timeline."""
    _expect(
        scope.active_track_tasks("client").index("comp")
        < scope.active_track_tasks("client").index("cg"),
        "En client el track _comp_ va arriba del _cg_",
    )
    _expect(
        scope.all_track_task_names()[0] == "comp",
        "Comp encabeza el stack de tracks de task",
    )


def check_resolucion_de_nombres():
    _expect(scope.task_folder_name("cg") == "CG", "La carpeta de cg es CG")
    _expect(scope.task_folder_name("comp") == "Comp", "La carpeta de comp es Comp")
    _expect(
        scope.task_folder_name("CG") == "CG",
        "task_folder_name es case-insensitive",
    )
    _expect(
        scope.task_folder_name("desconocida") == "Desconocida",
        "Una task no registrada cae al nombre capitalizado",
    )
    _expect(
        scope.task_folder_name("desconocida", default=None) is None,
        "Con default explicito, una task no registrada devuelve ese default",
    )
    _expect(scope.exr_track_for_task("cg") == "_cg_", "El track EXR de cg es _cg_")
    _expect(
        scope.rev_track_for_task("cg") == "_cgRev_", "El track REV de cg es _cgRev_"
    )
    _expect(
        scope.exr_track_for_task("dmp") is None,
        "DMP no tiene track registrado y no se le inventa uno",
    )
    _expect(scope.task_for_track("_cg_") == "cg", "El track _cg_ pertenece a cg")
    _expect(
        scope.task_for_track("_cgRev_") is None,
        "task_for_track resuelve tracks EXR, no los de review",
    )
    _expect(
        scope.task_for_track("EditRef") is None,
        "Un track editorial no pertenece a ninguna task",
    )


def check_entradas_basura():
    """Los callers traen valores de filenames, de la DB y de widgets de Qt.

    Un no-string reventaba con AttributeError en el .strip(), y un string de
    solo espacios devolvia "" en silencio. Ninguna de las dos cosas puede
    volver.
    """
    _expect(
        scope.task_folder_name(123) == "123",
        "Un no-string no puede reventar: %r" % (scope.task_folder_name(123),),
    )
    _expect(
        scope.exr_track_for_task(123) is None,
        "Un no-string que no es task devuelve None, no explota",
    )
    _expect(
        scope.task_folder_name("   ") is None,
        "Un string de solo espacios no es una task y no degenera en ''",
    )
    _expect(
        scope.is_track_task_active(None) is False,
        "None nunca es una task activa",
    )
    _expect(
        scope.task_for_track("  _CG_  ") == "cg",
        "El lookup de track tolera espacios y mayusculas",
    )
    _expect(
        scope.task_folder_name(" Cg ") == "CG",
        "El lookup de carpeta tolera espacios y mayusculas",
    )
    _expect(
        scope.rev_track_for_task("") is None,
        "El string vacio no resuelve ningun track de review",
    )


def check_resolve_mode():
    _expect(scope.resolve_mode("client") == "client", "resolve_mode respeta el override")
    _expect(scope.resolve_mode("CLIENT") == "client", "resolve_mode normaliza el caso")
    _expect(
        scope.resolve_mode("cualquiera") == "studio",
        "Un modo desconocido cae a studio",
    )


def check_familia_cg_sin_hiero():
    """La familia CG tiene que aplicarse FUERA de NKS, no solo adentro.

    Hasta v1.16 de NamingUtils esta regla importaba LGA_NKS_GetClip, que
    importa hiero: fuera de NKS el import fallaba, el `except Exception` se
    lo tragaba y normalize_task_name() devolvia el stream sin mapear, en
    silencio. Este test es la evidencia de que ya no pasa: si alguien vuelve
    a colgar la regla de un modulo que necesita hiero, falla aca.
    """
    import tempfile
    from LGA_NKS_Flow_NamingUtils import normalize_task_name

    ini_var = "LGA_HIEROTOOLS_CONTEXT_INI"
    previo = os.environ.get(ini_var)
    with tempfile.TemporaryDirectory() as tmp:
        for modo, esperado_layout, etiqueta in (
            ("client", "cg", "client mapea el stream a la task CG"),
            ("studio", "layout", "studio deja el nombre intacto"),
        ):
            ini_path = os.path.join(tmp, "contexto_%s.ini" % modo)
            with open(ini_path, "w", newline="\n", encoding="utf-8") as handle:
                handle.write("[Context]\nmode = %s\n" % modo)
            os.environ[ini_var] = ini_path
            try:
                _expect(
                    normalize_task_name("layout") == esperado_layout,
                    "%s: normalize_task_name('layout') dio %r"
                    % (etiqueta, normalize_task_name("layout")),
                )
                # Una task registrada nunca se remapea, en ningun contexto.
                _expect(
                    normalize_task_name("comp") == "comp",
                    "%s: comp es un track registrado y no se remapea" % etiqueta,
                )
                # Y el alias explicito sigue resolviendo antes que la familia.
                _expect(
                    normalize_task_name("compo") == "comp",
                    "%s: el alias compo->comp manda sobre la familia CG" % etiqueta,
                )
            finally:
                if previo is None:
                    os.environ.pop(ini_var, None)
                else:
                    os.environ[ini_var] = previo


def check_catalogo_de_creacion_por_contexto():
    """Create Shot ofrece solo tasks que existan en el sitio de Flow del contexto."""
    import LGA_NKS_Flow_Task_Config as task_config

    studio = task_config.get_available_task_names("studio")
    client = task_config.get_available_task_names("client")

    _expect(client == ["Comp", "CG"], "En client se ofrecen Comp y CG: %r" % (client,))
    _expect("CG" not in studio, "CG no se ofrece en studio")
    for ausente in ("Roto", "Cleanup", "DMP", "Lighting", "FX"):
        _expect(
            ausente not in client,
            "%s no existe en client y no se puede ofrecer" % ausente,
        )
        _expect(ausente in studio, "%s se sigue ofreciendo en studio" % ausente)

    _expect(
        len(studio) == len(task_config.AVAILABLE_TASKS) - 1,
        "En studio se ofrecen todas las tasks menos CG",
    )
    # El color de CG tiene que sobrevivir a haber salido de _TASK_COLOR_MAP.
    _expect(
        task_config.get_task_color("cg") == "#CA7A3B",
        "CG es naranja de la familia 3D: %r" % task_config.get_task_color("cg"),
    )
    # Y las tasks del catalogo tienen que cubrir las que tienen track propio.
    for task in scope.active_track_tasks("client"):
        _expect(
            task in [n.lower() for n in client],
            "La task con track '%s' tiene que estar en el catalogo de client" % task,
        )


def run():
    check_consistencia_con_getclip()
    check_scope_por_contexto()
    check_orden_del_stack()
    check_resolucion_de_nombres()
    check_entradas_basura()
    check_resolve_mode()
    check_catalogo_de_creacion_por_contexto()
    check_familia_cg_sin_hiero()


if __name__ == "__main__":
    run()
    print("test_task_scope: OK")
