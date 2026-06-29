from __future__ import annotations

from pathlib import Path

from app.agent.state import AgentState
from app.projects.registry import get_project
from app.security.sonar_client import fetch_demo_sonar_issues


def load_project_node(state: AgentState) -> AgentState:
    project_id = state["project_id"]
    project = get_project(project_id)

    return {
        **state,
        "project_id": project.id,
        "project_path": str(project.path),
        "project_root": str(Path.cwd()),
    }


def fetch_sonar_issues_node(state: AgentState) -> AgentState:
    issues = fetch_demo_sonar_issues(limit=100)

    return {
        **state,
        "issues": issues,
    }


def filter_project_issues_node(state: AgentState) -> AgentState:
    project_path = Path(state["project_path"]).resolve()
    project_root = Path(state["project_root"]).resolve()

    try:
        file_prefix = project_path.relative_to(project_root).as_posix()
    except ValueError as exc:
        raise RuntimeError(
            f"Project path is outside application root: {project_path}"
        ) from exc

    file_prefix = file_prefix.rstrip("/") + "/"

    selected_issues = [
        issue
        for issue in state.get("issues", [])
        if issue.get("file_path", "").startswith(file_prefix)
    ]

    return {
        **state,
        "selected_issues": selected_issues,
    }