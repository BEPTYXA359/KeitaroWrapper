"""Слой работы с Keitaro Admin API (транспорт и маппинг ошибок)."""

from app.keitaro.client import KeitaroClient
from app.keitaro.exceptions import (
    KeitaroApiError,
    KeitaroNotFoundError,
    KeitaroTimeoutError,
)

__all__ = [
    "KeitaroClient",
    "KeitaroApiError",
    "KeitaroNotFoundError",
    "KeitaroTimeoutError",
]
