"""Локальный сервер форума: раздаёт статику и хранит вопросы/ответы в data.json.

GET  /api/questions                — список вопросов (новые сверху)
POST /api/questions                — {name, text, avatar?, image?}  → опубликовать вопрос сразу
                                     (image — data:image/png|jpeg|webp|gif;base64, до 4 МБ)
POST /api/questions/<id>/answers   — {name, text, avatar?}  → ответ на вопрос
GET  /api/demo-answers             — ответы посетителей на примеры: {d1: [..]}
POST /api/demo/<d1..>/answers      — {name, text, avatar?} → ответ на пример
GET  /api/uploads/<file>           — картинка, прикреплённая к записи
POST /api/admin/delete            — {ids: [..]} или {all: true}, заголовок X-Admin-Token = ADMIN_TOKEN
                                     → удалить записи (вопросы, ответы, мнения в темах)
Если задана переменная окружения FORUM_PASSWORD, весь форум (страница и API)
закрывается HTTP Basic Auth: логин любой, пароль — значение переменной.

GET  /api/ai/status                — включён ли AI-поиск и его режимы
POST /api/ai/search                — {query, mode: quick|deep, parent?, assistant?} → SSE: status, delta, done | error
GET  /api/ai/results/<id>          — сохранённый ответ AI-поиска вместе с диалогом

HOST — адрес для прослушивания (по умолчанию 127.0.0.1); ALLOWED_ORIGINS — сайты через
запятую, которым разрешено обращаться к API (например https://presidentmodel.io);
TRUST_PROXY=1 — брать IP клиента из заголовков прокси (только за своим reverse proxy);
DATA_DIR — папка для data.json и ai.json (по умолчанию рядом с server.py);
API_ONLY=1 — отдавать только /api/*, без статических файлов (сервер только для API).

GET  /api/topics                   — мнения по темам: {topic_id: [..]}
POST /api/topics/<topic_id>/comments — {name, text, avatar?} → мнение в теме
"""
import base64
import binascii
import hmac
import json
import os
import re
import secrets
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import ai_search

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", ROOT)
DATA = os.path.join(DATA_DIR, "data.json")
PORT = int(os.environ.get("PORT", "8734"))
HOST = os.environ.get("HOST", "127.0.0.1")
ALLOWED_ORIGINS = {o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()} | {
    "https://botwrk.ru",
    "https://potwrk.ru",
}
TRUST_PROXY = os.environ.get("TRUST_PROXY") == "1"
API_ONLY = os.environ.get("API_ONLY") == "1"
PASSWORD = os.environ.get("FORUM_PASSWORD", "")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")
LINK_RE = re.compile(r"(https?://|www\.|t\.me/|\b[\w-]+\.(ru|com|io|net|org)\b)", re.I)
RATE_SECONDS = 15
TOPIC_IDS = {"greece", "tickets", "packing", "budget", "stay", "party", "safety", "meet", "season"}
AVATAR_ASSETS = {
    "assets/avatars/president-long-hair.png",
    "assets/avatars/president-dark-hair.png",
    "assets/avatars/president-veil.png",
}
UPLOADS = os.path.join(DATA_DIR, "uploads")
IMAGE_MAX = 4 * 1024 * 1024
IMAGE_DATA_RE = re.compile(r"data:image/(webp|png|jpeg|gif);base64,([A-Za-z0-9+/]+={0,2})\Z")
IMAGE_NAME_RE = re.compile(r"[0-9a-f]{32}\.(webp|png|jpg|gif)")
IMAGE_TYPES = {"webp": "image/webp", "png": "image/png", "jpg": "image/jpeg", "gif": "image/gif"}
AVATAR_DATA_RE = re.compile(r"data:image/(webp|png|jpeg);base64,([A-Za-z0-9+/]+={0,2})\Z")

lock = threading.Lock()
last_post = {}


def valid_avatar(value):
    if not isinstance(value, str):
        return False
    if value in AVATAR_ASSETS:
        return True
    if len(value) > 90_000:
        return False
    match = AVATAR_DATA_RE.fullmatch(value)
    if not match:
        return False
    try:
        image = base64.b64decode(match.group(2), validate=True)
    except (binascii.Error, ValueError):
        return False
    image_type = match.group(1)
    return (
        len(image) <= 65_536
        and (
            (image_type == "webp" and image.startswith(b"RIFF") and image[8:12] == b"WEBP")
            or (image_type == "png" and image.startswith(b"\x89PNG\r\n\x1a\n"))
            or (image_type == "jpeg" and image.startswith(b"\xff\xd8\xff"))
        )
    )


