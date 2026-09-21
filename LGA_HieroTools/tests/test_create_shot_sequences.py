import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
sys.path.insert(0, str(ROOT))

from LGA_NKS_Shared.LGA_NKS_Flow_Sequence import (
    SequencePreflightError,
    create_missing_sequences,
    find_missing_sequences,
    unapproved_missing_sequences,
)


class FakeSG:
    def __init__(self, existing=()):
        self.existing = set(existing)
        self.writes = []
        self.next_id = 100

    @staticmethod
    def _key(filters):
        project = next(item[2] for item in filters if item[0] == "project")
        code = next(item[2] for item in filters if item[0] == "code")
        return project["id"], code

    def find(self, entity, filters, fields):
        if entity != "Sequence":
            return []
        project_id, code = self._key(filters)
        if (project_id, code) in self.existing:
            return [{"id": self.next_id, "code": code}]
        return []

    def create(self, entity, data):
        self.writes.append((entity, data))
        key = (data["project"]["id"], data["code"])
        self.existing.add(key)
        self.next_id += 1
        return {"id": self.next_id, "code": data["code"]}


class CreateShotSequenceTests(unittest.TestCase):
    @staticmethod
    def project_id(project_name):
        return {"PROJA": 1, "PROJB": 2}.get(project_name)

    def test_existing_sequence_needs_no_confirmation_or_write(self):
        sg = FakeSG(existing={(1, "010")})
        missing = find_missing_sequences(
            sg,
            [{"project_name": "PROJA"}],
            "010",
            self.project_id,
        )
        self.assertEqual([], missing)
        self.assertEqual([], sg.writes)

    def test_missing_sequence_is_reported_without_writing(self):
        sg = FakeSG()
        missing = find_missing_sequences(
            sg,
            [{"project_name": "PROJA"}],
            "000",
            self.project_id,
        )
        self.assertEqual(
            [{
                "project_id": 1,
                "project_name": "PROJA",
                "sequence_name": "000",
            }],
            missing,
        )
        self.assertEqual([], sg.writes)

    def test_duplicate_clips_request_one_sequence(self):
        sg = FakeSG()
        missing = find_missing_sequences(
            sg,
            [
                {"project_name": "PROJA"},
                {"project_name": "PROJA"},
            ],
            "000",
            self.project_id,
        )
        self.assertEqual(1, len(missing))

    def test_path_sequence_has_priority_over_dialog_fallback(self):
        sg = FakeSG()
        missing = find_missing_sequences(
            sg,
            [{
                "project_name": "PROJA",
                "file_path": "T:/VFX-PROJA/020/PROJA_020_0010/file.exr",
            }],
            "999",
            self.project_id,
        )
        self.assertEqual("020", missing[0]["sequence_name"])

    def test_confirmed_sequence_uses_minimal_flow_payload(self):
        sg = FakeSG()
        created = create_missing_sequences(
            sg,
            [{
                "project_id": 1,
                "project_name": "PROJA",
                "sequence_name": "000",
            }],
        )
        self.assertEqual([{"id": 101, "code": "000"}], created)
        self.assertEqual(
            [("Sequence", {
                "project": {"type": "Project", "id": 1},
                "code": "000",
            })],
            sg.writes,
        )

    def test_approval_is_limited_to_exact_project_and_sequence(self):
        missing = [
            {"project_id": 1, "project_name": "PROJA", "sequence_name": "000"},
            {"project_id": 2, "project_name": "PROJB", "sequence_name": "000"},
        ]
        approved = [missing[0]]
        self.assertEqual(
            [missing[1]],
            unapproved_missing_sequences(missing, approved),
        )

    def test_sequence_created_by_another_process_is_reused(self):
        class RacingSG(FakeSG):
            def create(self, entity, data):
                self.existing.add((data["project"]["id"], data["code"]))
                raise RuntimeError("duplicate")

        sg = RacingSG()
        created = create_missing_sequences(
            sg,
            [{
                "project_id": 1,
                "project_name": "PROJA",
                "sequence_name": "000",
            }],
        )
        self.assertEqual([], created)
        self.assertIn((1, "000"), sg.existing)

    def test_missing_project_or_sequence_aborts_without_writes(self):
        for clip, fallback in (
            ({"project_name": "UNKNOWN"}, "000"),
            ({"project_name": "PROJA"}, ""),
        ):
            sg = FakeSG()
            with self.assertRaises(SequencePreflightError):
                find_missing_sequences(
                    sg, [clip], fallback, self.project_id
                )
            self.assertEqual([], sg.writes)


if __name__ == "__main__":
    unittest.main()
