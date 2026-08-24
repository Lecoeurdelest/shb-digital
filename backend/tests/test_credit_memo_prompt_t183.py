"""[BACKEND] T18-3 — contract prompt tờ trình sơ thẩm, deterministic từ task board."""

from app.orch.main_prompts import _build_event_prompt
from app.orch.main_skill import (
    CREDIT_MEMO_MIN_DISTINCT_DONE_ROLES,
    CREDIT_MEMO_SECTIONS,
    CREDIT_MEMO_TITLE,
    MAIN_SKILL,
)


def _task_done_prompt(board: list[dict]) -> str:
    return _build_event_prompt(
        "task_done",
        {
            "role": board[-1]["role"],
            "outcome": "done",
            "result_summary": "Kết quả chuyên gia có nguồn.",
            "board": board,
        },
    )


def test_main_skill_locks_six_section_credit_memo_contract():
    assert CREDIT_MEMO_MIN_DISTINCT_DONE_ROLES == 2
    assert f'`"{CREDIT_MEMO_TITLE}"`' in MAIN_SKILL
    assert "đúng 6 mục bắt buộc" in MAIN_SKILL
    assert "DSCR, LTV và CIC" in MAIN_SKILL
    assert "3 trụ, lane" in MAIN_SKILL and "assessment #id" in MAIN_SKILL
    assert "ma trận thẩm quyền" in MAIN_SKILL
    assert "`source` phải là string\n  khác rỗng" in MAIN_SKILL
    for section in CREDIT_MEMO_SECTIONS:
        assert MAIN_SKILL.count(f"`{section}`") == 1


def test_one_completed_operations_result_does_not_open_document_gate():
    prompt = _task_done_prompt(
        [
            {
                "role": "operations",
                "status": "done",
                "title": "Lập lộ trình xử lý hồ sơ",
            }
        ]
    )

    assert "CHƯA ĐỦ 2 role chuyên gia khác nhau đã done" in prompt
    assert "hiện có: operations" in prompt
    assert "KHÔNG ĐƯỢC gọi tool `present`" in prompt
    assert CREDIT_MEMO_TITLE not in prompt


def test_two_distinct_completed_roles_require_standard_credit_memo():
    prompt = _task_done_prompt(
        [
            {"role": "credit", "status": "done", "title": "Thẩm định tín dụng"},
            {"role": "legal", "status": "done", "title": "Thẩm định pháp lý"},
            {"role": "operations", "status": "running", "title": "Lập lộ trình"},
        ]
    )

    assert "ĐÃ ĐỦ 2 role chuyên gia khác nhau đã done (credit, legal)" in prompt
    assert f'title đúng `"{CREDIT_MEMO_TITLE}"`' in prompt
    assert "items đúng 6 mục theo thứ tự" in prompt
    assert "`source` string khác rỗng" in prompt
    assert "top-level `sources`" in prompt
    for section in CREDIT_MEMO_SECTIONS:
        assert f"`{section}`" in prompt


def test_failed_or_duplicate_role_does_not_fake_second_completed_specialist():
    prompt = _task_done_prompt(
        [
            {"role": "operations", "status": "done", "title": "Lộ trình lần 1"},
            {"role": "operations", "status": "done", "title": "Lộ trình lần 2"},
            {"role": "credit", "status": "failed", "title": "Thẩm định lỗi"},
        ]
    )

    assert "CHƯA ĐỦ 2 role chuyên gia khác nhau đã done" in prompt
    assert "hiện có: operations" in prompt
    assert "ĐÃ ĐỦ" not in prompt
