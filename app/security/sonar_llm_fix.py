from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.llm.client import get_llm
from app.security.sonar_prompt_builder import build_sonar_issue_prompt


SYSTEM_PROMPT = """You are a senior software repair assistant.

Your job:
- Fix only the reported SonarQube issue.
- Return a unified diff only.
- Do not wrap the diff in Markdown fences.
- Do not explain the change unless no safe fix is possible.
- Use paths relative to the repository root.
- The numbered lines in the prompt are context only. Do not include line numbers in the patched code.
"""


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


def propose_sonar_fix_with_llm(
    issue: dict[str, Any],
    project_root: Path,
) -> dict[str, str]:
    prompt_payload = build_sonar_issue_prompt(
        issue=issue,
        project_root=project_root,
    )

    llm = get_llm()

    response = llm.invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt_payload["prompt"]),
        ]
    )

    model_output = _strip_markdown_code_fence(
    _message_content_to_text(response.content)
)

    return {
        "issue_key": issue["issue_key"],
        "file_path": issue["file_path"],
        "prompt": prompt_payload["prompt"],
        "model_output": model_output,
    }

def _strip_markdown_code_fence(text: str) -> str:
    cleaned = text.strip()

    if cleaned.startswith("```diff"):
        cleaned = cleaned.removeprefix("```diff").strip()

    elif cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```").strip()

    if cleaned.endswith("```"):
        cleaned = cleaned.removesuffix("```").strip()

    return cleaned