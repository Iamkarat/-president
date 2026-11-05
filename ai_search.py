"""PRESIDENT AI SEARCH: ответы с поиском в интернете через OpenAI Responses API (инструмент web_search).

Ключ OPENAI_API_KEY читается только из окружения сервера и никогда не попадает в браузер.
Результаты и учёт расходов хранятся в ai.json рядом с data.json.

Переменные окружения:
  OPENAI_API_KEY        — ключ OpenAI (без него поиск выключен)
  AI_MODEL_QUICK        — модель Quick Search (по умолчанию gpt-6.1-terra)
  AI_MODEL_DEEP         — модель Deep Research (по умолчанию gpt-6.1-sol)
  AI_PRICE_QUICK        — цена модели Quick за 1M токенов «вход,выход» в $, по умолчанию 1,5
  AI_PRICE_DEEP         — то же для Deep, по умолчанию 2,10
  AI_DAILY_BUDGET_USD   — дневной лимит расходов в $, по умолчанию 5
  AI_HOURLY_QUICK       — запросов Quick в час с одного IP, по умолчанию 12
  AI_HOURLY_DEEP        — запросов Deep в час с одного IP, по умолчанию 3
  AI_MIN_INTERVAL       — секунд между запросами с одного IP, по умолчанию 8
"""
import json
import os
import re
import secrets
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

API_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/") + "/responses"
API_KEY = os.environ.get("OPENAI_API_KEY", "")
STORE = os.path.join(os.environ.get("DATA_DIR") or os.path.dirname(os.path.abspath(__file__)), "ai.json")

MIN_QUERY, MAX_QUERY = 3, 600
MAX_TURNS = 6              # вопросов в одном диалоге
MAX_RESULTS = 1000         # сохранённых результатов
MAX_CONCURRENT = 4         # одновременных исследований на сервер
MIN_INTERVAL = float(os.environ.get("AI_MIN_INTERVAL", "8"))  # секунд между запросами с одного IP
SEARCH_CALL_USD = 0.01     # $10 за 1000 вызовов web_search
DAILY_BUDGET = float(os.environ.get("AI_DAILY_BUDGET_USD", "5"))


def _price(name, default):
    pin, pout = (float(x) for x in os.environ.get(name, default).split(","))
    return pin, pout


MODES = {
    "quick": {
        "model": os.environ.get("AI_MODEL_QUICK", "gpt-6.1-terra"),
        "price": _price("AI_PRICE_QUICK", "1,5"),
        "effort": "low",
        "context": "medium",
        "max_tool_calls": 4,
        "max_output_tokens": 4000,
        "reserve": 0.08,
        "hourly": int(os.environ.get("AI_HOURLY_QUICK", "12")),
    },
    "deep": {
        "model": os.environ.get("AI_MODEL_DEEP", "gpt-6.1-sol"),
        "price": _price("AI_PRICE_DEEP", "2,10"),
        "effort": "medium",
        "context": "high",
        "max_tool_calls": 16,
        "max_output_tokens": 16000,
        "reserve": 0.80,
        "hourly": int(os.environ.get("AI_HOURLY_DEEP", "3")),
    },
}

FORMAT_DEEP = """## Краткий ответ
2–4 предложения по существу.

## Подробный анализ
Разбор вопроса по аспектам. Если источники расходятся — покажи обе позиции и объясни, какой стоит доверять больше и почему.

## Актуальная информация
Последние изменения и новости по теме с датами. Если свежих данных нет — так и напиши.

## Выводы
Маркированный список главных выводов.

## Рекомендации
Практические шаги — только если они уместны для вопроса, иначе раздел не нужен.

## Источники
Нумерованный список: [Название](URL) — издатель, дата публикации (или «дата не указана»)."""

FORMAT_QUICK = """## Краткий ответ
2–4 предложения по существу.

## Подробности
Короткий разбор: самое важное и актуальное, с датами.

## Выводы
2–4 пункта.

## Источники
Нумерованный список: [Название](URL) — издатель, дата публикации (или «дата не указана»)."""


