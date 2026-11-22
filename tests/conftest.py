"""Общие фикстуры тестов.

DATABASE_URL выставляем ДО импорта app.* — иначе engine создастся из .env.
"""

import os

os.environ["DATABASE_URL"] = "sqlite://"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)
