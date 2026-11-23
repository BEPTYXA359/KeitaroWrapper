"""REST-роуты: /api/*."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.keitaro.client import KeitaroClient
from app.keitaro.exceptions import KeitaroApiError
from app.services.campaign_creator import (
    OFFERS_SEARCH_LIMIT,
    CampaignValidationError,
    OfferNotFoundError,
    create_campaign,
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
