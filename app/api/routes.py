"""REST-роуты: /api/*."""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db

router = APIRouter(prefix="/api")


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Живость приложения + проверка коннекта к БД."""
    db.connection()  # достаточно проверить, что соединение с БД устанавливается
    return {"status": "ok", "database": "ok"}
