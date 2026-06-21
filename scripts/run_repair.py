import sys
from pathlib import Path

from app.llm.repair_chain import request_repair_plan
from app.scanner.context_collector import build_code_context

from app.scanner.project_scanner import build_project_overview

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ERROR_FILE = PROJECT_ROOT / "demo_projects" / "current_error.txt"


def resolve_input_file() -> Path:
    if len(sys.argv) >= 2:
        input_path = Path(sys.argv[1])

        if not input_path.is_absolute():
            input_path = PROJECT_ROOT / input_path

        return input_path

    return DEFAULT_ERROR_FILE


def main() -> None:
    error_file = resolve_input_file()

    if not error_file.exists():
        raise FileNotFoundError(f"Error file not found: {error_file}")

    problem = error_file.read_text(encoding="utf-8").strip()
    
    
    if not problem:
        raise ValueError(f"Error file is empty: {error_file}")

    code_context = build_code_context(
        problem,
        extra_files=[
            "requirements.txt",
            "pyproject.toml",
            "app/main.py",
            "app/config.py",
            "app/agent/graph.py",
            "app/agent/nodes.py",
            "app/llm/client.py",
            "app/llm/repair_chain.py",
            "app/llm/repair_schema.py",
        ],
    )

    context_report = (
     "\n\nProject context collector report:\n"
     f"- Included files: {code_context.included_files}\n"
     f"- Missing referenced files: {code_context.missing_referenced_files}\n"
     f"- Missing optional context files: {code_context.missing_optional_files}\n"
     f"- Skipped files: {code_context.skipped_files}\n"
    ) 
    print(context_report)
    
    project_overview = build_project_overview()

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

    plan = request_repair_plan(full_problem)

    print(plan.model_dump_json(indent=2))


if __name__ == "__main__":
    main()