from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from app.case_intake.context import linked_case_prompt_block
from app.mount.mount_role import mount_role
from app.orch import registry, store
from app.orch.audit_emit import _audit_main_tool_call, _audit_tool_call, _emit_thinking
from app.orch.main_prompts import _build_event_prompt, _customer_prompt_block
from app.orch.main_skill import get_main_skill
from app.orch.store import Task
from app.prompting import get_prompt_service

log = logging.getLogger("orch.session")


CONV_ROOT = Path(__file__).resolve().parents[2] / "data" / "conversations"


MAIN_MODEL = os.environ.get("MAIN_MODEL", "sonnet")
SUB_MODEL = "haiku"
MAIN_MAX_TURNS = 40
SUB_MAX_TURNS = 20


def conversation_cwd(conv_id: str) -> Path:

    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in conv_id)
    d = CONV_ROOT / safe
    d.mkdir(parents=True, exist_ok=True)
    return d


def _build_sub_options(task: Task, provider_env: dict[str, str] | None = None, model: str | None = None) -> Any:

    from claude_agent_sdk import ClaudeAgentOptions

    skill, server, allowed = mount_role(task.role)
    from app.orch.common_tools import COMMON_ALLOWED, COMMON_SERVER

    return ClaudeAgentOptions(
        system_prompt=skill,
        model=model or SUB_MODEL,
        mcp_servers={f"banking_{task.role}": server, "common": COMMON_SERVER},
        tools=[],
        allowed_tools=allowed + COMMON_ALLOWED,
        permission_mode="dontAsk",
        setting_sources=[],
        max_turns=SUB_MAX_TURNS,
        cwd=str(conversation_cwd(task.conv_id)),
        env=provider_env or {},
    )


async def run_sub_turn(task: Task) -> dict[str, Any]:

    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeSDKClient,
        ResultMessage,
        TextBlock,
        ThinkingBlock,
        ToolResultBlock,
        ToolUseBlock,
        UserMessage,
    )

    from app.orch.providers import conv_provider_env, conv_sub_model

    conv = await store.get_conversation(task.conv_id)
    _cprov = conv.get("provider") if conv else None
    penv = conv_provider_env(_cprov)

    smodel = conv_sub_model(_cprov)
    brief = task.input or task.title
    client = ClaudeSDKClient(options=_build_sub_options(task, penv, smodel))
    text_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []

    pending: dict[str, dict[str, Any]] = {}
    try:
        await client.connect()
        await client.query(brief)
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        text_parts.append(block.text)
                    elif isinstance(block, ThinkingBlock):
                        _emit_thinking(task.conv_id, task.id, block.thinking)
                    elif isinstance(block, ToolUseBlock):
                        tool_name = block.name.split("__")[-1]
                        tool_calls.append({"tool": tool_name, "input": block.input})
                        pending[block.id] = {"tool": tool_name, "input": block.input}
            elif isinstance(msg, UserMessage):
                for block in getattr(msg, "content", []) or []:
                    if isinstance(block, ToolResultBlock):
                        info = pending.pop(block.tool_use_id, None)
                        if info is not None:
                            await _audit_tool_call(task, info["tool"], info["input"], block.content)
            elif isinstance(msg, ResultMessage):
                from app.orch import instrument

                _m = instrument.extract_metrics(msg)
                await store.save_task_metrics(task.id, _m)
                instrument.log_turn(
                    conv_id=task.conv_id,
                    actor=f"sub:{task.role}",
                    provider=_cprov,
                    model=smodel,
                    base_url=penv.get("ANTHROPIC_BASE_URL") if penv else None,
                    metrics=_m,
                )
    finally:
        for info in pending.values():
            await _audit_tool_call(task, info["tool"], info["input"], None)
        try:
            await client.disconnect()
        except Exception as e:  # noqa: BLE001
            log.warning("sub-task disconnect failed: %s", e)
    return {"text": "".join(text_parts), "tool_calls": tool_calls}


