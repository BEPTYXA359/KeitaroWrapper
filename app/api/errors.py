"""Ошибки API: любой сбой -> JSON {"detail": <текст для человека>}.

Трассировки и сырые исключения наружу не уходят: непойманное исключение сервер
логирует сам, а клиент получает только понятный текст.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.keitaro.client import DEFAULT_TIMEOUT_SECONDS
from app.keitaro.exceptions import KeitaroApiError, KeitaroNotFoundError, KeitaroTimeoutError

# Частые причины ошибок валидации — по-русски; остальные оставляем как есть
_FIELD_ERRORS = {
    "missing": "обязательное поле",
    "int_parsing": "ожидается целое число",
    "int_type": "ожидается целое число",
    "int_from_float": "ожидается целое число",
    "greater_than": "ожидается число больше нуля",
    "string_type": "ожидается строка",
    "list_type": "ожидается массив",
    "uuid_parsing": "ожидается UUID",
}


def keitaro_error_detail(exc: KeitaroApiError) -> str:
    """Что случилось и что проверить: трекер недоступен, ключ отклонён, ответ 5xx."""
    if isinstance(exc, KeitaroTimeoutError):
        return (
            f"Keitaro не ответил за {DEFAULT_TIMEOUT_SECONDS:.0f} с. Проверьте доступность "
            "трекера (KT_BASE_URL) и повторите попытку."
        )
    # в detail транспортных ошибок приставка «Keitaro недоступен» уже стоит — не дублируем
    if exc.status is None:
        return f"{exc.detail}. Проверьте KT_BASE_URL и доступность трекера."
    if exc.status in (401, 403):
        return (
            f"Keitaro отклонил запрос (HTTP {exc.status}). Проверьте API-ключ: "
            "KT_API_KEY в .env."
        )
    if isinstance(exc, KeitaroNotFoundError):
        return (
            f"Keitaro вернул 404 ({exc.detail}). Проверьте KT_BASE_URL — в нём должен быть "
            "корень трекера, без /admin."
        )
    return f"Ошибка Keitaro API (HTTP {exc.status}): {exc.detail}"


def validation_detail(exc: RequestValidationError) -> str:
    """Ошибки валидации запроса одной строкой: поле и что не так."""
    parts: list[str] = []
    for error in exc.errors():
        location = ".".join(str(item) for item in error.get("loc", ()) if item != "body")
        reason = _FIELD_ERRORS.get(error.get("type"), error.get("msg", "неверное значение"))
        parts.append(f"{location} — {reason}" if location else reason)
    return "Некорректные данные запроса: " + "; ".join(parts)


async def _keitaro_error_handler(_: Request, exc: KeitaroApiError) -> JSONResponse:
    status = 504 if isinstance(exc, KeitaroTimeoutError) else 502
    return JSONResponse(status_code=status, content={"detail": keitaro_error_detail(exc)})


async def _validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": validation_detail(exc)})


async def _unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    # Трассировку пишет сервер: Starlette пробрасывает исключение дальше после ответа
    return JSONResponse(
        status_code=500,
        content={"detail": "Внутренняя ошибка сервера. Подробности — в логе приложения."},
    )


def register_error_handlers(app: FastAPI) -> None:
    """Вызвать до старта сервера — обработчики попадают в стек middleware при первом запросе."""
    app.add_exception_handler(KeitaroApiError, _keitaro_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(Exception, _unhandled_error_handler)
