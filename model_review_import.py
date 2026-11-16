"""Кешированный импорт внешней страницы отзывов о моделях.

Это отдельный от обсуждений импорт: текст не отправляется в ИИ и не
пересказывается. HTML никогда не отдаётся браузеру — сохраняются только
очищенные текстовые блоки. Cookie существует только в окружении Render.
"""
import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser


DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(DATA_DIR, "model_reviews.json")
SOURCE_URL = os.environ.get("MODEL_REVIEW_SOURCE_URL", "https://rlc.intimcity.beer/admin_pseudo.php").strip()
SOURCE_COOKIE = os.environ.get("DISCUSSION_SOURCE_COOKIE", "").strip()
SOURCE_TIMEOUT = max(3, min(60, int(os.environ.get("DISCUSSION_SOURCE_TIMEOUT", "20"))))
MAX_SOURCE_BYTES = 2_000_000
MAX_BLOCKS = 120
MAX_TOTAL_CHARS = 90_000

_lock = threading.RLock()


class ReviewPageParser(HTMLParser):
    """Берёт человеческий текст, но не переносит разметку или исполняемый код."""

    ignored = {"script", "style", "noscript", "svg", "canvas", "iframe", "form", "button", "header", "footer", "nav", "aside"}
    block_tags = {"p", "li", "blockquote", "td", "th", "tr", "h1", "h2", "h3", "h4", "h5", "pre"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.title = []
        self.h1 = []
        self.blocks = []
        self._buffer = []
        self._title_depth = 0
        self._h1_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self.ignored:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag in self.block_tags:
            self._flush()
        if tag == "title":
            self._title_depth += 1
        elif tag == "h1":
            self._h1_depth += 1
        elif tag == "br":
            self._buffer.append(" ")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.ignored and self.skip_depth:
            self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if tag == "title" and self._title_depth:
            self._title_depth -= 1
        elif tag == "h1" and self._h1_depth:
            self._h1_depth -= 1
        if tag in self.block_tags:
            self._flush()

    def handle_data(self, data):
        if self.skip_depth:
            return
        value = " ".join(data.split())
        if not value:
            return
        if self._title_depth:
            self.title.append(value)
            return
        self._buffer.append(value)
        if self._h1_depth:
            self.h1.append(value)

    def close(self):
        super().close()
        self._flush()

    def _flush(self):
        value = " ".join(self._buffer).strip()
        self._buffer.clear()
        if value:
            self.blocks.append(value)


def _now():
    return int(time.time() * 1000)


def _default_item():
    return {
        "id": "admin-pseudo",
        "title": "Внешние отзывы о моделях",
        "url": SOURCE_URL,
        "mode": "source-text",
        "updated_at": 0,
        "last_checked_at": 0,
        "stale": False,
        "blocks": [],
    }


def _load_store():
    try:
        with open(STORE, encoding="utf-8") as f:
            db = json.load(f)
    except FileNotFoundError:
        return {"version": 1, "item": _default_item()}
    except json.JSONDecodeError as exc:
        raise ValueError("Файл импортированных отзывов содержит некорректный JSON.") from exc
    if not isinstance(db, dict) or not isinstance(db.get("item"), dict):
        raise ValueError("Файл импортированных отзывов имеет неверную структуру.")
    return db


def _save_store(db):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = STORE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STORE)


def _ensure_item(db):
    item = db["item"]
    changed = False
    for key, value in (("id", "admin-pseudo"), ("title", "Внешние отзывы о моделях"), ("url", SOURCE_URL), ("mode", "source-text")):
        if item.get(key) != value:
            item[key] = value
            changed = True
    for key, value in (("updated_at", 0), ("last_checked_at", 0), ("stale", False), ("blocks", [])):
        if key not in item:
            item[key] = value
            changed = True
    return changed


def initialise():
    with _lock:
        db = _load_store()
        if _ensure_item(db):
            _save_store(db)


