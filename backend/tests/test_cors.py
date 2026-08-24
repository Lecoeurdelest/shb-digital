"""CORS cho SDK nhúng: exact allowlist, không wildcard hay URL có path."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import parse_cors_origins
from app.main import configure_cors


def _app(origins: tuple[str, ...]) -> FastAPI:
    target = FastAPI()
    configure_cors(target, origins)

    @target.post("/probe")
    def probe() -> dict[str, bool]:
        return {"ok": True}

    return target


def test_cors_empty_disables_middleware():
    target = _app(())

    assert target.user_middleware == []


def test_parse_cors_origins_exact_and_deduplicated():
    assert parse_cors_origins(" HTTPS://SAHA.SHB.VN:443,http://localhost:5173,https://saha.shb.vn ") == (
        "https://saha.shb.vn",
        "http://localhost:5173",
    )


@pytest.mark.parametrize(
    "raw",
    [
        "*",
        "https://*.shb.vn",
        "ftp://saha.shb.vn",
        "https://user:pass@saha.shb.vn",
        "https://saha.shb.vn/",
        "https://saha.shb.vn/widget",
        "https://saha.shb.vn?x=1",
        "https://saha.shb.vn?",
        "https://saha.shb.vn#x",
        "https://saha.shb.vn#",
        "https://saha.shb.vn,",
        "https://bad host.shb.vn",
        "https://saha.shb.vn:99999",
    ],
)
def test_parse_cors_origins_rejects_non_origins(raw: str):
    with pytest.raises(ValueError):
        parse_cors_origins(raw)


def test_allowed_preflight_has_exact_origin_credentials_methods_and_headers():
    client = TestClient(_app(("https://saha.shb.vn",)))

    response = client.options(
        "/probe",
        headers={
            "Origin": "https://saha.shb.vn",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://saha.shb.vn"
    assert response.headers["access-control-allow-credentials"] == "true"
    assert "POST" in response.headers["access-control-allow-methods"]
    allowed_headers = response.headers["access-control-allow-headers"].lower()
    assert "authorization" in allowed_headers
    assert "content-type" in allowed_headers


def test_unlisted_origin_preflight_is_rejected_without_allow_origin_header():
    client = TestClient(_app(("https://saha.shb.vn",)))

    response = client.options(
        "/probe",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
