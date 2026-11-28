"""Download validation, tested against a real local web server (no internet needed)."""
import http.server
import io
import os
import tempfile
import threading
import unittest
import zipfile
from unittest import mock

import _path  # noqa: F401
from nowri import config as C, sources

try:
    import requests  # noqa: F401
    HAVE_REQUESTS = True
except Exception:  # pragma: no cover
    HAVE_REQUESTS = False

HTML = b"<!DOCTYPE html><html><body>Just a moment... verifying you are human</body></html>"


def zip_bytes(names):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n in names:
            z.writestr(n, b"x" * 50)
    return buf.getvalue()


AF_ZIP = zip_bytes([f"RiverATLAS_v10_shp/RiverATLAS_v10_af.{e}" for e in ("shp", "shx", "dbf", "prj", "cpg")]
                   + ["RiverATLAS_v10_shp/RiverATLAS_v10_eu.shp"])


class Handler(http.server.BaseHTTPRequestHandler):
    routes = {}

    def do_GET(self):
        status, ctype, body = self.routes.get(self.path, (404, "text/plain", b"nope"))
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@unittest.skipUnless(HAVE_REQUESTS, "requests not installed")
class TestDownloads(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        Handler.routes = {
            "/html": (200, "text/html", HTML),
            "/challenge": (202, "text/html", HTML),
            "/good": (200, "application/zip", AF_ZIP),
        }

    def test_html_instead_of_zip_is_rejected_and_nothing_is_left_behind(self):
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "f.zip")
            for path in ("/html", "/challenge"):
                with self.assertRaises(sources.DownloadError) as cm:
                    sources.download_file(self.base + path, dest, expect_zip=True)
                self.assertIn("not a zip file", str(cm.exception))
                self.assertIn("Just a moment", str(cm.exception))   # shows what came back
            self.assertFalse(os.path.exists(dest))
            self.assertFalse(os.path.exists(dest + ".part"))

    def test_valid_zip_is_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "f.zip")
            sources.download_file(self.base + "/good", dest, expect_zip=True, min_bytes=100)
            self.assertTrue(zipfile.is_zipfile(dest))

    def test_too_small_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(sources.DownloadError):
                sources.download_file(self.base + "/good", os.path.join(d, "f.zip"),
                                      expect_zip=True, min_bytes=10**9)

    def test_second_route_is_used_when_first_returns_html(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(C, "RIVERATLAS_URL", self.base + "/html"), \
                mock.patch.object(C, "RIVERATLAS_API_URL", self.base + "/good"), \
                mock.patch.object(C, "RIVERATLAS_MIN_BYTES", 100):
            info = sources.fetch_riveratlas(d)
            self.assertEqual(info["tiles"], ["RiverATLAS_v10_af.shp"])

    def test_both_routes_failing_gives_manual_instructions(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(C, "RIVERATLAS_URL", self.base + "/html"), \
                mock.patch.object(C, "RIVERATLAS_API_URL", self.base + "/challenge"), \
                mock.patch.object(C, "RIVERATLAS_MIN_BYTES", 100):
            with self.assertRaises(RuntimeError) as cm:
                sources.fetch_riveratlas(d)
            msg = str(cm.exception)
            self.assertIn("/html", msg)
            self.assertIn("/challenge", msg)
            self.assertIn("--riveratlas-zip", msg)
            self.assertIn("Just a moment", msg)

    def test_bogus_earlier_download_is_replaced(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(C, "RIVERATLAS_URL", self.base + "/good"), \
                mock.patch.object(C, "RIVERATLAS_MIN_BYTES", 100):
            with open(os.path.join(d, C.RIVERATLAS_ZIP), "wb") as f:
                f.write(HTML)                      # what your first attempt left on disk
            info = sources.fetch_riveratlas(d)
            self.assertEqual(info["tiles"], ["RiverATLAS_v10_af.shp"])

    def test_manual_zip_is_used_without_any_download(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(C, "RIVERATLAS_URL", "http://127.0.0.1:9/never"), \
                mock.patch.object(C, "RIVERATLAS_API_URL", "http://127.0.0.1:9/never"), \
                mock.patch.object(C, "RIVERATLAS_MIN_BYTES", 100):
            mine = os.path.join(d, "mine.zip")
            with open(mine, "wb") as f:
                f.write(AF_ZIP)
            info = sources.fetch_riveratlas(os.path.join(d, "work"), zip_path=mine)
            self.assertEqual(info["tiles"], ["RiverATLAS_v10_af.shp"])
            bad = os.path.join(d, "bad.zip")
            with open(bad, "wb") as f:
                f.write(HTML)
            with self.assertRaises(FileNotFoundError):
                sources.fetch_riveratlas(os.path.join(d, "work2"), zip_path=bad)


class TestCliZipOption(unittest.TestCase):
    def test_option_parsed(self):
        from nowri import cli
        a = cli.build_parser().parse_args(["run", "--mode", "legacy", "--river-source", "riveratlas",
                                           "--riveratlas-zip", "/x/y.zip"])
        self.assertEqual(a.riveratlas_zip, "/x/y.zip")


if __name__ == "__main__":
    unittest.main()
