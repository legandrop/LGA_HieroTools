"""
Download AMF (LGA_NKS_FileManagerS3_DownloadAmf): de que shots baja Look_Files.

Lo que tiene que seguir siendo cierto:
  - con DOS o mas clips seleccionados se baja la Look_Files de todos esos
    shots en UNA sola llamada al CLI (`--download <ruta 1> <ruta 2> ...`);
  - varios clips del mismo shot mandan la carpeta una sola vez;
  - con UNO o ninguno seleccionado manda el clip del playhead (Hiero
    autoselecciona el clip bajo el playhead, asi que uno solo no es una
    eleccion del usuario).

El modulo importa `hiero` y los helpers de LGA_NKS_Shared: se carga con stubs
calificados por paquete, sin abrir el host.
"""

import importlib.util
import sys
import types
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "LGA_NKS_Flow_S3_Panel_py"
    / "LGA_NKS_FileManagerS3_DownloadAmf.py"
)

MEDIA = "T:/VFX-PROJA/101/%s/_input/%s_aPlate_v001/%s_aPlate_v001.1001.exr"


class FakeClip:
    def __init__(self, shot, media=None):
        self._shot = shot
        self._media = media if media is not None else MEDIA % (shot, shot, shot)

    def name(self):
        return self._shot

    def source(self):
        return self

    def mediaSource(self):
        return self

    def fileinfos(self):
        return [self] if self._media else []

    def filename(self):
        return self._media


def load_module(estado):
    """Carga el modulo con stubs y deja sys.modules como estaba.

    `estado` trae lo que devuelven los helpers de seleccion: 'seleccionados' y
    'playhead'. Se anota en 'llamadas_playhead' cada consulta al playhead.
    """
    shared = types.ModuleType("LGA_NKS_Shared")
    get_clip = types.ModuleType("LGA_NKS_Shared.LGA_NKS_GetClip")
    launcher = types.ModuleType("LGA_NKS_Shared.LGA_NKS_FileManagerS3Launcher")

    def get_clip_to_process(track_name=None, prioritize_multiple_selection=False):
        estado["llamadas_playhead"] = estado.get("llamadas_playhead", 0) + 1
        return estado.get("playhead")

    get_clip.get_clip_to_process = get_clip_to_process
    get_clip.get_selected_clips = lambda: list(estado.get("seleccionados", []))
    launcher.resolve_context_mode = lambda: "studio"
    launcher.build_filemanagers3_command = (
        lambda cli_args, **kwargs: ["FileManagerS3.exe", "--context", "studio"] + list(cli_args)
    )
    shared.LGA_NKS_GetClip = get_clip

    stubs = {
        "LGA_NKS_Shared": shared,
        "LGA_NKS_Shared.LGA_NKS_GetClip": get_clip,
        "LGA_NKS_Shared.LGA_NKS_FileManagerS3Launcher": launcher,
    }
    guardados = {n: sys.modules.get(n) for n in stubs}
    path_previo = list(sys.path)
    sys.modules.update(stubs)
    try:
        spec = importlib.util.spec_from_file_location("download_amf_under_test", str(SCRIPT_PATH))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = path_previo
        for nombre, previo in guardados.items():
            if previo is None:
                sys.modules.pop(nombre, None)
            else:
                sys.modules[nombre] = previo
    # El test no escribe en el .log real de la tool.
    module.DEBUG = False
    return module


class DownloadAmfBulkTest(unittest.TestCase):
    def correr(self, estado):
        module = load_module(estado)
        lanzados = []
        module.subprocess = types.SimpleNamespace(
            Popen=lambda cmd, shell=False: lanzados.append(cmd)
        )
        module.main()
        return lanzados

    def test_varios_clips_bajan_todos_los_shots_en_una_sola_llamada(self):
        estado = {
            "seleccionados": [
                FakeClip("PROJA_101_0010"),
                FakeClip("PROJA_101_0020"),
                FakeClip("PROJA_101_0030"),
            ],
            "playhead": FakeClip("PROJA_101_0099"),
        }
        lanzados = self.correr(estado)
        self.assertEqual(len(lanzados), 1)
        self.assertEqual(
            lanzados[0],
            [
                "FileManagerS3.exe", "--context", "studio", "--download",
                "T:/VFX-PROJA/101/PROJA_101_0010/_input/Look_Files",
                "T:/VFX-PROJA/101/PROJA_101_0020/_input/Look_Files",
                "T:/VFX-PROJA/101/PROJA_101_0030/_input/Look_Files",
            ],
        )
        self.assertEqual(estado.get("llamadas_playhead", 0), 0)

    def test_clips_del_mismo_shot_mandan_la_carpeta_una_vez(self):
        comp = (
            "T:/VFX-PROJA/101/PROJA_101_0010/comp/4_publish/"
            "PROJA_101_0010_comp_v003/PROJA_101_0010_comp_v003.1001.exr"
        )
        estado = {
            "seleccionados": [
                FakeClip("PROJA_101_0010"),
                FakeClip("PROJA_101_0010", media=comp),
                FakeClip("PROJA_101_0020"),
                FakeClip("sin_media", media=""),
            ],
        }
        lanzados = self.correr(estado)
        self.assertEqual(
            lanzados[0][4:],
            [
                "T:/VFX-PROJA/101/PROJA_101_0010/_input/Look_Files",
                "T:/VFX-PROJA/101/PROJA_101_0020/_input/Look_Files",
            ],
        )

    def test_un_solo_clip_seleccionado_manda_el_playhead(self):
        estado = {
            "seleccionados": [FakeClip("PROJA_101_0010")],
            "playhead": FakeClip("PROJA_101_0050"),
        }
        lanzados = self.correr(estado)
        self.assertEqual(
            lanzados[0][3:],
            ["--download", "T:/VFX-PROJA/101/PROJA_101_0050/_input/Look_Files"],
        )
        self.assertEqual(estado["llamadas_playhead"], 1)

    def test_sin_clips_no_lanza_nada(self):
        self.assertEqual(self.correr({"seleccionados": [], "playhead": None}), [])


if __name__ == "__main__":
    unittest.main()