def _build_main_options(
    conv_id: str,
    resume: str | None,
    provider_env: dict[str, str] | None = None,
    model: str | None = None,
    tenant_id: str | None = None,
) -> Any:

    from claude_agent_sdk import ClaudeAgentOptions

    from app.orch.common_tools import COMMON_ALLOWED, COMMON_SERVER
    from app.orch.orch_tools import ORCH_ALLOWED, build_orch_server

    skill = get_main_skill() + _customer_prompt_block(conv_id) + linked_case_prompt_block(conv_id, tenant_id)

    return ClaudeAgentOptions(
        system_prompt=skill,
        model=model or MAIN_MODEL,
        mcp_servers={"orch": build_orch_server(conv_id), "common": COMMON_SERVER},
        tools=[],
        allowed_tools=ORCH_ALLOWED + COMMON_ALLOWED,
        permission_mode="dontAsk",
        setting_sources=[],
        max_turns=MAIN_MAX_TURNS,
        cwd=str(conversation_cwd(conv_id)),
        resume=resume,
        env=provider_env or {},
    )


async def run_main_turn(conv_id: str, prompt: str, on_text: Any = None) -> dict[str, Any]:

    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeSDKClient,
        ProcessError,
        ResultMessage,
        TextBlock,
        ThinkingBlock,
        ToolResultBlock,
        ToolUseBlock,
        UserMessage,
    )

    registry.CTX_CONV.set(conv_id)
    registry.CTX_ACTOR.set("main")
    registry.CTX_TASK.set("")

    from app.orch.providers import conv_provider_env

    _conv = await store.get_conversation(conv_id)
    penv = conv_provider_env(_conv.get("provider") if _conv else None)
    cmodel = _conv.get("model") if _conv else None  # D-45b (c): model per-conv → MAIN (null → MAIN_MODEL)
    expected = await store.get_conv_session_id(conv_id)
    try:
        client = ClaudeSDKClient(
            options=_build_main_options(
                conv_id,
                resume=expected,
                provider_env=penv,
                model=cmodel,
                tenant_id=_conv.get("tenant_id") if _conv else None,
            )
        )
        await client.connect()
    except ProcessError:
        if not expected:
            raise
        log.warning("resume %s failed; starting fresh (conv %s)", expected, conv_id)
        await store.set_conv_session_id(conv_id, None)
        client = ClaudeSDKClient(
            options=_build_main_options(
                conv_id,
                resume=None,
                provider_env=penv,
                model=cmodel,
                tenant_id=_conv.get("tenant_id") if _conv else None,
            )
        )
        await client.connect()

    registry.main_clients[conv_id] = client  # Enable interrupt (§7); removed in finally.
    text_parts: list[str] = []
    session_id: str | None = None
    is_error = False
    main_metrics: dict[str, Any] = {}
    pending: dict[str, dict[str, Any]] = {}
    try:
        await client.query(prompt)
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        text_parts.append(block.text)
                        if on_text is not None:
                            await on_text(block.text)
                    elif isinstance(block, ThinkingBlock):
                        _emit_thinking(conv_id, None, block.thinking)
                    elif isinstance(block, ToolUseBlock):
                        pending[block.id] = {"tool": block.name.split("__")[-1], "input": block.input}
            elif isinstance(msg, UserMessage):
                for block in getattr(msg, "content", []) or []:
                    if isinstance(block, ToolResultBlock):
                        info = pending.pop(block.tool_use_id, None)
                        if info is not None:
                            await _audit_main_tool_call(conv_id, info["tool"], info["input"], block.content)
            elif isinstance(msg, ResultMessage):
                session_id = getattr(msg, "session_id", None)
                is_error = bool(getattr(msg, "is_error", False))

                from app.orch import instrument

                main_metrics = instrument.extract_metrics(msg)
                instrument.log_turn(
                    conv_id=conv_id,
                    actor="main",
                    provider=_conv.get("provider") if _conv else None,
                    model=cmodel,
                    base_url=penv.get("ANTHROPIC_BASE_URL") if penv else None,
                    metrics=main_metrics,
                )
    finally:
        for info in pending.values():
            await _audit_main_tool_call(conv_id, info["tool"], info["input"], None)
        registry.main_clients.pop(conv_id, None)
        try:
            await client.disconnect()
        except Exception as e:  # noqa: BLE001
            log.warning("main disconnect failed: %s", e)

    if session_id and session_id != expected:
        await store.set_conv_session_id(conv_id, session_id)
    return {"text": "".join(text_parts), "session_id": session_id, "is_error": is_error, "metrics": main_metrics}


