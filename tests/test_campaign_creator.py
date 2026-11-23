"""Тесты «создаватора» кампаний — на моках (KeitaroStub + MockTransport), сеть не дергается."""

import re

import httpx
import pytest

from app.keitaro.client import KeitaroClient
from app.models import Campaign
from app.services.campaign_creator import (
    CampaignValidationError,
    OfferNotFoundError,
    create_campaign,
    generate_alias,
    normalize_geo_codes,
)
from tests.helpers import memory_db, make_settings
from tests.keitaro_stub import KeitaroStub


def make_env(stub: KeitaroStub, **settings_overrides):
    """In-memory БД + клиент Keitaro на заглушке + тестовые настройки."""
    settings = make_settings(**settings_overrides)
    client = KeitaroClient(settings=settings, transport=httpx.MockTransport(stub.handler))
    return memory_db(), client, settings


# ----------------------------------------------------------------------
# Чистые функции: geo и alias
# ----------------------------------------------------------------------


def test_geo_parser_trims_and_uppercases():
    assert normalize_geo_codes(" mx, AU ,,ro ") == ["MX", "AU", "RO"]


def test_geo_parser_dedups_codes():
    assert normalize_geo_codes("mx,mx,MX") == ["MX"]


@pytest.mark.parametrize("geo", ["", "   ", ",,,", " , , "])
def test_geo_parser_empty_is_validation_error(geo):
    with pytest.raises(CampaignValidationError):
        normalize_geo_codes(geo)


def test_alias_translit_slug_and_suffix():
    alias = generate_alias("Кампа Иванова")
    assert re.fullmatch(r"kampa-ivanova-[a-z0-9]{6}", alias)


def test_alias_ascii_name_kept():
    assert re.fullmatch(r"iv-campaign1-[a-z0-9]{6}", generate_alias("iv_campaign1"))


def test_alias_slug_truncated_to_max():
    alias = generate_alias("Very Long Campaign Name Here")
    slug = alias.rsplit("-", 1)[0]
    assert len(slug) <= 16


def test_alias_fallback_when_no_latin_chars():
    assert re.fullmatch(r"campaign-[a-z0-9]{6}", generate_alias("!!!"))


def test_alias_suffix_unique():
    aliases = {generate_alias("Test") for _ in range(20)}
    assert len(aliases) > 1


# ----------------------------------------------------------------------
# create_campaign: оркестрация на моках
# ----------------------------------------------------------------------


def test_create_campaign_happy_path(stand):
    db, client, settings = make_env(stand)
    created = create_campaign(db, client, settings, "iv_campaign1", " MX,AU ,,ro ", 101)

    campaign = created.campaign
    assert campaign.keitaro_campaign_id == stand.campaign_id
    assert campaign.name == "test_iv_campaign1"
    assert campaign.id is not None
    assert created.streams_created == 2
    assert created.admin_url == f"https://kt.test/admin/#/campaigns/{stand.campaign_id}"

    # кампания сохранена локально
    rows = db.query(Campaign).all()
    assert len(rows) == 1
    assert rows[0].id == campaign.id
    assert rows[0].keitaro_campaign_id == stand.campaign_id


def test_create_campaign_sends_one_post_campaigns_with_right_payload(stand):
    db, client, settings = make_env(stand)
    create_campaign(db, client, settings, "iv_campaign1", "MX,AU,RO", 101)

    campaign_posts = stand.posted("/campaigns")
    assert len(campaign_posts) == 1
    payload = campaign_posts[0]
    assert payload["name"] == "test_iv_campaign1"
    assert re.fullmatch(r"iv-campaign1-[a-z0-9]{6}", payload["alias"])
    # group_id в Keitaro — строка
    assert payload["group_id"] == "7"
    assert isinstance(payload["group_id"], str)
    assert payload["traffic_source_id"] == 9
    assert payload["domain_id"] == 4
    assert payload["type"] == "position"
    assert payload["cost_type"] == "CPC"
    assert payload["cost_currency"] == "USD"
    assert payload["cost_value"] == 0
    assert payload["cost_auto"] is True
    assert payload["state"] == "active"


def test_create_campaign_sends_two_streams(stand):
    db, client, settings = make_env(stand)
    create_campaign(db, client, settings, "iv_campaign1", "MX,AU,RO", 101)

    stream_posts = stand.posted("/streams")
    assert len(stream_posts) == 2

    flow1, flow2 = stream_posts
    # в запросе — только поля StreamRequest; campaign_id/schema/type/name/action_type обязательны
    assert set(flow1) == {
        "campaign_id", "name", "type", "position", "schema", "action_type",
        "action_options", "filters", "collect_clicks", "state",
    }
    assert set(flow2) == {
        "campaign_id", "name", "type", "position", "schema", "action_type",
        "offers", "collect_clicks", "state",
    }

    assert flow1["campaign_id"] == stand.campaign_id
    assert flow1["name"] == "Flow 1"
    assert flow1["type"] == "regular"
    assert flow1["position"] == 1
    assert flow1["schema"] == "redirect"
    assert flow1["action_type"] == "http_redirect"  # тип редиректа из /stream_types
    assert flow1["action_options"] == {"url": "https://google.com/"}
    # country-фильтр из /stream_filters, accept с geo-кодами
    assert flow1["filters"] == [{"name": "country", "mode": "accept", "payload": ["MX", "AU", "RO"]}]
    assert flow1["collect_clicks"] is True
    assert flow1["state"] == "active"

    assert flow2["campaign_id"] == stand.campaign_id
    assert flow2["name"] == "Flow 2"
    assert flow2["type"] == "regular"
    assert flow2["position"] == 2
    assert flow2["schema"] == "landings"
    assert flow2["action_type"] == "show_html"
    assert flow2["offers"] == [{"offer_id": 101, "share": 100}]
    assert flow2["collect_clicks"] is True
    assert flow2["state"] == "active"


