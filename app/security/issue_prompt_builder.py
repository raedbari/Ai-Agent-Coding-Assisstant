from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal
import argparse
import hashlib
import json
import os
import re
import sys

import requests


IssueSource = Literal["sonarqube", "codeql"]


@dataclass(slots=True)
class NormalizedIssue:
    """
    Unified issue shape for findings coming from SonarQube and CodeQL.
    Keep `raw` for debugging/storage only. Do not send it to the model by default.
    """

    id: str
    source: IssueSource
    rule_id: str
    severity: str
    kind: str
    message: str
    file_path: str
    start_line: int | None
    end_line: int | None
    url: str | None = None
    raw: dict[str, Any] | None = None

    def to_public_dict(self, include_raw: bool = False) -> dict[str, Any]:
        payload = asdict(self)
        if not include_raw:
            payload.pop("raw", None)
        return payload

    def to_model_payload(self) -> dict[str, Any]:
        """
        Payload sent to the model. Never include raw scanner responses by default.
        """
        payload = self.to_public_dict(include_raw=False)
        return payload


def _stable_issue_id(
    source: str,
    rule_id: str,
    file_path: str,
    start_line: int | None,
    message: str,
    external_key: str | None = None,
) -> str:
    base = "|".join(
        [
            source or "",
            rule_id or "",
            file_path or "",
            str(start_line or ""),
            message or "",
            external_key or "",
        ]
    )
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]
    return f"{source}:{digest}"


def redact_secrets(text: str) -> str:
    """
    Basic redaction before sending code/context to the model.

    This is not a complete secret scanner. It only prevents obvious leaks.
    Use Gitleaks or GitHub Secret Scanning separately for real secret detection.
    """
    patterns: list[tuple[str, str]] = [
        (r"(?i)(api[_-]?key\s*=\s*)['\"][^'\"]+['\"]", r"\1***REDACTED***"),
        (r"(?i)(secret\s*=\s*)['\"][^'\"]+['\"]", r"\1***REDACTED***"),
        (r"(?i)(password\s*=\s*)['\"][^'\"]+['\"]", r"\1***REDACTED***"),
        (r"(?i)(token\s*=\s*)['\"][^'\"]+['\"]", r"\1***REDACTED***"),
        (r"sk-[A-Za-z0-9_\-]{20,}", "***REDACTED***"),
        (r"github_pat_[A-Za-z0-9_]+", "***REDACTED***"),
        (r"ghp_[A-Za-z0-9_]{20,}", "***REDACTED***"),
        (r"gho_[A-Za-z0-9_]{20,}", "***REDACTED***"),
        (r"ghs_[A-Za-z0-9_]{20,}", "***REDACTED***"),
        (r"ghu_[A-Za-z0-9_]{20,}", "***REDACTED***"),
    ]

    redacted = text
    for pattern, replacement in patterns:
        redacted = re.sub(pattern, replacement, redacted)

    return redacted


def _safe_resolve_file(project_root: str | Path, file_path: str) -> Path:
    """
    Resolve a scanner-provided file path safely inside project_root.
    Prevents path traversal like ../../etc/passwd.
    """
    root = Path(project_root).resolve()

    cleaned_path = file_path.strip().replace("\\", "/").lstrip("/")
    target = (root / cleaned_path).resolve()

    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Unsafe file path outside project root: {file_path}") from exc

    return target


def read_code_context(
    project_root: str | Path,
    file_path: str,
    start_line: int | None,
    end_line: int | None = None,
    radius: int = 25,
) -> str:
    """
    Read a focused code window around the issue line.

    Output format marks the affected lines with >>.
    """
    if not file_path:
        return "[No file path provided by scanner]"

    target = _safe_resolve_file(project_root, file_path)

    if not target.exists():
        return f"[File not found: {file_path}]"

    if target.is_dir():
        return f"[Path is a directory, not a file: {file_path}]"

    lines = target.read_text(encoding="utf-8", errors="replace").splitlines()

    if not lines:
        return f"[File is empty: {file_path}]"

    if not start_line or start_line < 1:
        start_line = 1

    end_line = end_line or start_line
    if end_line < start_line:
        end_line = start_line

    from_line = max(1, start_line - radius)
    to_line = min(len(lines), end_line + radius)

    output: list[str] = []
    for line_no in range(from_line, to_line + 1):
        marker = ">>" if start_line <= line_no <= end_line else "  "
        output.append(f"{marker} {line_no:4}: {lines[line_no - 1]}")

    return redact_secrets("\n".join(output))


def _request_json(
    session: requests.Session,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    timeout: int = 30,
) -> Any:
    response = session.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()


