"""Фоновый импорт внешних обсуждений.

В запросах посетителей нет сетевого обращения к источнику или к ИИ: API
отдаёт только последнюю сохранённую версию из discussions.json. Полный текст
разрешается только явной серверной настройкой; по умолчанию хранится краткий
пересказ с атрибуцией источника.
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

from discussion_sources import SOURCES, source_url


DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(DATA_DIR, "discussions.json")
IMPORT_MODE = os.environ.get("DISCUSSION_IMPORT_MODE", "summary").strip().lower()
if IMPORT_MODE not in {"summary", "full"}:
    IMPORT_MODE = "summary"
REFRESH_SECONDS = max(60, int(os.environ.get("DISCUSSION_REFRESH_SECONDS", "300")))
MAX_WORKERS = max(1, min(8, int(os.environ.get("DISCUSSION_IMPORT_CONCURRENCY", "3"))))
SOURCE_TIMEOUT = max(3, min(60, int(os.environ.get("DISCUSSION_SOURCE_TIMEOUT", "20"))))
BACKGROUND_ENABLED = os.environ.get("DISCUSSION_BACKGROUND", "1") != "0"
MAX_SOURCE_BYTES = 2_000_000
MAX_MESSAGE_CHARS = 3_500
MAX_MESSAGES = 80
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
SUMMARY_MODEL = os.environ.get("DISCUSSION_SUMMARY_MODEL", "gpt-6.1-terra")
# Полное значение заголовка Cookie для rlc.intimcity.beer. Секрет хранится
# только в переменных Render и никогда не попадает в API, JSON или логи.
SOURCE_COOKIE = os.environ.get("DISCUSSION_SOURCE_COOKIE", "").strip()

_lock = threading.RLock()
_background_started = False
_SOURCE_IDS = {source_id for source_id, _ in SOURCES}


class DiscussionParser(HTMLParser):
    """Из HTML берём только текст; теги, события, стили и ссылки не сохраняем."""

    ignored = {"script", "style", "noscript", "svg", "canvas", "iframe", "form", "button", "header", "footer", "nav", "aside"}
    block_tags = {"p", "li", "article", "blockquote", "pre", "h2", "h3", "h4", "td"}

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
        if tag == "h1":
            self._h1_depth += 1
        if tag == "br":
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
        if tag == "h1" and self._h1_depth:
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


def _default_item(source_id, title):
    return {
        "id": source_id,
        "title": title,
        "url": source_url(source_id),
        "mode": IMPORT_MODE,
        "updated_at": 0,
        "last_checked_at": 0,
        "stale": False,
    }


def _load_store():
    try:
        with open(STORE, encoding="utf-8") as f:
            db = json.load(f)
    except FileNotFoundError:
        db = {}
    except json.JSONDecodeError as exc:
        raise ValueError("Файл импортированных обсуждений содержит некорректный JSON.") from exc
    if not isinstance(db, dict) or not isinstance(db.get("items", {}), dict):
        raise ValueError("Файл импортированных обсуждений имеет неверную структуру.")
    db.setdefault("version", 1)
    db.setdefault("items", {})
    return db


def _save_store(db):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = STORE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STORE)


def _ensure_sources(db):
    changed = False
    for source_id, title in SOURCES:
        item = db["items"].get(source_id)
        if not isinstance(item, dict):
            db["items"][source_id] = _default_item(source_id, title)
            changed = True
            continue
        # URL и заголовок принадлежат коду, а не к скачанному документу.
        if item.get("url") != source_url(source_id):
            item["url"] = source_url(source_id)
            changed = True
        if not item.get("title"):
            item["title"] = title
            changed = True
        if item.get("mode") not in {"summary", "full"}:
            item["mode"] = IMPORT_MODE
            changed = True
    return changed


def initialise():
    with _lock:
        db = _load_store()
        if _ensure_sources(db):
            _save_store(db)


def _public(item, include_body=False):
    result = {
        "id": item["id"],
        "title": item["title"],
        "url": item["url"],
        "mode": item.get("mode", IMPORT_MODE),
        "updated_at": item.get("updated_at", 0),
        "last_checked_at": item.get("last_checked_at", 0),
        "stale": bool(item.get("stale")),
        "ready": bool(item.get("updated_at")),
    }
    if include_body:
        if result["mode"] == "full":
            result["messages"] = item.get("messages", [])
        else:
            result["summary"] = item.get("summary", "")
    return result


def list_discussions():
    with _lock:
        db = _load_store()
        if _ensure_sources(db):
            _save_store(db)
        return [_public(db["items"][source_id]) for source_id, _ in SOURCES]


def get_discussion(source_id):
    with _lock:
        db = _load_store()
        if _ensure_sources(db):
            _save_store(db)
        item = db["items"].get(source_id)
        return _public(item, include_body=True) if item else None


def _parse_html(raw):
    parser = DiscussionParser()
    parser.feed(raw)
    parser.close()
    title = " ".join(parser.h1 or parser.title).strip()
    blocks = []
    seen = set()
    for block in parser.blocks:
        clean = " ".join(block.split())[:MAX_MESSAGE_CHARS].strip()
        key = clean.casefold()
        if len(clean) >= 3 and key not in seen:
            seen.add(key)
            blocks.append(clean)
        if len(blocks) >= MAX_MESSAGES:
            break
    if not blocks:
        raise ValueError("Источник не вернул читаемый текст.")
    return title, blocks


def _fetch_source(url):
    headers = {
        "User-Agent": "PresidentForumImporter/1.0 (+https://presidentmodel.io/forum)",
        "Accept": "text/html,application/xhtml+xml",
    }
    if SOURCE_COOKIE:
        headers["Cookie"] = SOURCE_COOKIE
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=SOURCE_TIMEOUT) as response:
        content_type = response.headers.get_content_type()
        if content_type not in {"text/html", "application/xhtml+xml"}:
            raise ValueError("Источник вернул не HTML-документ.")
        raw = response.read(MAX_SOURCE_BYTES + 1)
        if len(raw) > MAX_SOURCE_BYTES:
            raise ValueError("Документ источника слишком большой.")
        charset = response.headers.get_content_charset() or "utf-8"
    return _parse_html(raw.decode(charset, "replace"))


_STOPWORDS = {
    "и", "в", "во", "не", "на", "я", "с", "со", "что", "а", "как", "это", "по", "но", "за", "от", "для", "у", "к", "о", "об", "из", "или", "же", "то", "мы", "вы", "они", "он", "она", "так", "уже", "бы", "ли", "до", "при", "без", "про",
}


def _extractive_summary(messages):
    """Локальная выжимка на случай, когда ИИ не настроен на Render."""
    text = " ".join(messages)
    sentences = [" ".join(s.split()) for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) >= 25]
    if not sentences:
        return "Материал источника сохранён, но в нём недостаточно текста для пересказа."
    counts = {}
    for word in re.findall(r"[\wа-яё-]{4,}", text.casefold()):
        if word not in _STOPWORDS:
            counts[word] = counts.get(word, 0) + 1
    ranked = sorted(
        enumerate(sentences),
        key=lambda pair: sum(counts.get(word, 0) for word in re.findall(r"[\wа-яё-]{4,}", pair[1].casefold())),
        reverse=True,
    )[:4]
    picked = [sentence for _, sentence in sorted(ranked)]
    return " ".join(picked)[:1_200].rstrip()


def _response_text(response):
    if isinstance(response.get("output_text"), str):
        return response["output_text"].strip()
    parts = []
    for item in response.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                parts.append(content["text"])
    return "\n".join(parts).strip()


def _summarize(title, messages):
    if not OPENAI_KEY:
        return _extractive_summary(messages)
    material = "\n\n".join(messages)[:45_000]
    prompt = (
        "Сделай нейтральный содержательный пересказ внешнего публичного обсуждения на русском. "
        "Не приписывай текст владельцам этого сайта и не называй пересказ сообщениями пользователей. "
        "Не используй имена авторов, личные контакты и оскорбления; если такие сведения есть, обобщи их. "
        "Сохрани главные разные позиции и практический вывод. Максимум 1 200 символов, без Markdown.\n\n"
        f"Заголовок: {title}\n\nМатериал:\n{material}"
    )
    body = {"model": SUMMARY_MODEL, "input": prompt, "max_output_tokens": 700, "store": False}
    request = urllib.request.Request(
        OPENAI_BASE + "/responses",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            summary = _response_text(json.loads(response.read()))
        if summary:
            return summary[:1_500]
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError):
        pass
    return _extractive_summary(messages)


def refresh_one(source_id):
    """Обновляет один источник. При ошибке не затирает последнюю версию."""
    if source_id not in _SOURCE_IDS:
        raise ValueError("Неизвестное обсуждение.")
    checked_at = _now()
    try:
        parsed_title, messages = _fetch_source(source_url(source_id))
        # Пересказ зависит от сообщений, а не от косметического изменения заголовка.
        digest = hashlib.sha256("\n\n".join(messages).encode()).hexdigest()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError):
        with _lock:
            db = _load_store()
            _ensure_sources(db)
            item = db["items"][source_id]
            item["last_checked_at"] = checked_at
            item["stale"] = bool(item.get("updated_at"))
            _save_store(db)
        return {"id": source_id, "status": "error"}

    with _lock:
        db = _load_store()
        _ensure_sources(db)
        item = db["items"][source_id]
        item["last_checked_at"] = checked_at
        if item.get("source_hash") == digest and item.get("mode") == IMPORT_MODE:
            item["stale"] = False
            _save_store(db)
            return {"id": source_id, "status": "unchanged"}

    title = parsed_title[:240] or item["title"]
    body = {"source_hash": digest, "updated_at": checked_at, "last_checked_at": checked_at, "stale": False, "mode": IMPORT_MODE}
    if IMPORT_MODE == "full":
        body["messages"] = messages
        body["summary"] = ""
    else:
        body["summary"] = _summarize(title, messages)
        body["messages"] = []

    with _lock:
        db = _load_store()
        _ensure_sources(db)
        item = db["items"][source_id]
        # Другой фоновый поток мог успеть обработать ту же версию.
        if item.get("source_hash") != digest:
            item.update(body)
            item["title"] = title
        else:
            item["last_checked_at"] = checked_at
            item["stale"] = False
        _save_store(db)
    return {"id": source_id, "status": "updated"}


def refresh_all():
    initialise()
    outcomes = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="forum-import") as pool:
        futures = [pool.submit(refresh_one, source_id) for source_id, _ in SOURCES]
        for future in as_completed(futures):
            try:
                outcomes.append(future.result())
            except Exception:
                # Один сбой не прерывает импорт остальных источников.
                outcomes.append({"status": "error"})
    return outcomes


def _background_loop():
    # Сервер начинает отвечать сразу; начальный импорт не задерживает healthcheck Render.
    time.sleep(2)
    while True:
        started = time.monotonic()
        refresh_all()
        time.sleep(max(1, REFRESH_SECONDS - (time.monotonic() - started)))


def start_background_refresh():
    global _background_started
    initialise()
    if not BACKGROUND_ENABLED:
        return
    with _lock:
        if _background_started:
            return
        _background_started = True
    threading.Thread(target=_background_loop, name="forum-discussion-refresh", daemon=True).start()