def decode_image(value):
    """data:image/...;base64 → (байты, расширение) или ValueError."""
    match = IMAGE_DATA_RE.fullmatch(value) if isinstance(value, str) and len(value) < IMAGE_MAX * 4 // 3 + 100 else None
    if not match:
        raise ValueError("Прикрепите PNG, JPEG, WebP или GIF до 4 МБ.")
    try:
        data = base64.b64decode(match.group(2), validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("Некорректное изображение.")
    kind = match.group(1)
    ok = (
        (kind == "webp" and data.startswith(b"RIFF") and data[8:12] == b"WEBP")
        or (kind == "png" and data.startswith(b"\x89PNG\r\n\x1a\n"))
        or (kind == "jpeg" and data.startswith(b"\xff\xd8\xff"))
        or (kind == "gif" and data[:6] in (b"GIF87a", b"GIF89a"))
    )
    if not ok or len(data) > IMAGE_MAX:
        raise ValueError("Прикрепите PNG, JPEG, WebP или GIF до 4 МБ.")
    return data, "jpg" if kind == "jpeg" else kind


def store_image(data, ext):
    os.makedirs(UPLOADS, exist_ok=True)
    name = f"{secrets.token_hex(16)}.{ext}"
    tmp = os.path.join(UPLOADS, name + ".tmp")
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, os.path.join(UPLOADS, name))
    return name


def remove_images(names):
    for name in names:
        if IMAGE_NAME_RE.fullmatch(name):
            try:
                os.remove(os.path.join(UPLOADS, name))
            except OSError:
                pass


def all_images(db):
    found = set()
    for q in db["questions"]:
        for item in [q, *q["answers"]]:
            if item.get("image"):
                found.add(item["image"])
    return found


def load():
    try:
        with open(DATA, encoding="utf-8") as f:
            db = json.load(f)
    except FileNotFoundError:
        return {"next_id": 1, "questions": []}
    except json.JSONDecodeError as e:
        raise ValueError("Файл данных форума содержит некорректный JSON.") from e

    if (
        not isinstance(db, dict)
        or type(db.get("next_id")) is not int
        or db["next_id"] < 1
        or not isinstance(db.get("questions"), list)
        or not isinstance(db.get("topics", {}), dict)
        or not isinstance(db.get("demo_answers", {}), dict)
    ):
        raise ValueError("Файл данных форума имеет неверную структуру.")

    def valid_post(item):
        return (
            isinstance(item, dict)
            and type(item.get("id")) is int
            and item["id"] > 0
            and isinstance(item.get("name"), str)
            and isinstance(item.get("text"), str)
            and type(item.get("created")) is int
            and ("avatar" not in item or valid_avatar(item["avatar"]))
            and ("image" not in item or (isinstance(item["image"], str) and IMAGE_NAME_RE.fullmatch(item["image"])))
        )

    entries = []
    for question in db["questions"]:
        if not valid_post(question) or not isinstance(question.get("answers"), list):
            raise ValueError("В файле данных форума есть некорректный вопрос.")
        entries.append(question)
        entries.extend(question["answers"])
    for comments in [*db.get("topics", {}).values(), *db.get("demo_answers", {}).values()]:
        if not isinstance(comments, list):
            raise ValueError("В файле данных форума есть некорректный список мнений.")
        entries.extend(comments)
    if any(not valid_post(entry) for entry in entries):
        raise ValueError("В файле данных форума есть некорректная публикация.")
    ids = [entry["id"] for entry in entries]
    if len(ids) != len(set(ids)) or (ids and max(ids) >= db["next_id"]):
        raise ValueError("В файле данных форума обнаружены повторяющиеся идентификаторы.")
    return db


def save(db):
    tmp = DATA + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=1)
    os.replace(tmp, DATA)


