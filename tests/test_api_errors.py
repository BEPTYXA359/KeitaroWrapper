"""Как API отдаёт ошибки: всегда JSON {"detail": <текст для человека>}, без трассировок."""

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.errors import register_error_handlers
from app.api.routes import get_keitaro_client
from app.keitaro.client import KeitaroClient
from tests.helpers import api_client, memory_db, make_settings
from tests.keitaro_stub import KeitaroStub

OFFERS_SEARCH = "GET /offers"


@pytest.mark.parametrize(
    ("planned", "status", "hint"),
    [
        ("timeout", 504, "Keitaro не ответил"),
        (401, 502, "KT_API_KEY"),
        (403, 502, "KT_API_KEY"),
        (404, 502, "KT_BASE_URL"),
        (500, 502, "HTTP 500"),
        (503, 502, "HTTP 503"),
    ],
)
def test_keitaro_failure_is_readable_json(planned, status, hint):
    stub = KeitaroStub(fail={OFFERS_SEARCH: planned})
    with api_client(stub) as client:
        resp = client.get("/api/offers/search")

    assert resp.status_code == status
    assert list(resp.json()) == ["detail"]
    assert hint in resp.json()["detail"]
    assert "Traceback" not in resp.text


def test_keitaro_unreachable_is_502_without_doubled_text():
    stub = KeitaroStub(fail={OFFERS_SEARCH: "connect"})
    with api_client(stub) as client:
        resp = client.get("/api/offers/search")

    assert resp.status_code == 502
    assert resp.json()["detail"] == (
        "Keitaro недоступен: connection refused. Проверьте KT_BASE_URL и доступность трекера."
    )


def test_missing_api_key_is_503_without_calling_keitaro():
    settings = make_settings(KT_API_KEY="")
    # stub=None: настоящий клиент Keitaro, до запроса к трекеру дело не должно дойти
    with api_client(settings=settings) as client:
        resp = client.get("/api/offers/search")

    assert resp.status_code == 503
    assert "KT_API_KEY не задан" in resp.json()["detail"]


def test_validation_error_names_field_and_reason():
    stub = KeitaroStub()
    with api_client(stub, db=memory_db()) as client:
        missing = client.post("/api/campaigns", json={"name": "x", "geo": "MX"})
        wrong_type = client.post(
            "/api/campaigns", json={"name": "x", "geo": "MX", "offer_id": "abc"}
        )
        nested = client.put(
            f"/api/campaigns/{uuid.uuid4()}/streams/502",
            json={"offers": [{"offer_id": 101}]},
        )
        bad_uuid = client.get("/api/campaigns/not-a-uuid/streams")

    assert missing.status_code == 422
    assert missing.json()["detail"] == "Некорректные данные запроса: offer_id — обязательное поле"
    assert wrong_type.json()["detail"] == "Некорректные данные запроса: offer_id — ожидается целое число"
    assert nested.json()["detail"] == (
        "Некорректные данные запроса: offers.0.share — обязательное поле"
    )
    assert bad_uuid.json()["detail"] == (
        "Некорректные данные запроса: path.campaign_uuid — ожидается UUID"
    )


def test_unhandled_error_is_json_without_traceback():
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom")
    def _boom() -> dict:
        raise RuntimeError("secret internal detail")

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/boom")

    assert resp.status_code == 500
    assert resp.json() == {"detail": "Внутренняя ошибка сервера. Подробности — в логе приложения."}
    assert "secret" not in resp.text


def test_keitaro_client_dependency_closes_client_even_on_error(monkeypatch):
    closed = []
    monkeypatch.setattr(KeitaroClient, "close", lambda self: closed.append(self))

    dependency = get_keitaro_client(make_settings())
    client = next(dependency)
    with pytest.raises(RuntimeError, match="request failed"):
        dependency.throw(RuntimeError("request failed"))

    assert closed == [client]
