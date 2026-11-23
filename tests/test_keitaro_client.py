"""Тесты KeitaroClient — только на httpx.MockTransport, сеть не дергается.

Тестовый Api-Key генерируется хешем: в коде нет ключей-литералов,
это не настоящий ключ Keitaro и не секрет.
"""

import hashlib
import json

import httpx
import pytest

from app.config import Settings
from app.keitaro.client import KeitaroClient
from app.keitaro.exceptions import KeitaroApiError, KeitaroNotFoundError, KeitaroTimeoutError

# Явно тестовое значение Api-Key: sha256-хеш, а не литерал «как настоящий ключ»
TEST_API_KEY = hashlib.sha256(b"keitaro-wrapper-test-only").hexdigest()


def make_client(handler, **settings_overrides) -> KeitaroClient:
    settings_values = {
        "KT_BASE_URL": "https://kt.test",
        "KT_API_KEY": TEST_API_KEY,
        **settings_overrides,
    }
    settings = Settings(**settings_values)
    return KeitaroClient(settings=settings, transport=httpx.MockTransport(handler))


# ----------------------------------------------------------------------
# Транспорт: URL, заголовок Api-Key, сквозная передача payload
# ----------------------------------------------------------------------


def test_api_key_header_and_base_url():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["api_key"] = request.headers.get("Api-Key")
        return httpx.Response(200, json=[])

    client = make_client(handler)
    assert client.list_offers() == []

    assert seen["url"] == "https://kt.test/admin_api/v1/offers"
    assert seen["api_key"] == TEST_API_KEY


def test_base_url_trailing_slash_normalized():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json=[])

    client = make_client(handler, KT_BASE_URL="https://kt.test/")
    client.list_offers()

    assert seen["url"] == "https://kt.test/admin_api/v1/offers"


def test_create_campaign_sends_payload_as_is():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": 301, "name": "test_ivanov_campaign1"})

    client = make_client(handler)
    payload = {
        "name": "test_ivanov_campaign1",
        "alias": "campaign1_ab12cd",
        "group_id": "7",  # group_id в Keitaro — строка; клиент не должен «чинить» тип
        "traffic_source_id": 9,
        "domain_id": 4,
        "type": "position",
    }
    result = client.create_campaign(payload)

    assert result["id"] == 301
    assert captured["method"] == "POST"
    assert captured["url"] == "https://kt.test/admin_api/v1/campaigns"
    assert captured["body"] == payload
    assert isinstance(captured["body"]["group_id"], str)


def test_create_group_sends_name():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": 7, "name": "FORTESTS", "position": 0, "type": "campaigns"})

    client = make_client(handler)
    group = client.create_group("FORTESTS")

    assert group["id"] == 7
    assert captured["url"].endswith("/groups")
    assert captured["method"] == "POST"
    assert captured["body"] == {"name": "FORTESTS"}


def test_update_stream_sends_payload():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": 502, "offers": []})

    client = make_client(handler)
    payload = {"offers": [{"offer_id": 101, "share": 60, "state": "active"}]}
    client.update_stream(502, payload)

    assert captured["url"].endswith("/streams/502")
    assert captured["method"] == "PUT"
    assert captured["body"] == payload


def test_build_report_sends_payload():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"data": []})

    client = make_client(handler)
    payload = {
        "range": {"interval": "today", "timezone": "UTC"},
        "dimensions": ["stream_id"],
        "measures": ["clicks"],
    }
    client.build_report(payload)

    assert captured["url"].endswith("/report/build")
    assert captured["method"] == "POST"
    assert captured["body"] == payload


@pytest.mark.parametrize(
    ("call", "expected_path"),
    [
        (lambda c: c.list_campaigns(), "/campaigns"),
        (lambda c: c.get_campaign(301), "/campaigns/301"),
        (lambda c: c.get_campaign_streams(301), "/campaigns/301/streams"),
        (lambda c: c.get_stream(501), "/streams/501"),
        (lambda c: c.create_stream({"name": "Flow 1"}), "/streams"),
        (lambda c: c.get_offer(101), "/offers/101"),
        (lambda c: c.list_domains(), "/domains"),
        (lambda c: c.list_traffic_sources(), "/traffic_sources"),
        (lambda c: c.list_stream_filters(), "/stream_filters"),
        (lambda c: c.list_stream_types(), "/stream_types"),
        (lambda c: c.list_stream_schemas(), "/stream_schemas"),
    ],
)
def test_endpoints_paths(call, expected_path):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json={})

    client = make_client(handler)
    call(client)

    assert seen["url"] == f"https://kt.test/admin_api/v1{expected_path}"


# ----------------------------------------------------------------------
# Маппинг ошибок Keitaro -> свои исключения
# ----------------------------------------------------------------------


def test_404_raises_not_found():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "Offer not found"})

    client = make_client(handler)

    with pytest.raises(KeitaroNotFoundError) as exc_info:
        client.get_offer(999)

    assert exc_info.value.status == 404
    assert "Offer not found" in exc_info.value.detail
    assert isinstance(exc_info.value, KeitaroApiError)


def test_500_raises_api_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "Internal error"})

    client = make_client(handler)

    with pytest.raises(KeitaroApiError) as exc_info:
        client.list_offers()

    assert exc_info.value.status == 500
    assert "Internal error" in exc_info.value.detail


def test_non_json_error_body():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="Bad Gateway")

    client = make_client(handler)

    with pytest.raises(KeitaroApiError) as exc_info:
        client.list_offers()

    assert exc_info.value.status == 502
    assert "Bad Gateway" in exc_info.value.detail


def test_timeout_raises_timeout_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("boom")

    client = make_client(handler)

    with pytest.raises(KeitaroTimeoutError) as exc_info:
        client.list_offers()

    assert exc_info.value.status is None
    assert isinstance(exc_info.value, KeitaroApiError)


def test_connect_error_raises_api_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = make_client(handler)

    with pytest.raises(KeitaroApiError) as exc_info:
        client.list_offers()

    assert exc_info.value.status is None
    assert "connection refused" in exc_info.value.detail


def test_non_json_success_body_raises_api_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json")

    client = make_client(handler)

    with pytest.raises(KeitaroApiError) as exc_info:
        client.list_offers()

    assert exc_info.value.status == 200
    assert "not json" in exc_info.value.detail


# ----------------------------------------------------------------------
# Фикстуры (переиспользуются бизнес-логикой в следующих итерациях)
# ----------------------------------------------------------------------


def test_list_offers_returns_fixture(load_fixture):
    offers = load_fixture("offers")
    client = make_client(lambda request: httpx.Response(200, json=offers))

    result = client.list_offers()

    assert [offer["id"] for offer in result] == [101, 102]


def test_campaign_streams_fixture_has_both_schemas(load_fixture):
    streams = load_fixture("streams")
    client = make_client(lambda request: httpx.Response(200, json=streams))

    result = client.get_campaign_streams(301)

    assert {stream["schema"] for stream in result} == {"redirect", "landings"}
