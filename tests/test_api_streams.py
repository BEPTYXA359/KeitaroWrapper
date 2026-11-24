"""Тесты GET/PUT потоков кампании — на моках KeitaroStub + in-memory БД."""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from app.models import Campaign, StreamOfferMemory
from app.services import streams as streams_service
from tests.helpers import api_client, memory_db
from tests.keitaro_stub import KeitaroStub


@contextmanager
def streams_env(
    load_fixture,
    *,
    streams: list[dict] | None = None,
    offers: list[dict] | None = None,
    fail: dict[str, int | str] | None = None,
) -> Iterator[tuple[KeitaroStub, object, str]]:
    """Заглушка с кампанией 301 и её потоками + TestClient; локальная БД знает uuid -> 301."""
    with streams_db_env(load_fixture, streams=streams, offers=offers, fail=fail) as (
        stub,
        client,
        campaign_uuid,
        _db,
    ):
        yield stub, client, campaign_uuid


@contextmanager
def streams_db_env(
    load_fixture,
    *,
    streams: list[dict] | None = None,
    offers: list[dict] | None = None,
    fail: dict[str, int | str] | None = None,
) -> Iterator[tuple[KeitaroStub, object, str, object]]:
    """Как streams_env, но дополнительно отдаёт сессию БД (для посева памяти состава)."""
    db = memory_db()
    campaign = Campaign(name="test_iv_campaign1", keitaro_campaign_id=301)
    db.add(campaign)
    db.commit()
    stub = KeitaroStub(
        offers=load_fixture("offers") if offers is None else offers,
        campaigns=[{"id": 301, "name": "test_iv_campaign1"}],
        streams=load_fixture("streams") if streams is None else streams,
        fail=fail,
    )
    with api_client(stub, db=db) as client:
        yield stub, client, str(campaign.id), db


@pytest.fixture()
def env(load_fixture):
    with streams_env(load_fixture) as environment:
        yield environment


def put_requests(stub: KeitaroStub, path: str) -> list[tuple[str, dict | None]]:
    return [(method, payload) for method, payload in stub.requests_to(path) if method == "PUT"]


# ----------------------------------------------------------------------
# GET: нормализация потоков
# ----------------------------------------------------------------------


def test_get_streams_normalized(env):
    stub, client, campaign_uuid = env
    resp = client.get(f"/api/campaigns/{campaign_uuid}/streams")

    assert resp.status_code == 200
    body = resp.json()
    assert body["campaign"] == {
        "name": "test_iv_campaign1",
        "keitaro_id": 301,
        "admin_url": "https://kt.test/admin/#!/campaign.editor/301",
    }
    # сортировка по позиции
    assert [s["stream_id"] for s in body["streams"]] == [501, 502]

    flow1, flow2 = body["streams"]
    # redirect-поток: фильтр строкой -> массив кодов, офферов нет
    assert flow1["schema"] == "redirect"
    assert flow1["filter"] == {"name": "country", "mode": "accept", "payload": ["MX", "AU", "RO"]}
    assert flow1["offers"] == []
    # landings-поток: имя оффера подтянуто из /offers по offer_id
    assert flow2["schema"] == "landings"
    assert flow2["filter"] is None
    assert flow2["offers"] == [
        {
            "offer_id": 101,
            "offer_name": "Sweeper MX",
            "preview_url": None,
            "share": 100,
            "state": "active",
        }
    ]


def test_get_streams_offer_preview_url(load_fixture):
    url_offer = {
        **load_fixture("offers")[0],
        "id": 201,
        "name": "Url offer",
        "action_type": "url",
        "action_payload": "https://offers.example/click?id=201",
    }
    streams = load_fixture("streams")
    streams[1]["offers"].append(
        {"offer_id": 201, "state": "active", "share": 100, "id": 902, "stream_id": 502}
    )
    with streams_env(load_fixture, streams=streams, offers=[*load_fixture("offers"), url_offer]) as env:
        _, client, campaign_uuid = env
        resp = client.get(f"/api/campaigns/{campaign_uuid}/streams")

    offers = resp.json()["streams"][1]["offers"]
    # URL берётся из action_payload оффера; у оффера с HTML-действием ссылки нет
    assert [offer["preview_url"] for offer in offers] == [None, "https://offers.example/click?id=201"]
    assert [offer["offer_name"] for offer in offers] == ["Sweeper MX", "Url offer"]


def test_get_streams_unknown_campaign(env):
    _, client, _ = env
    resp = client.get(f"/api/campaigns/{uuid.uuid4()}/streams")

    assert resp.status_code == 404
    assert "не найдена" in resp.json()["detail"]