def make_sonar_session(
    token: str,
    auth_mode: Literal["bearer", "basic"] = "bearer",
) -> requests.Session:
    """
    SonarQube versions differ in accepted auth style.
    Newer docs recommend Bearer auth; some older setups may need basic token auth.
    """
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})

    if auth_mode == "bearer":
        session.headers.update({"Authorization": f"Bearer {token}"})
    elif auth_mode == "basic":
        session.auth = (token, "")
    else:
        raise ValueError(f"Unsupported SonarQube auth mode: {auth_mode}")

    return session


def fetch_sonarqube_issues(
    sonar_url: str,
    token: str,
    project_key: str,
    *,
    auth_mode: Literal["bearer", "basic"] = "bearer",
    max_issues: int = 500,
    page_size: int = 100,
) -> list[NormalizedIssue]:
    """
    Read open SonarQube issues and normalize them.

    Required:
    - sonar_url: example http://localhost:9000
    - token: SonarQube token
    - project_key: SonarQube project key
    """
    if not sonar_url:
        raise ValueError("sonar_url is required")
    if not token:
        raise ValueError("SonarQube token is required")
    if not project_key:
        raise ValueError("SonarQube project_key is required")

    page_size = max(1, min(page_size, 500))
    max_issues = max(1, max_issues)

    session = make_sonar_session(token=token, auth_mode=auth_mode)
    endpoint = f"{sonar_url.rstrip('/')}/api/issues/search"

    issues: list[NormalizedIssue] = []
    page = 1

    while len(issues) < max_issues:
        params = {
            "componentKeys": project_key,
            "resolved": "false",
            "p": page,
            "ps": page_size,
        }

        data = _request_json(session, endpoint, params=params)
        raw_issues = data.get("issues", [])

        if not raw_issues:
            break

        for item in raw_issues:
            component = item.get("component") or ""
            file_path = component.split(":", 1)[1] if ":" in component else component

            text_range = item.get("textRange") or {}
            start_line = item.get("line") or text_range.get("startLine")
            end_line = text_range.get("endLine") or start_line

            message = item.get("message") or ""
            rule_id = item.get("rule") or ""
            external_key = item.get("key")

            issue = NormalizedIssue(
                id=_stable_issue_id(
                    source="sonarqube",
                    rule_id=rule_id,
                    file_path=file_path,
                    start_line=start_line,
                    message=message,
                    external_key=external_key,
                ),
                source="sonarqube",
                rule_id=rule_id,
                severity=item.get("severity") or "UNKNOWN",
                kind=item.get("type") or item.get("cleanCodeAttributeCategory") or "unknown",
                message=message,
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                url=item.get("url"),
                raw=item,
            )
            issues.append(issue)

            if len(issues) >= max_issues:
                break

        paging = data.get("paging") or {}
        total = paging.get("total")

        if total is not None and page * page_size >= int(total):
            break

        page += 1

    return issues


def make_github_session(token: str) -> requests.Session:
    if not token:
        raise ValueError("GitHub token is required")

    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
    )
    return session


def _github_paginated_get(
    session: requests.Session,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    max_items: int = 100,
) -> list[dict[str, Any]]:
    """
    Simple GitHub REST pagination using page/per_page.
    """
    max_items = max(1, max_items)
    per_page = min(100, max_items)

    results: list[dict[str, Any]] = []
    page = 1

    while len(results) < max_items:
        query = dict(params or {})
        query["per_page"] = per_page
        query["page"] = page

        data = _request_json(session, url, params=query)

        if not isinstance(data, list):
            raise ValueError(f"Expected GitHub API list response, got: {type(data).__name__}")

        if not data:
            break

        for item in data:
            results.append(item)
            if len(results) >= max_items:
                break

        if len(data) < per_page:
            break

        page += 1

    return results


def _extract_codeql_location_from_instance(instance: dict[str, Any]) -> dict[str, Any]:
    """
    GitHub Code Scanning instances usually expose a location object.
    This helper is defensive because the exact nesting can vary.
    """
    location = instance.get("location") or {}

    if location:
        return location

    physical_location = instance.get("physicalLocation") or instance.get("physical_location") or {}
    artifact_location = physical_location.get("artifactLocation") or physical_location.get("artifact_location") or {}
    region = physical_location.get("region") or {}

    return {
        "path": artifact_location.get("uri") or "",
        "start_line": region.get("startLine"),
        "end_line": region.get("endLine") or region.get("startLine"),
        "start_column": region.get("startColumn"),
        "end_column": region.get("endColumn"),
    }


