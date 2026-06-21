import json
from typing import Any

from app.scanner.models import IssueRecord


MAX_ISSUE_MESSAGE_CHARS = 3000
MAX_CONTEXT_CHARS = 6000
MAX_RELATED_CONTEXT_CHARS = 8000


def limit_text(value: str | None, max_chars: int) -> str:
    if not value:
        return ""

    value = value.strip()

    if len(value) <= max_chars:
        return value

    return value[:max_chars] + "\n... truncated ..."


def build_repair_payload(
    issue: IssueRecord,
    issue_context: dict[str, object],
    related_contexts: list[dict[str, object]],
) -> dict[str, Any]:
    return {
        "task": "analyze_one_issue_and_propose_minimal_fix",
        "rules": [
            "Do not rewrite the whole project.",
            "Do not suggest unrelated refactors.",
            "Use only the provided context.",
            "If the provided context is insufficient, say so clearly.",
            "Return a minimal patch proposal.",
            "Do not invent files that are not mentioned.",
        ],
        "issue": {
            "id": issue.id,
            "type": issue.type.value,
            "severity": issue.severity.value,
            "checker": issue.checker,
            "file_path": issue.file_path,
            "line": issue.line,
            "column": issue.column,
            "code": issue.code,
            "message": limit_text(issue.message, MAX_ISSUE_MESSAGE_CHARS),
        },
        "issue_context": {
            "file_path": issue_context.get("file_path"),
            "line": issue_context.get("line"),
            "context": limit_text(
                str(issue_context.get("context", "")),
                MAX_CONTEXT_CHARS,
            ),
        },
        "related_contexts": [
            {
                "file_path": item.get("file_path"),
                "symbol": item.get("symbol"),
                "module": item.get("module"),
                "reason": item.get("reason"),
                "context": limit_text(
                    str(item.get("context", "")),
                    MAX_RELATED_CONTEXT_CHARS,
                ),
            }
            for item in related_contexts
        ],
    }


def build_llm_messages(
    repair_payload: dict[str, Any],
) -> list[tuple[str, str]]:
    system_message = (
        "You are a careful coding repair assistant. "
        "You analyze one detected issue at a time. "
        "Use only the provided context. "
        "Never claim that you inspected files that were not provided. "
        "If the context is insufficient, set needs_more_context to true. "
        "Return a minimal repair plan only."
    )

    user_message = json.dumps(
        repair_payload,
        ensure_ascii=False,
        indent=2,
    )

    return [
        ("system", system_message),
        ("human", user_message),
    ]