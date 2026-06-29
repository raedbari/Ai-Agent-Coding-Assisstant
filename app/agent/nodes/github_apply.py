from __future__ import annotations

from pathlib import Path

from app.agent.state import AgentState
from app.projects.registry import get_project
from app.security.sonar_github_apply import push_sonar_project_diff_to_github


def apply_patch_to_github_node(state: AgentState) -> AgentState:
    if state.get("approval_status") != "approved":
        return {
            **state,
            "error": "Patch was not approved.",
        }

    diff = state.get("diff")

    if not diff:
        return {
            **state,
            "error": "No diff is available to apply.",
        }

    project = get_project(state["project_id"])

    result = push_sonar_project_diff_to_github(
        diff_text=diff,
        project_id=project.id,
        project_path=project.path,
        project_root=Path(state["project_root"]),
    )

    return {
        **state,
        "apply_result": result,
    }