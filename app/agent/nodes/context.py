from __future__ import annotations

from pathlib import Path

from app.agent.state import AgentState


MAX_CONTEXT_CHARS_PER_FILE = 12_000


def _safe_resolve(project_root: Path, relative_path: str) -> Path:
    root = project_root.resolve()
    candidate = (root / relative_path).resolve()

    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(f"Unsafe file path: {relative_path}") from exc

    return candidate


def collect_code_context_node(state: AgentState) -> AgentState:
    project_root = Path(state["project_root"]).resolve()
    selected_issues = state.get("selected_issues", [])

    included_files: list[str] = []
    context_parts: list[str] = []
    seen_files: set[str] = set()

    for issue in selected_issues:
        file_path = issue.get("file_path")

        if not file_path or file_path in seen_files:
            continue

        seen_files.add(file_path)

        target_file = _safe_resolve(project_root, file_path)

        if not target_file.is_file():
            context_parts.append(f"## Missing file: {file_path}")
            continue

        content = target_file.read_text(
            encoding="utf-8",
            errors="replace",
        )

        if len(content) > MAX_CONTEXT_CHARS_PER_FILE:
            content = (
                content[:MAX_CONTEXT_CHARS_PER_FILE]
                + "\n\n# ... file truncated for context ..."
            )

        included_files.append(file_path)

        context_parts.append(
            f"## File: {file_path}\n"
            f"```text\n{content}\n```"
        )

    return {
        **state,
        "included_files": included_files,
        "context_report": "\n\n".join(context_parts),
    }