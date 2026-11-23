"""Общие фикстуры тестов.

DATABASE_URL выставляем ДО импорта app.* — иначе engine создастся из .env.
"""

import os

os.environ["DATABASE_URL"] = "sqlite://"

import json  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture()
def load_fixture():
    """Загрузить JSON-фикстуру из tests/fixtures (примеры ответов Keitaro для моков)."""

    def _load(name: str) -> dict | list:
        return json.loads((FIXTURES_DIR / f"{name}.json").read_text(encoding="utf-8"))

    return _load
