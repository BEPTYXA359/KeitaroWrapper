"""Тесты REST /api/campaigns, /api/offers/search, /api/config — на моках KeitaroStub."""

import uuid
from contextlib import contextmanager
from datetime import UTC, datetime

import pytest

from app.config import get_settings
from app.models import Campaign
from tests.helpers import api_client, memory_db
from tests.keitaro_stub import KeitaroStub


@pytest.fixture()
def env(stand):
    """Заглушка Keitaro + TestClient с in-memory БД."""
    with api_client(stand, db=memory_db()) as client:
        yield stand, client


@pytest.fixture()
def clean_settings(monkeypatch):
    """Гарантированные значения Settings без чтения .env (get_settings кэшируется)."""
    monkeypatch.setenv("CAMPAIGN_PREFIX", "test_")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ----------------------------------------------------------------------
# POST /api/campaigns
# ----------------------------------------------------------------------


def test_create_campaign_endpoint_201(env):
    stand, client = env
    resp = client.post(
        "/api/campaigns",
        json={"name": "iv_campaign1", "geo": "MX,AU", "offer_id": 101},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body == {
        "uuid": body["uuid"],
        "keitaro_campaign_id": stand.campaign_id,
        "name": "test_iv_campaign1",
        "streams_created": 2,
        "admin_url": f"https://kt.test/admin/#/campaigns/{stand.campaign_id}",
    }
    uuid.UUID(body["uuid"])  # валидный UUID, не падает

    assert len(stand.posted("/campaigns")) == 1
    assert len(stand.posted("/streams")) == 2


def test_create_campaign_offer_not_found_404(env):
    stand, client = env
    resp = client.post(
        "/api/campaigns",
        json={"name": "iv_campaign1", "geo": "MX", "offer_id": 999},
    )

    assert resp.status_code == 404
    assert "Оффер 999 не найден" in resp.json()["detail"]
    assert stand.posted("/campaigns") == []


def test_create_campaign_invalid_geo_400(env):
    _, client = env
    resp = client.post(
        "/api/campaigns",
        json={"name": "iv_campaign1", "geo": " , , ", "offer_id": 101},
    )

    assert resp.status_code == 400
    assert "Geo пуст" in resp.json()["detail"]


def test_create_campaign_keitaro_error_502(stand):
    stub = KeitaroStub(
        offers=stand.offers,
        groups=stand.groups,
        domains=stand.domains,
        traffic_sources=stand.traffic_sources,
        fail={"POST /campaigns": 500},
    )
    with api_client(stub, db=memory_db()) as client:
        resp = client.post(
            "/api/campaigns",
            json={"name": "iv_campaign1", "geo": "MX", "offer_id": 101},
        )

    assert resp.status_code == 502
    assert "HTTP 500" in resp.json()["detail"]
    # кампания создана в Keitaro частично (потоки не отправлялись), локально ничего не сохранено
    assert stub.posted("/streams") == []


# ----------------------------------------------------------------------
# GET /api/campaigns: список созданных кампаний
# ----------------------------------------------------------------------


def test_list_campaigns_empty(env):
    _, client = env
    resp = client.get("/api/campaigns")

    assert resp.status_code == 200
    assert resp.json() == []


def test_list_campaigns_newest_first_with_links(stand):
    db = memory_db()
    older = Campaign(
        name="test_one", keitaro_campaign_id=301, created_at=datetime(2026, 11, 1, 10, tzinfo=UTC)
    )
    newer = Campaign(
        name="test_two", keitaro_campaign_id=302, created_at=datetime(2026, 11, 2, 10, tzinfo=UTC)
    )
    db.add_all([older, newer])
    db.commit()
    with api_client(stand, db=db) as client:
        resp = client.get("/api/campaigns")

    assert resp.status_code == 200
    body = resp.json()
    assert body == [
        {
            "uuid": str(newer.id),
            "name": "test_two",
            "keitaro_campaign_id": 302,
            "created_at": "2026-11-02T10:00:00+00:00",
            "admin_url": "https://kt.test/admin/#/campaigns/302",
        },
        {
            "uuid": str(older.id),
            "name": "test_one",
            "keitaro_campaign_id": 301,
            "created_at": "2026-11-01T10:00:00+00:00",
            "admin_url": "https://kt.test/admin/#/campaigns/301",
        },
    ]


def test_list_campaigns_without_keitaro_id_has_no_admin_link(stand):
    db = memory_db()
    local_only = Campaign(name="local only", keitaro_campaign_id=None)
    db.add(local_only)
    db.commit()
    with api_client(stand, db=db) as client:
        resp = client.get("/api/campaigns")

    assert resp.status_code == 200
    assert [item["admin_url"] for item in resp.json()] == [None]


# ----------------------------------------------------------------------
# POST /api/campaigns/link: открытие кампании, созданной мимо приложения
# ----------------------------------------------------------------------


@contextmanager
def link_env(campaigns: list[dict], fail: dict[str, int | str] | None = None):
    """Keitaro с заданными кампаниями + пустая локальная база."""
    stub = KeitaroStub(campaigns=campaigns, fail=fail)
    with api_client(stub, db=memory_db()) as client:
        yield client


def test_link_existing_keitaro_campaign_opens_it_in_editor():
    with link_env([{"id": 301, "name": "Created in Keitaro"}]) as client:
        resp = client.post("/api/campaigns/link", json={"keitaro_campaign_id": 301})

        assert resp.status_code == 200
        body = resp.json()
        assert body == {
            "uuid": body["uuid"],
            "name": "Created in Keitaro",
            "keitaro_campaign_id": 301,
            "created_at": body["created_at"],
            "admin_url": "https://kt.test/admin/#/campaigns/301",
        }
        uuid.UUID(body["uuid"])
        # связанная кампания открывается в редакторе и попадает в список
        streams = client.get(f"/api/campaigns/{body['uuid']}/streams")
        assert streams.status_code == 200
        assert streams.json()["campaign"]["name"] == "Created in Keitaro"
        assert [item["uuid"] for item in client.get("/api/campaigns").json()] == [body["uuid"]]


def test_link_same_campaign_twice_keeps_one_record():
    with link_env([{"id": 301, "name": "Created in Keitaro"}]) as client:
        first = client.post("/api/campaigns/link", json={"keitaro_campaign_id": 301}).json()
        second = client.post("/api/campaigns/link", json={"keitaro_campaign_id": 301}).json()

        assert second == first
        assert len(client.get("/api/campaigns").json()) == 1


def test_link_unknown_campaign_404():
    with link_env([{"id": 301, "name": "Created in Keitaro"}]) as client:
        resp = client.post("/api/campaigns/link", json={"keitaro_campaign_id": 999})

        assert resp.status_code == 404
        assert "Кампания 999 не найдена в Keitaro" in resp.json()["detail"]
        assert client.get("/api/campaigns").json() == []


@pytest.mark.parametrize("value", [0, -5, "abc"])
def test_link_rejects_invalid_id(value):
    with link_env([]) as client:
        resp = client.post("/api/campaigns/link", json={"keitaro_campaign_id": value})

        assert resp.status_code == 422
        assert "keitaro_campaign_id" in resp.json()["detail"]


def test_link_keitaro_down_is_502_and_stores_nothing():
    with link_env([{"id": 301, "name": "x"}], fail={"GET /campaigns/301": 503}) as client:
        resp = client.post("/api/campaigns/link", json={"keitaro_campaign_id": 301})

        assert resp.status_code == 502
        assert "HTTP 503" in resp.json()["detail"]
        assert client.get("/api/campaigns").json() == []


# ----------------------------------------------------------------------
# GET /api/offers/search
# ----------------------------------------------------------------------


def test_offers_search_filters_by_name(env):
    _, client = env
    resp = client.get("/api/offers/search", params={"q": "cle"})

    assert resp.status_code == 200
    assert resp.json() == [{"id": 102, "name": "Cleaner AU", "state": "active", "preview_url": None}]


def test_offers_search_filters_by_id(env):
    _, client = env
    resp = client.get("/api/offers/search", params={"q": "101"})

    assert resp.status_code == 200
    assert [item["id"] for item in resp.json()] == [101]


def test_offers_search_empty_q_returns_all(env):
    _, client = env
    resp = client.get("/api/offers/search")

    assert resp.status_code == 200
    assert [item["id"] for item in resp.json()] == [101, 102]


def test_offers_search_limits_to_15(stand):
    catalog = [
        {**stand.offers[0], "id": i, "name": f"Bulk offer {i}"}
        for i in range(1, 21)
    ]
    with api_client(KeitaroStub(offers=catalog)) as client:
        resp = client.get("/api/offers/search")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 15
    assert [item["id"] for item in body] == list(range(1, 16))


@pytest.mark.parametrize(
    ("action_payload", "expected"),
    [
        ("https://offers.example/click?id=1", "https://offers.example/click?id=1"),
        ("  http://offers.example/click  ", "http://offers.example/click"),
        ("javascript:alert(1)", None),
        ("data:text/html,hello", None),
        ("ftp://offers.example/file", None),
        ("https:///no-host", None),
        ("https://bad\x7fhost.example", None),
        ("", None),
        (None, None),
    ],
)
def test_offers_search_preview_url_only_for_clean_http(stand, action_payload, expected):
    offer = {**stand.offers[0], "id": 7, "action_type": "url", "action_payload": action_payload}
    with api_client(KeitaroStub(offers=[offer])) as client:
        resp = client.get("/api/offers/search")

    assert resp.json()[0]["preview_url"] == expected


# ----------------------------------------------------------------------
# GET /api/config
# ----------------------------------------------------------------------


def test_config_returns_campaign_prefix(clean_settings, client):
    resp = client.get("/api/config")

    assert resp.status_code == 200
    assert resp.json() == {"campaign_prefix": "test_"}
