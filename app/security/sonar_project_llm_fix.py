from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.llm.client import get_llm


SYSTEM_PROMPT = """You are a senior software repair assistant.

You receive SonarQube issues and the relevant source files.

Your job:
- Use the SonarQube issues as the source of truth.
- Fix all listed SonarQube issues in the provided files.
- If multiple issues are in the same file, produce one coherent patch for that file.
- Do not modify files that are not included in the prompt.
- Do not invent new requirements.
- Preserve public function names and existing intent when clear.
- Return a unified diff only.
- Do not wrap the diff in Markdown fences.
- Use paths relative to the repository root.
"""


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


def _read_file_with_line_numbers(file_path: Path) -> str:
    lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()

    rendered: list[str] = []
    for index, line in enumerate(lines, start=1):
        rendered.append(f"{index:5d}: {line}")

    return "\n".join(rendered)


def _message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []

        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
            else:
                parts.append(str(item))

        return "\n".join(parts)

    return str(content)


def build_project_sonar_prompt(
    issues: list[dict[str, Any]],
    project_root: Path,
) -> str:
    if not issues:
        raise ValueError("No SonarQube issues were provided.")

    issues_by_file: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for issue in issues:
        file_path = issue.get("file_path")
        if not file_path:
            continue

        issues_by_file[file_path].append(issue)

    if not issues_by_file:
        raise ValueError("No SonarQube issues with file paths were provided.")

    prompt_parts: list[str] = [
        "Repair the project using the SonarQube issues below.",
        "",
        "Important:",
        "- The SonarQube issue list is dynamic and is the source of the requested fixes.",
        "- Fix all listed issues.",
        "- If the same file contains multiple listed issues, fix them together in one patch.",
        "- Return a unified diff only.",
        "",
        "SonarQube issues:",
    ]

    issue_number = 1

    for file_path, file_issues in sorted(issues_by_file.items()):
        prompt_parts.append("")
        prompt_parts.append(f"File: {file_path}")

        for issue in file_issues:
            prompt_parts.extend(
                [
                    f"Issue #{issue_number}:",
                    f"- Key: {issue.get('issue_key')}",
                    f"- Rule: {issue.get('rule_id')}",
                    f"- Severity: {issue.get('severity')}",
                    f"- Type: {issue.get('type')}",
                    f"- Message: {issue.get('message')}",
                    f"- Start line: {issue.get('start_line')}",
                    f"- End line: {issue.get('end_line')}",
                    f"- Tags: {', '.join(issue.get('tags') or []) or 'none'}",
                ]
            )
            issue_number += 1

    prompt_parts.append("")
    prompt_parts.append("Relevant source files:")

    for file_path in sorted(issues_by_file):
        absolute_path = _safe_resolve(project_root, file_path)
        source = _read_file_with_line_numbers(absolute_path)

        prompt_parts.extend(
            [
                "",
                f"<<<FILE_START path=\"{file_path}\">>>",
                source,
                "<<<FILE_END>>>",
            ]
        )

    return "\n".join(prompt_parts)


def propose_project_sonar_fix_with_llm(
    issues: list[dict[str, Any]],
    project_root: Path,
) -> dict[str, str]:
    prompt = build_project_sonar_prompt(
        issues=issues,
        project_root=project_root,
    )

    llm = get_llm()

    response = llm.invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]
    )

    model_output = _message_content_to_text(response.content).strip()

    return {
        "prompt": prompt,
        "model_output": model_output,
    }