def clean(payload, min_len, max_len):
    if payload.get("website"):  # honeypot
        raise ValueError("Не удалось отправить")
    text = " ".join(str(payload.get("text", "")).split())
    name = " ".join(str(payload.get("name", "")).split())[:40] or "Аноним"
    if len(text) < min_len:
        raise ValueError(f"Напишите хотя бы {min_len} символов.")
    if len(text) > max_len:
        raise ValueError(f"Не больше {max_len} символов.")
    if LINK_RE.search(text) or LINK_RE.search(name):
        raise ValueError("Ссылки публиковать нельзя.")
    avatar = payload.get("avatar", "")
    if not isinstance(avatar, str) or (avatar and not valid_avatar(avatar)):
        raise ValueError("Некорректный аватар.")
    return name, text, avatar


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        origin = self.headers.get("Origin", "")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        super().end_headers()

    def client_ip(self):
        if TRUST_PROXY:
            real = self.headers.get("True-Client-IP") or self.headers.get("CF-Connecting-IP")
            forwarded = self.headers.get("X-Forwarded-For", "")
            if real or forwarded:
                return (real or forwarded.split(",")[0]).strip()
        return self.client_address[0]

    def do_HEAD(self):
        if API_ONLY or self.is_private_path():
            return self.send_error(404)
        return super().do_HEAD()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def authorized(self):
        if not PASSWORD:
            return True
        header = self.headers.get("Authorization", "")
        try:
            _, _, password = base64.b64decode(header.removeprefix("Basic ")).decode().partition(":")
        except (binascii.Error, UnicodeDecodeError):
            password = ""
        if password and hmac.compare_digest(password.encode(), PASSWORD.encode()):
            return True
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="forum", charset="UTF-8"')
        self.send_header("Content-Length", "0")
        self.end_headers()
        return False

    def send_json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self, limit):
        """Читает тело запроса как объект JSON; при ошибке отвечает сам и возвращает None."""
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            return self.send_json(400, {"error": "Некорректный запрос"})
        if length < 0:
            return self.send_json(400, {"error": "Некорректный размер запроса"})
        if length > limit:
            return self.send_json(413, {"error": "Запрос слишком большой"})
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self.send_json(400, {"error": "Некорректный запрос"})
        if not isinstance(payload, dict):
            return self.send_json(400, {"error": "Ожидается объект JSON"})
        return payload

    def is_private_path(self):
        target = os.path.realpath(self.translate_path(urlsplit(self.path).path))
        root = os.path.realpath(ROOT)
        relative = os.path.relpath(target, root)
        old_dir = os.path.realpath(os.path.join(ROOT, "_old"))
        return (
            relative == "server.py"
            or relative == "data.json"
            or relative.startswith("data.json.")
            or relative.startswith("ai.json")
            or relative.endswith(".py")
            or relative.startswith("__pycache__")
            or os.path.commonpath((old_dir, target)) == old_dir
        )

    def admin_delete(self):
        token = self.headers.get("X-Admin-Token", "")
        if not ADMIN_TOKEN or not hmac.compare_digest(token.encode(), ADMIN_TOKEN.encode()):
            return self.send_json(403, {"error": "Нет доступа"})
        payload = self.read_json(10_000)
        if payload is None:
            return
        ids = payload.get("ids", [])
        if payload.get("all") is not True and (not isinstance(ids, list) or not all(type(i) is int for i in ids)):
            return self.send_json(400, {"error": "Ожидается {ids: [числа]} или {all: true}"})
        with lock:
            try:
                db = load()
            except (OSError, ValueError) as e:
                return self.send_json(500, {"error": str(e)})
            before = json.dumps(db)
            images_before = all_images(db)
            if payload.get("all") is True:
                db["questions"] = []
            else:
                drop = set(ids)
                db["questions"] = [q for q in db["questions"] if q["id"] not in drop]
                for q in db["questions"]:
                    q["answers"] = [a for a in q["answers"] if a["id"] not in drop]
                for group in ("topics", "demo_answers"):
                    for key, items in db.get(group, {}).items():
                        db[group][key] = [c for c in items if c["id"] not in drop]
            changed = json.dumps(db) != before
            if changed:
                try:
                    save(db)
                except OSError as e:
                    return self.send_json(500, {"error": f"Не удалось сохранить данные: {e}"})
                remove_images(images_before - all_images(db))
        return self.send_json(200, {"ok": True, "changed": changed, "left": [q["id"] for q in db["questions"]]})

    def do_GET(self):
        if not self.authorized():
            return
        path = urlsplit(self.path).path
        if self.is_private_path():
            return self.send_error(404)
        if path == "/api/questions":
            try:
                with lock:
                    return self.send_json(200, load()["questions"])
            except (OSError, ValueError) as e:
                return self.send_json(500, {"error": str(e)})
        if path == "/api/demo-answers":
            try:
                with lock:
                    return self.send_json(200, load().get("demo_answers", {}))
            except (OSError, ValueError) as e:
                return self.send_json(500, {"error": str(e)})
        if path == "/api/topics":
            try:
                with lock:
                    return self.send_json(200, load().get("topics", {}))
            except (OSError, ValueError) as e:
                return self.send_json(500, {"error": str(e)})
        up = re.fullmatch(r"/api/uploads/([^/]+)", path)
        if up:
            name = up.group(1)
            file = os.path.join(UPLOADS, name)
            if not IMAGE_NAME_RE.fullmatch(name) or not os.path.isfile(file):
                return self.send_error(404)
            with open(file, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", IMAGE_TYPES[name.rsplit(".", 1)[1]])
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'")
            self.end_headers()
            return self.wfile.write(data)
        if path == "/api/ai/status":
            return self.send_json(200, {
                "enabled": bool(ai_search.API_KEY),
                "max_query": ai_search.MAX_QUERY,
                "modes": {k: {"hourly": v["hourly"]} for k, v in ai_search.MODES.items()},
            })
        r = re.fullmatch(r"/api/ai/results/([A-Za-z0-9_-]{8,32})", path)
        if r:
            turns = ai_search.chain(r.group(1))
            if not turns:
                return self.send_json(404, {"error": "Результат не найден"})
            return self.send_json(200, {"turns": [ai_search.public(t) for t in turns]})
        if API_ONLY:
            return self.send_error(404)
        return super().do_GET()

    def do_POST(self):
        if not self.authorized():
            return
        if self.path == "/api/admin/delete":
            return self.admin_delete()
        if self.path == "/api/ai/search":
            payload = self.read_json(4_000)
            if payload is not None:
                ai_search.run(self, payload, self.client_ip())
            return
        m = re.fullmatch(r"/api/questions(?:/(\d+)/answers)?", self.path)
        t = re.fullmatch(r"/api/topics/([a-z0-9-]{1,40})/comments", self.path)
        dm = re.fullmatch(r"/api/demo/(d[1-9][0-9]{0,2})/answers", self.path)
        if not m and not dm and not (t and t.group(1) in TOPIC_IDS):
            return self.send_error(404)
        payload = self.read_json(6_000_000 if m and not m.group(1) else 120_000)
        if payload is None:
            return

        ip = self.client_ip()
        try:
            name, text, avatar = clean(payload, 10 if m and not m.group(1) else 2, 1000)
            image = decode_image(payload["image"]) if m and not m.group(1) and payload.get("image") else None
        except ValueError as e:
            return self.send_json(400, {"error": str(e)})

        with lock:
            now = time.time()
            if now - last_post.get(ip, 0) < RATE_SECONDS:
                return self.send_json(429, {"error": "Слишком часто. Подождите несколько секунд."})
            try:
                db = load()
            except (OSError, ValueError) as e:
                return self.send_json(500, {"error": str(e)})
            item = {"id": db["next_id"], "name": name, "text": text, "created": int(now * 1000)}
            if avatar:
                item["avatar"] = avatar
            if image:
                try:
                    item["image"] = store_image(*image)
                except OSError as e:
                    return self.send_json(500, {"error": f"Не удалось сохранить изображение: {e}"})
            db["next_id"] += 1
            if dm:
                db.setdefault("demo_answers", {}).setdefault(dm.group(1), []).append(item)
            elif t:
                db.setdefault("topics", {}).setdefault(t.group(1), []).append(item)
            elif m.group(1):
                q = next((q for q in db["questions"] if q["id"] == int(m.group(1))), None)
                if not q:
                    return self.send_json(404, {"error": "Вопрос не найден"})
                q["answers"].append(item)
            else:
                item["answers"] = []
                db["questions"].insert(0, item)
            try:
                save(db)
            except OSError as e:
                return self.send_json(500, {"error": f"Не удалось сохранить данные: {e}"})
            last_post[ip] = now
        self.send_json(201, item)


if __name__ == "__main__":
    print(f"http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
