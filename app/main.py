"""FastAPI-приложение: /api/* + раздача собранного SPA из frontend/dist.

Запуск: uvicorn app.main:app
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from app.api.errors import register_error_handlers
from app.api.routes import router as api_router

app = FastAPI(title="Keitaro Wrapper", docs_url="/api/docs", openapi_url="/api/openapi.json")
register_error_handlers(app)
app.include_router(api_router)

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


class SPAStaticFiles(StaticFiles):
    """Статика с fallback на index.html — чтобы SPA-роутинг жил после F5.

    Для неизвестных /api/* путей fallback НЕ делаем — там честный 404.
    """

    async def get_response(self, path: str, scope):  # type: ignore[override]
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
            if scope.get("path", "").startswith("/api"):
                raise
            return await super().get_response("index.html", scope)


if FRONTEND_DIST.is_dir():
    app.mount("/", SPAStaticFiles(directory=FRONTEND_DIST, html=True), name="spa")
else:
    # frontend/dist не собран — API продолжает работать, фронт запускают через npm run dev
    @app.get("/")
    def _no_frontend() -> dict[str, str]:
        return {
            "status": "ok",
            "hint": "frontend/dist не найден — соберите: cd frontend && npm i && npm run build",
        }
