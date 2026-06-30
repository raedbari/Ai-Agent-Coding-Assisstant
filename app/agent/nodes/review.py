from __future__ import annotations

from pathlib import Path
from typing import Any

from langgraph.types import interrupt

from app.agent.schemas import ReviewPayload
from app.agent.state import AgentState
from app.security.sonar_github_apply import validate_sonar_project_diff_for_github


def _get_value(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)

    return getattr(value, key, default)


def review_fix_node(state: AgentState) -> dict:
    fix = state.get("fix")

    if fix is None:
        return {
            "error": "No fix was generated before review.",
        }

    diff = _get_value(fix, "diff", "")

    if not diff or not str(diff).strip():
        return {
            "error": "Generated fix does not contain a diff.",
        }

    project_id = str(state.get("project_id") or "")
    project_path_raw = state.get("project_path")
    project_root_raw = state.get("project_root")

    if not project_id:
        return {
            "error": "Missing project_id before diff review.",
        }

    if not project_path_raw:
        return {
            "error": "Missing project_path before diff review.",
        }

    if not project_root_raw:
        return {
            "error": "Missing project_root before diff review.",
        }

    validation_result = validate_sonar_project_diff_for_github(
        diff_text=str(diff),
        project_id=project_id,
        project_path=Path(str(project_path_raw)),
        project_root=Path(str(project_root_raw)),
    )

    if not validation_result.get("success"):
        return {
            "error": (
                "Generated diff failed pre-review validation: "
                f"{validation_result.get('message')}"
            ),
            "diff_validation": validation_result,
        }

    payload = ReviewPayload(
        type="review_diff",
        project_id=project_id,
        summary=str(_get_value(fix, "summary", "")),
        risk=_get_value(fix, "risk", "medium"),
        changed_files=list(_get_value(fix, "changed_files", [])),
        diff=str(diff),
    )

    decision = interrupt(payload.model_dump(mode="json"))

    approved = bool(_get_value(decision, "approved", False))
    reason = _get_value(decision, "reason", None)

    return {
        "approval_status": "approved" if approved else "rejected",
        "approval_payload": {
            "approved": approved,
            "reason": reason,
        },
    }