def test_get_streams_campaign_deleted_in_keitaro(load_fixture):
    with streams_env(load_fixture, fail={"GET /campaigns/301": 404}) as (_, client, campaign_uuid):
        resp = client.get(f"/api/campaigns/{campaign_uuid}/streams")

    assert resp.status_code == 404
    assert "Кампания 301 не найдена в Keitaro" in resp.json()["detail"]


def test_get_streams_keitaro_timeout_is_504(load_fixture):
    fail = {"GET /campaigns/301/streams": "timeout"}
    with streams_env(load_fixture, fail=fail) as (_, client, campaign_uuid):
        resp = client.get(f"/api/campaigns/{campaign_uuid}/streams")

    assert resp.status_code == 504
    assert "Keitaro не ответил" in resp.json()["detail"]


# ----------------------------------------------------------------------
# PUT: подмена offers с сохранением остальных полей потока
# ----------------------------------------------------------------------


def test_put_stream_replaces_offers_keeps_other_fields(env):
    stub, client, campaign_uuid = env
    resp = client.put(
        f"/api/campaigns/{campaign_uuid}/streams/502",
        json={"offers": [{"offer_id": 102, "share": 100}]},
    )

    assert resp.status_code == 200
    puts = put_requests(stub, "/streams/502")
    assert len(puts) == 1
    _, payload = puts[0]
    # существующие поля потока сохранены, offers подменён
    assert payload["schema"] == "landings"
    assert payload["campaign_id"] == 301
    assert payload["name"] == "Flow 2"
    assert payload["collect_clicks"] is True
    # убранный из потока оффер 101 уходит отключённым с долей 0, а не исчезает из запроса
    assert payload["offers"] == [
        {"offer_id": 102, "share": 100, "state": "active"},
        {"offer_id": 101, "share": 0, "state": "disabled"},
    ]
    # ответ — обновлённый поток из Keitaro
    assert resp.json()["offers"] == payload["offers"]


def test_removed_offer_stays_disabled_in_keitaro_and_can_return(env):
    stub, client, campaign_uuid = env
    client.put(
        f"/api/campaigns/{campaign_uuid}/streams/502",
        json={"offers": [{"offer_id": 102, "share": 100}]},
    )

    # после перечитывания убранный оффер приходит из Keitaro отключённым — UI покажет 0% + BRING BACK
    after_remove = client.get(f"/api/campaigns/{campaign_uuid}/streams").json()["streams"][1]
    assert [(o["offer_id"], o["share"], o["state"]) for o in after_remove["offers"]] == [
        (102, 100, "active"),
        (101, 0, "disabled"),
    ]

    # возврат: оффер снова уходит активным, отключённых записей не остаётся
    client.put(
        f"/api/campaigns/{campaign_uuid}/streams/502",
        json={"offers": [{"offer_id": 101, "share": 50}, {"offer_id": 102, "share": 50}]},
    )
    _, payload = put_requests(stub, "/streams/502")[1]
    assert payload["offers"] == [
        {"offer_id": 101, "share": 50, "state": "active"},
        {"offer_id": 102, "share": 50, "state": "active"},
    ]


def test_manually_deleted_offer_restored_as_disabled_on_push(load_fixture):
    """Оффер, вычеркнутый из потока в админке Keitaro (есть в памяти состава), при PUSH
    возвращается в поток отключённым: Keitaro снова его хранит, UI — «0% + BRING BACK»."""
    with streams_db_env(load_fixture) as (stub, client, campaign_uuid, db):
        campaign = db.query(Campaign).one()
        db.add(
            StreamOfferMemory(
                campaign_id=campaign.id, keitaro_stream_id=502, offer_id=103, offer_name="103 Ghost"
            )
        )
        db.commit()

        resp = client.put(
            f"/api/campaigns/{campaign_uuid}/streams/502",
            json={"offers": [{"offer_id": 101, "share": 100}]},
        )

        assert resp.status_code == 200
        _, payload = put_requests(stub, "/streams/502")[0]
        assert payload["offers"] == [
            {"offer_id": 101, "share": 100, "state": "active"},
            {"offer_id": 103, "share": 0, "state": "disabled"},
        ]

        after_push = client.get(f"/api/campaigns/{campaign_uuid}/streams").json()["streams"][1]
        assert [(o["offer_id"], o["share"], o["state"]) for o in after_push["offers"]] == [
            (101, 100, "active"),
            (103, 0, "disabled"),
        ]


