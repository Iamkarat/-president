"""Кешированный импорт карточек «Лжесотрудники».

Источник содержит каталог и отдельные страницы подробностей. Сервер заранее
сохраняет карточки, фотографии и развёрнутые ответы; браузер к источнику не
обращается и не получает cookie или внешний HTML.
"""
import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit


DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(DATA_DIR, "model_reviews.json")
IMAGE_DIR = os.path.join(DATA_DIR, "external-review-images")
SOURCE_URL = os.environ.get("MODEL_REVIEW_SOURCE_URL", "https://rlc.intimcity.beer/admin_pseudo.php").strip()
SOURCE_COOKIE = os.environ.get("DISCUSSION_SOURCE_COOKIE", "").strip()
SOURCE_TIMEOUT = max(3, min(60, int(os.environ.get("DISCUSSION_SOURCE_TIMEOUT", "20"))))
MAX_SOURCE_BYTES = 2_000_000
MAX_IMAGE_BYTES = 4 * 1024 * 1024
MAX_REVIEWS = 120
MAX_DETAIL_BLOCKS = 160
MAX_DETAIL_CHARS = 90_000
DETAIL_WORKERS = max(1, min(3, int(os.environ.get("DISCUSSION_IMPORT_CONCURRENCY", "3"))))
SOURCE_ORIGIN = (urlsplit(SOURCE_URL).scheme, urlsplit(SOURCE_URL).netloc.casefold())

_lock = threading.RLock()
_NOISE = {"главная", "форум", "вход", "выход", "регистрация", "авторизация", "поиск", "наверх", "правила", "контакты", "меню", "читать далее"}
_DETAIL_TEXT_RE = re.compile(r"(подроб|развер|полный|отзыв|читать|more|view)", re.I)
_CARD_CLASS_RE = re.compile(r"(card|item|pseudo|model|review|profile|anket|list)", re.I)
_SKIP_CLASS_RE = re.compile(r"(header|footer|sidebar|side-bar|navbar|nav-|menu|banner|advert|breadcrumbs?)", re.I)
_SECRET_RE = re.compile(r"(?i)\b(cookie|password|пароль|token|authorization)\s*[:=]\s*[^\s<]{3,}")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b", re.I)
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?7|8)[\s().-]*\d(?:[\s().-]*\d){9,}(?!\d)")


class Node:
    def __init__(self, tag="root", attrs=None, parent=None):
        self.tag, self.attrs, self.parent = tag, dict(attrs or ()), parent
        self.children = []

    def attr(self, key):
        return self.attrs.get(key, "").strip()


class PageParser(HTMLParser):
    """Небольшое DOM-дерево для карточек, ссылок и фото без сохранения HTML."""

    ignored = {"script", "style", "noscript", "svg", "canvas", "iframe", "form", "button", "header", "footer", "nav", "aside"}
    void = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root, self.current, self.skip_depth = Node(), None, 0
        self.current = self.root

    def handle_starttag(self, tag, attrs):
        tag = tag.casefold()
        attrs = [(str(k).casefold(), str(v or "")) for k, v in attrs]
        if self.skip_depth:
            if tag not in self.void:
                self.skip_depth += 1
            return
        if tag in self.ignored or _SKIP_CLASS_RE.search(dict(attrs).get("class", "")):
            self.skip_depth = 1
            return
        node = Node(tag, attrs, self.current)
        self.current.children.append(node)
        if tag not in self.void:
            self.current = node

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag.casefold() not in self.void:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self.skip_depth:
            self.skip_depth -= 1
            return
        tag = tag.casefold()
        cursor = self.current
        while cursor is not self.root:
            if cursor.tag == tag:
                self.current = cursor.parent
                return
            cursor = cursor.parent

    def handle_data(self, data):
        if not self.skip_depth:
            text = " ".join(data.split())
            if text:
                self.current.children.append(text)


def _now():
    return int(time.time() * 1000)


def _walk(node):
    for child in node.children:
        if isinstance(child, Node):
            yield child
            yield from _walk(child)


def _text(node):
    return " ".join(" ".join((child if isinstance(child, str) else _text(child)) for child in node.children).split())


def _clean_text(value):
    value = " ".join(value.split())
    if value.casefold() in _NOISE:
        return ""
    value = _SECRET_RE.sub(lambda m: m.group(1) + ": [скрыто]", value)
    value = _EMAIL_RE.sub("[скрыто]", value)
    return _PHONE_RE.sub("[скрыто]", value).strip()


def _safe_url(value, base=SOURCE_URL):
    if not value:
        return ""
    result = urljoin(base, value)
    parsed = urlsplit(result)
    if (parsed.scheme, parsed.netloc.casefold()) != SOURCE_ORIGIN:
        return ""
    if parsed.scheme != "https" and parsed.hostname not in {"127.0.0.1", "localhost"}:
        return ""
    return result


