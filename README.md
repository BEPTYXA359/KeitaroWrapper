# KeitaroWrapper

Обёртка над рекламным трекером **Keitaro** (Admin API) — тестовое задание «Adrobot».

Две функциональные части:
1. **«Создаватор» кампаний** — форма (название / гео / оффер) → кампания в Keitaro с двумя потоками: Flow 1 (редирект на Google с гео-фильтром) и Flow 2 (выбранный оффер).
2. **Редактор кампании** — управление офферами в потоках (добавление/удаление/возврат), автопересчёт долей (сумма всегда 100%), синхронизация с Keitaro (PUSH TO KT / CANCEL / FETCH).

## Стек

- Бэкенд: **FastAPI + SQLAlchemy + Alembic** (Python 3.12)
- Фронтенд: **Vue 3 + TypeScript + Vite** (собранный `frontend/dist` коммитится — для запуска нужен только Python)
- UI: строгий монохром, прямые углы — см. [docs/UI.md](.docs/UI.md)

## Запуск

> Будет добавлено на фазе 1 плана разработки (`.docs/adrobot-phases.md`, локальная папка).

Быстрый ориентир (после фазы 1):
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # заполнить KT_BASE_URL и KT_API_KEY
alembic upgrade head
uvicorn app.main:app --reload
```

## Переменные окружения

| Переменная | Назначение |
|---|---|
| `KT_BASE_URL` | База трекера, напр. `https://tlgk.host` |
| `KT_API_KEY` | API-ключ (админка Keitaro → Профиль → API ключи) |
| `DATABASE_URL` | По умолчанию `sqlite:///./dev.db` |
| `CAMPAIGN_PREFIX` | Префикс имён кампаний, обязателен по ТЗ (`test_<фамилия>_`) |
| `KT_GROUP_NAME` / `KT_SOURCE_NAME` | Группа и источник кампании (default `FORTESTS`) |
| `KT_DOMAIN_ID` | Домен кампании (если пусто — первый доступный) |
