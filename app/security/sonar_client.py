from __future__ import annotations

import base64
import json
import os
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_SONAR_PROJECT_KEY = "ai-coding-demo-projects"


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _sonar_get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    host_url = _required_env("SONAR_HOST_URL").rstrip("/")
    token = _required_env("SONAR_TOKEN")

    query = urlencode(params)
    url = f"{host_url}{path}?{query}"

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


def _component_to_file_path(project_key: str, component: str) -> str:
    prefix = f"{project_key}:"

    if component.startswith(prefix):
        return component[len(prefix):]

    return component


def normalize_sonar_issue(project_key: str, issue: dict[str, Any]) -> dict[str, Any]:
    text_range = issue.get("textRange") or {}

    return {
        "id": issue.get("key"),
        "issue_key": issue.get("key"),
        "source": "sonarqube",
        "rule_id": issue.get("rule"),
        "severity": issue.get("severity"),
        "type": issue.get("type"),
        "message": issue.get("message"),
        "file_path": _component_to_file_path(
            project_key=project_key,
            component=issue.get("component", ""),
        ),
        "line": text_range.get("startLine") or issue.get("line"),
        "start_line": text_range.get("startLine") or issue.get("line"),
        "end_line": text_range.get("endLine") or issue.get("line"),
        "status": issue.get("status"),
        "tags": issue.get("tags", []),
        "effort": issue.get("effort"),
        "clean_code_attribute": issue.get("cleanCodeAttribute"),
        "impacts": issue.get("impacts", []),
        "quick_fix_available": issue.get("quickFixAvailable", False),
    }


def fetch_demo_sonar_issues(limit: int = 50) -> list[dict[str, Any]]:
    project_key = os.getenv("SONAR_PROJECT_KEY", DEFAULT_SONAR_PROJECT_KEY)

    data = _sonar_get(
        path="/api/issues/search",
        params={
            "componentKeys": project_key,
            "resolved": "false",
            "ps": limit,
        },
    )

    return [
        normalize_sonar_issue(project_key=project_key, issue=issue)
        for issue in data.get("issues", [])
    ]


def get_demo_sonar_issue(issue_key: str) -> dict[str, Any]:
    issues = fetch_demo_sonar_issues(limit=100)

    for issue in issues:
        if issue["issue_key"] == issue_key:
            return issue

    raise ValueError(f"Sonar issue not found: {issue_key}")