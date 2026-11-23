"""Ручная smoke-проверка доступа к боевому трекеру Keitaro. Не участвует в CI.

Запуск: .venv/bin/python scripts/smoke_keitaro.py
Читает .env (KT_BASE_URL / KT_API_KEY), печатает количество сущностей в Keitaro
и имя country-фильтра из каталога фильтров потоков (GET /stream_filters).
"""

import sys
from pathlib import Path

# прямой запуск скрипта: корень репо в sys.path, чтобы импортировался пакет app
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.keitaro.client import KeitaroClient
from app.keitaro.exceptions import KeitaroApiError

PREVIEW_LIMIT = 5


def main() -> int:
    settings = get_settings()
    if not settings.KT_API_KEY:
        print("KT_API_KEY пуст — заполни .env (админка Keitaro → Профиль → API ключи)")
        return 1

    try:
        with KeitaroClient(settings) as client:
            offers = client.list_offers()
            domains = client.list_domains()
            groups = client.list_groups()
            sources = client.list_traffic_sources()
            filters = client.list_stream_filters()
    except KeitaroApiError as exc:
        print(f"Ошибка: {exc}")
        return 1

    print(f"offers: {len(offers)}")
    for offer in offers[:PREVIEW_LIMIT]:
        print(f"  [{offer.get('id')}] {offer.get('name')}")

    print(f"domains: {len(domains)}")
    for domain in domains[:PREVIEW_LIMIT]:
        print(f"  [{domain.get('id')}] {domain.get('name')} ({domain.get('state')})")

    print(f"groups: {len(groups)}")
    for group in groups[:PREVIEW_LIMIT]:
        print(f"  [{group.get('id')}] {group.get('name')}")

    print(f"traffic_sources: {len(sources)}")
    for source in sources[:PREVIEW_LIMIT]:
        print(f"  [{source.get('id')}] {source.get('name')}")

    country = next((f for f in filters if str(f.get("value", "")).lower() == "country"), None)
    if country:
        print(f"\ncountry-фильтр из /stream_filters: name={country['value']!r} — использовать в гео-фильтре потоков")
    else:
        print("\nФильтр country в каталоге не найден; доступные фильтры:")
        for f in filters:
            print(f"  {f.get('value')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
