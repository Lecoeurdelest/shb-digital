"""Admin-only versioned prompt configuration."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.deps import require_admin
from app.prompting.admin import save_prompt, snapshot

router = APIRouter(prefix="/api/admin/agent-config", tags=["agent-config"])


class PromptSaveBody(BaseModel):
    content: str
    activate: bool = True


@router.get("")
def get_agent_config(_claims: dict = Depends(require_admin)) -> dict:
    return snapshot()


@router.post("/prompts/{key}")
def save_agent_prompt(key: str, body: PromptSaveBody, claims: dict = Depends(require_admin)) -> dict:
    return save_prompt(key, body.content, body.activate, str(claims["username"]))