def test_get_streams_marks_manually_deleted_offer(load_fixture):
    with streams_db_env(load_fixture) as (_stub, client, campaign_uuid, db):
        campaign = db.query(Campaign).one()
        db.add(
            StreamOfferMemory(
                campaign_id=campaign.id, keitaro_stream_id=502, offer_id=103, offer_name="103 Ghost"
            )
        )
        db.commit()

        resp = client.get(f"/api/campaigns/{campaign_uuid}/streams")

        assert resp.status_code == 200
        flow2 = resp.json()["streams"][1]
        ghost = next(o for o in flow2["offers"] if o["offer_id"] == 103)
        assert ghost == {
            "offer_id": 103,
            "offer_name": "103 Ghost",
            "preview_url": None,
            "share": 0,
            "state": "deleted",
        }


def test_get_streams_persists_seen_offers_to_memory(load_fixture):
    with streams_db_env(load_fixture) as (_stub, client, campaign_uuid, db):
        client.get(f"/api/campaigns/{campaign_uuid}/streams")

        rows = db.query(StreamOfferMemory).all()
        assert [(row.keitaro_stream_id, row.offer_id, row.offer_name) for row in rows] == [
            (502, 101, "Sweeper MX")
        ]


def test_memory_union_keeps_offers_missing_from_keitaro(load_fixture):
    """GET не теряет память: оффер, исчезнувший из ответа Keitaro, отдаётся со state deleted."""
    with streams_db_env(load_fixture) as (stub, client, campaign_uuid, db):
        client.get(f"/api/campaigns/{campaign_uuid}/streams")  # запомнили 101 в потоке 502

        # воспроизводим «ручное удаление»: в Keitaro у потока не остаётся офферов
        stub.streams[1]["offers"] = []
        resp = client.get(f"/api/campaigns/{campaign_uuid}/streams")

        flow2 = resp.json()["streams"][1]
        assert [(o["offer_id"], o["state"]) for o in flow2["offers"]] == [(101, "deleted")]


def test_removed_offer_ids_are_not_part_of_contract(load_fixture):
    with streams_db_env(load_fixture) as (_stub, client, campaign_uuid, _db):
        resp = client.put(
            f"/api/campaigns/{campaign_uuid}/streams/502",
            json={"offers": [{"offer_id": 101, "share": 100}], "removed_offer_ids": [103]},
        )

        # лишние поля просто игнорируются: контракт — {offers}
        assert resp.status_code == 200


def test_put_removed_omitted_with_fallback_strategy(env, monkeypatch):
    monkeypatch.setattr(streams_service, "REMOVED_OFFERS_STRATEGY", "omit")
    stub, client, campaign_uuid = env
    resp = client.put(
        f"/api/campaigns/{campaign_uuid}/streams/502",
        json={"offers": [{"offer_id": 102, "share": 100}]},
    )

    assert resp.status_code == 200
    _, payload = put_requests(stub, "/streams/502")[0]
    # запасной вариант: в запросе только активные офферы
    assert payload["offers"] == [{"offer_id": 102, "share": 100, "state": "active"}]


def test_put_stream_keitaro_5xx_is_502(load_fixture):
    with streams_env(load_fixture, fail={"PUT /streams/502": 500}) as (stub, client, campaign_uuid):
        resp = client.put(
            f"/api/campaigns/{campaign_uuid}/streams/502",
            json={"offers": [{"offer_id": 102, "share": 100}]},
        )

    assert resp.status_code == 502
    assert "HTTP 500" in resp.json()["detail"]
    assert len(put_requests(stub, "/streams/502")) == 1


def test_put_stream_of_other_campaign_404(load_fixture):
    foreign = {**load_fixture("streams")[1], "campaign_id": 999}
    with streams_env(load_fixture, streams=[foreign]) as (stub, client, campaign_uuid):
        resp = client.put(
            f"/api/campaigns/{campaign_uuid}/streams/502",
            json={"offers": [{"offer_id": 102, "share": 100}]},
        )

    assert resp.status_code == 404
    assert "не относится к кампании" in resp.json()["detail"]
    assert put_requests(stub, "/streams/502") == []


def test_put_unknown_stream_404(env):
    _, client, campaign_uuid = env
    resp = client.put(
        f"/api/campaigns/{campaign_uuid}/streams/999",
        json={"offers": []},
    )

    assert resp.status_code == 404
    assert "не найден" in resp.json()["detail"]


def test_put_unknown_campaign_404(env):
    _, client, _ = env
    resp = client.put(
        f"/api/campaigns/{uuid.uuid4()}/streams/502",
        json={"offers": []},
    )

    assert resp.status_code == 404
    assert "не найдена" in resp.json()["detail"]
