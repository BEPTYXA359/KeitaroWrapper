"""«Создаватор» кампаний: форма -> кампания в Keitaro с двумя правильными потоками.

Flow 1 — редирект на https://google.com/ с фильтром «страны принимать» (geo из формы);
Flow 2 — ротация landings/offers с выбранным оффером на 100%.

Состояние кампаний живёт в Keitaro; локально сохраняем только маппинг
Campaign(uuid, name, keitaro_campaign_id).
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import Settings
from app.keitaro.client import KeitaroClient
from app.keitaro.exceptions import KeitaroNotFoundError
from app.models import Campaign

# Транслит кириллицы для alias (Keitaro ждёт URL-совместимый alias)
_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}

ALIAS_SLUG_MAX_LEN = 16
ALIAS_SUFFIX_LEN = 6
ALIAS_FALLBACK = "campaign"

REDIRECT_URL = "https://google.com/"
STREAM_TYPE = "regular"
REDIRECT_ACTION_TYPE = "http_redirect"
# Поток с ротацией офферов не выполняет действие, но action_type в запросе обязателен
LANDING_ACTION_TYPE = "show_html"


class CampaignCreationError(Exception):
    """Ошибка создания кампании с человекочитаемым текстом (для UI)."""


class CampaignValidationError(CampaignCreationError):
    """Некорректные данные формы (пустое имя, пустой geo...)."""


class OfferNotFoundError(CampaignCreationError):
    """Оффер с таким id в Keitaro не найден."""


@dataclass(frozen=True)
class CreatedCampaign:
    """Результат создания: сущность + ссылки для UI."""

    campaign: Campaign
    admin_url: str
    streams_created: int


def campaign_admin_url(settings: Settings, keitaro_campaign_id: int) -> str:
    """Ссылка на кампанию в админке Keitaro (хост — из KT_BASE_URL, не хардкод)."""
    return settings.KT_BASE_URL.rstrip("/") + f"/admin/#/campaigns/{keitaro_campaign_id}"


# ----------------------------------------------------------------------
# Чистые функции: geo-парсер и alias
# ----------------------------------------------------------------------


def normalize_geo_codes(geo: str) -> list[str]:
    """Строку "MX, AU,RO" -> ["MX", "AU", "RO"] (трим, верхний регистр, дедуп).

    Пустой результат (пустая строка или только запятые) — ошибка валидации.
    """
    codes: list[str] = []
    for part in geo.split(","):
        code = part.strip().upper()
        if code and code not in codes:
            codes.append(code)
    if not codes:
        raise CampaignValidationError(
            "Geo пуст — укажите хотя бы один код страны (например MX,AU,RO)"
        )
    return codes


def generate_alias(name: str) -> str:
    """Alias кампании: транслит + slug до 16 символов + случайный суффикс.

    Суффикс нужен для уникальности: alias в Keitaro глобальный.
    """
    transliterated = "".join(_TRANSLIT.get(ch, ch) for ch in name.lower())
    slug = re.sub(r"[^a-z0-9]+", "-", transliterated).strip("-")
    slug = slug[:ALIAS_SLUG_MAX_LEN].rstrip("-") or ALIAS_FALLBACK
    suffix = "".join(
        random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=ALIAS_SUFFIX_LEN)
    )
    return f"{slug}-{suffix}"


# ----------------------------------------------------------------------
# Каталоги Keitaro: имена country-фильтра и типа редиректа
# ----------------------------------------------------------------------


def _country_filter_name(client: KeitaroClient) -> str:
    """Имя country-фильтра из GET /stream_filters (value == "country")."""
    filters = client.list_stream_filters()
    for item in filters:
        if item.get("value") == "country":
            return str(item["value"])
    # запасной вариант: первый geo-фильтр каталога, иначе стандартное имя
    for item in filters:
        if item.get("group") == "geo":
            return str(item.get("value", "country"))
    return "country"


def _redirect_action_type(client: KeitaroClient) -> str:
    """Тип редиректа из GET /stream_types.

    Точное совпадение важнее перебора: «redirect» есть и в других ключах каталога
    (например, редирект на URL оффера), а его порядок не гарантирован.
    """
    keys = [str(item.get("key", "")) for item in client.list_stream_types()]
    if REDIRECT_ACTION_TYPE in keys:
        return REDIRECT_ACTION_TYPE
    for key in keys:
        if "redirect" in key and "offer" not in key:
            return key
    return REDIRECT_ACTION_TYPE


# ----------------------------------------------------------------------
# Группа / источник / домен: найти или создать
# ----------------------------------------------------------------------


def _ensure_group(client: KeitaroClient, name: str) -> int | str:
    for group in client.list_groups():
        if group.get("name") == name:
            return group["id"]
    return client.create_group(name)["id"]


def _ensure_traffic_source(client: KeitaroClient, name: str) -> int | str:
    for source in client.list_traffic_sources():
        if source.get("name") == name:
            return source["id"]
    # минимально валидный payload: name обязателен, postback_url пустым валиден
    return client.create_traffic_source({"name": name, "postback_url": ""})["id"]


def _resolve_domain_id(client: KeitaroClient, settings: Settings) -> int:
    if settings.KT_DOMAIN_ID is not None:
        return settings.KT_DOMAIN_ID
    domains = client.list_domains()
    for domain in domains:
        if domain.get("state") == "active":
            return domain["id"]
    raise CampaignValidationError("В Keitaro нет активных доменов — создание невозможно")


# ----------------------------------------------------------------------
# Главная функция
# ----------------------------------------------------------------------


def create_campaign(
    db: Session,
    client: KeitaroClient,
    settings: Settings,
    name: str,
    geo: str,
    offer_id: int,
) -> CreatedCampaign:
    """Создать кампанию в Keitaro с двумя потоками и сохранить локальный маппинг.

    Ошибки наружу: CampaignValidationError/OfferNotFoundError (человекочитаемые)
    и KeitaroApiError от клиента — API превращает их в 502/504 с текстом для пользователя.

    Частичный сбой не компенсируется: если POST /campaigns прошёл, а один из
    POST /streams упал, кампания остаётся в Keitaro без локального маппинга —
    смотреть и доудалять вручную в админке.
    """
    clean_name = name.strip()
    if not clean_name:
        raise CampaignValidationError("Name пуст — укажите название кампании")
    geo_codes = normalize_geo_codes(geo)

    try:
        offer = client.get_offer(offer_id)
    except KeitaroNotFoundError as exc:
        raise OfferNotFoundError(f"Оффер {offer_id} не найден") from exc

    group_id = _ensure_group(client, settings.KT_GROUP_NAME)
    source_id = _ensure_traffic_source(client, settings.KT_SOURCE_NAME)
    domain_id = _resolve_domain_id(client, settings)
    final_name = settings.CAMPAIGN_PREFIX + clean_name

    campaign = client.create_campaign(
        {
            "name": final_name,
            "alias": generate_alias(clean_name),
            # group_id в Keitaro — строка, не int
            "group_id": str(group_id),
            "traffic_source_id": source_id,
            "domain_id": domain_id,
            "type": "position",
            "cost_type": "CPC",
            "cost_currency": "USD",
            "cost_value": 0,
            "cost_auto": True,
            "state": "active",
        }
    )
    keitaro_campaign_id = campaign["id"]

    client.create_stream(
        {
            "campaign_id": keitaro_campaign_id,
            "name": "Flow 1",
            "type": STREAM_TYPE,
            "position": 1,
            "schema": "redirect",
            "action_type": _redirect_action_type(client),
            "action_options": {"url": REDIRECT_URL},
            "filters": [
                {
                    "name": _country_filter_name(client),
                    "mode": "accept",
                    "payload": geo_codes,
                }
            ],
            "collect_clicks": True,
            "state": "active",
        }
    )
    client.create_stream(
        {
            "campaign_id": keitaro_campaign_id,
            "name": "Flow 2",
            "type": STREAM_TYPE,
            "position": 2,
            "schema": "landings",
            "action_type": LANDING_ACTION_TYPE,
            "offers": [{"offer_id": offer["id"], "share": 100}],
            "collect_clicks": True,
            "state": "active",
        }
    )

    record = Campaign(name=final_name, keitaro_campaign_id=keitaro_campaign_id)
    db.add(record)
    db.commit()

    admin_url = campaign_admin_url(settings, keitaro_campaign_id)
    return CreatedCampaign(campaign=record, admin_url=admin_url, streams_created=2)
