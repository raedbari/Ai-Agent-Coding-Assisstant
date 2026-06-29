from __future__ import annotations

from typing import Any, TypedDict

from app.agent.schemas import ApprovalStatus


class AgentState(TypedDict, total=False):
    project_id: str
    project_path: str
    project_root: str

    issues: list[dict[str, Any]]
    selected_issues: list[dict[str, Any]]

    included_files: list[str]
    context_report: str

    prompt: str

    fix: dict[str, Any]
    diff: str

    approval_status: ApprovalStatus
    approval_payload: dict[str, Any]

    apply_result: dict[str, Any]

    error: str