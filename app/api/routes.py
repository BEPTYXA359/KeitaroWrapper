"""REST-роуты: /api/*."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.keitaro.client import KeitaroClient
from app.keitaro.exceptions import KeitaroApiError, KeitaroNotFoundError
from app.models import Campaign
from app.services.campaign_creator import (
    OFFERS_SEARCH_LIMIT,
    CampaignValidationError,
    OfferNotFoundError,
    campaign_admin_url,
    create_campaign,
)
from app.services.streams import (
    StreamNotFoundError,
    get_campaign_streams as fetch_campaign_streams,
    update_stream_offers as put_stream_offers,
)

router = APIRouter(prefix="/api")


def get_keitaro_client() -> "KeitaroClient":
    """FastAPI-зависимость: клиент Keitaro на время запроса."""
    return KeitaroClient(get_settings())


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Живость приложения + проверка коннекта к БД."""
    db.connection()  # достаточно проверить, что соединение с БД устанавливается
    return {"status": "ok", "database": "ok"}


@router.get("/config")
def config(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    """Константы для UI (префикс имён кампаний)."""
    return {"campaign_prefix": settings.CAMPAIGN_PREFIX}


# ----------------------------------------------------------------------
# Кампании
# ----------------------------------------------------------------------


class CampaignCreateRequest(BaseModel):
    name: str
    geo: str
    offer_id: int


@router.post("/campaigns", status_code=201)
def create_campaign_endpoint(
    payload: CampaignCreateRequest,
    db: Session = Depends(get_db),
    client: KeitaroClient = Depends(get_keitaro_client),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Создать кампанию в Keitaro (Flow 1 redirect + Flow 2 landings)."""
    try:
        created = create_campaign(
            db, client, settings, payload.name, payload.geo, payload.offer_id
        )
    except CampaignValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OfferNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except KeitaroApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    campaign = created.campaign
    return {
        "uuid": str(campaign.id),
        "keitaro_campaign_id": campaign.keitaro_campaign_id,
        "name": campaign.name,
        "streams_created": created.streams_created,
        "admin_url": created.admin_url,
    }


# ----------------------------------------------------------------------
# Потоки кампании (редактор)
# ----------------------------------------------------------------------


def _get_campaign_or_404(db: Session, campaign_uuid: UUID) -> Campaign:
    campaign = db.get(Campaign, campaign_uuid)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Кампания не найдена")
    if campaign.keitaro_campaign_id is None:
        raise HTTPException(status_code=404, detail="Кампания не связана с Keitaro")
    return campaign


@router.get("/campaigns/{campaign_uuid}/streams")
def get_campaign_streams_endpoint(
    campaign_uuid: UUID,
    db: Session = Depends(get_db),
    client: KeitaroClient = Depends(get_keitaro_client),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Нормализованные потоки кампании (состояние всегда из Keitaro)."""
    campaign = _get_campaign_or_404(db, campaign_uuid)
    try:
        data = fetch_campaign_streams(client, campaign.keitaro_campaign_id)
    except KeitaroNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Кампания {campaign.keitaro_campaign_id} не найдена в Keitaro",
        ) from exc
    except KeitaroApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    data["campaign"]["admin_url"] = campaign_admin_url(
        settings, campaign.keitaro_campaign_id
    )
    return data


class OfferShare(BaseModel):
    offer_id: int
    share: int


class StreamOffersUpdate(BaseModel):
    offers: list[OfferShare]


@router.put("/campaigns/{campaign_uuid}/streams/{stream_id}")
def update_stream_offers_endpoint(
    campaign_uuid: UUID,
    stream_id: int,
    payload: StreamOffersUpdate,
    db: Session = Depends(get_db),
    client: KeitaroClient = Depends(get_keitaro_client),
) -> dict[str, Any]:
    """Заменить offers потока; остальные поля потока сохраняются как были."""
    campaign = _get_campaign_or_404(db, campaign_uuid)
    offers = [{"offer_id": item.offer_id, "share": item.share} for item in payload.offers]
    try:
        return put_stream_offers(client, campaign.keitaro_campaign_id, stream_id, offers)
    except StreamNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except KeitaroNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail=f"Поток {stream_id} не найден в Keitaro"
        ) from exc
    except KeitaroApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# ----------------------------------------------------------------------
# Офферы: поиск для автокомплита
# ----------------------------------------------------------------------


@router.get("/offers/search")
def search_offers(
    q: str = "",
    client: KeitaroClient = Depends(get_keitaro_client),
) -> list[dict[str, Any]]:
    """Офферы Keitaro, отфильтрованные по q (id и название), лимит 15."""
    try:
        offers = client.list_offers()
    except KeitaroApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    needle = q.strip().lower()
    result: list[dict[str, Any]] = []
    for offer in offers:
        name = str(offer.get("name", ""))
        if not needle or needle in name.lower() or needle in str(offer.get("id", "")):
            result.append({"id": offer.get("id"), "name": name, "state": offer.get("state")})
        if len(result) >= OFFERS_SEARCH_LIMIT:
            break
    return result
