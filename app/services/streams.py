"""Чтение и правка потоков кампании.

Состояние потоков всегда тянется из Keitaro; локальная БД хранит маппинг
uuid -> keitaro_campaign_id и память о составе потоков (StreamOfferMemory).
GET нормализует ответы Keitaro для UI (payload фильтра строкой -> массив кодов,
к офферам потока подтягиваются название и URL из /offers), PUT меняет только
offers потока, сохраняя остальные поля как были.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.keitaro.client import KeitaroClient
from app.models import Campaign, StreamOfferMemory
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


def get_campaign_streams(db: Session, client: KeitaroClient, campaign: Campaign) -> dict:
    """Данные страницы потоков: кампания + нормализованные потоки (сортировка по позиции).

    Состав потоков сверяется с памятью (StreamOfferMemory): офферы, которые раньше
    видели в потоке, а в ответе Keitaro их уже нет (удалены в админке вручную),
    отдаются со state "deleted" — UI показывает «0% + BRING BACK». Память при этом
    пополняется актуальным составом.
    """
    campaign_id = campaign.keitaro_campaign_id
    kt_campaign = client.get_campaign(campaign_id)
    streams = client.get_campaign_streams(campaign_id)
    offers = {offer.get("id"): offer for offer in client.list_offers()}

    memory = (
        db.query(StreamOfferMemory)
        .filter(StreamOfferMemory.campaign_id == campaign.id)
        .all()
    )
    seen: dict[int, dict[int, str | None]] = {}
    for row in memory:
        seen.setdefault(row.keitaro_stream_id, {})[row.offer_id] = row.offer_name

    normalized = []
    for stream in streams:
        stream_id = stream["id"]
        result = normalize_stream(stream, offers)
        present_ids = {item["offer_id"] for item in result["offers"]}
        for offer_id, name in seen.get(stream_id, {}).items():
            if offer_id in present_ids:
                continue
            catalog = offers.get(offer_id) or {}
            result["offers"].append(
                {
                    "offer_id": offer_id,
                    "offer_name": name if name is not None else catalog.get("name"),
                    "preview_url": offer_preview_url(catalog),
                    "share": 0,
                    "state": "deleted",
                }
            )
        # union памяти: имена виденных офферов обновляем свежими из ответа
        stream_seen = seen.setdefault(stream_id, {})
        for item in result["offers"]:
            stream_seen[item["offer_id"]] = item["offer_name"]
        normalized.append(result)
    normalized.sort(key=lambda item: (item["position"] is None, item["position"] or 0))

    _sync_memory(db, campaign.id, seen)
    return {
        "campaign": {"name": kt_campaign.get("name"), "keitaro_id": kt_campaign.get("id")},
        "streams": normalized,
    }


def _sync_memory(
    db: Session, campaign_id: int, seen: dict[int, dict[int, str | None]]
) -> None:
    """Догрузить в память новые (stream_id, offer_id) и обновить имена виденных."""
    stored = {
        (row.keitaro_stream_id, row.offer_id): row
        for row in db.query(StreamOfferMemory)
        .filter(StreamOfferMemory.campaign_id == campaign_id)
        .all()
    }
    for stream_id, offers_map in seen.items():
        for offer_id, name in offers_map.items():
            row = stored.get((stream_id, offer_id))
            if row is None:
                db.add(
                    StreamOfferMemory(
                        campaign_id=campaign_id,
                        keitaro_stream_id=stream_id,
                        offer_id=offer_id,
                        offer_name=name,
                    )
                )
            elif row.offer_name != name and name is not None:
                row.offer_name = name
    db.commit()


def update_stream_offers(
    db: Session,
    client: KeitaroClient,
    campaign: Campaign,
    stream_id: int,
    offers: list[dict],
) -> dict:
    """Заменить offers потока (GET текущего -> подмена -> PUT), вернуть обновленный поток.

    offers — полный набор активных офферов: [{offer_id, share}]. Остальные офферы
    потока отправляются отключёнными (см. REMOVED_OFFERS_STRATEGY). «Пропавшие» —
    офферы из памяти потока, которых в Keitaro нет (удалены в админке вручную) —
    тоже дописываются как disabled с долей 0: после PUT Keitaro снова их хранит.
    """
    stream = client.get_stream(stream_id)
    if stream.get("campaign_id") != campaign.keitaro_campaign_id:
        raise StreamNotFoundError(
            f"Поток {stream_id} не относится к кампании {campaign.keitaro_campaign_id}"
        )

    payload = {**stream}
    active = [
        {"offer_id": item["offer_id"], "share": item["share"], "state": "active"}
        for item in offers
    ]
    if REMOVED_OFFERS_STRATEGY == "omit":
        payload["offers"] = active
    else:
        active_ids = {item["offer_id"] for item in offers}
        existing_ids = {existing["offer_id"] for existing in stream.get("offers") or []}
        disabled = [
            {"offer_id": existing["offer_id"], "share": 0, "state": "disabled"}
            for existing in stream.get("offers") or []
            if existing.get("offer_id") not in active_ids
        ]
        ghost_ids = {
            row.offer_id
            for row in db.query(StreamOfferMemory)
            .filter(
                StreamOfferMemory.campaign_id == campaign.id,
                StreamOfferMemory.keitaro_stream_id == stream_id,
            )
            .all()
            if row.offer_id not in active_ids and row.offer_id not in existing_ids
        }
        restored = [
            {"offer_id": offer_id, "share": 0, "state": "disabled"}
            for offer_id in sorted(ghost_ids)
        ]
        payload["offers"] = active + disabled + restored
    return client.update_stream(stream_id, payload)
