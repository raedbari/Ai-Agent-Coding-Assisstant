from __future__ import annotations

from pathlib import Path


def _safe_resolve(project_root: Path, relative_path: str) -> Path:
    root = project_root.resolve()
    candidate = (root / relative_path).resolve()

    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(f"Unsafe file path: {relative_path}") from exc

    if not candidate.is_file():
        raise RuntimeError(f"File not found: {candidate}")

    return candidate


def _read_code_context(file_path: Path, line: int | None, radius: int = 25) -> str:
    lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()

    if not line:
        start = 1
        end = min(len(lines), radius * 2)
    else:
        start = max(1, line - radius)
        end = min(len(lines), line + radius)

    rendered: list[str] = []

    for number in range(start, end + 1):
        marker = ">>" if line and number == line else "  "
        rendered.append(f"{marker} {number:4d}: {lines[number - 1]}")

    return "\n".join(rendered)


def build_sonar_issue_prompt(
    issue: dict,
    project_root: Path,
    context_radius: int = 25,
) -> dict[str, str]:
    file_path = _safe_resolve(project_root, issue["file_path"])

    code_context = _read_code_context(
        file_path=file_path,
        line=issue.get("start_line"),
        radius=context_radius,
    )

    language_hint = file_path.suffix.lstrip(".") or "text"

    prompt = f"""You are fixing a static analysis issue reported by SonarQube.

Rules:
- Fix only the reported issue.
- Do not rewrite unrelated code.
- Preserve existing behavior unless the issue is specifically about wrong behavior.
- Do not invent missing requirements.
- Return a unified diff only.
- If there is not enough context to safely fix the issue, explain why instead of inventing a patch.

Issue:
- Source: {issue["source"]}
- Rule: {issue["rule_id"]}
- Severity: {issue["severity"]}
- Type: {issue["type"]}
- Message: {issue["message"]}
- File: {issue["file_path"]}
- Start line: {issue["start_line"]}
- End line: {issue["end_line"]}
- Tags: {", ".join(issue["tags"]) if issue.get("tags") else "none"}

Code context:
```{language_hint}
{code_context}