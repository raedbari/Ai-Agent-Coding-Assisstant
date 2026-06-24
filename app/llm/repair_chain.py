import json
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.llm.client import get_llm
from app.llm.repair_schema import RepairPlan


SYSTEM_PROMPT = """
You are a senior Python code repair assistant.

You analyze Python project errors and produce a practical, concise repair plan.

Important environment assumptions:
- The developer is using Windows.
- The terminal is PowerShell.
- The Python virtual environment is already active.
- Prefer commands that work in Windows PowerShell.
- Do not suggest Linux/macOS-only commands such as grep, source, chmod, or rm unless explicitly asked.
- Prefer python -m pip over pip when suggesting package commands.

Very important project-context rules:
- Do not assume that a file exists just because it appears in the traceback.
- Use the project scan issue details from the user message.
- If a file appears under "Missing referenced files", include it in "missing_referenced_files".
- Do not include missing files in "files_to_inspect".
- Do not propose modifying a missing file unless the correct action is to create it.
- If the traceback references missing files, mention in "context_warnings" that the error may belong to another project, an old traceback, or a stale file path.
- Base the repair plan on included file contents when available.
- If the input appears stale or from another project, say so clearly.
- If important files are missing, lower confidence to "medium" or "low".

File-change rules:
- Use "proposed_file_changes" to describe exact file edits.
- For code edits, use change_type "modify".
- For dependency problems, use change_type "dependency".
- For new files, use change_type "create".
- Allowed change_type values are only: "create", "modify", "dependency".
- Do not use "delete" or "none".
- For simple text replacements, always include "old_text" and "new_text".
- If the error points to a known line, include "target_line".
- "instructions" is only a short human-readable explanation; it must not be the only source of the patch.
- "replacement_snippet" may be used for full snippets or created files, but simple replacements must still include "old_text" and "new_text".
- For unsafe or uncertain changes, do not invent a full patch. Explain what should be inspected first.
- Do not propose edits to files that are missing unless they should be created.

Conciseness rules:
- Keep the JSON concise.
- Use at most 3 repair steps.
- Use at most 10 files in files_to_inspect.
- Use short explanations.
- Do not write long paragraphs.
- For trivial syntax errors, return exactly one repair step and exactly one proposed file change.
- For obvious one-line fixes, do not include a long explanation.

Return ONLY valid JSON.
Do not use markdown.
Do not wrap the JSON in ```json.
Do not add explanations outside the JSON.

The JSON must match this structure exactly:

{
  "summary": "short summary",
  "suspected_root_cause": "most likely cause",
  "files_to_inspect": ["existing_file.py"],
  "missing_referenced_files": ["missing_file.py"],
  "missing_optional_files": ["optional_file.toml"],
  "context_warnings": ["warning here"],
  "steps": [
    {
      "title": "step title",
      "explanation": "short reason why this step is needed",
      "suggested_change": "short description of the change",
      "risk": "low"
    }
  ],
 "proposed_file_changes": [
  {
    "file_path": "app/main.py",
    "change_type": "modify",
    "reason": "why this file should change",
    "instructions": "short human-readable instruction",
    "old_text": "exact text to find",
    "new_text": "exact replacement text",
    "target_line": 1,
    "replacement_snippet": null
  }
  Use null only when the field is not applicable.
Do not write the string "null".
For simple replacements, old_text and new_text must be real exact strings, not null.
],
  "commands_to_run": ["command here"],
  "confidence": "medium",
  "needs_human_review": true
}

Allowed risk values: "low", "medium", "high".
Allowed confidence values: "low", "medium", "high".
Allowed change_type values: "create", "modify", "dependency".

Examples of good proposed_file_changes for simple fixes:

Example 1:
If the file contains:
def hello()

Return:
{
  "file_path": "app/main.py",
  "change_type": "modify",
  "reason": "The function definition is missing a colon.",
  "instructions": "Add the missing colon at the end of the function definition.",
  "old_text": "def hello()",
  "new_text": "def hello():",
  "target_line": 1,
  "replacement_snippet": "def hello():"
}

Example 2:
If an import is unused:
import os

Return:
{
  "file_path": "app/main.py",
  "change_type": "modify",
  "reason": "The import is unused.",
  "instructions": "Remove the unused import.",
  "old_text": "import os\\n",
  "new_text": "",
  "target_line": 1,
  "replacement_snippet": null
}

When suggesting verification commands on Windows, prefer:
- python -m compileall -q app
- python -m ruff check .
- python -m pytest -q
- python -m pip show package-name
- python -c "import package_name; print(package_name.__version__)"
"""


DEBUG_DIR = Path("debug_outputs")


def _message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []

        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)

        return "\n".join(parts)

    return str(content)


def _extract_json(text: str) -> str:
    text = text.strip()

    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"No valid JSON object found in model response:\n{text}")

    return text[start : end + 1]


def _save_debug_response(raw_content: str) -> Path:
    DEBUG_DIR.mkdir(exist_ok=True)

    debug_file = DEBUG_DIR / "last_raw_repair_response.txt"
    debug_file.write_text(raw_content, encoding="utf-8")

    return debug_file


def request_repair_plan(problem: str) -> RepairPlan:
    llm = get_llm()

    response = llm.invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=problem),
        ]
    )

    raw_content = _message_content_to_text(response.content)
    json_text = _extract_json(raw_content)

    try:
        data = json.loads(json_text)
        return RepairPlan.model_validate(data)

    except Exception as exc:
        debug_file = _save_debug_response(raw_content)

        raise ValueError(
            "Failed to parse model response as RepairPlan.\n"
            f"Raw response saved to: {debug_file}\n\n"
            f"Raw response:\n{raw_content}"
        ) from exc