def _extract_codeql_location_from_alert(alert: dict[str, Any]) -> dict[str, Any]:
    most_recent = alert.get("most_recent_instance") or {}
    return most_recent.get("location") or _extract_codeql_location_from_instance(most_recent)


def fetch_codeql_alerts_from_github(
    owner: str,
    repo: str,
    token: str,
    *,
    max_alerts: int = 100,
    instances_per_alert: int = 1,
) -> list[NormalizedIssue]:
    """
    Read open CodeQL alerts from GitHub Code Scanning API and normalize them.

    This returns one NormalizedIssue per alert instance.
    For MVP use instances_per_alert=1.
    """
    if not owner:
        raise ValueError("GitHub owner is required")
    if not repo:
        raise ValueError("GitHub repo is required")

    session = make_github_session(token=token)

    base = f"https://api.github.com/repos/{owner}/{repo}/code-scanning/alerts"

    alerts = _github_paginated_get(
        session,
        base,
        params={
            "state": "open",
            "tool_name": "CodeQL",
        },
        max_items=max_alerts,
    )

    issues: list[NormalizedIssue] = []

    for alert in alerts:
        alert_number = alert.get("number")
        rule = alert.get("rule") or {}

        rule_id = rule.get("id") or ""
        severity = (
            rule.get("security_severity_level")
            or rule.get("severity")
            or alert.get("severity")
            or "unknown"
        )

        message = (
            (alert.get("message") or {}).get("text")
            or rule.get("description")
            or rule.get("full_description")
            or ""
        )

        alert_url = alert.get("html_url")

        instances: list[dict[str, Any]] = []
        if alert_number is not None:
            instances_url = f"{base}/{alert_number}/instances"
            try:
                instances = _github_paginated_get(
                    session,
                    instances_url,
                    max_items=max(1, instances_per_alert),
                )
            except requests.HTTPError:
                instances = []

        if not instances:
            instances = [alert.get("most_recent_instance") or {}]

        for idx, instance in enumerate(instances):
            location = _extract_codeql_location_from_instance(instance)
            if not location:
                location = _extract_codeql_location_from_alert(alert)

            file_path = location.get("path") or ""
            start_line = location.get("start_line") or location.get("startLine")
            end_line = location.get("end_line") or location.get("endLine") or start_line

            external_key = f"{alert_number}:{idx}"

            issue = NormalizedIssue(
                id=_stable_issue_id(
                    source="codeql",
                    rule_id=rule_id,
                    file_path=file_path,
                    start_line=start_line,
                    message=message,
                    external_key=external_key,
                ),
                source="codeql",
                rule_id=rule_id,
                severity=str(severity),
                kind="security",
                message=message,
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                url=alert_url,
                raw=alert,
            )
            issues.append(issue)

    return issues


def severity_rank(issue: NormalizedIssue) -> int:
    """
    Higher number means higher priority.
    This is intentionally simple and can be refined later.
    """
    value = (issue.severity or "").lower()

    if value in {"blocker", "critical", "error"}:
        return 100
    if value in {"high"}:
        return 90
    if value in {"major", "medium", "warning"}:
        return 70
    if value in {"minor", "low"}:
        return 40
    if value in {"info", "informational"}:
        return 10

    return 0


def collect_security_issues(
    *,
    sonar_url: str | None = None,
    sonar_token: str | None = None,
    sonar_project_key: str | None = None,
    sonar_auth_mode: Literal["bearer", "basic"] = "bearer",
    github_owner: str | None = None,
    github_repo: str | None = None,
    github_token: str | None = None,
    max_sonar_issues: int = 100,
    max_codeql_alerts: int = 50,
) -> list[NormalizedIssue]:
    """
    Collect issues from the configured tools.

    If SonarQube config is missing, SonarQube is skipped.
    If GitHub config is missing, CodeQL is skipped.
    """
    issues: list[NormalizedIssue] = []

    if sonar_url and sonar_token and sonar_project_key:
        issues.extend(
            fetch_sonarqube_issues(
                sonar_url=sonar_url,
                token=sonar_token,
                project_key=sonar_project_key,
                auth_mode=sonar_auth_mode,
                max_issues=max_sonar_issues,
            )
        )

    if github_owner and github_repo and github_token:
        issues.extend(
            fetch_codeql_alerts_from_github(
                owner=github_owner,
                repo=github_repo,
                token=github_token,
                max_alerts=max_codeql_alerts,
                instances_per_alert=1,
            )
        )

    issues.sort(key=severity_rank, reverse=True)
    return issues


