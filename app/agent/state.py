from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    problem: str
    project_id: str
    project_path: str

    context_report: str
    project_overview: str
    full_problem: str

    included_files: list[str]
    missing_referenced_files: list[str]
    missing_optional_files: list[str]
    skipped_files: list[str]

    repair_plan: dict[str, Any]
    error: str

