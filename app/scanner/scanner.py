from app.scanner.compile_checker import check_python_syntax
from app.scanner.file_index import build_file_index
from app.scanner.models import IssueRecord, IssueSeverity, IssueType, ScanReport
from app.scanner.path_guard import resolve_project_root
from app.scanner.pytest_checker import run_pytest_check
from app.scanner.ruff_checker import run_ruff_check


SEVERITY_ORDER: dict[IssueSeverity, int] = {
    IssueSeverity.HIGH: 0,
    IssueSeverity.MEDIUM: 1,
    IssueSeverity.LOW: 2,
}


def sort_issues(issues: list[IssueRecord]) -> list[IssueRecord]:
    return sorted(
        issues,
        key=lambda issue: (
            SEVERITY_ORDER.get(issue.severity, 99),
            issue.file_path or "",
            issue.line or 0,
            issue.code or "",
        ),
    )


def has_syntax_errors(issues: list[IssueRecord]) -> bool:
    return any(issue.type == IssueType.SYNTAX_ERROR for issue in issues)


def scan_project(project_root: str) -> ScanReport:
    root = resolve_project_root(project_root)

    files = build_file_index(str(root))

    issues: list[IssueRecord] = []

    syntax_issues = check_python_syntax(
        project_root=str(root),
        files=files,
    )

    issues.extend(syntax_issues)

    ruff_issues = run_ruff_check(project_root=str(root))
    issues.extend(ruff_issues)

    if not has_syntax_errors(issues):
        pytest_issues = run_pytest_check(project_root=str(root))
        issues.extend(pytest_issues)

    sorted_issues = sort_issues(issues)

    return ScanReport(
        project_name=root.name,
        project_root=str(root),
        status="failed" if sorted_issues else "passed",
        files_indexed=len(files),
        issues_count=len(sorted_issues),
        issues=sorted_issues,
    )