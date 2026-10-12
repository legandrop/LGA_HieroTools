"""Pruebas de conservacion de bytes y proteccion contra perdida de archivos."""

import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'LGA_NKS_Project_Downgrade.py'
spec = importlib.util.spec_from_file_location('project_downgrade', SCRIPT)
converter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(converter)

DOCUMENT = b'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE hieroXML>
<hieroXML name="NukeStudio" release="17.0v4" revision="123" version="12">
 <Project name="PROJA"><items/><data><![CDATA[<Annotation>preset</Annotation>]]></data></Project>
</hieroXML>
'''


class DowngradeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / 'PROJA.hrox'
        self.source.write_bytes(DOCUMENT)

    def tearDown(self):
        self.temp.cleanup()

    def test_changes_only_format_version_and_keeps_original(self):
        output = converter.convert_project(self.source)
        self.assertEqual(output.name, 'PROJA_NKS16.hrox')
        self.assertEqual(self.source.read_bytes(), DOCUMENT)
        self.assertEqual(output.read_bytes(), DOCUMENT.replace(b'version="12"', b'version="11"'))
        with self.assertRaises(FileExistsError):
            converter.convert_project(self.source)

    def test_refuses_source_and_existing_destination(self):
        with self.assertRaises(FileExistsError):
            converter.convert_project(self.source, self.source)
        other = self.root / 'existing.hrox'
        other.write_bytes(b'valuable data')
        with self.assertRaises(FileExistsError):
            converter.convert_project(self.source, other)
        self.assertEqual(other.read_bytes(), b'valuable data')

    def test_refuses_invalid_or_unknown_project_before_writing(self):
        for data in (b'<broken>', DOCUMENT.replace(b'version="12"', b'version="13"'),
                     DOCUMENT.replace(b'version="12"', b'version="11"'),
                     DOCUMENT.replace(b'release="17.0v4"', b'release="18.0v1"'),
                     DOCUMENT.replace(b'Project', b'NotAProject'),
                     DOCUMENT.replace(b'<!DOCTYPE hieroXML>',
                                      b'<!DOCTYPE hieroXML [<!ENTITY x "abc">]>')):
            self.source.write_bytes(data)
            with self.assertRaises(Exception):
                converter.convert_project(self.source)
            self.assertFalse((self.root / 'PROJA_NKS16.hrox').exists())

    def test_annotations_require_explicit_loss_and_preserve_cdata(self):
        annotation = b'<annotations><Annotation start="0"><AnnotationComment><Text>Note</Text></AnnotationComment></Annotation><Annotation start="1"/></annotations>'
        data = DOCUMENT.replace(b'<items/>', annotation + b'<items/>')
        self.source.write_bytes(data)
        with self.assertRaisesRegex(ValueError, '2 annotations'):
            converter.convert_project(self.source)
        output = converter.convert_project(self.source, drop_annotations=True)
        expected = DOCUMENT.replace(b'<items/>', b'<annotations></annotations><items/>')
        self.assertEqual(output.read_bytes(), expected.replace(b'version="12"', b'version="11"'))
        self.assertEqual(self.source.read_bytes(), data)

    def test_accepts_hiero_16_1_and_empty_annotation_container(self):
        self.source.write_bytes(DOCUMENT.replace(b'17.0v4', b'16.1v2').replace(
            b'<items/>', b'<annotations/><items/>'))
        self.assertTrue(converter.convert_project(self.source).is_file())

    def test_missing_destination_directory_creates_nothing(self):
        with self.assertRaises(FileNotFoundError):
            converter.convert_project(self.source, self.root / 'missing' / 'new.hrox')
        self.assertEqual(self.source.read_bytes(), DOCUMENT)

    def test_inspection_is_read_only_and_counts_real_annotations(self):
        info = converter.inspect_project(self.source)
        self.assertEqual(info, dict(version=12, release='17.0v4', annotations=0))
        self.assertEqual(self.source.read_bytes(), DOCUMENT)
        self.assertEqual(list(self.root.iterdir()), [self.source])
        self.source.write_bytes(DOCUMENT.replace(b'<items/>', b'<annotations><Annotation/></annotations>'))
        self.assertEqual(converter.inspect_project(self.source)['annotations'], 1)

    def test_next_filename_preserves_padding_prefix_and_suffix(self):
        for before, after in (
            ('PROJA_SUP_105.hrox', 'PROJA_SUP_106.hrox'),
            ('PROJA_SUP_v009.hrox', 'PROJA_SUP_v010.hrox'),
            ('PROJA_SUP_V099_Mac.HROX', 'PROJA_SUP_V100_Mac.hrox'),
            ('PROJA_SUP_999.hrox', 'PROJA_SUP_1000.hrox'),
            ('PROJA_SUP.hrox', 'PROJA_SUP_NKS16.hrox'),
        ):
            self.assertEqual(converter.suggest_project_name(before), after)


if __name__ == '__main__':
    unittest.main()
