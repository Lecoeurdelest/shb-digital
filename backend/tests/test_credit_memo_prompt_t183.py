"""T18-3 credit-memo prompt contract derived deterministically from the task board."""

from types import SimpleNamespace

import pytest

from app.orch import main_prompts
from app.orch.main_prompts import _build_event_prompt
from app.orch.main_skill import (
    CREDIT_MEMO_MIN_DISTINCT_DONE_ROLES,
    CREDIT_MEMO_SECTIONS,
    CREDIT_MEMO_TITLE,
    MAIN_SKILL,
)
from app.prompting import FilePromptCatalog
from app.reason_taxonomy import get_reason_taxonomy


@pytest.fixture(autouse=True)
def _repository_prompt_catalog(monkeypatch: pytest.MonkeyPatch):
    """File-contract tests must not depend on whichever immutable DB version a prior run bound.

    Deployment activates repository versions through ``app.prompting.sync``; that integration is
    covered separately in ``test_prompt_catalog.py``.
    """
    files = FilePromptCatalog()
    service = SimpleNamespace(render=lambda key, values: files.render(key, values))
    monkeypatch.setattr(main_prompts, "get_prompt_service", lambda: service)


def _task_done_prompt(board: list[dict]) -> str:
    return _build_event_prompt(
        "task_done",
        {
            "role": board[-1]["role"],
            "outcome": "done",
            "result_summary": "Source-backed specialist result.",
            "board": board,
        },
    )


def test_main_skill_locks_six_section_credit_memo_contract():
    assert CREDIT_MEMO_MIN_DISTINCT_DONE_ROLES == 2
    assert f'`"{CREDIT_MEMO_TITLE}"`' in MAIN_SKILL
    assert "exactly six required sections" in MAIN_SKILL
    assert "DSCR, LTV, and CIC" in MAIN_SKILL
    assert "three legal pillars, lane" in MAIN_SKILL and "assessment #id" in MAIN_SKILL
    assert "approval-matrix" in MAIN_SKILL
    assert "`reason_codes`" in MAIN_SKILL
    assert get_reason_taxonomy().checksum in MAIN_SKILL
    for code in get_reason_taxonomy().codes:
        assert MAIN_SKILL.count(f"`{code.id}`") == 1
    assert "`source` must be a nonempty string" in MAIN_SKILL
    for section in CREDIT_MEMO_SECTIONS:
        assert MAIN_SKILL.count(f"`{section}`") == 1


def test_one_completed_operations_result_does_not_open_document_gate():
    prompt = _task_done_prompt(
        [
            {
                "role": "operations",
                "status": "done",
                "title": "Prepare the case-processing timeline",
            }
        ]
    )

    assert "Fewer than 2 distinct specialist roles have completed" in prompt
    assert "current: operations" in prompt
    assert "DO NOT call `present`" in prompt
    assert CREDIT_MEMO_TITLE not in prompt


def test_two_distinct_completed_roles_require_standard_credit_memo():
    prompt = _task_done_prompt(
        [
            {"role": "credit", "status": "done", "title": "Credit assessment"},
            {"role": "legal", "status": "done", "title": "Legal assessment"},
            {"role": "operations", "status": "running", "title": "Prepare timeline"},
        ]
    )

    assert "2 distinct specialist roles have completed (credit, legal)" in prompt
    assert f'exact title `"{CREDIT_MEMO_TITLE}"`' in prompt
    assert "six items in this order" in prompt
    assert "nonempty `source` string" in prompt
    assert "Top-level `sources`" in prompt
    assert "`reason_codes`" in prompt
    for section in CREDIT_MEMO_SECTIONS:
        assert f"`{section}`" in prompt


def test_failed_or_duplicate_role_does_not_fake_second_completed_specialist():
    prompt = _task_done_prompt(
        [
            {"role": "operations", "status": "done", "title": "First timeline"},
            {"role": "operations", "status": "done", "title": "Second timeline"},
            {"role": "credit", "status": "failed", "title": "Failed assessment"},
        ]
    )

    assert "Fewer than 2 distinct specialist roles have completed" in prompt
    assert "current: operations" in prompt
