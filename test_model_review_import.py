"""Проверка импорта карточек «Лжесотрудники» без реального источника."""
import http.server
import importlib
import json
import os
import tempfile
import threading
import urllib.request
import unittest


PNG = b"\x89PNG\r\n\x1a\nfixture-image"


class ReviewSourceHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.headers.get("Cookie") != "session=fixture":
            self.send_response(401)
            self.end_headers()
            return
        if self.path == "/admin_pseudo.php":
            body = b"""<!doctype html><body><header><a href='/forum'>Forum</a></header><main>
              <article class='profile-card'><img src='/images/alice.png'><h3>Alice</h3><p>Alice short caption.</p><a href='/profile/alice'>Open full review</a></article>
              <article class='profile-card'><img src='/images/bella.png'><h3>Bella</h3><p>Bella short caption.</p><a href='/profile/bella'>Open full review</a></article>
              </main><aside>Sidebar information must not be imported.</aside><script>evil()</script></body>"""
            return self._send("text/html; charset=utf-8", body)
        if self.path.startswith("/profile/"):
            name = self.path.rsplit("/", 1)[-1].title().encode()
            body = b"<html><body><main><h1>" + name + b" detail</h1><p>Full answer for " + name + b" keeps original source order.</p><p>Second source paragraph.</p></main><footer>Footer must not be imported.</footer></body></html>"
            return self._send("text/html; charset=utf-8", body)
        if self.path.startswith("/images/"):
            return self._send("image/png", PNG)
        self.send_error(404)

    def _send(self, content_type, body):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class ModelReviewImportTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), ReviewSourceHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.stopped = False
        self.previous = {key: os.environ.get(key) for key in ("DATA_DIR", "DISCUSSION_SOURCE_COOKIE", "MODEL_REVIEW_SOURCE_URL")}
        os.environ.update({
            "DATA_DIR": self.temp.name,
            "DISCUSSION_SOURCE_COOKIE": "session=fixture",
            "MODEL_REVIEW_SOURCE_URL": f"http://127.0.0.1:{self.server.server_port}/admin_pseudo.php",
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
        if self.stopped:
            return
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.stopped = True

    def test_imports_individual_cards_details_and_cached_photo(self):
        self.importer.initialise()
        self.assertEqual(self.importer.refresh()["count"], 2)
        cards = self.importer.list_model_reviews()
        self.assertEqual([card["title"] for card in cards], ["Alice", "Bella"])
        self.assertTrue(all(card["image"] for card in cards))
        self.assertTrue(all("blocks" not in card for card in cards))
        detail = self.importer.get_model_review(cards[0]["id"])
        self.assertEqual(detail["blocks"], ["Alice detail", "Full answer for Alice keeps original source order.", "Second source paragraph."])
        self.assertNotIn("Sidebar", " ".join(detail["blocks"]))
        self.assertTrue(self.importer.image_path(cards[0]["image"]))

    def test_keeps_cached_cards_when_catalog_source_fails(self):
        self.importer.initialise()
        self.importer.refresh()
        before = self.importer.list_model_reviews()
        self._stop_source()
        self.assertEqual(self.importer.refresh()["status"], "error")
        after = self.importer.list_model_reviews()
        self.assertEqual([item["id"] for item in after], [item["id"] for item in before])
        self.assertTrue(all(item["stale"] for item in after))

    def test_api_lists_cards_then_serves_detail_and_image(self):
        self.importer.initialise()
        self.importer.refresh()
        import server
        api_module = importlib.reload(server)
        api_server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), api_module.Handler)
        api_thread = threading.Thread(target=api_server.serve_forever, daemon=True)
        api_thread.start()
        base = f"http://127.0.0.1:{api_server.server_port}"
        try:
            with urllib.request.urlopen(base + "/api/model-reviews/external", timeout=2) as response:
                cards = json.loads(response.read())
            with urllib.request.urlopen(base + "/api/model-reviews/external/" + cards[0]["id"], timeout=2) as response:
                detail = json.loads(response.read())
            with urllib.request.urlopen(base + "/api/model-review-images/" + cards[0]["image"], timeout=2) as response:
                image = response.read()
        finally:
            api_server.shutdown()
            api_server.server_close()
            api_thread.join(timeout=2)
        self.assertNotIn("blocks", cards[0])
        self.assertIn("Full answer", " ".join(detail["blocks"]))
        self.assertEqual(image, PNG)


if __name__ == "__main__":
    unittest.main()
