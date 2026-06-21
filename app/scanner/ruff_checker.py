import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from app.scanner.models import IssueRecord, IssueSeverity, IssueType
from app.scanner.compile_checker import make_issue_id
from app.scanner.path_guard import resolve_project_root


def map_ruff_severity(rule_code: str | None) -> IssueSeverity:
    if not rule_code:
        return IssueSeverity.LOW

    if rule_code.startswith(("F821", "E9")):
        return IssueSeverity.HIGH

    if rule_code.startswith(("F", "E", "B")):
        return IssueSeverity.MEDIUM

    return IssueSeverity.LOW


def map_ruff_issue_type(rule_code: str | None) -> IssueType:
    if not rule_code:
        return IssueType.LINT_ERROR

    if rule_code == "F821":
        return IssueType.NAME_ERROR

    if rule_code.startswith("E9"):
        return IssueType.SYNTAX_ERROR

    return IssueType.LINT_ERROR


def normalize_ruff_path(project_root: Path, filename: str) -> str:
    path = Path(filename)

    if path.is_absolute():
        try:
            return path.resolve().relative_to(project_root).as_posix()
        except ValueError:
            return path.name

    return path.as_posix()


def run_ruff_check(project_root: str) -> list[IssueRecord]:
    root = resolve_project_root(project_root)

    if shutil.which("ruff") is None:
        return [
            IssueRecord(
                id=make_issue_id(
                    issue_type=IssueType.UNKNOWN,
                    file_path=str(root),
                    line=None,
                    message="Ruff is not installed or not available in PATH",
                ),
                type=IssueType.UNKNOWN,
                severity=IssueSeverity.MEDIUM,
                checker="ruff",
                message="Ruff is not installed or not available in PATH",
                file_path=None,
            )
        ]

    command = [
        "ruff",
        "check",
        str(root),
        "--output-format",
        "json",
        "--no-cache",
    ]

    completed = subprocess.run(
        command,
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    if completed.returncode == 2:
        return [
            IssueRecord(
                id=make_issue_id(
                    issue_type=IssueType.UNKNOWN,
                    file_path=str(root),
                    line=None,
                    message=completed.stderr or completed.stdout or "Ruff failed",
                ),
                type=IssueType.UNKNOWN,
                severity=IssueSeverity.HIGH,
                checker="ruff",
                message=completed.stderr or completed.stdout or "Ruff failed",
                file_path=None,
            )
        ]

    output = completed.stdout.strip()

    if not output:
        return []

    try:
        raw_issues: list[dict[str, Any]] = json.loads(output)
    except json.JSONDecodeError as error:
        return [
            IssueRecord(
                id=make_issue_id(
                    issue_type=IssueType.UNKNOWN,
                    file_path=str(root),
                    line=None,
                    message=f"Could not parse Ruff JSON output: {error}",
                ),
                type=IssueType.UNKNOWN,
                severity=IssueSeverity.HIGH,
                checker="ruff",
                message=f"Could not parse Ruff JSON output: {error}",
                file_path=None,
            )
        ]

    issues: list[IssueRecord] = []

    for item in raw_issues:
        rule_code = item.get("code")
        message = item.get("message", "Ruff violation")
        filename = item.get("filename", "")
        location = item.get("location") or {}

        line = location.get("row")
        column = location.get("column")
        relative_path = normalize_ruff_path(root, filename)

        issue_type = map_ruff_issue_type(rule_code)

        issues.append(
            IssueRecord(
                id=make_issue_id(
                    issue_type=issue_type,
                    file_path=relative_path,
                    line=line,
                    message=f"{rule_code}: {message}",
                ),
                type=issue_type,
                severity=map_ruff_severity(rule_code),
                checker="ruff",
                message=message,
                file_path=relative_path,
                line=line,
                column=column,
                code=rule_code,
            )
        )

    return issues