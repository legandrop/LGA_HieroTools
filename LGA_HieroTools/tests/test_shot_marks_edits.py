"""Pruebas de los cambios locales de Shot Marks (sin host)."""

import csv
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

FOLDER = Path(__file__).resolve().parents[1] / "LGA_NKS_Review_Panel_py"
spec = importlib.util.spec_from_file_location("LGA_NKS_ShotMarks_Edits",
                                              FOLDER / "LGA_NKS_ShotMarks_Edits.py")
edits = importlib.util.module_from_spec(spec)
spec.loader.exec_module(edits)

WHEN = "2026-11-04 10:00"


class EditsTest(unittest.TestCase):

    def test_path_sin_version(self):
        path = edits.edits_path("T:/VFX-PROJA/PROJA_SUP/PROJA_Spotting_v10.hrox", "PROJA_Spotting_v10", "C:/tmp")
        self.assertEqual(os.path.basename(path), "PROJA_Spotting_ShotMarks_Edits.json")
        self.assertTrue(path.startswith("T:/VFX-PROJA/PROJA_SUP"))
        self.assertTrue(edits.edits_path("", "PROJA_Spotting_v10", "C:/tmp").startswith("C:/tmp"))

    def test_un_cambio_por_campo_conserva_el_valor_original(self):
        data = edits.empty()
        edits.set_value(data, "PROJA_010_0100", 4, "difficulty", "hard", "mid", author="a", when=WHEN)
        edit = edits.set_value(data, "PROJA_010_0100", 4, "difficulty", "mid", "Easy", author="a", when=WHEN)
        self.assertEqual(len(edits.pending(data)), 1)
        self.assertEqual(edit["before"], "hard")
        self.assertEqual(edit["after"], "Easy")

    def test_volver_al_valor_de_la_planilla_borra_el_cambio(self):
        data = edits.empty()
        edits.set_value(data, "PROJA_010_0100", 4, "notes", "Keep the rig.", "Remove the rig.", author="a")
        self.assertIsNone(edits.set_value(data, "PROJA_010_0100", 4, "notes", "x", " Keep the rig. ",
                                          author="a"))
        self.assertEqual(edits.pending(data), [])
        # Dificultad: sin importar mayusculas.
        self.assertIsNone(edits.set_value(data, "S", 1, "difficulty", "mid", "Mid", author="a"))

    def test_preguntas_se_suman(self):
        data = edits.empty()
        edits.add_question(data, "S", 1, "Is the rig in the final cut?", author="a")
        edits.add_question(data, "S", 1, "Who shot reel B?", author="a")
        self.assertIsNone(edits.add_question(data, "S", 1, "   ", author="a"))
        self.assertEqual(len(edits.pending(data, "S")), 2)
        edit_id = edits.pending(data, "S")[0]["id"]
        edits.remove(data, edit_id)
        self.assertEqual(len(edits.pending(data, "S")), 1)

    def test_overlay(self):
        data = edits.empty()
        edits.set_value(data, "S", 1, "notes2", "", "Ask editorial", author="a")
        edits.set_value(data, "S", 1, "difficulty", "hard", "Very hard", author="a")
        edits.add_question(data, "S", 1, "Is it in the cut?", author="a")
        info = edits.overlay({"shot": "S", "notes2": "", "difficulty": "hard"}, data)
        self.assertEqual(info["notes2"], "Ask editorial")
        self.assertEqual(info["difficulty"], "Very hard")
        self.assertEqual(info["edited"], {"notes2": "", "difficulty": "hard"})
        self.assertEqual(info["conflict"], {})
        self.assertEqual(len(info["questions"]), 1)
        # La planilla cambio despues del cambio local: conflicto.
        info = edits.overlay({"shot": "S", "notes2": "", "difficulty": "Easy"}, data)
        self.assertEqual(info["conflict"], {"difficulty": "hard"})
        # La planilla ya tiene el valor nuevo: no se muestra como cambio.
        info = edits.overlay({"shot": "S", "notes2": "Ask editorial", "difficulty": "very hard"}, data)
        self.assertEqual(info["edited"], {})
        self.assertEqual(len(info["applied"]), 2)
        self.assertEqual(edits.mark_applied(data, info["applied"]), 2)
        # Quedan como historial; pendiente solo la pregunta.
        self.assertEqual(len(data["edits"]), 3)
        self.assertEqual([e["field"] for e in edits.pending(data)], ["question"])
        # Otro shot no se toca.
        self.assertEqual(edits.overlay({"shot": "T", "notes2": ""}, data)["edited"], {})

    def test_guardar_cargar_y_exportar(self):
        data = edits.empty()
        edits.set_value(data, "PROJA_010_0100", 4, "notes", "Viejo", "Nuevo, con acentos: canción",
                        timeline="PROJA_Cut", source="PROJA Breakdown | Shots", author="a", when=WHEN)
        edits.add_question(data, "PROJA_010_0100", 4, "Is it in?", author="a", when=WHEN)
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "sub", "PROJA_ShotMarks_Edits.json")
            edits.save(path, data)
            self.assertEqual(edits.load(path), data)
            out = os.path.join(folder, "cambios.csv")
            count = edits.export_csv(out, edits.load(path),
                                     sheet_now=lambda shot, field: "Viejo")
            self.assertEqual(count, 2)
            with open(out, encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.reader(handle))
        self.assertEqual(rows[0][0], "Shot")
        notes = [r for r in rows if r[2] == "Notes"][0]
        self.assertEqual(notes[3:6], ["Viejo", "Nuevo, con acentos: canción", "Viejo"])
        question = [r for r in rows if r[2] == "Question"][0]
        self.assertEqual(question[4:6], ["Is it in?", ""])

    def test_archivo_roto_no_se_pisa(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "x.json")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("[1, 2]")
            with self.assertRaises(ValueError):
                edits.load(path)


if __name__ == "__main__":
    unittest.main()