def _default_db():
    return {"version": 2, "items": {}, "order": [], "last_checked_at": 0, "stale": False}


def _load_store():
    try:
        with open(STORE, encoding="utf-8") as f:
            db = json.load(f)
    except FileNotFoundError:
        return _default_db()
    except json.JSONDecodeError as exc:
        raise ValueError("Файл импортированных отзывов содержит некорректный JSON.") from exc
    # Старый единый текст не может стать карточкой — его заменит новый импорт.
    if not isinstance(db, dict) or db.get("version") != 2:
        return _default_db()
    if not isinstance(db.get("items"), dict) or not isinstance(db.get("order"), list):
        raise ValueError("Файл импортированных отзывов имеет неверную структуру.")
    return db


def _save_store(db):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = STORE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STORE)


def initialise():
    with _lock:
        _save_store(_load_store())


def _source_request(url):
    request = urllib.request.Request(url, headers={
        "User-Agent": "PresidentForumImporter/1.0 (+https://presidentmodel.io/forum)",
        "Accept": "text/html,application/xhtml+xml",
    })
    if SOURCE_COOKIE and (urlsplit(url).scheme, urlsplit(url).netloc.casefold()) == SOURCE_ORIGIN:
        # При переходе на другой origin urllib этот Cookie не перенесёт.
        request.add_unredirected_header("Cookie", SOURCE_COOKIE)
    return request


def _fetch_document(url):
    with urllib.request.urlopen(_source_request(url), timeout=SOURCE_TIMEOUT) as response:
        if response.headers.get_content_type() not in {"text/html", "application/xhtml+xml"}:
            raise ValueError("Источник вернул не HTML-документ.")
        raw = response.read(MAX_SOURCE_BYTES + 1)
        if len(raw) > MAX_SOURCE_BYTES:
            raise ValueError("Документ источника слишком большой.")
        charset = response.headers.get_content_charset() or "utf-8"
    parser = PageParser()
    parser.feed(raw.decode(charset, "replace"))
    parser.close()
    return parser.root


def _nearest_card(node):
    cursor = node
    while cursor and cursor.parent:
        if cursor.tag in {"article", "li", "tr"} or (cursor.tag == "div" and _CARD_CLASS_RE.search(cursor.attr("class"))):
            return cursor
        cursor = cursor.parent
    return node.parent or node


def _first_image(node, base):
    for candidate in (node, *_walk(node)):
        if candidate.tag == "img":
            image = _safe_url(candidate.attr("src"), base)
            if image:
                return image
    return ""


def _card_title(card, fallback):
    for node in (card, *_walk(card)):
        if node.tag in {"h1", "h2", "h3", "h4", "strong", "b"}:
            title = _clean_text(_text(node))
            if len(title) >= 2:
                return title[:160]
    for node in (card, *_walk(card)):
        if node.tag == "a":
            title = _clean_text(_text(node))
            if len(title) >= 2 and not _DETAIL_TEXT_RE.search(title):
                return title[:160]
    return fallback[:160]


def _catalog_entries(root):
    entries, seen = [], set()
    for anchor in _walk(root):
        if anchor.tag != "a":
            continue
        detail_url = _safe_url(anchor.attr("href"))
        if not detail_url or detail_url == SOURCE_URL or detail_url in seen:
            continue
        label, card = _clean_text(_text(anchor)), _nearest_card(anchor)
        image, card_text = _first_image(card, SOURCE_URL), _clean_text(_text(card))
        path = urlsplit(detail_url).path.casefold()
        likely_detail = bool(_DETAIL_TEXT_RE.search(label)) or bool(re.search(r"(pseudo|model|review|otz|profile|anket)", path))
        # Ссылка из меню не имеет ни фото, ни карточечного текста.
        if not likely_detail or not card_text or (not image and len(card_text) < 24):
            continue
        seen.add(detail_url)
        entries.append({
            "id": hashlib.sha256(detail_url.encode()).hexdigest()[:20],
            "title": _card_title(card, label or "Лжесотрудник"),
            "excerpt": card_text[:700],
            "detail_url": detail_url,
            "image_url": image,
        })
        if len(entries) >= MAX_REVIEWS:
            break
    if not entries:
        raise ValueError("На странице не найдены карточки со ссылками на подробности.")
    return entries


def _detail_blocks(root):
    blocks, seen, chars = [], set(), 0
    for node in _walk(root):
        if node.tag not in {"p", "li", "blockquote", "td", "th", "tr", "h1", "h2", "h3", "h4", "h5", "pre"}:
            continue
        value, key = _clean_text(_text(node)), ""
        key = value.casefold()
        if len(value) < 3 or key in seen:
            continue
        if len(blocks) >= MAX_DETAIL_BLOCKS or chars + len(value) > MAX_DETAIL_CHARS:
            break
        seen.add(key)
        blocks.append(value)
        chars += len(value)
    if not blocks:
        value = _clean_text(_text(root))
        if value:
            blocks = [value[:MAX_DETAIL_CHARS]]
    if not blocks:
        raise ValueError("Подробная страница не вернула читаемый текст.")
    return blocks


