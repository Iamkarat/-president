# Бэкенд форума presidentmodel.io/forum/

API для страницы форума (сама страница лежит в ветке `main`, папка `forum/`, и публикуется GitHub Pages):
вопросы и ответы, мнения по темам, PRESIDENT AI SEARCH (OpenAI Responses API + web_search).

Python 3.9+, без зависимостей. Хостинг — Render, конфигурация в `render.yaml`.

## Запуск на Render
1. render.com → войти через GitHub.
2. New → Blueprint → репозиторий `Iamkarat/-president`, ветка `forum-backend`.
3. Вставить ключ в поле `OPENAI_API_KEY` (platform.openai.com → API keys) и подтвердить.

Сервис станет доступен по адресу https://presidentmodel-forum-api.onrender.com —
он уже прописан в `forum/config.js` (`apiBase`) в ветке `main`.

## Настройки (переменные окружения)
Описаны в начале `server.py` и `ai_search.py`. Главное:
- `AI_DAILY_BUDGET_USD` — дневной лимит расходов на OpenAI (сейчас $3);
- `AI_HOURLY_QUICK` / `AI_HOURLY_DEEP` — запросов в час с одного IP;
- `FORUM_PASSWORD` — закрыть API паролем (HTTP Basic Auth).

## Локально
    OPENAI_API_KEY=... python3 server.py   # http://127.0.0.1:8734
