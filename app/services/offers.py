"""Офферы Keitaro для UI: поиск по id/названию и ссылка на URL оффера."""

from __future__ import annotations

from urllib.parse import urlsplit

from app.keitaro.client import KeitaroClient

OFFERS_SEARCH_LIMIT = 15


def offer_preview_url(offer: dict) -> str | None:
    """URL оффера (action_payload) для ссылки «открыть в новой вкладке».

    Значение приходит из Keitaro и попадает в href, поэтому пропускаем только
    абсолютные http/https-адреса без управляющих символов; всё остальное — None.
    """
    payload = str(offer.get("action_payload") or "").strip()
    if not payload or any(ord(ch) < 32 or ord(ch) == 127 for ch in payload):
        return None
    try:
        parts = urlsplit(payload)
    except ValueError:
        return None
    if parts.scheme in ("http", "https") and parts.netloc:
        return payload
    return None


def search_offers(client: KeitaroClient, query: str) -> list[dict]:
    """Офферы Keitaro, где query — подстрока id или названия; лимит OFFERS_SEARCH_LIMIT.

    Keitaro не ищет по названиям, поэтому фильтруем полный список /offers у себя.
    """
    needle = query.strip().lower()
    result: list[dict] = []
    for offer in client.list_offers():
        name = str(offer.get("name", ""))
        if not needle or needle in name.lower() or needle in str(offer.get("id", "")):
            result.append(
                {
                    "id": offer.get("id"),
                    "name": name,
                    "state": offer.get("state"),
                    "preview_url": offer_preview_url(offer),
                }
            )
        if len(result) >= OFFERS_SEARCH_LIMIT:
            break
    return result
