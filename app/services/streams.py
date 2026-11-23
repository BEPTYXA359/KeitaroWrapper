"""Чтение и правка потоков кампании.

Состояние потоков всегда тянется из Keitaro; локальная БД хранит только маппинг
uuid -> keitaro_campaign_id. GET нормализует ответы Keitaro для UI (payload
фильтра строкой -> массив кодов, к офферам потока подтягиваются название и URL
из /offers), PUT меняет только offers потока, сохраняя остальные поля как были.
"""

from __future__ import annotations

from app.keitaro.client import KeitaroClient
from app.services.offers import offer_preview_url


class StreamNotFoundError(Exception):
    """Поток не найден или не относится к этой кампании."""


# Как отправлять в Keitaro офферы, убранные из потока.
# "disable" (по умолчанию): оффер уходит со state "disabled" и долей 0 и остаётся
# в потоке отключённым — он не участвует в ротации, но его можно вернуть
# (BRING BACK); удаление срабатывает и если PUT заменяет массив offers, и если
# объединяет его с существующим.
# "omit" — запасной вариант: удалённые не включаются в запрос целиком.
REMOVED_OFFERS_STRATEGY = "disable"  # "disable" | "omit"


def normalize_stream(stream: dict, offers: dict[int, dict]) -> dict:
    """Ответ Keitaro -> плоская структура для UI.

    offers — офферы Keitaro по id (из GET /offers): оттуда берём название и URL.
    """
    filters = stream.get("filters") or []
    stream_filter = None
    if filters:
        first = filters[0]
        raw_payload = str(first.get("payload") or "")
        codes = [code.strip().upper() for code in raw_payload.split(",") if code.strip()]
        stream_filter = {
            "name": first.get("name"),
            "mode": first.get("mode"),
            "payload": codes,
        }
    return {
        "stream_id": stream["id"],
        "name": stream.get("name"),
        "position": stream.get("position"),
        "schema": stream.get("schema"),
        "filter": stream_filter,
        "offers": [
            {
                "offer_id": item["offer_id"],
                "offer_name": (offers.get(item["offer_id"]) or {}).get("name"),
                "preview_url": offer_preview_url(offers.get(item["offer_id"]) or {}),
                "share": item.get("share"),
                "state": item.get("state"),
            }
            for item in stream.get("offers") or []
        ],
    }


def get_campaign_streams(client: KeitaroClient, campaign_id: int) -> dict:
    """Данные страницы потоков: кампания + нормализованные потоки (сортировка по позиции)."""
    campaign = client.get_campaign(campaign_id)
    streams = client.get_campaign_streams(campaign_id)
    offers = {offer.get("id"): offer for offer in client.list_offers()}
    normalized = [normalize_stream(stream, offers) for stream in streams]
    normalized.sort(key=lambda item: (item["position"] is None, item["position"] or 0))
    return {
        "campaign": {"name": campaign.get("name"), "keitaro_id": campaign.get("id")},
        "streams": normalized,
    }


def update_stream_offers(
    client: KeitaroClient,
    campaign_id: int,
    stream_id: int,
    offers: list[dict],
) -> dict:
    """Заменить offers потока (GET текущего -> подмена -> PUT), вернуть обновлённый поток.

    offers — полный набор активных офферов: [{offer_id, share}]. Остальные офферы
    потока отправляются отключёнными (см. REMOVED_OFFERS_STRATEGY).
    """
    stream = client.get_stream(stream_id)
    if stream.get("campaign_id") != campaign_id:
        raise StreamNotFoundError(f"Поток {stream_id} не относится к кампании {campaign_id}")

    payload = {**stream}
    active = [
        {"offer_id": item["offer_id"], "share": item["share"], "state": "active"}
        for item in offers
    ]
    if REMOVED_OFFERS_STRATEGY == "omit":
        payload["offers"] = active
    else:
        active_ids = {item["offer_id"] for item in offers}
        disabled = [
            {"offer_id": existing["offer_id"], "share": 0, "state": "disabled"}
            for existing in stream.get("offers") or []
            if existing.get("offer_id") not in active_ids
        ]
        payload["offers"] = active + disabled
    return client.update_stream(stream_id, payload)
