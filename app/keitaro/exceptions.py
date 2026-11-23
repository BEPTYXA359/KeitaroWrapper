"""Исключения слоя Keitaro.

Единый предок KeitaroApiError — бизнес-слой ловит одной строкой `except KeitaroApiError`,
не разбираясь, что именно случилось (404 / 5xx / таймаут / сетевой сбой).
"""


class KeitaroApiError(Exception):
    """Ошибка ответа Keitaro API (HTTP >= 400, таймаут или сетевой сбой).

    status — HTTP-код ответа (None для таймаутов и сетевых сбоев);
    detail — человекочитаемое описание (текст ошибки из тела ответа Keitaro).
    """

    def __init__(self, status: int | None, detail: str) -> None:
        self.status = status
        self.detail = detail
        super().__init__(str(self))

    def __str__(self) -> str:
        where = f"HTTP {self.status}" if self.status is not None else "сеть/таймаут"
        return f"Ошибка Keitaro API ({where}): {self.detail}"


class KeitaroNotFoundError(KeitaroApiError):
    """404 — сущность (оффер, кампания, поток...) в Keitaro не найдена."""

    def __init__(self, detail: str) -> None:
        super().__init__(status=404, detail=detail)


class KeitaroTimeoutError(KeitaroApiError):
    """Keitaro не ответил за отведённое время."""

    def __init__(self, detail: str = "Keitaro не ответил за отведённое время") -> None:
        super().__init__(status=None, detail=detail)
