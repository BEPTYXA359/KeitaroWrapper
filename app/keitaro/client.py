"""Клиент Keitaro Admin API (синхронный, на httpx).

Только транспорт и маппинг ошибок — без бизнес-логики кампаний: методы принимают
и отдают словари/списки «как есть», их формат описан в OpenAPI-спеке Keitaro
(https://admin-api.docs.keitaro.io/openapi.json). Все list-эндпоинты Keitaro
возвращают голые массивы (пагинации в API нет).

Особенности API, которые нельзя «исправить» на клиенте:
- group_id в Keitaro — строка, а не число (payload проходит без преобразований);
- в ответах фильтры потока отдают payload строкой ("MX,AU,RO"), при создании
  потока фильтр ждёт payload массивом.
"""

from __future__ import annotations

import httpx

from app.config import Settings, get_settings
from app.keitaro.exceptions import KeitaroApiError, KeitaroNotFoundError, KeitaroTimeoutError

API_PREFIX = "/admin_api/v1"
DEFAULT_TIMEOUT_SECONDS = 15.0


class KeitaroClient:
    """HTTP-клиент Keitaro Admin API.

    Args:
        settings: настройки (по умолчанию из .env через get_settings()).
        transport: httpx-транспорт; подставляйте httpx.MockTransport в тестах.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        settings = settings or get_settings()
        self._client = httpx.Client(
            base_url=settings.KT_BASE_URL.rstrip("/") + API_PREFIX,
            headers={"Api-Key": settings.KT_API_KEY},
            timeout=DEFAULT_TIMEOUT_SECONDS,
            transport=transport,
        )

    # ------------------------------------------------------------------
    # Транспорт: единая обработка ошибок, наружу — только свои исключения
    # ------------------------------------------------------------------

    def _request(self, method: str, path: str, payload: dict | list | None = None) -> dict | list:
        try:
            response = self._client.request(method, path, json=payload)
        except httpx.TimeoutException as exc:
            raise KeitaroTimeoutError() from exc
        except httpx.HTTPError as exc:
            raise KeitaroApiError(status=None, detail=f"Keitaro недоступен: {exc}") from exc
        return self._parse_response(response)

    def _parse_response(self, response: httpx.Response) -> dict | list:
        if response.status_code == 404:
            raise KeitaroNotFoundError(detail=self._error_detail(response))
        if response.status_code >= 400:
            raise KeitaroApiError(status=response.status_code, detail=self._error_detail(response))
        try:
            return response.json()
        except ValueError as exc:
            raise KeitaroApiError(
                status=response.status_code,
                detail=f"Keitaro вернул не-JSON ответ: {response.text[:200]}",
            ) from exc

    @staticmethod
    def _error_detail(response: httpx.Response) -> str:
        """Достать текст ошибки из тела ответа (спека: {"error": "..."})."""
        try:
            body = response.json()
        except ValueError:
            return (response.text or response.reason_phrase).strip()[:500]
        if isinstance(body, dict):
            for key in ("error", "message", "detail"):
                if body.get(key):
                    return str(body[key])[:500]
        return str(body)[:500]

    def _get(self, path: str) -> dict | list:
        return self._request("GET", path)

    def _post(self, path: str, payload: dict | list) -> dict | list:
        return self._request("POST", path, payload)

    def _put(self, path: str, payload: dict | list) -> dict | list:
        return self._request("PUT", path, payload)

    # ------------------------------------------------------------------
    # Кампании
    # ------------------------------------------------------------------

    def list_campaigns(self) -> list[dict]:
        return self._get("/campaigns")

    def get_campaign(self, campaign_id: int) -> dict:
        return self._get(f"/campaigns/{campaign_id}")

    def create_campaign(self, payload: dict) -> dict:
        return self._post("/campaigns", payload)

    def get_campaign_streams(self, campaign_id: int) -> list[dict]:
        return self._get(f"/campaigns/{campaign_id}/streams")

    # ------------------------------------------------------------------
    # Потоки
    # ------------------------------------------------------------------

    def get_stream(self, stream_id: int) -> dict:
        return self._get(f"/streams/{stream_id}")

    def create_stream(self, payload: dict) -> dict:
        return self._post("/streams", payload)

    def update_stream(self, stream_id: int, payload: dict) -> dict:
        return self._put(f"/streams/{stream_id}", payload)

    # ------------------------------------------------------------------
    # Офферы
    # ------------------------------------------------------------------

    def list_offers(self) -> list[dict]:
        return self._get("/offers")

    def get_offer(self, offer_id: int) -> dict:
        return self._get(f"/offers/{offer_id}")

    # ------------------------------------------------------------------
    # Домены
    # ------------------------------------------------------------------

    def list_domains(self) -> list[dict]:
        return self._get("/domains")

    # ------------------------------------------------------------------
    # Группы
    # ------------------------------------------------------------------

    def list_groups(self) -> list[dict]:
        return self._get("/groups")

    def create_group(self, name: str, group_type: str = "campaigns") -> dict:
        """Создать группу; type в запросе обязателен (campaigns/offers/landings/domains)."""
        return self._post("/groups", {"name": name, "type": group_type})

    # ------------------------------------------------------------------
    # Источники трафика
    # ------------------------------------------------------------------

    def list_traffic_sources(self) -> list[dict]:
        return self._get("/traffic_sources")

    def create_traffic_source(self, payload: dict) -> dict:
        return self._post("/traffic_sources", payload)

    # ------------------------------------------------------------------
    # Жизненный цикл
    # ------------------------------------------------------------------

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "KeitaroClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