def test_offer_not_found_is_human_error(stand):
    db, client, settings = make_env(stand)

    with pytest.raises(OfferNotFoundError) as exc_info:
        create_campaign(db, client, settings, "iv_campaign1", "MX", 999)

    assert "Оффер 999 не найден" in str(exc_info.value)
    # до POST /campaigns дело не дошло
    assert stand.posted("/campaigns") == []


def test_missing_group_and_source_are_created(stand):
    stub = KeitaroStub(
        offers=stand.offers,
        groups=[],
        domains=stand.domains,
        traffic_sources=[],
        stream_filters=stand.stream_filters,
        stream_types=stand.stream_types,
    )
    db, client, settings = make_env(stub)
    create_campaign(db, client, settings, "iv_campaign1", "MX", 101)

    group_posts = stub.posted("/groups")
    source_posts = stub.posted("/traffic_sources")
    # type у группы обязателен; источнику достаточно name
    assert group_posts == [{"name": "FORTESTS", "type": "campaigns"}]
    assert source_posts == [{"name": "FORTESTS", "postback_url": ""}]

    campaign_payload = stub.posted("/campaigns")[0]
    # id созданных через POST сущностей попали в payload
    created_group_id = stub.groups[-1]["id"]
    created_source_id = stub.traffic_sources[-1]["id"]
    assert campaign_payload["group_id"] == str(created_group_id)
    assert campaign_payload["traffic_source_id"] == created_source_id


def test_existing_group_and_source_not_duplicated(stand):
    db, client, settings = make_env(stand)
    create_campaign(db, client, settings, "iv_campaign1", "MX", 101)

    assert stand.posted("/groups") == []
    assert stand.posted("/traffic_sources") == []


def test_domain_id_from_settings_skips_domain_lookup(stand):
    db, client, settings = make_env(stand, KT_DOMAIN_ID=42)
    create_campaign(db, client, settings, "iv_campaign1", "MX", 101)

    assert stand.requests_to("/domains") == []
    assert stand.posted("/campaigns")[0]["domain_id"] == 42


def test_first_active_domain_used(stand):
    active = stand.domains[0]
    inactive = {**active, "id": 5, "state": "disabled"}
    stub = KeitaroStub(offers=stand.offers, domains=[inactive, active])
    db, client, settings = make_env(stub)
    create_campaign(db, client, settings, "iv_campaign1", "MX", 101)

    assert stub.posted("/campaigns")[0]["domain_id"] == active["id"]


def test_no_active_domains_is_validation_error(stand):
    inactive = {**stand.domains[0], "state": "disabled"}
    stub = KeitaroStub(offers=stand.offers, domains=[inactive])
    db, client, settings = make_env(stub)

    with pytest.raises(CampaignValidationError, match="нет активных доменов"):
        create_campaign(db, client, settings, "iv_campaign1", "MX", 101)


def test_empty_name_is_validation_error(stand):
    db, client, settings = make_env(stand)

    with pytest.raises(CampaignValidationError, match="Name пуст"):
        create_campaign(db, client, settings, "   ", "MX", 101)


# ----------------------------------------------------------------------
# Тип редиректа: порядок и имена ключей каталога /stream_types не гарантированы
# ----------------------------------------------------------------------


def created_redirect_type(stand, catalog_keys: list[str]) -> str:
    stub = KeitaroStub(
        offers=stand.offers,
        groups=stand.groups,
        domains=stand.domains,
        traffic_sources=stand.traffic_sources,
        stream_filters=stand.stream_filters,
        stream_types=[{"key": key} for key in catalog_keys],
    )
    db, client, settings = make_env(stub)
    create_campaign(db, client, settings, "iv_campaign1", "MX", 101)
    return stub.posted("/streams")[0]["action_type"]


def test_redirect_type_is_http_redirect_whatever_the_catalog_order(stand):
    keys = ["redirect_to_offer_url", "meta_redirect", "js_redirect", "http_redirect"]

    assert created_redirect_type(stand, keys) == "http_redirect"


def test_redirect_type_falls_back_to_another_redirect_key(stand):
    assert created_redirect_type(stand, ["show_html", "meta_redirect"]) == "meta_redirect"


def test_redirect_type_fallback_when_no_suitable_key(stand):
    assert created_redirect_type(stand, ["redirect_to_offer_url", "show_html"]) == "http_redirect"
    assert created_redirect_type(stand, []) == "http_redirect"
