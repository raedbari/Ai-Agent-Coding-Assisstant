from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.schemas import StructuredFix
from app.agent.state import AgentState
from app.llm.client import get_llm
from app.security.sonar_project_llm_fix import build_project_sonar_prompt


SYSTEM_PROMPT = """You are a senior software repair assistant.

You receive SonarQube issues and relevant source files.

Your job:
- Use the SonarQube issues as the source of truth.
- Fix only the listed issues.
- Do not modify unrelated code.
- Return a safe, minimal patch.
- Use repository-relative paths.
"""


JSON_OUTPUT_INSTRUCTIONS = """Return your answer as JSON only.

Required JSON schema:
{
  "summary": "short explanation",
  "risk": "low | medium | high",
  "changed_files": ["path/to/file.py"],
  "diff": "valid unified diff"
}

Rules:
- The diff must be a valid unified diff.
- Do not wrap JSON in Markdown fences.
- Do not add prose outside JSON.
- For python:S125 commented-out code, the diff must remove the complete commented-out code block, not only selected lines.
- A valid S125 fix must not leave behind commented indented body lines such as "#     connection = ..." after deleting "# def ...".
- Prefer one coherent hunk that removes the whole dead commented block.
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


def _strip_markdown_code_fence(text: str) -> str:
    cleaned = text.strip()

    if cleaned.startswith("```json"):
        cleaned = cleaned.removeprefix("```json").strip()
    elif cleaned.startswith("```diff"):
        cleaned = cleaned.removeprefix("```diff").strip()
    elif cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```").strip()

    if cleaned.endswith("```"):
        cleaned = cleaned.removesuffix("```").strip()

    return cleaned


def _extract_json_object(text: str) -> str:
    cleaned = _strip_markdown_code_fence(text)

    if cleaned.startswith("{") and cleaned.endswith("}"):
        return cleaned

    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)

    if not match:
        raise ValueError("LLM response did not contain a JSON object.")

    return match.group(0)


def _extract_changed_files_from_diff(diff_text: str) -> list[str]:
    files: list[str] = []

    for line in diff_text.splitlines():
        if not line.startswith("+++ "):
            continue

        path = line[4:].strip().split()[0]

        if path == "/dev/null":
            continue

        if path.startswith("b/"):
            path = path[2:]

        files.append(path)

    return sorted(set(files))


def _fix_to_dict(fix: StructuredFix) -> dict[str, Any]:
    if hasattr(fix, "model_dump"):
        return fix.model_dump()

    return fix.dict()


def _validate_fix_from_json(text: str) -> StructuredFix:
    json_text = _extract_json_object(text)
    payload = json.loads(json_text)

    return StructuredFix(**payload)


def _fallback_diff_response(text: str) -> StructuredFix:
    diff = _strip_markdown_code_fence(text)

    if not diff.startswith("--- ") and "\n--- " not in diff:
        raise ValueError("LLM response was neither structured JSON nor unified diff.")

    return StructuredFix(
        summary="The model returned a unified diff without structured metadata.",
        risk="medium",
        changed_files=_extract_changed_files_from_diff(diff),
        diff=diff,
    )


def generate_structured_fix_node(state: AgentState) -> AgentState:
    selected_issues = state.get("selected_issues", [])

    if not selected_issues:
        return {
            **state,
            "error": "No SonarQube issues found for this project.",
        }

    prompt = build_project_sonar_prompt(
        issues=selected_issues,
        project_root=Path(state["project_root"]),
    )

    full_prompt = f"{prompt}\n\n{JSON_OUTPUT_INSTRUCTIONS}"

    llm = get_llm()

    try:
        structured_llm = llm.with_structured_output(StructuredFix)
        structured_response = structured_llm.invoke(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=full_prompt),
            ]
        )

        if isinstance(structured_response, StructuredFix):
            fix = structured_response
        elif isinstance(structured_response, dict):
            fix = StructuredFix(**structured_response)
        else:
            fix = StructuredFix(**dict(structured_response))

    except Exception:
        response = llm.invoke(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=full_prompt),
            ]
        )

        content = _message_content_to_text(response.content)

        try:
            fix = _validate_fix_from_json(content)
        except Exception:
            fix = _fallback_diff_response(content)

    fix_dict = _fix_to_dict(fix)

    return {
        **state,
        "prompt": full_prompt,
        "fix": fix_dict,
        "diff": fix.diff,
        "approval_status": "pending",
    }