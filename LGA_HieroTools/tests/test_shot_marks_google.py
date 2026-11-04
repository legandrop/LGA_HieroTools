"""Pruebas de la descarga de Shot Marks desde Google Sheets, sin red."""

import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import urllib.error

SCRIPT = (Path(__file__).resolve().parents[1] / "LGA_NKS_Review_Panel_py"
          / "LGA_NKS_ShotMarks_Google.py")
spec = importlib.util.spec_from_file_location("shotmarks_google", SCRIPT)
google = importlib.util.module_from_spec(spec)
spec.loader.exec_module(google)

FILE_ID = "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789_-xyz"
LINK = "https://docs.google.com/spreadsheets/d/%s/edit?usp=sharing" % FILE_ID


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class LinkTests(unittest.TestCase):
    def test_sheet_id(self):
        self.assertEqual(google.sheet_id(LINK), FILE_ID)
        self.assertEqual(google.sheet_id("https://docs.google.com/spreadsheets/d/%s" % FILE_ID),
                         FILE_ID)
        self.assertEqual(google.sheet_id(
            "https://docs.google.com/spreadsheets/d/%s/edit#gid=12" % FILE_ID), FILE_ID)

    def test_not_a_link(self):
        for text in ("", r"T:\VFX-PROJA\PROJA_breakdown.xlsx",
                     "https://docs.google.com/document/d/%s/edit" % FILE_ID):
            self.assertIsNone(google.sheet_id(text))
            self.assertFalse(google.is_link(text))

    def test_safe_name(self):
        self.assertEqual(google.safe_name('PROJA - VFX BKD: v02 / "final"'),
                         "PROJA - VFX BKD_ v02 _ _final_")
        self.assertEqual(google.safe_name(" . "), "Google Sheet")


class FetchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.modified = "2026-11-04T00:02:41.414Z"
        self.downloads = 0
        self.connect = True
        self._saved = (google.access_token, google._get, google._download)

        def token(_log, _open_url=None):
            if not self.connect:
                raise google.GoogleSheetError("Could not connect to oauth2.googleapis.com.")
            return "tok"

        def get(url, _token, _log, timeout=120):
            meta = {"id": FILE_ID, "name": "PROJA - VFX BKD", "mimeType": google.SHEET_MIME,
                    "modifiedTime": self.modified,
                    "exportLinks": {google.XLSX_MIME: "https://docs.google.com/export"}}
            return _Response(json.dumps(meta).encode("utf-8"))

        def download(_url, _token, dest, _log):
            self.downloads += 1
            dest.write_bytes(b"PK fake xlsx")
            return 12

        google.access_token, google._get, google._download = token, get, download

    def tearDown(self):
        google.access_token, google._get, google._download = self._saved
        self.temp.cleanup()

    def test_downloads_once_while_unchanged(self):
        first = google.fetch(LINK, folder=self.folder)
        self.assertTrue(first["downloaded"])
        self.assertEqual(first["title"], "PROJA - VFX BKD")
        self.assertEqual(Path(first["path"]), self.folder / (FILE_ID + ".xlsx"))
        second = google.fetch(LINK, folder=self.folder)
        self.assertFalse(second["downloaded"])
        self.assertEqual(self.downloads, 1)

    def test_downloads_again_when_changed(self):
        google.fetch(LINK, folder=self.folder)
        self.modified = "2026-11-05T10:00:00.000Z"
        again = google.fetch(LINK, folder=self.folder)
        self.assertTrue(again["downloaded"])
        self.assertEqual(self.downloads, 2)

    def test_offline_uses_the_previous_copy(self):
        google.fetch(LINK, folder=self.folder)
        self.connect = False
        result = google.fetch(LINK, folder=self.folder)
        self.assertTrue(result["stale"])
        self.assertFalse(result["downloaded"])
        self.assertEqual(result["modified"], self.modified)

    def test_offline_without_copy_fails(self):
        self.connect = False
        with self.assertRaises(google.GoogleSheetError):
            google.fetch(LINK, folder=self.folder)

    def test_not_a_link_fails(self):
        with self.assertRaises(google.GoogleSheetError):
            google.fetch(r"T:\VFX-PROJA\PROJA_breakdown.xlsx", folder=self.folder)


class RetryTests(unittest.TestCase):
    def setUp(self):
        self._saved = (google.urllib.request.urlopen, google.RETRY_WAIT)
        google.RETRY_WAIT = 0

    def tearDown(self):
        google.urllib.request.urlopen, google.RETRY_WAIT = self._saved

    def _request(self):
        return google.urllib.request.Request("https://doc-04-34-sheets.googleusercontent.com/x")

    def test_retries_a_blocked_connection(self):
        calls = []

        def urlopen(_request, timeout=None):
            calls.append(1)
            if len(calls) < 3:
                raise urllib.error.URLError(OSError(10051, "unreachable network"))
            return _Response(b"ok")

        google.urllib.request.urlopen = urlopen
        self.assertEqual(google._open(self._request(), lambda _m: None).read(), b"ok")
        self.assertEqual(len(calls), 3)

    def test_gives_up_with_a_clear_error(self):
        def urlopen(_request, timeout=None):
            raise urllib.error.URLError(OSError(10013, "forbidden"))

        google.urllib.request.urlopen = urlopen
        with self.assertRaises(google.GoogleSheetError) as caught:
            google._open(self._request(), lambda _m: None)
        self.assertIn("doc-04-34-sheets.googleusercontent.com", str(caught.exception))

    def test_http_errors_are_not_retried(self):
        calls = []

        def urlopen(request, timeout=None):
            calls.append(1)
            raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", {}, io.BytesIO(b"{}"))

        google.urllib.request.urlopen = urlopen
        with self.assertRaises(urllib.error.HTTPError):
            google._open(self._request(), lambda _m: None)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
