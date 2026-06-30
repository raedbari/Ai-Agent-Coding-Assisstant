from __future__ import annotations

import json
from typing import Any, Iterator
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
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


def _find_interrupt_payload(value: Any) -> dict[str, Any] | None:
    payload = _extract_interrupt_payload(value)

    if payload:
        return payload

    if isinstance(value, dict):
        for child in value.values():
            child_payload = _find_interrupt_payload(child)

            if child_payload:
                return child_payload

    if isinstance(value, (list, tuple)):
        for child in value:
            child_payload = _find_interrupt_payload(child)

            if child_payload:
                return child_payload

    return None


def _summarize_fix(fix: Any) -> dict[str, Any] | None:
    if not isinstance(fix, dict):
        return None

    return {
        "summary": fix.get("summary"),
        "risk": fix.get("risk"),
        "changed_files": fix.get("changed_files", []),
    }


def _summarize_apply_result(apply_result: Any) -> Any:
    if not isinstance(apply_result, dict):
        return apply_result

    return {
        "success": apply_result.get("success"),
        "status": apply_result.get("status"),
        "message": apply_result.get("message"),
        "branch": apply_result.get("branch"),
        "commit_sha": apply_result.get("commit_sha"),
        "applied_files": apply_result.get("applied_files", []),
        "diff": apply_result.get("diff"),
    }


def _summarize_agent_output(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {"result": str(result)}

    fix = result.get("fix") or {}
    apply_result = result.get("apply_result")

    return {
        "project_id": result.get("project_id"),
        "approval_status": result.get("approval_status"),
        "approval_payload": result.get("approval_payload"),
        "fix": _summarize_fix(fix),
        "apply_result": _summarize_apply_result(apply_result),
        "error": result.get("error"),
    }


def _summarize_node_update(node_name: str, update: Any) -> dict[str, Any]:
    if not isinstance(update, dict):
        return {
            "node": node_name,
            "update": str(update),
        }

    summary: dict[str, Any] = {
        "node": node_name,
    }

    if update.get("project_id"):
        summary["project_id"] = update.get("project_id")

    if update.get("project_path"):
        summary["project_path"] = str(update.get("project_path"))

    if update.get("error"):
        summary["error"] = update.get("error")

    if "issues" in update and isinstance(update.get("issues"), list):
        summary["issues_count"] = len(update["issues"])

    if "selected_issues" in update and isinstance(update.get("selected_issues"), list):
        summary["selected_issues_count"] = len(update["selected_issues"])
        summary["selected_issues"] = [
            {
                "rule_id": issue.get("rule_id"),
                "severity": issue.get("severity"),
                "message": issue.get("message"),
                "file_path": issue.get("file_path"),
                "line": issue.get("line") or issue.get("start_line"),
            }
            for issue in update["selected_issues"][:10]
            if isinstance(issue, dict)
        ]

    if "fix" in update:
        summary["fix"] = _summarize_fix(update.get("fix"))

    if "approval_status" in update:
        summary["approval_status"] = update.get("approval_status")

    if "approval_payload" in update:
        summary["approval_payload"] = update.get("approval_payload")

    if "apply_result" in update:
        summary["apply_result"] = _summarize_apply_result(update.get("apply_result"))

    if "diff_validation" in update and isinstance(update.get("diff_validation"), dict):
        validation = update["diff_validation"]
        summary["diff_validation"] = {
            "success": validation.get("success"),
            "status": validation.get("status"),
            "message": validation.get("message"),
        }

    return summary


def _get_graph_state_values(graph: Any, config: dict[str, Any]) -> dict[str, Any] | None:
    try:
        snapshot = graph.get_state(config)
    except Exception:
        return None

    values = getattr(snapshot, "values", None)

    if isinstance(values, dict):
        return values

    if isinstance(snapshot, dict) and isinstance(snapshot.get("values"), dict):
        return snapshot["values"]

    return None


def _ndjson_event(event: str, data: dict[str, Any]) -> str:
    return json.dumps(
        {
            "event": event,
            "data": data,
        },
        ensure_ascii=False,
        default=str,
    ) + "\n"


def _stream_graph_run(
    graph_input: Any,
    thread_id: str,
    action: str,
) -> Iterator[str]:
    graph = build_repair_graph()
    config = _thread_config(thread_id)

    yield _ndjson_event(
        "run_started",
        {
            "thread_id": thread_id,
            "action": action,
        },
    )

    try:
        interrupted = False

        for chunk in graph.stream(
            graph_input,
            config=config,
            stream_mode="updates",
        ):
            review_payload = _find_interrupt_payload(chunk)

            if review_payload:
                interrupted = True
                yield _ndjson_event(
                    "review_required",
                    {
                        "thread_id": thread_id,
                        "review_payload": review_payload,
                    },
                )
                continue

            if isinstance(chunk, dict):
                for node_name, update in chunk.items():
                    if node_name == "__interrupt__":
                        continue

                    yield _ndjson_event(
                        "node_update",
                        _summarize_node_update(str(node_name), update),
                    )
            else:
                yield _ndjson_event(
                    "node_update",
                    {
                        "node": "graph",
                        "update": str(chunk),
                    },
                )

        if interrupted:
            yield _ndjson_event(
                "done",
                {
                    "thread_id": thread_id,
                    "status": "interrupted",
                },
            )
            return

        values = _get_graph_state_values(graph, config)

        yield _ndjson_event(
            "completed",
            {
                "thread_id": thread_id,
                "status": "completed",
                "output": _summarize_agent_output(values or {}),
            },
        )

        yield _ndjson_event(
            "done",
            {
                "thread_id": thread_id,
                "status": "completed",
            },
        )

    except Exception as exc:
        yield _ndjson_event(
            "error",
            {
                "thread_id": thread_id,
                "message": str(exc),
            },
        )

        yield _ndjson_event(
            "done",
            {
                "thread_id": thread_id,
                "status": "error",
            },
        )


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
        output=_summarize_agent_output(result),
    )


@router.post("/projects/{project_id}/start/stream")
def start_agent_repair_stream(project_id: str) -> StreamingResponse:
    thread_id = str(uuid4())

    return StreamingResponse(
        _stream_graph_run(
            graph_input={"project_id": project_id},
            thread_id=thread_id,
            action="start",
        ),
        media_type="application/x-ndjson; charset=utf-8",
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
        output=_summarize_agent_output(result),
    )


@router.post("/threads/{thread_id}/resume/stream")
def resume_agent_repair_stream(
    thread_id: str,
    decision: ReviewDecision,
) -> StreamingResponse:
    return StreamingResponse(
        _stream_graph_run(
            graph_input=Command(resume=decision.model_dump(mode="json")),
            thread_id=thread_id,
            action="resume",
        ),
        media_type="application/x-ndjson; charset=utf-8",
    )