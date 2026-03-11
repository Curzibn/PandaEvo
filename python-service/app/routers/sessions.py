from __future__ import annotations

import json
import re
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select

from app.agent import AgentRunner
from app.db import async_session
from app.providers.store import get_models_for_purpose, get_provider_for_model, resolved_to_provider_like
from app.db.models import Plan
from app.logger import get_logger
from app.orchestrator import OrchestratorAgent, decide_route
from app.providers.llm import llm_provider
from app.sandbox import sandbox_manager
from app.sessions.store import SessionData, SessionSummary, session_store
from app.tools._utils import safe_path, session_ctx

logger = get_logger(__name__)

router = APIRouter(prefix="/sessions", tags=["sessions"])

_AT_REF_RE = re.compile(r"@([\w./\\-]+)")


async def _generate_title(
    session_id: str,
    model: str,
    user_content: str,
    api_key: str,
    api_base: str | None,
) -> str | None:
    try:
        title_response = await llm_provider.complete(
            model=model,
            messages=[{
                "role": "user",
                "content": f"请用10字以内概括下面这个问题的主题，只输出标题本身，不加任何解释：\n\n{user_content}",
            }],
            api_key=api_key,
            api_base=api_base,
            extra_body={"enable_thinking": False},
        )
        title = (title_response.get("content") or "").strip()
        if title:
            await session_store.update_title(session_id, title)
            return title
        return None
    except Exception:
        logger.exception("Failed to generate title for session %s", session_id)
        return None


def _expand_at_refs(content: str) -> str:
    def _replace(match: re.Match) -> str:
        rel = match.group(1)
        try:
            target = safe_path(rel)
        except PermissionError:
            return match.group(0)
        if not target.exists() or not target.is_file():
            return match.group(0)
        try:
            file_content = target.read_text(encoding="utf-8", errors="replace")
            return f"@{rel}\n```\n{file_content}\n```"
        except OSError:
            return match.group(0)

    return _AT_REF_RE.sub(_replace, content)


class SessionCreate(BaseModel):
    model: str


class SessionOut(BaseModel):
    id: str
    model: str
    messages: list[dict[str, Any]]
    created_at: str


class SessionSummaryOut(BaseModel):
    id: str
    model: str
    title: str | None
    created_at: str
    message_count: int


class ModelUpdate(BaseModel):
    model: str


class ChatMessage(BaseModel):
    content: str
    multi: bool | None = None
    route_mode: Literal["auto", "direct", "orchestrator"] = "auto"


class TitleGenerateRequest(BaseModel):
    content: str


class TitleGenerateResponse(BaseModel):
    title: str | None


def _session_out(data: SessionData) -> SessionOut:
    return SessionOut(
        id=data.id,
        model=data.model,
        messages=data.messages,
        created_at=data.created_at,
    )


def _summary_out(data: SessionSummary) -> SessionSummaryOut:
    return SessionSummaryOut(
        id=data.id,
        model=data.model,
        title=data.title,
        created_at=data.created_at,
        message_count=data.message_count,
    )