TZ = timezone(timedelta(hours=3))  # Москва, без перехода на летнее время


def today():
    return datetime.now(TZ).date().isoformat()


def instructions(mode, assistant="PRESIDENT AI SEARCH"):
    identity = (
        "Тебя зовут AI Day. Если спрашивают, как тебя зовут, ответь ровно: «Меня зовут AI Day.» "
        "Если спрашивают, кто ты, ответь кратко: «Я AI Day, поисковый помощник one.day.» "
        "Не называй себя ChatGPT или PRESIDENT AI SEARCH. На вопрос только об имени не ищи в интернете."
        if assistant == "AI Day"
        else "Тебя зовут PRESIDENT AI SEARCH."
    )
    return f"""Ты — {assistant}, исследовательский поисковый ассистент. Сегодня {today()} (по московскому времени).

Правила:
- {identity}
- Кроме прямого вопроса о твоём имени или идентичности, перед ответом обязательно ищи в интернете актуальную информацию. {"Используй много независимых источников (не меньше 6), проверяй факты перекрёстно." if mode == "deep" else "Используй несколько независимых источников."}
- Предпочитай первоисточники: официальные сайты, документы, законы, исследования, заявления компаний. СМИ и блоги — как дополнение.
- Обращай внимание на даты публикаций: свежие данные важнее устаревших; явно отмечай, если информация может быть неактуальной.
- Пиши только то, что подтверждено найденными источниками. Не выдумывай факты, цифры, цитаты и ссылки. Если данных недостаточно — прямо скажи об этом.
- Ссылки давай только на страницы, которые действительно нашёл поиск. Ставь ссылки на источники прямо в тексте рядом с утверждениями.
- Отвечай на языке вопроса пользователя (по умолчанию — по-русски), ясно и без воды.
- Оформляй ответ в Markdown строго по структуре:

{FORMAT_DEEP if mode == "deep" else FORMAT_QUICK}"""


# ---------- хранилище и учёт расходов ----------

store_lock = threading.Lock()
slots = threading.BoundedSemaphore(MAX_CONCURRENT)
last_request = {}
hourly = {}


def load_store():
    try:
        with open(STORE, encoding="utf-8") as f:
            db = json.load(f)
    except FileNotFoundError:
        db = {}
    db.setdefault("results", [])
    db.setdefault("spend", {"day": "", "usd": 0.0})
    return db


def save_store(db):
    tmp = STORE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STORE)


def add_spend(usd):
    """Прибавляет к дневным расходам; возвращает False, если бюджет уже исчерпан (при usd > 0)."""
    with store_lock:
        db = load_store()
        day = today()
        if db["spend"]["day"] != day:
            db["spend"] = {"day": day, "usd": 0.0}
        if usd > 0 and db["spend"]["usd"] + usd > DAILY_BUDGET:
            return False
        db["spend"]["usd"] = round(max(0.0, db["spend"]["usd"] + usd), 6)
        save_store(db)
        return True


def find_result(result_id):
    with store_lock:
        return next((r for r in load_store()["results"] if r["id"] == result_id), None)


def chain(result_id):
    """Диалог, который заканчивается результатом result_id: от первого вопроса к последнему."""
    with store_lock:
        by_id = {r["id"]: r for r in load_store()["results"]}
    turns = []
    while result_id in by_id and len(turns) < MAX_TURNS:
        turns.append(by_id[result_id])
        result_id = by_id[result_id].get("parent")
    return list(reversed(turns))


def public(result):
    return {k: result[k] for k in ("id", "query", "mode", "answer", "citations", "sources", "created", "parent", "incomplete") if k in result}


