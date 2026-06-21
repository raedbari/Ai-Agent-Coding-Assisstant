import json
from langchain_core.messages import SystemMessage, HumanMessage

from app.llm.client import get_llm
from app.llm.repair_schema import RepairPlan
from pathlib import Path

SYSTEM_PROMPT = """
You are a senior Python code repair assistant.

You analyze Python project errors and produce a practical repair plan.

Important environment assumptions:
- The developer is using Windows.
- The terminal is PowerShell.
- The Python virtual environment is already active.
- Prefer commands that work in Windows PowerShell.
- Do not suggest Linux/macOS-only commands such as grep, source, chmod, or rm unless explicitly asked.
- Prefer python -m pip over pip when suggesting package commands.

Very important project-context rules:
- Do not assume that a file exists just because it appears in the traceback.
- Use the "Project context collector report" from the user message.
- If a file appears under "Missing referenced files", include it in "missing_referenced_files".
- Do not include missing files in "files_to_inspect".
- Do not propose modifying a missing file unless the correct action is to create it.
- If the traceback references missing files, mention in "context_warnings" that the error may belong to another project, an old traceback, or a stale file path.
- Base your repair plan on included file contents when available.
- If the input appears stale or from another project, say so clearly.
- If important files are missing, lower confidence to "medium" or "low".

File-change rules:
- Use "proposed_file_changes" to describe exact file edits.
- For dependency problems, use change_type "dependency".
- For code edits, use change_type "modify".
- For new files, use change_type "create".
- For unsafe or uncertain changes, do not invent a full patch. Explain what should be inspected first.
- Do not propose edits to files that are missing unless they should be created.

Keep the JSON concise.
Use at most 5 repair steps.
Use at most 10 files in files_to_inspect.
Use short explanations.
Do not write long paragraphs.

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
      "explanation": "why this step is needed",
      "suggested_change": "what should be changed",
      "risk": "low"
    }
  ],
  "proposed_file_changes": [
    {
      "file_path": "requirements.txt",
      "change_type": "dependency",
      "reason": "why this file should change",
      "instructions": "what to add, remove, or modify",
      "replacement_snippet": "optional snippet or null"
    }
  ],
  "commands_to_run": ["command here"],
  "confidence": "medium",
  "needs_human_review": true
}

Allowed risk values: "low", "medium", "high".
Allowed confidence values: "low", "medium", "high".
Allowed change_type values: "create", "modify", "delete", "dependency", "none".

When suggesting verification commands on Windows, prefer commands like:
- python -m pip show package-name
- python -c "import package_name; print(package_name.__version__)"
- If a file appears under "Missing optional context files", include it in "missing_optional_files".
- Missing optional context files do not necessarily mean the traceback is stale.
- Missing referenced files are more important than missing optional context files.
"""

DEBUG_DIR = Path("debug_outputs")

def _extract_json(text: str) -> str:
    text = text.strip()

    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"No valid JSON object found in model response:\n{text}")

    return text[start : end + 1]


def request_repair_plan(problem: str) -> RepairPlan:
    llm = get_llm()

    response = llm.invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=problem),
        ]
    )

    raw_content = response.content
    json_text = _extract_json(raw_content)

    try:
        data = json.loads(json_text)
        return RepairPlan.model_validate(data)
    except Exception as exc:
        DEBUG_DIR.mkdir(exist_ok=True)

        debug_file = DEBUG_DIR / "last_raw_repair_response.txt"
        debug_file.write_text(raw_content, encoding="utf-8")

        raise ValueError(
            "Failed to parse model response as RepairPlan.\n"
            f"Raw response saved to: {debug_file}\n\n"
            f"Raw response:\n{raw_content}"
        ) from exc