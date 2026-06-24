from pathlib import Path

from app.agent.state import AgentState
from app.llm.repair_chain import request_repair_plan
from app.scanner.context_collector import build_code_context
from app.scanner.project_scanner import build_project_overview, scan_project_files


DEFAULT_EXTRA_CONTEXT_FILES = [
    "requirements.txt",
    "pyproject.toml",
    "app/main.py",
    "app/config.py",
    "app/agent/graph.py",
    "app/agent/nodes.py",
    "app/agent/state.py",
    "app/llm/client.py",
    "app/llm/repair_chain.py",
    "app/llm/repair_schema.py",
]


def collect_context_node(state: AgentState) -> AgentState:
    problem = state["problem"]

    project_path_value = state.get("project_path")
    project_root = Path(project_path_value).resolve() if project_path_value else None

    if project_root:
        extra_files = scan_project_files(
            project_root=project_root,
            max_files=30,
        )
    else:
        extra_files = DEFAULT_EXTRA_CONTEXT_FILES

    code_context = build_code_context(
        problem,
        extra_files=extra_files,
        project_root=project_root,
        max_files=12,
    )

    context_report = (
        "\n\nProject context collector report:\n"
        f"- Project path: {project_root if project_root else 'default'}\n"
        f"- Included files: {code_context.included_files}\n"
        f"- Missing referenced files: {code_context.missing_referenced_files}\n"
        f"- Missing optional context files: {code_context.missing_optional_files}\n"
        f"- Skipped files: {code_context.skipped_files}\n"
    )

    project_overview = build_project_overview(project_root=project_root)

    full_problem = (
        problem
        + context_report
        + "\n\n"
        + project_overview
    )

    if code_context.text:
        full_problem += (
            "\n\nRelevant project file contents:\n\n"
            + code_context.text
        )

    return {
        "context_report": context_report,
        "project_overview": project_overview,
        "full_problem": full_problem,
        "included_files": code_context.included_files,
        "missing_referenced_files": code_context.missing_referenced_files,
        "missing_optional_files": code_context.missing_optional_files,
        "skipped_files": code_context.skipped_files,
    }


def create_repair_plan_node(state: AgentState) -> AgentState:
    full_problem = state["full_problem"]

    plan = request_repair_plan(full_problem)

    return {
        "repair_plan": plan.model_dump(mode="json")
    }
