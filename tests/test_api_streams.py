"""Тесты GET/PUT потоков кампании — на моках KeitaroStub + локальная in-memory БД."""

import uuid
from contextlib import contextmanager

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import get_keitaro_client
from app.config import Settings, get_settings
from app.db import get_db
from app.keitaro.client import KeitaroClient
from app.main import app
from app.models import Base, Campaign
from app.services import streams as streams_service
from tests.keitaro_stub import KeitaroStub
from tests.test_campaign_creator import TEST_API_KEY


@contextmanager
def streams_env_ctx(load_fixture, *, streams: list[dict]):
    """TestClient с локальной БД (одна кампания -> Keitaro 301) и мок-клиентом Keitaro."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    campaign = Campaign(name="test_iv_campaign1", keitaro_campaign_id=301)
    db.add(campaign)
    db.commit()
    campaign_uuid = str(campaign.id)

    stub = KeitaroStub(
        offers=load_fixture("offers"),
        campaigns=[{"id": 301, "name": "test_iv_campaign1"}],
        streams=streams,
    )
    settings = Settings(
        KT_BASE_URL="https://kt.test", KT_API_KEY=TEST_API_KEY, DATABASE_URL="sqlite://"
    )
    override_client = KeitaroClient(settings=settings, transport=httpx.MockTransport(stub.handler))
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_keitaro_client] = lambda: override_client
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        yield stub, TestClient(app), campaign_uuid
    finally:
        app.dependency_overrides.clear()
        override_client.close()
        db.close()


@pytest.fixture()
def streams_env(load_fixture):
    with streams_env_ctx(load_fixture, streams=load_fixture("streams")) as env:
        yield env


def put_requests(stub: KeitaroStub, path: str) -> list[tuple[str, dict | None]]:
    return [(method, payload) for method, payload in stub.requests_to(path) if method == "PUT"]


# ----------------------------------------------------------------------
# GET: нормализация потоков
# ----------------------------------------------------------------------


def test_get_streams_normalized(streams_env):
    _, client, campaign_uuid = streams_env
    resp = client.get(f"/api/campaigns/{campaign_uuid}/streams")

    assert resp.status_code == 200
    body = resp.json()
    assert body["campaign"] == {
        "name": "test_iv_campaign1",
        "keitaro_id": 301,
        "admin_url": "https://kt.test/admin/#/campaigns/301",
    }
    # сортировка по позиции
    assert [s["stream_id"] for s in body["streams"]] == [501, 502]

    flow1, flow2 = body["streams"]
    # redirect-поток: фильтр строкой -> массив кодов, офферов нет
    assert flow1["schema"] == "redirect"
    assert flow1["filter"] == {"name": "country", "mode": "accept", "payload": ["MX", "AU", "RO"]}
    assert flow1["offers"] == []
    # landings-поток: имя оффера склеено по offer_id
    assert flow2["schema"] == "landings"
    assert flow2["filter"] is None
    assert flow2["offers"] == [
        {"offer_id": 101, "offer_name": "Sweeper MX", "share": 100, "state": "active"}
    ]


def test_get_streams_unknown_campaign(streams_env):
    _, client, _ = streams_env
    resp = client.get(f"/api/campaigns/{uuid.uuid4()}/streams")

    assert resp.status_code == 404
    assert "не найдена" in resp.json()["detail"]


# ----------------------------------------------------------------------
# PUT: подмена offers с сохранением остальных полей потока
# ----------------------------------------------------------------------


def test_put_stream_replaces_offers_keeps_other_fields(streams_env):
    stub, client, campaign_uuid = streams_env
    resp = client.put(
        f"/api/campaigns/{campaign_uuid}/streams/502",
        json={"offers": [{"offer_id": 102, "share": 100}]},
    )

    assert resp.status_code == 200
    puts = put_requests(stub, "/streams/502")
    assert len(puts) == 1
    _, payload = puts[0]
    # существующие поля потока сохранены, offers подменён (стратегия omit: только активные)
    assert payload["schema"] == "landings"
    assert payload["campaign_id"] == 301
    assert payload["name"] == "Flow 2"
    assert payload["collect_clicks"] is True
    assert payload["offers"] == [{"offer_id": 102, "share": 100, "state": "active"}]
    # ответ — обновлённый поток из Keitaro
    assert resp.json()["offers"] == payload["offers"]


def test_put_removed_disabled_when_merge_strategy(streams_env, monkeypatch):
    monkeypatch.setattr(streams_service, "REMOVED_OFFERS_STRATEGY", "disable")
    stub, client, campaign_uuid = streams_env
    resp = client.put(
        f"/api/campaigns/{campaign_uuid}/streams/502",
        json={"offers": [{"offer_id": 102, "share": 100}]},
    )

    assert resp.status_code == 200
    _, payload = put_requests(stub, "/streams/502")[0]
    # не вошедшие в набор офферы уходят disabled с долей 0
    assert payload["offers"] == [
        {"offer_id": 102, "share": 100, "state": "active"},
        {"offer_id": 101, "share": 0, "state": "disabled"},
    ]


def test_put_stream_of_other_campaign_404(load_fixture):
    foreign = {**load_fixture("streams")[1], "campaign_id": 999}
    with streams_env_ctx(load_fixture, streams=[foreign]) as (stub, client, campaign_uuid):
        resp = client.put(
            f"/api/campaigns/{campaign_uuid}/streams/502",
            json={"offers": [{"offer_id": 102, "share": 100}]},
        )

    assert resp.status_code == 404
    assert "не относится к кампании" in resp.json()["detail"]
    assert put_requests(stub, "/streams/502") == []


def test_put_unknown_stream_404(streams_env):
    _, client, campaign_uuid = streams_env
    resp = client.put(
        f"/api/campaigns/{campaign_uuid}/streams/999",
        json={"offers": []},
    )

    assert resp.status_code == 404
    assert "не найден" in resp.json()["detail"]


def test_put_unknown_campaign_404(streams_env):
    _, client, _ = streams_env
    resp = client.put(
        f"/api/campaigns/{uuid.uuid4()}/streams/502",
        json={"offers": []},
    )

    assert resp.status_code == 404
    assert "не найдена" in resp.json()["detail"]
