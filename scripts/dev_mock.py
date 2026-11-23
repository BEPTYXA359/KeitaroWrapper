"""Локальный запуск приложения с заглушкой Keitaro — смотреть UI без доступа к трекеру.

Запуск: .venv/bin/python scripts/dev_mock.py [порт]   →  http://127.0.0.1:<порт>, по умолчанию 8000
Нужен собранный фронт (cd frontend && npm i && npm run build); .env и API-ключ не требуются.

Keitaro подменяется in-memory заглушкой (tests/keitaro_stub.py) с демонстрационными данными,
база — временная in-memory SQLite с одной кампанией. Ничего не пишется ни в трекер, ни в dev.db:
после перезапуска всё сбрасывается. Заглушка не различает созданные через форму кампании —
все получают один и тот же id в Keitaro.
"""

import sys
from pathlib import Path

# прямой запуск скрипта: корень репо в sys.path, чтобы импортировались пакеты app и tests
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402
import uvicorn  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.api.routes import get_keitaro_client  # noqa: E402
from app.config import Settings, get_settings  # noqa: E402
from app.db import get_db  # noqa: E402
from app.keitaro.client import KeitaroClient  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, Campaign  # noqa: E402
from tests.keitaro_stub import KeitaroStub  # noqa: E402

DEFAULT_PORT = 8000

CAMPAIGN_ID = 564210
CAMPAIGN_NAME = "test_demo_campaign1"
UNLINKED_CAMPAIGN_ID = 564211

OFFERS = [
    # (id, название, URL оффера или None) — названия вымышленные
    (3749, "Nordwind [HOME-DE_0007]", "https://offers.example/click?offer=3749"),
    (3760, "Solaris [FIT-FR_0012]", "https://offers.example/click?offer=3760"),
    (3771, "Borealis [HOME-MX_0004]", None),
    (3790, "Meridian [FIT-AU_0002]", "https://offers.example/click?offer=3790"),
    (3802, "Cascade [HOME-IT_0031]", "https://offers.example/click?offer=3802"),
    (3815, "Aurora [FIT-US_0017]", "https://offers.example/click?offer=3815"),
    (3827, "Polaris [APP-JP_0005]", None),
    (3840, "Zenith [FIN-GB_0022]", "https://offers.example/click?offer=3840"),
]


def demo_stub() -> KeitaroStub:
    def offer(offer_id: int, name: str, url: str | None) -> dict:
        return {
            "id": offer_id,
            "name": name,
            "action_type": "url" if url else "show_html",
            "action_payload": url if url else "PGgxPk9mZmVyPC9oMT4=",
            "state": "active",
        }

    def stream_offer(stream_id: int, row_id: int, offer_id: int, share: int) -> dict:
        return {
            "id": row_id,
            "stream_id": stream_id,
            "offer_id": offer_id,
            "state": "active",
            "share": share,
        }

    streams = [
        {
            "id": 564221,
            "type": "regular",
            "name": "Flow 1",
            "campaign_id": CAMPAIGN_ID,
            "position": 1,
            "schema": "redirect",
            "action_type": "http_redirect",
            "action_options": {"url": "https://google.com/"},
            "collect_clicks": True,
            "state": "active",
            "filters": [
                {"id": 1, "stream_id": 564221, "name": "country", "mode": "accept", "payload": "MX,AU,RO"}
            ],
            "offers": [],
        },
        {
            "id": 564222,
            "type": "regular",
            "name": "Flow 2",
            "campaign_id": CAMPAIGN_ID,
            "position": 2,
            "schema": "landings",
            "action_type": "show_html",
            "collect_clicks": True,
            "state": "active",
            "filters": [],
            "offers": [
                stream_offer(564222, 9001, 3749, 34),
                stream_offer(564222, 9002, 3760, 33),
                stream_offer(564222, 9003, 3790, 33),
            ],
        },
    ]
    return KeitaroStub(
        offers=[offer(*row) for row in OFFERS],
        groups=[{"id": 7, "name": "FORTESTS", "type": "campaigns"}],
        domains=[{"id": 4, "name": "tracker.example", "state": "active"}],
        traffic_sources=[{"id": 9, "name": "FORTESTS"}],
        stream_filters=[{"value": "country", "modes": {"accept": "Accept countries"}}],
        stream_types=[{"key": "http_redirect"}, {"key": "show_html"}],
        campaigns=[
            {"id": CAMPAIGN_ID, "name": CAMPAIGN_NAME},
            # есть в Keitaro, но приложение о ней ещё не знает — открывается по id
            {"id": UNLINKED_CAMPAIGN_ID, "name": "test_created_in_keitaro"},
        ],
        streams=streams,
    )


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT

    stub = demo_stub()
    settings = Settings(_env_file=None, KT_BASE_URL="https://keitaro.example", CAMPAIGN_PREFIX="test_")
    keitaro = KeitaroClient(settings=settings, transport=httpx.MockTransport(stub.handler))

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # одно in-memory соединение для всех воркеров
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    demo_campaign = Campaign(name=CAMPAIGN_NAME, keitaro_campaign_id=CAMPAIGN_ID)
    db.add(demo_campaign)
    db.commit()

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_keitaro_client] = lambda: keitaro
    app.dependency_overrides[get_db] = lambda: db

    base = f"http://127.0.0.1:{port}"
    print(f"Keitaro подменён заглушкой, данные демонстрационные и живут до остановки.\n")
    print(f"  новая кампания:   {base}/")
    print(f"  список кампаний:  {base}/campaigns")
    print(f"  потоки демо-кампании: {base}/campaigns/{demo_campaign.id}/streams")
    print(f"  кампания, которая есть только в Keitaro (открыть по id {UNLINKED_CAMPAIGN_ID})\n")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
