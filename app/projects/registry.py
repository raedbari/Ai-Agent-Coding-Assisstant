from typing import Any

from app.scanner.project_issue_scanner import ScanIssue


_SCAN_RESULTS: dict[str, list[ScanIssue]] = {}
_REPAIR_PLANS: dict[tuple[str, str], dict[str, Any]] = {}
_PATCHES: dict[tuple[str, str], list[dict[str, Any]]] = {}


def save_project_issues(project_id: str, issues: list[ScanIssue]) -> None:
    _SCAN_RESULTS[project_id] = issues


def get_project_issues(project_id: str) -> list[ScanIssue]:
    return _SCAN_RESULTS.get(project_id, [])


def get_project_issue(project_id: str, issue_id: str) -> ScanIssue:
    issues = get_project_issues(project_id)

    for issue in issues:
        if issue.id == issue_id:
            return issue

    raise ValueError(f"Issue not found: {issue_id}")


def save_repair_plan(
    project_id: str,
    issue_id: str,
    repair_plan: dict[str, Any],
) -> None:
    _REPAIR_PLANS[(project_id, issue_id)] = repair_plan


def get_repair_plan(project_id: str, issue_id: str) -> dict[str, Any]:
    try:
        return _REPAIR_PLANS[(project_id, issue_id)]
    except KeyError as exc:
        raise ValueError(
            "No repair plan found for this issue. Run propose-fix first."
        ) from exc


def save_project_patches(
    project_id: str,
    issue_id: str,
    patches: list[dict[str, Any]],
) -> None:
    _PATCHES[(project_id, issue_id)] = patches


def get_project_patches(project_id: str, issue_id: str) -> list[dict[str, Any]]:
    try:
        return _PATCHES[(project_id, issue_id)]
    except KeyError as exc:
        raise ValueError(
            "No patches found for this issue. Run build-diff first."
        ) from exc