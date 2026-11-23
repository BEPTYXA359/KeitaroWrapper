"""Тесты REST /api/campaigns, /api/offers/search, /api/config — на моках KeitaroStub."""

import uuid
from contextlib import contextmanager

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings, get_settings
from app.db import get_db
from app.keitaro.client import KeitaroClient
from app.main import app
from app.models import Base
from app.api.routes import get_keitaro_client
from tests.keitaro_stub import KeitaroStub
from tests.test_campaign_creator import TEST_API_KEY


@pytest.fixture()
def api_env(load_fixture) -> tuple[KeitaroStub, TestClient]:
    """TestClient с подменёнными клиентом Keitaro (мок-транспорт) и БД (общая in-memory)."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # одна in-memory БД для всех потоков TestClient
    )
    Base.metadata.create_all(engine)
    app.dependency_overrides[get_db] = lambda: sessionmaker(bind=engine)()

    stub = KeitaroStub(
        offers=load_fixture("offers"),
        groups=[load_fixture("group")],
        domains=[load_fixture("domain")],
        traffic_sources=[load_fixture("traffic_source")],
        stream_filters=load_fixture("stream_filters"),
        stream_types=load_fixture("stream_types"),
    )
    settings = Settings(
        KT_BASE_URL="https://kt.test",
        KT_API_KEY=TEST_API_KEY,
        DATABASE_URL="sqlite://",
    )
    override_client = KeitaroClient(settings=settings, transport=httpx.MockTransport(stub.handler))
    app.dependency_overrides[get_keitaro_client] = lambda: override_client
    app.dependency_overrides[get_settings] = lambda: settings
    yield stub, TestClient(app)
    app.dependency_overrides.clear()
    override_client.close()


@pytest.fixture()
def clean_settings(monkeypatch):
    """Гарантированные значения Settings без чтения .env (get_settings кэшируется)."""
    monkeypatch.setenv("CAMPAIGN_PREFIX", "test_")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_create_campaign_endpoint_201(api_env):
    stub, client = api_env
    resp = client.post(
        "/api/campaigns",
        json={"name": "iv_campaign1", "geo": "MX,AU", "offer_id": 101},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["keitaro_campaign_id"] == stub.campaign_id
    assert body["name"] == "test_iv_campaign1"
    assert body["streams_created"] == 2
    assert body["admin_url"] == f"https://kt.test/admin/#/campaigns/{stub.campaign_id}"
    uuid.UUID(body["uuid"])  # валидный UUID, не падает

    assert len(stub.posted("/campaigns")) == 1
    assert len(stub.posted("/streams")) == 2


def test_create_campaign_offer_not_found_404(api_env):
    stub, client = api_env
    resp = client.post(
        "/api/campaigns",
        json={"name": "iv_campaign1", "geo": "MX", "offer_id": 999},
    )

    assert resp.status_code == 404
    assert "Оффер 999 не найден" in resp.json()["detail"]
    assert stub.posted("/campaigns") == []


def test_create_campaign_invalid_geo_400(api_env):
    _, client = api_env
    resp = client.post(
        "/api/campaigns",
        json={"name": "iv_campaign1", "geo": " , , ", "offer_id": 101},
    )

    assert resp.status_code == 400
    assert "Geo пуст" in resp.json()["detail"]


@contextmanager
def mount_stub(stub: KeitaroStub):
    """Подменить клиент Keitaro (и настройки) на мок-версию; без подмены БД."""
    settings = Settings(KT_BASE_URL="https://kt.test", KT_API_KEY=TEST_API_KEY, DATABASE_URL="sqlite://")
    override_client = KeitaroClient(settings=settings, transport=httpx.MockTransport(stub.handler))
    app.dependency_overrides[get_keitaro_client] = lambda: override_client
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        override_client.close()


def test_create_campaign_keitaro_error_502(load_fixture):
    stub = KeitaroStub(
        offers=load_fixture("offers"),
        groups=[load_fixture("group")],
        domains=[load_fixture("domain")],
        traffic_sources=[load_fixture("traffic_source")],
        campaign_post_error=500,
    )
    with mount_stub(stub) as client:
        resp = client.post(
            "/api/campaigns",
            json={"name": "iv_campaign1", "geo": "MX", "offer_id": 101},
        )

    assert resp.status_code == 502
    assert "Internal error" in resp.json()["detail"]


def test_offers_search_filters_by_name(api_env):
    _, client = api_env
    resp = client.get("/api/offers/search", params={"q": "cle"})

    assert resp.status_code == 200
    assert resp.json() == [{"id": 102, "name": "Cleaner AU", "state": "active"}]


def test_offers_search_filters_by_id(api_env):
    _, client = api_env
    resp = client.get("/api/offers/search", params={"q": "101"})

    assert resp.status_code == 200
    assert [item["id"] for item in resp.json()] == [101]


def test_offers_search_empty_q_returns_all(api_env):
    _, client = api_env
    resp = client.get("/api/offers/search")

    assert resp.status_code == 200
    assert [item["id"] for item in resp.json()] == [101, 102]


def test_offers_search_limits_to_15(load_fixture):
    catalog = [
        {**load_fixture("offers")[0], "id": i, "name": f"Bulk offer {i}"}
        for i in range(1, 21)
    ]
    with mount_stub(KeitaroStub(offers=catalog)) as client:
        resp = client.get("/api/offers/search")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 15
    assert [item["id"] for item in body] == list(range(1, 16))


def test_config_returns_campaign_prefix(clean_settings, client):
    resp = client.get("/api/config")

    assert resp.status_code == 200
    assert resp.json() == {"campaign_prefix": "test_"}
