"""Проверка импорта внешней страницы отзывов без реального внешнего сайта."""
import http.server
import importlib
import json
import os
import tempfile
import threading
import urllib.request
import unittest


class ReviewSourceHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.headers.get("Cookie") != "session=fixture":
            self.send_response(401)
            self.end_headers()
            return
        body = b"""<!doctype html><html><head><title>Reviews fixture</title><script>steal()</script></head>
        <body><nav>Forum</nav><h1>Model reviews</h1><article>
        <p>First source review is kept in its original wording.</p>
        <p>Second review keeps the source order. mail@example.com +7 999 123-45-67</p>
        <p>token=should-never-be-published</p></article></body></html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class ModelReviewImportTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous = {key: os.environ.get(key) for key in ("DATA_DIR", "DISCUSSION_SOURCE_COOKIE", "MODEL_REVIEW_SOURCE_URL")}
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), ReviewSourceHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.source_stopped = False
        self.source_url = f"http://127.0.0.1:{self.server.server_port}/admin_pseudo.php"
        os.environ.update({
            "DATA_DIR": self.temp.name,
            "DISCUSSION_SOURCE_COOKIE": "session=fixture",
            "MODEL_REVIEW_SOURCE_URL": self.source_url,
        })
        import model_review_import
        self.importer = importlib.reload(model_review_import)

    def tearDown(self):
        self._stop_source()
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.temp.cleanup()

    def _stop_source(self):
        if self.source_stopped:
            return
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.source_stopped = True

    def test_source_text_is_cached_safely_without_a_summary(self):
        self.importer.initialise()
        self.assertEqual(self.importer.refresh()["status"], "updated")
        item = self.importer.get_model_reviews()
        self.assertTrue(item["ready"])
        self.assertEqual(item["mode"], "source-text")
        self.assertIn("First source review is kept in its original wording.", item["blocks"])
        self.assertIn("Second review keeps the source order. [скрыто] [скрыто]", item["blocks"])
        joined = " ".join(item["blocks"]).lower()
        self.assertNotIn("script", joined)
        self.assertNotIn("token=", joined)
        self.assertNotIn("mail@example.com", joined)
        self.assertNotIn("999 123", joined)

    def test_saved_version_remains_when_source_is_unavailable(self):
        self.importer.initialise()
        self.importer.refresh()
        original = self.importer.get_model_reviews()["blocks"]
        self._stop_source()
        self.assertEqual(self.importer.refresh()["status"], "error")
        stale = self.importer.get_model_reviews()
        self.assertTrue(stale["stale"])
        self.assertEqual(stale["blocks"], original)

    def test_api_returns_cached_external_reviews(self):
        self.importer.initialise()
        self.importer.refresh()
        import server
        api_module = importlib.reload(server)
        api_server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), api_module.Handler)
        api_thread = threading.Thread(target=api_server.serve_forever, daemon=True)
        api_thread.start()
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{api_server.server_port}/api/model-reviews/external", timeout=2) as response:
                body = json.loads(response.read())
        finally:
            api_server.shutdown()
            api_server.server_close()
            api_thread.join(timeout=2)
        self.assertEqual(body["id"], "admin-pseudo")
        self.assertEqual(body["blocks"][1], "First source review is kept in its original wording.")
        self.assertEqual(self.importer._source_request().unredirected_hdrs.get("Cookie"), "session=fixture")


if __name__ == "__main__":
    unittest.main()
