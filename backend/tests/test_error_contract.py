"""Framework-generated HTTP errors must obey CONTRACT §0 too."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

_FIELDS = {"code", "message", "hint", "retryable"}


def test_unknown_route_returns_exact_four_field_envelope():
    response = client.get("/api/route-that-does-not-exist")

    assert response.status_code == 404
    assert set(response.json()) == _FIELDS
    assert response.json()["code"] == "not_found"


def test_wrong_method_returns_exact_four_field_envelope_and_allow_header():
    response = client.post("/api/health")

    assert response.status_code == 405
    assert set(response.json()) == _FIELDS
    assert response.json()["code"] == "method_not_allowed"
    assert response.headers["allow"] == "GET"