def _public(item):
    return {
        "id": item["id"],
        "title": item["title"],
        "url": item["url"],
        "mode": "source-text",
        "updated_at": item.get("updated_at", 0),
        "last_checked_at": item.get("last_checked_at", 0),
        "stale": bool(item.get("stale")),
        "ready": bool(item.get("updated_at")),
        "blocks": item.get("blocks", []),
    }


def get_model_reviews():
    with _lock:
        db = _load_store()
        if _ensure_item(db):
            _save_store(db)
        return _public(db["item"])


def _source_request():
    headers = {
        "User-Agent": "PresidentForumImporter/1.0 (+https://presidentmodel.io/forum)",
        "Accept": "text/html,application/xhtml+xml",
    }
    request = urllib.request.Request(SOURCE_URL, headers=headers)
    if SOURCE_COOKIE:
        # Cookie остаётся у исходного домена даже при 30x на другой origin.
        request.add_unredirected_header("Cookie", SOURCE_COOKIE)
    return request


_NOISE = {
    "главная", "форум", "вход", "выход", "регистрация", "авторизация",
    "поиск", "наверх", "правила", "контакты", "меню",
}
_SECRET_RE = re.compile(r"(?i)\b(cookie|password|пароль|token|authorization)\s*[:=]\s*[^\s<]{3,}")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b", re.I)
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?7|8)[\s().-]*\d(?:[\s().-]*\d){9,}(?!\d)")


def _clean_block(value):
    value = " ".join(value.split())
    if value.casefold() in _NOISE:
        return ""
    # Даже при разрешённой полной передаче не публикуем случайно попавшие секреты
    # или контакты из служебной страницы.
    value = _SECRET_RE.sub(lambda m: m.group(1) + ": [скрыто]", value)
    value = _EMAIL_RE.sub("[скрыто]", value)
    value = _PHONE_RE.sub("[скрыто]", value)
    return value.strip()


def _parse_html(raw):
    parser = ReviewPageParser()
    parser.feed(raw)
    parser.close()
    title = " ".join(parser.h1 or parser.title).strip()
    blocks, seen, chars = [], set(), 0
    for raw_block in parser.blocks:
        block = _clean_block(raw_block)
        key = block.casefold()
        if len(block) < 3 or key in seen:
            continue
        if len(blocks) >= MAX_BLOCKS or chars + len(block) > MAX_TOTAL_CHARS:
            break
        seen.add(key)
        blocks.append(block)
        chars += len(block)
    if not blocks:
        raise ValueError("Источник не вернул читаемый текст отзывов.")
    return title, blocks


def _fetch_source():
    with urllib.request.urlopen(_source_request(), timeout=SOURCE_TIMEOUT) as response:
        content_type = response.headers.get_content_type()
        if content_type not in {"text/html", "application/xhtml+xml"}:
            raise ValueError("Источник вернул не HTML-документ.")
        raw = response.read(MAX_SOURCE_BYTES + 1)
        if len(raw) > MAX_SOURCE_BYTES:
            raise ValueError("Документ источника слишком большой.")
        charset = response.headers.get_content_charset() or "utf-8"
    return _parse_html(raw.decode(charset, "replace"))


def refresh():
    """Обновляет отзывную страницу, сохраняя последнюю версию при сбое."""
    checked_at = _now()
    try:
        page_title, blocks = _fetch_source()
        digest = hashlib.sha256("\n\n".join(blocks).encode()).hexdigest()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError):
        with _lock:
            db = _load_store()
            _ensure_item(db)
            item = db["item"]
            item["last_checked_at"] = checked_at
            item["stale"] = bool(item.get("updated_at"))
            _save_store(db)
        return {"status": "error"}

    with _lock:
        db = _load_store()
        _ensure_item(db)
        item = db["item"]
        item["last_checked_at"] = checked_at
        if item.get("source_hash") == digest:
            item["stale"] = False
            _save_store(db)
            return {"status": "unchanged"}
        item.update({
            "source_hash": digest,
            "updated_at": checked_at,
            "last_checked_at": checked_at,
            "stale": False,
            "blocks": blocks,
        })
        if page_title:
            item["title"] = page_title[:240]
        _save_store(db)
    return {"status": "updated"}
