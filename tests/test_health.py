"""Тесты health-эндпоинта и раздачи SPA."""


def test_health_ok(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


def test_unknown_api_path_is_404(client):
    # несуществующий /api-путь не должен отдавать index.html
    resp = client.get("/api/nope")
    assert resp.status_code == 404