def _image_extension(data, content_type):
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "webp"
    if content_type.startswith("image/"):
        raise ValueError("Источник вернул повреждённое изображение.")
    raise ValueError("Источник вернул не изображение.")


def _cache_image(image_url):
    if not image_url:
        return ""
    request = _source_request(image_url)
    request.headers["Accept"] = "image/avif,image/webp,image/png,image/jpeg,image/gif"
    with urllib.request.urlopen(request, timeout=SOURCE_TIMEOUT) as response:
        content_type = response.headers.get_content_type()
        data = response.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Изображение источника слишком большое.")
    name = hashlib.sha256(data).hexdigest() + "." + _image_extension(data, content_type)
    os.makedirs(IMAGE_DIR, exist_ok=True)
    target = os.path.join(IMAGE_DIR, name)
    if not os.path.exists(target):
        # Несколько карточек могут ссылаться на одно фото: временный файл должен
        # быть уникальным для потока, иначе один импорт перетрёт другой.
        tmp = target + "." + str(threading.get_ident()) + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, target)
    return name


def _fetch_review(entry):
    root = _fetch_document(entry["detail_url"])
    blocks = _detail_blocks(root)
    image_url = _first_image(root, entry["detail_url"]) or entry["image_url"]
    image = _cache_image(image_url) if image_url else ""
    digest = hashlib.sha256((entry["title"] + "\n" + "\n".join(blocks) + "\n" + image).encode()).hexdigest()
    return {**entry, "blocks": blocks, "image": image, "source_hash": digest}


def _public(item, include_body=False):
    result = {
        "id": item["id"], "title": item["title"], "excerpt": item.get("excerpt", ""),
        "image": item.get("image", ""), "url": item["detail_url"],
        "updated_at": item.get("updated_at", 0), "last_checked_at": item.get("last_checked_at", 0),
        "stale": bool(item.get("stale")), "ready": bool(item.get("updated_at")),
    }
    if include_body:
        result["blocks"] = item.get("blocks", [])
    return result


def list_model_reviews():
    with _lock:
        db = _load_store()
        return [_public(db["items"][key]) for key in db["order"] if key in db["items"]]


def get_model_review(review_id):
    with _lock:
        item = _load_store()["items"].get(review_id)
        return _public(item, include_body=True) if item else None


def image_path(name):
    if not re.fullmatch(r"[0-9a-f]{64}\.(?:png|jpg|gif|webp)", name):
        return ""
    path = os.path.join(IMAGE_DIR, name)
    return path if os.path.isfile(path) else ""


def refresh():
    """Обновляет каталог и все подробности; ошибка не затирает старые карточки."""
    checked_at = _now()
    try:
        entries = _catalog_entries(_fetch_document(SOURCE_URL))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError):
        with _lock:
            db = _load_store()
            for item in db["items"].values():
                item.update({"last_checked_at": checked_at, "stale": bool(item.get("updated_at"))})
            db.update({"last_checked_at": checked_at, "stale": bool(db["order"])})
            _save_store(db)
        return {"status": "error"}

    fetched = {}
    with ThreadPoolExecutor(max_workers=DETAIL_WORKERS, thread_name_prefix="review-import") as pool:
        futures = {pool.submit(_fetch_review, entry): entry for entry in entries}
        for future in as_completed(futures):
            entry = futures[future]
            try:
                fetched[entry["id"]] = future.result()
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError):
                fetched[entry["id"]] = None

    with _lock:
        db = _load_store()
        old_items, items = db["items"], {}
        for entry in entries:
            review_id, fresh, old = entry["id"], fetched.get(entry["id"]), old_items.get(entry["id"])
            if fresh is None and old:
                item = {**old, "title": entry["title"], "excerpt": entry["excerpt"], "detail_url": entry["detail_url"], "last_checked_at": checked_at, "stale": True}
            elif fresh is None:
                item = {**entry, "blocks": [], "image": "", "updated_at": 0, "last_checked_at": checked_at, "stale": True}
            else:
                item = {**fresh, "last_checked_at": checked_at, "stale": False}
                item["updated_at"] = old.get("updated_at", checked_at) if old and old.get("source_hash") == fresh["source_hash"] else checked_at
            items[review_id] = item
        db.update({"version": 2, "items": items, "order": [entry["id"] for entry in entries], "last_checked_at": checked_at, "stale": any(item["stale"] for item in items.values())})
        _save_store(db)
    return {"status": "updated", "count": len(entries), "ready": sum(bool(item["updated_at"]) for item in items.values())}