def check_limits(ip, mode):
    now = time.time()
    with store_lock:
        if now - last_request.get(ip, 0) < MIN_INTERVAL:
            return "Слишком часто. Подождите несколько секунд."
        stamps = [t for t in hourly.get((ip, mode), []) if now - t < 3600]
        if len(stamps) >= MODES[mode]["hourly"]:
            return "Лимит запросов этого режима на час исчерпан. Попробуйте позже."
        stamps.append(now)
        hourly[(ip, mode)] = stamps
        last_request[ip] = now
    return None


# ---------- запрос к OpenAI ----------

def api_error_message(code):
    if code in (401, 403):
        return "AI-поиск не настроен на сервере."
    if code == 429:
        return "AI-поиск сейчас перегружен. Попробуйте через минуту."
    if code == 400:
        return "Запрос не удалось обработать. Переформулируйте вопрос."
    return "Сервис поиска временно недоступен. Попробуйте позже."


def stream_events(body):
    """Отправляет запрос в Responses API и по одному отдаёт события SSE (dict)."""
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json", "Accept": "text/event-stream"},
    )
    with urllib.request.urlopen(req, timeout=120) as res:
        for raw in res:
            line = raw.decode("utf-8", "replace").strip()
            if line.startswith("data:"):
                data = line[5:].strip()
                if data and data != "[DONE]":
                    try:
                        yield json.loads(data)
                    except ValueError:
                        continue


def collect_output(output, citations, sources):
    """Собирает цитаты и источники из итогового output ответа."""
    searches = 0
    for item in output or []:
        if item.get("type") == "web_search_call":
            searches += 1
            for s in (item.get("action") or {}).get("sources") or []:
                if isinstance(s, dict) and s.get("url"):
                    sources.setdefault(s["url"], s.get("title") or "")
        if item.get("type") == "message":
            for part in item.get("content") or []:
                for a in part.get("annotations") or []:
                    if a.get("type") == "url_citation" and a.get("url"):
                        citations.setdefault(a["url"], a.get("title") or "")
    return searches


def run(handler, payload, ip):
    """Обрабатывает POST /api/ai/search: стримит ход исследования и ответ событиями SSE."""
    if not API_KEY:
        return handler.send_json(503, {"error": "AI-поиск не настроен на сервере."})
    query = " ".join(str(payload.get("query", "")).split())
    mode = payload.get("mode") if payload.get("mode") in MODES else "quick"
    assistant = "AI Day" if payload.get("assistant") == "ai-day" else "PRESIDENT AI SEARCH"
    parent_id = payload.get("parent")
    if len(query) < MIN_QUERY:
        return handler.send_json(400, {"error": f"Напишите вопрос хотя бы из {MIN_QUERY} символов."})
    if len(query) > MAX_QUERY:
        return handler.send_json(400, {"error": f"Вопрос не длиннее {MAX_QUERY} символов."})

    previous = None
    if parent_id is not None:
        if not isinstance(parent_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,32}", parent_id):
            return handler.send_json(400, {"error": "Некорректный диалог."})
        previous = find_result(parent_id)
        if not previous:
            return handler.send_json(404, {"error": "Предыдущий ответ не найден. Начните новый поиск."})
        if len(chain(parent_id)) >= MAX_TURNS:
            return handler.send_json(400, {"error": "Диалог слишком длинный. Начните новый поиск."})

    limit = check_limits(ip, mode)
    if limit:
        return handler.send_json(429, {"error": limit})
    cfg = MODES[mode]
    if not slots.acquire(blocking=False):
        return handler.send_json(503, {"error": "Сейчас идёт много исследований. Попробуйте через минуту."})
    try:
        if not add_spend(cfg["reserve"]):
            return handler.send_json(503, {"error": "Дневной лимит AI-поиска исчерпан. Попробуйте завтра."})
        _stream(handler, query, mode, cfg, previous, assistant)
    finally:
        slots.release()


