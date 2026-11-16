"""Локальная проверка импорта без обращения к реальному внешнему форуму."""
import http.server
import importlib
import os
import tempfile
import threading
import time
import urllib.request
import unittest


class SourceHandler(http.server.BaseHTTPRequestHandler):
    required_cookie = "session=fixture"

    def do_GET(self):
        if self.headers.get("Cookie") != self.required_cookie:
            self.send_response(401)
            self.end_headers()
            return
        time.sleep(0.18)  # имитируем задержку внешнего источника
        body = b"""<!doctype html><html><head><title>Fixture title</title><script>window.evil = true</script></head>
        <body><h1>Fixture discussion</h1><article><p>First useful message about travel planning.</p>
        <p>Second useful message keeps its original order.</p></article><style>.hidden { display:none }</style></body></html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class DiscussionImportTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous = {key: os.environ.get(key) for key in ("DATA_DIR", "DISCUSSION_IMPORT_MODE", "DISCUSSION_BACKGROUND", "DISCUSSION_SOURCE_COOKIE")}
        os.environ.update({"DATA_DIR": self.temp.name, "DISCUSSION_IMPORT_MODE": "full", "DISCUSSION_BACKGROUND": "0", "DISCUSSION_SOURCE_COOKIE": "session=fixture"})
        import discussion_import
        self.importer = importlib.reload(discussion_import)
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), SourceHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.source_stopped = False
        base = f"http://127.0.0.1:{self.server.server_port}/discussion"
        self.importer.SOURCES = (("101", "Fixture discussion"),)
        self.importer._SOURCE_IDS = {"101"}
        self.importer.source_url = lambda source_id: base

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

    def test_import_keeps_saved_version_when_source_goes_down(self):
        self.importer.initialise()
        self.assertEqual(self.importer.refresh_one("101")["status"], "updated")
        item = self.importer.get_discussion("101")
        self.assertEqual(item["mode"], "full")
        self.assertEqual(item["messages"], [
            "Fixture discussion",
            "First useful message about travel planning.",
            "Second useful message keeps its original order.",
        ])
        self.assertNotIn("script", " ".join(item["messages"]).lower())
        self.assertEqual(len(self.importer.list_discussions()), 1)

        self._stop_source()
        self.assertEqual(self.importer.refresh_one("101")["status"], "error")
        cached = self.importer.get_discussion("101")
        self.assertTrue(cached["stale"])
        self.assertEqual(cached["messages"], item["messages"])

    def test_api_returns_titles_then_one_cached_body(self):
        self.importer.initialise()
        started = time.perf_counter()
        self.importer.refresh_one("101")
        source_ms = (time.perf_counter() - started) * 1000
        import server
        api_module = importlib.reload(server)
        api_server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), api_module.Handler)
        api_thread = threading.Thread(target=api_server.serve_forever, daemon=True)
        api_thread.start()
        base = f"http://127.0.0.1:{api_server.server_port}/api/discussions"
        try:
            with urllib.request.urlopen(base, timeout=2) as response:
                index = __import__("json").loads(response.read())
            started = time.perf_counter()
            with urllib.request.urlopen(base + "/101", timeout=2) as response:
                body = __import__("json").loads(response.read())
            cached_ms = (time.perf_counter() - started) * 1000
        finally:
            api_server.shutdown()
            api_server.server_close()
            api_thread.join(timeout=2)
        self.assertEqual([item["id"] for item in index], ["101"])
        self.assertNotIn("messages", index[0])
        self.assertEqual(body["messages"][1], "First useful message about travel planning.")
        self.assertLess(cached_ms, source_ms)
        print(f"source refresh: {source_ms:.1f} ms; cached discussion API: {cached_ms:.1f} ms")


if __name__ == "__main__":
    unittest.main()
