"""Заглушка Keitaro Admin API для тестов бизнес-логики.

Подключается через httpx.MockTransport — сеть не дергается. Маршрутизирует
запросы по путям (в рамках /admin_api/v1), создаёт сущности по POST и пишет
все запросы в .requests как (method, path, payload), чтобы тесты проверяли
«что и куда ушло».
"""

from __future__ import annotations

import json
import re

import httpx

API_PREFIX = "/admin_api/v1"


class KeitaroStub:
    def __init__(
        self,
        *,
        offers: list[dict] | None = None,
        groups: list[dict] | None = None,
        domains: list[dict] | None = None,
        traffic_sources: list[dict] | None = None,
        stream_filters: list[dict] | None = None,
        stream_types: list[dict] | None = None,
        campaigns: list[dict] | None = None,
        streams: list[dict] | None = None,
        campaign_post_error: int | None = None,
    ) -> None:
        self.offers = offers or []
        self.groups = groups or []
        self.domains = domains or []
        self.traffic_sources = traffic_sources or []
        self.stream_filters = stream_filters or []
        self.stream_types = stream_types or []
        self.campaigns = campaigns or []
        self.streams = streams or []
        self.campaign_post_error = campaign_post_error
        self.requests: list[tuple[str, str, dict | None]] = []
        self._next_id = 1000
        self.campaign_id = 301
        self.stream_id = 600

    # ------------------------------------------------------------------
    # Служебные хелперы для тестов
    # ------------------------------------------------------------------

    def _next(self) -> int:
        self._next_id += 1
        return self._next_id

    def posted(self, path: str) -> list[dict | None]:
        """Payload-ы всех POST на путь (без префикса /admin_api/v1)."""
        return [p for method, full_path, p in self.requests
                if method == "POST" and full_path == API_PREFIX + path]

    def requests_to(self, path: str) -> list[tuple[str, dict | None]]:
        """Все запросы на путь (без префикса /admin_api/v1)."""
        return [(method, p) for method, full_path, p in self.requests
                if full_path == API_PREFIX + path]

    # ------------------------------------------------------------------
    # httpx.MockTransport
    # ------------------------------------------------------------------

    def handler(self, request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content) if request.content else None
        path = str(request.url.path).removeprefix(API_PREFIX)
        self.requests.append((request.method, str(request.url.path), payload))

        if path == "/groups":
            if request.method == "GET":
                return _ok(self.groups)
            return _ok(self._create(self.groups, payload))

        if path == "/traffic_sources":
            if request.method == "GET":
                return _ok(self.traffic_sources)
            return _ok(self._create(self.traffic_sources, payload))

        if path == "/domains" and request.method == "GET":
            return _ok(self.domains)

        if path == "/offers" and request.method == "GET":
            return _ok(self.offers)

        match = re.fullmatch(r"/offers/(\d+)", path)
        if match and request.method == "GET":
            offer_id = int(match.group(1))
            offer = next((o for o in self.offers if o["id"] == offer_id), None)
            if offer is None:
                return httpx.Response(404, json={"error": f"Offer {offer_id} not found"})
            return _ok(offer)

        if path == "/campaigns" and request.method == "POST":
            if self.campaign_post_error is not None:
                return httpx.Response(
                    self.campaign_post_error, json={"error": "Internal error"}
                )
            created = {"id": self.campaign_id, **(payload or {})}
            self.campaigns.append(created)
            return _ok(created)

        if path == "/streams" and request.method == "POST":
            stream = {"id": self.stream_id, **(payload or {})}
            self.stream_id += 1
            self.streams.append(stream)
            return _ok(stream)

        match = re.fullmatch(r"/campaigns/(\d+)", path)
        if match and request.method == "GET":
            campaign_id = int(match.group(1))
            campaign = next((c for c in self.campaigns if c["id"] == campaign_id), None)
            if campaign is None:
                return httpx.Response(
                    404, json={"error": f"Campaign {campaign_id} not found"}
                )
            return _ok(campaign)

        match = re.fullmatch(r"/campaigns/(\d+)/streams", path)
        if match and request.method == "GET":
            campaign_id = int(match.group(1))
            return _ok(
                [s for s in self.streams if s.get("campaign_id") == campaign_id]
            )

        match = re.fullmatch(r"/streams/(\d+)", path)
        if match:
            stream_id = int(match.group(1))
            stream = next((s for s in self.streams if s["id"] == stream_id), None)
            if stream is None:
                return httpx.Response(
                    404, json={"error": f"Stream {stream_id} not found"}
                )
            if request.method == "GET":
                return _ok(stream)
            if request.method == "PUT":
                updated = {**stream, **(payload or {})}
                self.streams[self.streams.index(stream)] = updated
                return _ok(updated)

        if path == "/stream_filters" and request.method == "GET":
            return _ok(self.stream_filters)

        if path == "/stream_types" and request.method == "GET":
            return _ok(self.stream_types)

        if path == "/stream_schemas" and request.method == "GET":
            return _ok(self.stream_types)

        return httpx.Response(404, json={"error": f"not mocked: {request.method} {path}"})

    def _create(self, storage: list[dict], payload: dict | None) -> dict:
        created = {"id": self._next(), **(payload or {})}
        storage.append(created)
        return created


def _ok(body: dict | list) -> httpx.Response:
    return httpx.Response(200, json=body)