def _stream(handler, query, mode, cfg, previous, assistant):
    handler.send_response(200)
    handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
    handler.send_header("X-Accel-Buffering", "no")
    handler.end_headers()
    handler.close_connection = True

    def emit(event, data):
        handler.wfile.write(f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode())
        handler.wfile.flush()

    body = {
        "model": cfg["model"],
        "instructions": instructions(mode, assistant),
        "input": query,
        "tools": [{"type": "web_search", "search_context_size": cfg["context"]}],
        "tool_choice": "auto",
        "include": ["web_search_call.action.sources"],
        "reasoning": {"effort": cfg["effort"]},
        "max_tool_calls": cfg["max_tool_calls"],
        "max_output_tokens": cfg["max_output_tokens"],
        "store": True,
        "stream": True,
    }
    if previous:
        body["previous_response_id"] = previous["response_id"]

    answer, citations, sources = [], {}, {}
    response_id, usage, searches, failure, incomplete = None, {}, 0, None, True
    client_gone = False
    try:
        emit("status", {"stage": "start"})
        for ev in stream_events(body):
            kind = ev.get("type", "")
            if kind == "response.created":
                response_id = (ev.get("response") or {}).get("id")
            elif kind.startswith("response.web_search_call."):
                emit("status", {"stage": "searching"})
            elif kind == "response.output_item.done" and (ev.get("item") or {}).get("type") == "web_search_call":
                action = ev["item"].get("action") or {}
                for s in action.get("sources") or []:
                    if isinstance(s, dict) and s.get("url"):
                        sources.setdefault(s["url"], s.get("title") or "")
                emit("status", {"stage": "searched", "action": action.get("type", "search"), "query": action.get("query") or action.get("url") or "", "sources": len(sources)})
            elif kind == "response.output_text.delta":
                answer.append(ev.get("delta", ""))
                emit("delta", {"text": ev.get("delta", "")})
            elif kind == "response.output_text.annotation.added":
                a = ev.get("annotation") or {}
                if a.get("type") == "url_citation" and a.get("url"):
                    citations.setdefault(a["url"], a.get("title") or "")
            elif kind in ("response.completed", "response.incomplete"):
                resp = ev.get("response") or {}
                response_id = resp.get("id") or response_id
                usage = resp.get("usage") or {}
                searches = collect_output(resp.get("output"), citations, sources)
                incomplete = kind == "response.incomplete"  # до этого события ответ считается неполным
            elif kind == "response.failed":
                resp = ev.get("response") or {}
                usage = resp.get("usage") or {}
                failure = "Исследование не удалось завершить. Попробуйте ещё раз."
            elif kind == "error":
                failure = "Сервис поиска вернул ошибку. Попробуйте позже."
    except urllib.error.HTTPError as e:
        failure = api_error_message(e.code)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        if isinstance(e, (BrokenPipeError, ConnectionResetError)):
            client_gone = True
        failure = "Сервис поиска не отвечает. Попробуйте позже."

    pin, pout = cfg["price"]
    cost = (usage.get("input_tokens", 0) * pin + usage.get("output_tokens", 0) * pout) / 1e6 + searches * SEARCH_CALL_USD
    # Без usage (обрыв посреди ответа) точная цена неизвестна — резерв остаётся списанным.
    if usage or not response_id:
        add_spend(cost - cfg["reserve"])

    text = "".join(answer).strip()
    if client_gone:
        return
    try:
        if failure and not text:
            return emit("error", {"error": failure})
        result = {
            "id": secrets.token_urlsafe(9),
            "query": query,
            "mode": mode,
            "answer": text,
            "citations": [{"url": u, "title": t} for u, t in citations.items()],
            "sources": [{"url": u, "title": t} for u, t in list(sources.items())[:60]],
            "created": int(time.time() * 1000),
            "parent": previous["id"] if previous else None,
            "response_id": response_id,
            "incomplete": bool(incomplete or failure),
        }
        with store_lock:
            db = load_store()
            db["results"] = ([result] + db["results"])[:MAX_RESULTS]
            save_store(db)
        emit("done", public(result))
    except (BrokenPipeError, ConnectionResetError):
        pass
