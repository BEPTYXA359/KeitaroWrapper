"""Модели SQLAlchemy."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Campaign(Base):
    """Локальный маппинг: наш UUID ↔ кампания в Keitaro.

    Состояние кампаний всегда живёт в Keitaro; локальная БД — только ссылка.
    """

    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    keitaro_campaign_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return f"<Campaign id={self.id} name={self.name!r} keitaro_id={self.keitaro_campaign_id}>"


class StreamOfferMemory(Base):
    """Память о составе потоков: какие офферы когда-либо видели в потоке кампании.

    Ручное удаление в админке Keitaro вычёркивает оффер из потока целиком — по этой
    таблице бэк узнаёт «пропавших» и отдаёт их UI со state "deleted" («0% +
    BRING BACK»), а PUSH восстанавливает их в Keitaro как disabled с долей 0.
    """

    __tablename__ = "stream_offer_memory"
    __table_args__ = (
        UniqueConstraint("campaign_id", "keitaro_stream_id", "offer_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id"), nullable=False)
    keitaro_stream_id: Mapped[int] = mapped_column(Integer, nullable=False)
    offer_id: Mapped[int] = mapped_column(Integer, nullable=False)
    offer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<StreamOfferMemory stream={self.keitaro_stream_id} "
            f"offer={self.offer_id} name={self.offer_name!r}>"
        )
