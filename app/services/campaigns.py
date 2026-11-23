"""Связь существующих кампаний Keitaro с приложением.

Локальная база хранит только маппинг uuid -> keitaro_campaign_id. Кампании,
созданные мимо приложения, тоже можно открыть в редакторе — для этого их
достаточно один раз связать по id.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.keitaro.client import KeitaroClient
from app.keitaro.exceptions import KeitaroNotFoundError
from app.models import Campaign


class KeitaroCampaignNotFound(Exception):
    """Кампании с таким id в Keitaro нет."""


def link_keitaro_campaign(
    db: Session, client: KeitaroClient, keitaro_campaign_id: int
) -> Campaign:
    """Связать кампанию Keitaro с приложением и вернуть её локальную запись.

    Кампания берётся из Keitaro (имя — оттуда же). Повторный вызов с тем же id
    возвращает уже существующую запись, а не создаёт вторую.
    """
    try:
        keitaro_campaign = client.get_campaign(keitaro_campaign_id)
    except KeitaroNotFoundError as exc:
        raise KeitaroCampaignNotFound(
            f"Кампания {keitaro_campaign_id} не найдена в Keitaro"
        ) from exc

    campaign = (
        db.query(Campaign)
        .filter(Campaign.keitaro_campaign_id == keitaro_campaign_id)
        .first()
    )
    if campaign is None:
        campaign = Campaign(
            name=str(keitaro_campaign.get("name") or f"campaign {keitaro_campaign_id}"),
            keitaro_campaign_id=keitaro_campaign_id,
        )
        db.add(campaign)
        db.commit()
    return campaign
