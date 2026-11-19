"""
Las herramientas de Wasabi del panel de assignees ven las policies de desborde de PipeSync
(`{usuario}_policy_2` ...) y mandan el documento compacto (Wasabi corta en 5120 caracteres
contando los espacios). Corre contra un IAM falso: nada sale a la red.
"""

import json
import os
import sys
import types
import unittest

PANEL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "LGA_NKS_Assignee_Panel_py")


class _NoSuchEntity(Exception):
    pass


class FakeIam:
    def __init__(self, docs):
        self.docs = dict(docs)  # nombre -> documento
        self.sent = []          # (nombre, texto mandado)

    def _name(self, arn):
        return arn.rsplit("/", 1)[1]

    def get_policy(self, PolicyArn):
        if self._name(PolicyArn) not in self.docs:
            raise _NoSuchEntity("NoSuchEntity: no existe")
        return {"Policy": {"DefaultVersionId": "v1"}}

    def get_policy_version(self, PolicyArn, VersionId):
        return {"PolicyVersion": {"Document": self.docs[self._name(PolicyArn)]}}

    def list_policy_versions(self, PolicyArn):
        return {"Versions": [{"VersionId": "v1", "IsDefaultVersion": True}]}

    def create_policy_version(self, PolicyArn, PolicyDocument, SetAsDefault):
        self.sent.append((self._name(PolicyArn), PolicyDocument))
        self.docs[self._name(PolicyArn)] = json.loads(PolicyDocument)


def build(shots):
    prefixes = [""]
    resources = []
    for seq, shot in shots:
        prefixes += [f"{seq}/", f"{seq}/{shot}/*"]
        resources += [f"arn:aws:s3:::vfx-erso/{seq}/{shot}", f"arn:aws:s3:::vfx-erso/{seq}/{shot}/*"]
    return {"Version": "2012-10-17", "Statement": [
        {"Effect": "Allow", "Action": ["s3:ListAllMyBuckets", "s3:GetBucketLocation"], "Resource": "*"},
        {"Effect": "Allow", "Action": "s3:ListBucket", "Resource": "arn:aws:s3:::vfx-erso",
         "Condition": {"StringLike": {"s3:prefix": sorted(set(prefixes))}}},
        {"Effect": "Allow", "Action": "s3:*", "Resource": resources},
    ]}


class WasabiOverflowTest(unittest.TestCase):
    def setUp(self):
        self.iam = FakeIam({
            "ana_policy": build([("101", "ERSO_1005_0100_WAN"), ("101", "ERSO_1005_0200_WAN")]),
            "ana_policy_2": build([("102", "ERSO_2017_0200_WAN")]),
        })
        fake_boto3 = types.ModuleType("boto3")
        iam = self.iam
        fake_boto3.Session = lambda: types.SimpleNamespace(client=lambda *a, **k: iam)
        fake_reader = types.ModuleType("SecureConfig_Reader")
        fake_reader.get_s3_credentials = lambda: ("ak", "sk", "", "us-east-1")
        self._saved = {k: sys.modules.get(k) for k in ("boto3", "SecureConfig_Reader", "wasabi_policy_utils")}
        sys.modules["boto3"] = fake_boto3
        sys.modules["SecureConfig_Reader"] = fake_reader
        sys.modules.pop("wasabi_policy_utils", None)
        sys.path.insert(0, PANEL)
        import wasabi_policy_utils  # noqa: E402
        self.utils = wasabi_policy_utils

    def tearDown(self):
        sys.path.remove(PANEL)
        for name, module in self._saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    def test_lee_la_principal_y_la_de_desborde(self):
        self.assertEqual(
            self.utils.read_user_policy_shots("ana"),
            ["ERSO_1005_0100_WAN", "ERSO_1005_0200_WAN", "ERSO_2017_0200_WAN"],
        )

    def test_saca_un_shot_de_la_de_desborde_y_manda_compacto(self):
        self.assertTrue(self.utils.remove_shot_from_policy("ana", "ERSO_2017_0200_WAN"))
        self.assertEqual([name for name, _ in self.iam.sent], ["ana_policy_2"])
        text = self.iam.sent[0][1]
        self.assertNotIn(", ", text)
        self.assertNotIn('": ', text)
        self.assertEqual(
            self.utils.read_user_policy_shots("ana"),
            ["ERSO_1005_0100_WAN", "ERSO_1005_0200_WAN"],
        )

    def test_shot_que_no_esta_en_ninguna(self):
        self.assertFalse(self.utils.remove_shot_from_policy("ana", "ERSO_9999_0000_WAN"))
        self.assertEqual(self.iam.sent, [])


if __name__ == "__main__":
    unittest.main()
