import re
import subprocess
import sys
from pathlib import Path

from app.scanner.compile_checker import make_issue_id
from app.scanner.models import IssueRecord, IssueSeverity, IssueType
from app.scanner.path_guard import resolve_project_root


PYTEST_LOCATION_PATTERN = re.compile(
    r"(?P<file>[\w./\\-]+\.py):(?P<line>\d+)"
)


def limit_text(value: str, max_chars: int = 4000) -> str:
    value = value.strip()

    if len(value) <= max_chars:
        return value

    return value[:max_chars] + "\n... output truncated ..."


def extract_first_pytest_location(output: str, project_root: Path) -> tuple[str | None, int | None]:
    match = PYTEST_LOCATION_PATTERN.search(output)

    if not match:
        return None, None

    raw_file = match.group("file")
    raw_line = match.group("line")

    path = Path(raw_file)

    if path.is_absolute():
        try:
            file_path = path.resolve().relative_to(project_root).as_posix()
        except ValueError:
            file_path = path.name
    else:
        file_path = path.as_posix()

    try:
        line = int(raw_line)
    except ValueError:
        line = None

    return file_path, line


def has_tests_directory(project_root: Path) -> bool:
    tests_dir = project_root / "tests"

    if tests_dir.exists() and tests_dir.is_dir():
        return True

    return any(project_root.glob("test_*.py"))


def run_pytest_check(
    project_root: str,
    timeout_seconds: int = 120,
) -> list[IssueRecord]:
    root = resolve_project_root(project_root)

    if not has_tests_directory(root):
        return []

    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--tb=short",
        "--maxfail=20",
        "--disable-warnings",
    ]

    try:
        completed = subprocess.run(
            command,
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout_seconds,
        )

    except subprocess.TimeoutExpired:
        return [
            IssueRecord(
                id=make_issue_id(
                    issue_type=IssueType.TEST_ERROR,
                    file_path=str(root),
                    line=None,
                    message=f"pytest timed out after {timeout_seconds} seconds",
                ),
                type=IssueType.TEST_ERROR,
                severity=IssueSeverity.HIGH,
                checker="pytest",
                message=f"pytest timed out after {timeout_seconds} seconds",
                file_path=None,
            )
        ]

    output = "\n".join(
        part for part in [completed.stdout, completed.stderr] if part
    )

    output = limit_text(output)

    if completed.returncode == 0:
        return []

    if completed.returncode == 5:
        return []

    file_path, line = extract_first_pytest_location(output, root)

    if completed.returncode == 1:
        return [
            IssueRecord(
                id=make_issue_id(
                    issue_type=IssueType.TEST_ERROR,
                    file_path=file_path or str(root),
                    line=line,
                    message=output,
                ),
                type=IssueType.TEST_ERROR,
                severity=IssueSeverity.HIGH,
                checker="pytest",
                message=output,
                file_path=file_path,
                line=line,
                code="PYTEST_FAILED",
            )
        ]

    return [
        IssueRecord(
            id=make_issue_id(
                issue_type=IssueType.TEST_ERROR,
                file_path=file_path or str(root),
                line=line,
                message=output or f"pytest failed with exit code {completed.returncode}",
            ),
            type=IssueType.TEST_ERROR,
            severity=IssueSeverity.HIGH,
            checker="pytest",
            message=output or f"pytest failed with exit code {completed.returncode}",
            file_path=file_path,
            line=line,
            code=f"PYTEST_EXIT_{completed.returncode}",
        )
    ]