"""Чтение и правка потоков кампании.

Состояние потоков всегда тянется из Keitaro; локальная БД хранит только маппинг
uuid -> keitaro_campaign_id. GET нормализует ответы Keitaro для UI (payload
фильтра строкой -> массив кодов, имена офферов склеиваются по offer_id),
PUT меняет только offers потока, сохраняя остальные поля как были.
"""

from __future__ import annotations

from app.keitaro.client import KeitaroClient


class StreamNotFoundError(Exception):
    """Поток не найден или не относится к этой кампании."""


# Семантика PUT /streams/{id} (заменяет массив offers целиком или мерджит)
# подтверждается живой проверкой на тестовой кампании. По умолчанию считаем,
# что заменяет: удалённые офферы просто не включаем в payload. Если проверка
# покажет, что API мерджит массивы, переключить на "disable" — тогда удалённые
# уйдут со state "disabled" (Keitaro не считает их в ротации); иначе REMOVE
# не сработает — офферы останутся активными в Keitaro.
REMOVED_OFFERS_STRATEGY = "omit"  # "omit" | "disable"


def normalize_stream(stream: dict, offer_names: dict[int, str | None]) -> dict:
    """Ответ Keitaro -> плоская структура для UI."""
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
                "offer_id": offer["offer_id"],
                "offer_name": offer_names.get(offer["offer_id"]),
                "share": offer.get("share"),
                "state": offer.get("state"),
            }
            for offer in stream.get("offers") or []
        ],
    }


def get_campaign_streams(client: KeitaroClient, campaign_id: int) -> dict:
    """Данные страницы потоков: кампания + нормализованные потоки (сортировка по позиции)."""
    campaign = client.get_campaign(campaign_id)
    streams = client.get_campaign_streams(campaign_id)
    offer_names = {offer.get("id"): offer.get("name") for offer in client.list_offers()}
    normalized = [normalize_stream(stream, offer_names) for stream in streams]
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

    offers — полный желаемый набор активных офферов: [{offer_id, share}].
    """
    stream = client.get_stream(stream_id)
    if stream.get("campaign_id") != campaign_id:
        raise StreamNotFoundError(f"Поток {stream_id} не относится к кампании {campaign_id}")

    payload = {**stream}
    active = [
        {"offer_id": item["offer_id"], "share": item["share"], "state": "active"}
        for item in offers
    ]
    if REMOVED_OFFERS_STRATEGY == "disable":
        active_ids = {item["offer_id"] for item in offers}
        disabled = [
            {"offer_id": existing["offer_id"], "share": 0, "state": "disabled"}
            for existing in stream.get("offers") or []
            if existing.get("offer_id") not in active_ids
        ]
        payload["offers"] = active + disabled
    else:
        payload["offers"] = active
    return client.update_stream(stream_id, payload)
