"""Prompt text is externalized, versioned, and safely rendered."""

from __future__ import annotations

import hashlib
import json
from uuid import uuid4

import psycopg2
import pytest

import app.prompting.sync as sync_module
from app.db.config import DATABASE_URL
from app.orch.main_skill import CREDIT_MEMO_TITLE, MAIN_SKILL
from app.prompting import FilePromptCatalog, PromptService
from app.prompting.catalog import DatabasePromptCatalog, PromptRenderError, render_template
from app.prompting.sync import repository_prompts, sync_repository_prompts

from .conftest import requires_db


def test_repository_main_prompt_and_manifest_are_complete():
    catalog = FilePromptCatalog()
    definitions = catalog.definitions()
    assert {
        "main.system",
        "event.user_message",
        "event.approval.approved",
        "task.approved_execution",
        "compare.single.system",
    } <= definitions.keys()
    assert f'`"{CREDIT_MEMO_TITLE}"`' in MAIN_SKILL
    assert "ĐÃ ĐƯỢC DUYỆT" in catalog.render(
        "task.approved_execution",
        {"action": "disburse", "payload_summary": "loan_id=L001"},
    )
    assert len(repository_prompts()) >= len(definitions) + 4


def test_renderer_rejects_missing_or_undeclared_variables():
    with pytest.raises(PromptRenderError, match="missing"):
        render_template("Hello $name", ("name",), {})
    with pytest.raises(PromptRenderError, match="undeclared"):
        render_template("Hello $other", ("name",), {"name": "Lan"})


def test_repository_sync_takes_transaction_lock_before_writing(monkeypatch):
    statements: list[tuple[str, tuple | None]] = []

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement, params=None):
            statements.append((statement, params))

    class FakeConnection:
        committed = False
        closed = False

        def cursor(self, **_kwargs):
            return FakeCursor()

        def commit(self):
            self.committed = True

        def rollback(self):
            raise AssertionError("sync should not roll back")

        def close(self):
            self.closed = True

    connection = FakeConnection()
    monkeypatch.setattr(sync_module, "connect_capability", lambda _capability: connection)
    monkeypatch.setattr(sync_module, "repository_prompts", lambda: [])

    result = sync_module.sync_repository_prompts()

    assert result == {"definitions": 0, "versions_created": 0, "bindings_updated": 0}
    assert statements == [("SELECT pg_advisory_xact_lock(%s)", (sync_module._SYNC_LOCK_KEY,))]
    assert connection.committed is True
    assert connection.closed is True


@requires_db
def test_repository_sync_is_idempotent_and_active_prompt_renders():
    first = sync_repository_prompts(activate=True, actor="pytest")
    second = sync_repository_prompts(activate=False, actor="pytest")
    assert first["definitions"] >= 17
    assert second["versions_created"] == 0
    service = PromptService(ttl_seconds=0)
    assert service.render("event.user_message", {"content": "xin chào"}) == "Tin nhắn người dùng: xin chào\n"
    ready = service.render(
        "event.credit_memo.ready",
        {
            "role_count": 2,
            "role_text": "credit, legal",
            "title": CREDIT_MEMO_TITLE,
            "sections": "six canonical sections",
        },
    )
    assert "`reason_codes`" in ready


@requires_db
def test_database_adapter_can_activate_a_new_prompt_without_code_change():
    key = f"test.runtime.{uuid4().hex}"
    content = "Xin chào $name"
    checksum = hashlib.sha256(content.encode()).hexdigest()
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO prompt_definitions(prompt_key,scope,variables) VALUES(%s,'test',%s)",
                (key, json.dumps(["name"])),
            )
            cur.execute(
                "INSERT INTO prompt_versions(prompt_key,version,content,checksum) VALUES(%s,1,%s,%s) RETURNING id",
                (key, content, checksum),
            )
            version_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO prompt_bindings(prompt_key,environment,version_id) VALUES(%s,'test',%s)",
                (key, version_id),
            )
        service = PromptService(database=DatabasePromptCatalog("test"), ttl_seconds=0)
        assert service.render(key, {"name": "Minh"}) == "Xin chào Minh"
    finally:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM prompt_bindings WHERE prompt_key=%s", (key,))
            cur.execute("DELETE FROM prompt_versions WHERE prompt_key=%s", (key,))
            cur.execute("DELETE FROM prompt_definitions WHERE prompt_key=%s", (key,))
        conn.close()
