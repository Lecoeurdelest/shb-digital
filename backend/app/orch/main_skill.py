"""MAIN prompt policy loaded from the versioned prompt catalog."""

from __future__ import annotations

import json

from app.prompting import FilePromptCatalog, get_prompt_service
from app.prompting.catalog import DEFAULT_PROMPT_ROOT

_MEMO_POLICY = json.loads((DEFAULT_PROMPT_ROOT / "main" / "credit_memo.json").read_text(encoding="utf-8"))
CREDIT_MEMO_TITLE = str(_MEMO_POLICY["title"])
CREDIT_MEMO_MIN_DISTINCT_DONE_ROLES = int(_MEMO_POLICY["minimum_distinct_done_roles"])
CREDIT_MEMO_SECTIONS = tuple(str(item) for item in _MEMO_POLICY["sections"])


def _values() -> dict[str, str | int]:
    section_lines = "\n".join(f"   {index}. `{section}`" for index, section in enumerate(CREDIT_MEMO_SECTIONS, 1))
    return {
        "credit_memo_min_roles": CREDIT_MEMO_MIN_DISTINCT_DONE_ROLES,
        "credit_memo_title": CREDIT_MEMO_TITLE,
        "credit_memo_section_lines": section_lines,
    }


# Compatibility export for tests and callers that inspect the repository default.
MAIN_SKILL = FilePromptCatalog().render("main.system", _values())


def get_main_skill() -> str:
    """Resolve the active DB version, falling back to the reviewed repository prompt."""
    return get_prompt_service().render("main.system", _values())