async def _resume_dispatch_guard(conv_id: str, event: str, data: dict) -> bool:

    from app.orch import store_approvals
    from app.orch.dispatch import orch_dispatch_impl
    from app.orch.gated import GATED_ROLE

    if event == "approval_decided" and data.get("decision") == "approved":
        role = GATED_ROLE.get(data.get("action", ""))
        if role and registry.get_running_task_id(conv_id, role) is not None:
            log.info(
                "resume-guard A: %s is still running; deferring redispatch until task_done (conv %s)", role, conv_id
            )
            return True

    if event == "task_done":
        grant = await store_approvals.peek_grant(conv_id)
        if grant is None:
            return False

        done_role = data.get("role")
        action = grant["action"]
        role = GATED_ROLE.get(action)

        if not (role and role == done_role and registry.get_running_task_id(conv_id, role) is None):
            return False

        if grant["exec_attempts"] >= store_approvals.MAX_EXEC_ATTEMPTS:
            await store_approvals.mark_exec_failed(grant["id"])
            log.warning(
                "resume-guard B: %s exceeded the redispatch limit of %d; marking exec_failed (conv %s)",
                action,
                store_approvals.MAX_EXEC_ATTEMPTS,
                conv_id,
            )

            data["exec_failed"] = {
                "action": action,
                "attempts": store_approvals.MAX_EXEC_ATTEMPTS,
                "payload_summary": ", ".join(f"{k}={v}" for k, v in (grant.get("payload") or {}).items()),
            }
            return False

        attempt = await store_approvals.claim_exec_attempt(grant["id"])
        payload_summary = ", ".join(f"{k}={v}" for k, v in (grant.get("payload") or {}).items())
        brief = (
            get_prompt_service()
            .render(
                "task.approved_execution",
                {"action": action, "payload_summary": payload_summary},
            )
            .rstrip("\n")
        )
        title = f"Execute approved {action} ({payload_summary})"
        log.info("resume-guard B: redispatching %s claim %s attempt %d (conv %s)", role, action, attempt, conv_id)

        await orch_dispatch_impl(conv_id, role, title, brief)
        return True
    return False


async def _turn_runner(conv_id: str, event: str, data: dict) -> None:

    import uuid

    from app.sse.emit import emit_chat_delta, emit_chat_done, emit_conversation_status

    if await _resume_dispatch_guard(conv_id, event, data):
        return

    prompt = _build_event_prompt(event, data)
    turn_id = str(uuid.uuid4())

    await store.set_conv_status(conv_id, "running")
    emit_conversation_status(conv_id, "running")

    async def on_text(chunk: str) -> None:
        emit_chat_delta(conv_id, turn_id, chunk)

    try:
        result = await run_main_turn(conv_id, prompt, on_text=on_text)
        text = result["text"]
        if result["is_error"]:
            await store.add_message(conv_id, "system", text or "The processing turn failed.")
            emit_chat_done(conv_id, turn_id, text)
            await store.set_conv_status(conv_id, "failed")
            emit_conversation_status(conv_id, "failed")
        else:
            if text:
                _meta = {"metrics": result.get("metrics")} if result.get("metrics") else None
                await store.add_message(conv_id, "assistant", text, meta=_meta)
            emit_chat_done(conv_id, turn_id, text)
            await store.set_conv_status(conv_id, "idle")
            emit_conversation_status(conv_id, "idle")
    except Exception as e:  # noqa: BLE001
        import logging

        logging.getLogger("orch.session").error("main turn failed conv %s: %s", conv_id, e)
        msg = f"The system encountered an error while processing: {str(e)[:200]}. Send the message again to continue."
        await store.add_message(conv_id, "system", msg)
        emit_chat_done(conv_id, turn_id, "")
        await store.set_conv_status(conv_id, "failed")
        emit_conversation_status(conv_id, "failed")


def boot() -> None:

    from app.orch import room, sub_runner

    sub_runner.set_default_runner(run_sub_turn)
    room.set_turn_runner(_turn_runner)
    room.wire_event_sink()


def roles_available() -> list[str]:
    from app.orch.sub_runner import discovered_roles

    return sorted(discovered_roles())
