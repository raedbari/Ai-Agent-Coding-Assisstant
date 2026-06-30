from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from langgraph.types import Command
from pydantic import BaseModel

from app.agent.graph import build_repair_graph
from app.agent.schemas import ReviewDecision


router = APIRouter(prefix="/agent", tags=["agent"])


class AgentStartResponse(BaseModel):
    thread_id: str
    status: str
    review_payload: dict[str, Any] | None = None
    output: dict[str, Any] | None = None


class AgentResumeResponse(BaseModel):
    thread_id: str
    status: str
    output: dict[str, Any] | None = None


def _thread_config(thread_id: str) -> dict[str, Any]:
    return {
        "configurable": {
            "thread_id": thread_id,
        }
    }


def _extract_interrupt_payload(result: Any) -> dict[str, Any] | None:
    if not isinstance(result, dict):
        return None

    interrupts = result.get("__interrupt__")

    if not interrupts:
        return None

    first_interrupt = interrupts[0]

    value = getattr(first_interrupt, "value", None)

    if isinstance(value, dict):
        return value

    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")

    return {"value": value}


@router.post("/projects/{project_id}/start", response_model=AgentStartResponse)
def start_agent_repair(project_id: str) -> AgentStartResponse:
    thread_id = str(uuid4())
    graph = build_repair_graph()

    try:
        result = graph.invoke(
            {"project_id": project_id},
            config=_thread_config(thread_id),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Agent start failed: {exc}",
        ) from exc

    review_payload = _extract_interrupt_payload(result)

    if review_payload:
        return AgentStartResponse(
            thread_id=thread_id,
            status="interrupted",
            review_payload=review_payload,
            output=None,
        )

    return AgentStartResponse(
        thread_id=thread_id,
        status="completed",
        review_payload=None,
        output=result if isinstance(result, dict) else {"result": str(result)},
    )


@router.post("/threads/{thread_id}/resume", response_model=AgentResumeResponse)
def resume_agent_repair(
    thread_id: str,
    decision: ReviewDecision,
) -> AgentResumeResponse:
    graph = build_repair_graph()

    try:
        result = graph.invoke(
            Command(resume=decision.model_dump(mode="json")),
            config=_thread_config(thread_id),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Agent resume failed: {exc}",
        ) from exc

    review_payload = _extract_interrupt_payload(result)

    if review_payload:
        return AgentResumeResponse(
            thread_id=thread_id,
            status="interrupted",
            output={"review_payload": review_payload},
        )

    return AgentResumeResponse(
        thread_id=thread_id,
        status="completed",
        output=result if isinstance(result, dict) else {"result": str(result)},
    )