def _export_iso(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


async def _load_session_plans(session_id: str) -> list[dict[str, Any]]:
    async with async_session() as db:
        result = await db.execute(
            select(Plan).where(Plan.session_id == session_id).order_by(Plan.created_at.asc())
        )
        plans = result.scalars().all()
    return [
        {
            "id": plan.id,
            "tasks": plan.tasks,
            "status": plan.status,
            "created_at": _export_iso(plan.created_at),
        }
        for plan in plans
    ]


def _build_export_payload(data: SessionData, plans: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "session": {
            "id": data.id,
            "title": data.title,
            "model": data.model,
            "created_at": data.created_at,
        },
        "messages": data.messages,
        "plans": plans,
        "meta": {
            "source": "pandaevo",
            "trace_mode": "full_trace",
        },
    }


async def _resolve_provider(model: str):
    async with async_session() as db:
        row = await get_provider_for_model(db, model)
    if row is None:
        raise HTTPException(
            status_code=422,
            detail=f"Model '{model}' not found in any configured provider.",
        )
    return row


@router.get("/{session_id}/export")
async def export_session(session_id: str) -> Response:
    data = await session_store.get(session_id)
    if not data:
        raise HTTPException(status_code=404, detail="Session not found.")

    plans = await _load_session_plans(session_id)
    payload = _build_export_payload(data, plans)
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    filename = f"pandaevo-session-{session_id}-{stamp}.json"
    return Response(
        content=body,
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("", response_model=list[SessionSummaryOut])
async def list_sessions() -> list[SessionSummaryOut]:
    summaries = await session_store.list_sessions()
    return [_summary_out(s) for s in summaries]


@router.post("", response_model=SessionOut, status_code=201)
async def create_session(body: SessionCreate) -> SessionOut:
    await _resolve_provider(body.model)
    data = await session_store.create(body.model)
    return _session_out(data)


@router.get("/{session_id}", response_model=SessionOut)
async def get_session(session_id: str) -> SessionOut:
    data = await session_store.get(session_id)
    if not data:
        raise HTTPException(status_code=404, detail="Session not found.")
    return _session_out(data)


@router.delete("/{session_id}", status_code=204)
async def delete_session(session_id: str) -> None:
    deleted = await session_store.delete(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found.")
    await sandbox_manager.cleanup(session_id)


@router.patch("/{session_id}/model", response_model=SessionOut)
async def update_model(session_id: str, body: ModelUpdate) -> SessionOut:
    await _resolve_provider(body.model)
    data = await session_store.update_model(session_id, body.model)
    if not data:
        raise HTTPException(status_code=404, detail="Session not found.")
    return _session_out(data)


@router.post("/{session_id}/title", response_model=TitleGenerateResponse)
async def generate_title(session_id: str, body: TitleGenerateRequest) -> TitleGenerateResponse:
    data = await session_store.get(session_id)
    if not data:
        raise HTTPException(status_code=404, detail="Session not found.")
    
    if not body.content:
        return TitleGenerateResponse(title=None)
    
    if data.title is not None:
        import re
        if not re.match(r"^(新对话|对话)\s*\d+$", data.title or ""):
            raise HTTPException(status_code=409, detail="Session already has a title.")
    
    provider = await _resolve_provider(data.model)
    async with async_session() as db:
        title_candidates = await get_models_for_purpose(db, "title")

    if not title_candidates:
        title_candidates = []

    title: str | None = None
    for candidate in title_candidates:
        title = await _generate_title(
            session_id=session_id,
            model=candidate.model_id,
            user_content=body.content,
            api_key=candidate.api_key,
            api_base=candidate.api_base,
        )
        if title:
            break

    if not title:
        title = await _generate_title(
            session_id=session_id,
            model=data.model,
            user_content=body.content,
            api_key=provider.api_key,
            api_base=provider.api_base,
        )

    return TitleGenerateResponse(title=title)


@router.post("/{session_id}/chat")
async def chat(session_id: str, body: ChatMessage) -> StreamingResponse:
    data = await session_store.get(session_id)
    if not data:
        raise HTTPException(status_code=404, detail="Session not found.")

    provider = await _resolve_provider(data.model)
    expanded_content = _expand_at_refs(body.content)
    await session_store.append_message(session_id, "user", expanded_content)

    refreshed = await session_store.get(session_id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    async with async_session() as db:
        worker_candidates = await get_models_for_purpose(db, "worker") if body.multi else []

    worker_res = worker_candidates[0] if worker_candidates else None

    async def _resolve_route_mode() -> tuple[str, str]:
        if body.multi is not None:
            return ("orchestrator", "explicit: multi=true") if body.multi else ("direct", "explicit: multi=false")
        if body.route_mode == "direct":
            return "direct", "explicit: route_mode=direct"
        if body.route_mode == "orchestrator":
            return "orchestrator", "explicit: route_mode=orchestrator"
        decision = await decide_route(
            model=data.model,
            messages=refreshed.messages,
            provider=provider,
        )
        return decision.route, decision.reason

    def _event_stream(route: str) -> AsyncGenerator[dict[str, Any], None]:
        if route == "orchestrator":
            if worker_res is not None:
                worker_model = worker_res.model_id
                worker_provider = resolved_to_provider_like(worker_res)
            else:
                worker_model = data.model
                worker_provider = provider
            return OrchestratorAgent().run(
                task=body.content,
                model=data.model,
                messages=refreshed.messages,
                orchestrator_provider=provider,
                worker_model=worker_model,
                worker_provider=worker_provider,
            )
        return AgentRunner().run(
            model=data.model,
            messages=refreshed.messages,
            provider=provider,
        )

    async def sse_generator() -> AsyncGenerator[str, None]:
        token = session_ctx.set(session_id)
        current_plan_id: str | None = None

        async def _save_plan(tasks: list[dict[str, Any]]) -> str:
            async with async_session() as db:
                plan = Plan(session_id=session_id, tasks=tasks, status="running")
                db.add(plan)
                await db.commit()
                await db.refresh(plan)
                return plan.id

        async def _update_plan_status(plan_id: str, status: str) -> None:
            from sqlalchemy import update as sa_update
            async with async_session() as db:
                await db.execute(
                    sa_update(Plan).where(Plan.id == plan_id).values(status=status)
                )
                await db.commit()

        try:
            assistant_tokens: list[str] = []
            route, reason = await _resolve_route_mode()
            yield f"data: {json.dumps({'type': 'route', 'route': route, 'reason': reason}, ensure_ascii=False)}\n\n"

            async for event in _event_stream(route):
                etype = event["type"]

                if etype == "token":
                    assistant_tokens.append(event["content"])
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

                elif etype == "plan":
                    try:
                        current_plan_id = await _save_plan(event.get("tasks", []))
                        event = {**event, "plan_id": current_plan_id}
                    except Exception:
                        logger.exception("Failed to persist plan for session %s", session_id)
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

                elif etype in ("tool_call", "tool_result", "error", "thinking",
                               "worker_start", "worker_event", "worker_done"):
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

                elif etype == "checkpoint":
                    for msg in event.get("messages", []):
                        role = msg.get("role", "")
                        if role == "assistant":
                            serialized = json.dumps(
                                {"content": msg.get("content", ""), "tool_calls": msg.get("tool_calls")},
                                ensure_ascii=False,
                            )
                            await session_store.append_message(session_id, "assistant", serialized)
                        elif role == "tool":
                            serialized = json.dumps(
                                {"tool_call_id": msg.get("tool_call_id", ""), "content": msg.get("content", "")},
                                ensure_ascii=False,
                            )
                            await session_store.append_message(session_id, "tool", serialized)

                elif etype == "done":
                    new_msg: dict[str, Any] | None = event.get("new_message")
                    if new_msg:
                        thinking = new_msg.get("thinking")
                        content = "".join(assistant_tokens) or new_msg.get("content", "")
                        if thinking:
                            serialized = json.dumps(
                                {"content": content, "thinking": thinking},
                                ensure_ascii=False,
                            )
                            await session_store.append_message(session_id, "assistant", serialized)
                        else:
                            await session_store.append_message(session_id, "assistant", content)

                    if current_plan_id:
                        try:
                            await _update_plan_status(current_plan_id, "completed")
                        except Exception:
                            logger.exception("Failed to update plan status for session %s", session_id)

                    yield "data: [DONE]\n\n"
                    return

        except Exception:
            logger.exception("sse_generator error for session %s", session_id)
            if current_plan_id:
                try:
                    await _update_plan_status(current_plan_id, "failed")
                except Exception:
                    logger.exception("Failed to mark plan as failed for session %s", session_id)
            raise
        finally:
            session_ctx.reset(token)

    return StreamingResponse(sse_generator(), media_type="text/event-stream")
