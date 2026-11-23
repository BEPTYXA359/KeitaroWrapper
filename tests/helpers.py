"""Общие хелперы тестов: изолированные настройки, in-memory БД, TestClient с подменами."""

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import get_keitaro_client
from app.config import Settings, get_settings
from app.db import get_db
from app.keitaro.client import KeitaroClient
from app.main import app
from app.models import Base
from tests.keitaro_stub import KeitaroStub

# Явно тестовое значение Api-Key: sha256-хеш, в коде нет ключей-литералов
TEST_API_KEY = hashlib.sha256(b"keitaro-wrapper-test-only").hexdigest()


def make_settings(**overrides) -> Settings:
    """Настройки, не зависящие от .env и переменных окружения машины."""
    values: dict = {
        "KT_BASE_URL": "https://kt.test",
        "KT_API_KEY": TEST_API_KEY,
        "DATABASE_URL": "sqlite://",
        "CAMPAIGN_PREFIX": "test_",
        "KT_GROUP_NAME": "FORTESTS",
        "KT_SOURCE_NAME": "FORTESTS",
        "KT_DOMAIN_ID": None,
        **overrides,
    }
    return Settings(_env_file=None, **values)


def memory_db() -> Session:
    """Сессия in-memory SQLite с созданными таблицами.

    StaticPool держит одно соединение: роуты выполняются в потоках TestClient,
    и без этого каждый поток получал бы свою пустую базу.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


@contextmanager
def api_client(
    stub: KeitaroStub | None = None,
    *,
    db: Session | None = None,
    settings: Settings | None = None,
    **testclient_options,
) -> Iterator[TestClient]:
    """TestClient с подменёнными зависимостями: Keitaro -> заглушка, настройки и БД -> тестовые.

    stub=None оставляет настоящий клиент Keitaro (для проверки guard по API-ключу).
    """
    settings = settings or make_settings()
    overrides: dict = {get_settings: lambda: settings}
    client: KeitaroClient | None = None
    if stub is not None:
        client = KeitaroClient(settings=settings, transport=httpx.MockTransport(stub.handler))
        overrides[get_keitaro_client] = lambda: client
    if db is not None:
        overrides[get_db] = lambda: db

    app.dependency_overrides.update(overrides)
    try:
        yield TestClient(app, **testclient_options)
    finally:
        for dependency in overrides:
            app.dependency_overrides.pop(dependency, None)
        if client is not None:
            client.close()
