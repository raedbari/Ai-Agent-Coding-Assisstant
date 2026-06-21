import tokenize
from pathlib import Path

from app.scanner.models import IssueRecord
from app.scanner.path_guard import (
    is_allowed_index_file,
    resolve_project_root,
    safe_relative_path,
)


MAX_CONTEXT_CHARS = 6000


def read_text_file(path: Path) -> str:
    with tokenize.open(path) as file:
        return file.read()


def clamp_line_range(
    target_line: int,
    total_lines: int,
    before: int,
    after: int,
) -> tuple[int, int]:
    start_line = max(1, target_line - before)
    end_line = min(total_lines, target_line + after)

    return start_line, end_line


def extract_code_context(
    project_root: str,
    issue: IssueRecord,
    before: int = 8,
    after: int = 8,
    max_chars: int = MAX_CONTEXT_CHARS,
) -> dict[str, object]:
    root = resolve_project_root(project_root)

    if not issue.file_path:
        return {
            "file_path": None,
            "line": issue.line,
            "context": "",
            "reason": "Issue has no file path",
        }

    target_path = (root / issue.file_path).resolve()

    try:
        safe_relative_path(root, target_path)
    except ValueError:
        return {
            "file_path": issue.file_path,
            "line": issue.line,
            "context": "",
            "reason": "File path is outside project root",
        }

    if not target_path.exists() or not target_path.is_file():
        return {
            "file_path": issue.file_path,
            "line": issue.line,
            "context": "",
            "reason": "File does not exist",
        }

    if not is_allowed_index_file(target_path):
        return {
            "file_path": issue.file_path,
            "line": issue.line,
            "context": "",
            "reason": "File is not allowed",
        }

    try:
        source = read_text_file(target_path)
    except (OSError, UnicodeDecodeError, SyntaxError) as error:
        return {
            "file_path": issue.file_path,
            "line": issue.line,
            "context": "",
            "reason": f"Could not read file: {error}",
        }

    lines = source.splitlines()

    if not lines:
        return {
            "file_path": issue.file_path,
            "line": issue.line,
            "context": "",
            "reason": "File is empty",
        }

    target_line = issue.line or 1
    start_line, end_line = clamp_line_range(
        target_line=target_line,
        total_lines=len(lines),
        before=before,
        after=after,
    )

    selected_lines: list[str] = []

    for line_number in range(start_line, end_line + 1):
        line_text = lines[line_number - 1]
        marker = ">>" if line_number == target_line else "  "
        selected_lines.append(f"{marker} {line_number}: {line_text}")

    context = "\n".join(selected_lines)

    if len(context) > max_chars:
        context = context[:max_chars] + "\n... context truncated ..."

    return {
        "file_path": issue.file_path,
        "line": issue.line,
        "context": context,
        "reason": "ok",
    }