def build_fix_prompt(
    issue: NormalizedIssue,
    project_root: str | Path,
    *,
    extra_project_context: str = "",
    code_radius: int = 25,
) -> str:
    """
    Build a focused prompt for exactly one issue.

    Do not call this for every issue automatically.
    Call it only after the user selects an issue.
    """
    code_context = read_code_context(
        project_root=project_root,
        file_path=issue.file_path,
        start_line=issue.start_line,
        end_line=issue.end_line,
        radius=code_radius,
    )

    issue_json = json.dumps(issue.to_model_payload(), ensure_ascii=False, indent=2)

    prompt = f"""
You are a senior secure-code reviewer and repair planner.

Your task:
Analyze exactly one issue detected by a static analysis tool and propose a minimal, safe fix.

Hard rules:
- Use only the provided issue data and code context.
- Do not invent files, functions, dependencies, APIs, or business requirements.
- Prefer the smallest correct change.
- Do not rewrite unrelated code.
- If the issue is security-related, explain the real risk clearly.
- If the provided context is insufficient, request exactly the missing file/function.
- Do not apply the fix yourself.
- Return valid JSON only. No Markdown. No extra text.

Required JSON response shape:
{{
  "issue_summary": "short explanation of the issue",
  "risk": "why this matters",
  "fix_strategy": "minimal safe repair strategy",
  "files_to_change": [
    {{
      "path": "file path",
      "reason": "why this file must change",
      "suggested_change": "precise change description"
    }}
  ],
  "needs_more_context": false,
  "missing_context": [],
  "confidence": "low|medium|high"
}}

Tool issue JSON:
<tool_issue_json>
{issue_json}
</tool_issue_json>

Relevant code context:
<code_context>
{code_context}
</code_context>

Extra project context:
<extra_project_context>
{extra_project_context}
</extra_project_context>
""".strip()

    return prompt


def find_issue_by_id(issues: list[NormalizedIssue], issue_id: str) -> NormalizedIssue:
    for issue in issues:
        if issue.id == issue_id:
            return issue

    raise KeyError(f"Issue not found: {issue_id}")


def issues_to_json(issues: list[NormalizedIssue], *, include_raw: bool = False) -> str:
    return json.dumps(
        [issue.to_public_dict(include_raw=include_raw) for issue in issues],
        ensure_ascii=False,
        indent=2,
    )


def collect_from_env() -> list[NormalizedIssue]:
    """
    Convenience function for CLI/testing.

    Environment variables:
    - SONAR_URL
    - SONAR_TOKEN
    - SONAR_PROJECT_KEY
    - SONAR_AUTH_MODE = bearer|basic
    - GITHUB_OWNER
    - GITHUB_REPO
    - GITHUB_TOKEN
    """
    sonar_auth_mode = os.getenv("SONAR_AUTH_MODE", "bearer").lower()
    if sonar_auth_mode not in {"bearer", "basic"}:
        raise ValueError("SONAR_AUTH_MODE must be 'bearer' or 'basic'")

    return collect_security_issues(
        sonar_url=os.getenv("SONAR_URL"),
        sonar_token=os.getenv("SONAR_TOKEN"),
        sonar_project_key=os.getenv("SONAR_PROJECT_KEY"),
        sonar_auth_mode=sonar_auth_mode,  # type: ignore[arg-type]
        github_owner=os.getenv("GITHUB_OWNER"),
        github_repo=os.getenv("GITHUB_REPO"),
        github_token=os.getenv("GITHUB_TOKEN"),
        max_sonar_issues=int(os.getenv("MAX_SONAR_ISSUES", "100")),
        max_codeql_alerts=int(os.getenv("MAX_CODEQL_ALERTS", "50")),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect SonarQube and CodeQL issues, then optionally build a model prompt for one issue."
    )

    parser.add_argument(
        "--project-root",
        default=".",
        help="Local project root used to read code context.",
    )

    parser.add_argument(
        "--issue-id",
        default=None,
        help="If provided, build a prompt for this issue id.",
    )

    parser.add_argument(
        "--include-raw",
        action="store_true",
        help="Include raw scanner responses in printed issue list. Do not use for model prompts.",
    )

    args = parser.parse_args()

    issues = collect_from_env()

    if args.issue_id:
        issue = find_issue_by_id(issues, args.issue_id)
        prompt = build_fix_prompt(
            issue=issue,
            project_root=args.project_root,
        )
        print(prompt)
        return 0

    print(issues_to_json(issues, include_raw=args.include_raw))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except requests.HTTPError as exc:
        print(f"HTTP error: {exc}", file=sys.stderr)
        if exc.response is not None:
            print(exc.response.text[:2000], file=sys.stderr)
        raise SystemExit(1)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)