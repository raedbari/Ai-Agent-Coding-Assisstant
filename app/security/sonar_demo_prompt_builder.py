from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_PROJECT_KEY = "ai-coding-demo-projects"


def require_env(name: str) -> str:
    value = os.getenv(name)

    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")

    return value


def sonar_get(
    host_url: str,
    token: str,
    path: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    query = urlencode(params)
    url = f"{host_url.rstrip('/')}{path}?{query}"

    auth = base64.b64encode(f"{token}:".encode("utf-8")).decode("ascii")

    request = Request(
        url,
        headers={
            "Authorization": f"Basic {auth}",
            "Accept": "application/json",
        },
    )

    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def component_to_file_path(project_key: str, component: str) -> str:
    prefix = f"{project_key}:"

    if component.startswith(prefix):
        return component[len(prefix):]

    return component


def safe_resolve(root: Path, relative_path: str) -> Path:
    candidate = (root / relative_path).resolve()
    root_resolved = root.resolve()

    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise RuntimeError(f"Unsafe file path from SonarQube: {relative_path}") from exc

    if not candidate.is_file():
        raise RuntimeError(f"File not found: {candidate}")

    return candidate


def read_code_context(file_path: Path, line: int | None, radius: int) -> str:
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
        content = lines[number - 1]
        rendered.append(f"{marker} {number:4d}: {content}")

    return "\n".join(rendered)


def normalize_issue(project_key: str, issue: dict[str, Any]) -> dict[str, Any]:
    text_range = issue.get("textRange") or {}

    return {
        "key": issue.get("key"),
        "source": "sonarqube",
        "rule_id": issue.get("rule"),
        "severity": issue.get("severity"),
        "type": issue.get("type"),
        "message": issue.get("message"),
        "file_path": component_to_file_path(project_key, issue.get("component", "")),
        "start_line": text_range.get("startLine") or issue.get("line"),
        "end_line": text_range.get("endLine") or issue.get("line"),
        "status": issue.get("status"),
        "tags": issue.get("tags", []),
        "clean_code_attribute": issue.get("cleanCodeAttribute"),
        "impacts": issue.get("impacts", []),
    }


def build_prompt(issue: dict[str, Any], code_context: str) -> str:
    language_hint = Path(issue["file_path"]).suffix.lstrip(".") or "text"

    return f"""You are fixing a static analysis issue reported by SonarQube.

Your task:
- Fix only the reported issue.
- Do not rewrite unrelated code.
- Preserve existing behavior unless the issue is specifically about wrong behavior.
- Do not invent missing requirements.
- Return a unified diff only.
- If there is not enough context to safely fix the issue, return a short explanation instead of a diff.

Issue:
- Source: {issue["source"]}
- Rule: {issue["rule_id"]}
- Severity: {issue["severity"]}
- Type: {issue["type"]}
- Message: {issue["message"]}
- File: {issue["file_path"]}
- Start line: {issue["start_line"]}
- End line: {issue["end_line"]}
- Tags: {", ".join(issue["tags"]) if issue["tags"] else "none"}

Code context:
```{language_hint}
{code_context}
```
"""


def fetch_issues(
    host_url: str,
    token: str,
    project_key: str,
    limit: int,
) -> list[dict[str, Any]]:
    data = sonar_get(
        host_url=host_url,
        token=token,
        path="/api/issues/search",
        params={
            "componentKeys": project_key,
            "resolved": "false",
            "ps": limit,
        },
    )

    return data.get("issues", [])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build repair prompts from SonarQube issues for demo_projects."
    )

    parser.add_argument("--project-key", default=DEFAULT_PROJECT_KEY)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--context-radius", type=int, default=25)
    parser.add_argument("--issue-key", default=None)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of plain prompts.",
    )

    args = parser.parse_args()

    host_url = require_env("SONAR_HOST_URL")
    token = require_env("SONAR_TOKEN")
    root = Path.cwd()

    raw_issues = fetch_issues(
        host_url=host_url,
        token=token,
        project_key=args.project_key,
        limit=args.limit,
    )

    prompts: list[dict[str, Any]] = []

    for raw_issue in raw_issues:
        issue = normalize_issue(args.project_key, raw_issue)

        if args.issue_key and issue["key"] != args.issue_key:
            continue

        if not issue["file_path"].startswith("demo_projects/"):
            continue

        file_path = safe_resolve(root, issue["file_path"])

        code_context = read_code_context(
            file_path=file_path,
            line=issue["start_line"],
            radius=args.context_radius,
        )

        prompt = build_prompt(issue, code_context)

        prompts.append(
            {
                "issue": issue,
                "prompt": prompt,
            }
        )

    if args.json:
        print(json.dumps(prompts, indent=2, ensure_ascii=False))
        return

    for index, item in enumerate(prompts, start=1):
        issue = item["issue"]

        print("=" * 100)
        print(f"PROMPT #{index}")
        print(f"Issue: {issue['rule_id']} | {issue['file_path']}:{issue['start_line']}")
        print("=" * 100)
        print(item["prompt"])


if __name__ == "__main__":
    main()