from fastapi.testclient import TestClient

import app.api.agent_config as agent_config_api
from app.main import app

from .conftest import requires_db


def test_agent_config_requires_admin():
    response = TestClient(app).get("/api/admin/agent-config")

    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


@requires_db
def test_admin_can_read_and_activate_prompt(monkeypatch):
    saved: dict[str, object] = {}

    expected = {
        "environment": "default",
        "providers": [{"id": "openai", "configured": True}],
        "prompts": [
            {
                "key": "main.system",
                "scope": "main",
                "description": "Main orchestrator",
                "variables": [],
                "active": {"version": 2, "content": "New prompt", "activated_by": "admin", "activated_at": None},
            }
        ],
    }
    monkeypatch.setattr(agent_config_api, "snapshot", lambda: expected)

    def save(key: str, content: str, activate: bool, actor: str) -> dict:
        saved.update(key=key, content=content, activate=activate, actor=actor)
        return expected

    monkeypatch.setattr(agent_config_api, "save_prompt", save)
    client = TestClient(app)
    login = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})

    response = client.post(
        "/api/admin/agent-config/prompts/main.system",
        json={"content": "New prompt", "activate": True},
        cookies=login.cookies,
    )

    assert login.status_code == 200
    assert response.status_code == 200
    assert response.json() == expected
    assert saved == {"key": "main.system", "content": "New prompt", "activate": True, "actor": "admin"}
