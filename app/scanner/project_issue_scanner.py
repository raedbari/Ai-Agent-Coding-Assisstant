import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4


@dataclass
class ToolRun:
    tool: str
    command: str
    status: str
    exit_code: int
    output: str


@dataclass
class ScanIssue:
    id: str
    tool: str
    title: str
    severity: str
    details: str
    command: str


@dataclass
class ScanResult:
    project_id: str
    tool_runs: list[ToolRun]
    issues: list[ScanIssue]


def run_command(command: list[str], cwd: Path) -> tuple[int, str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )

    output_parts = []

    if completed.stdout:
        output_parts.append(completed.stdout)

    if completed.stderr:
        output_parts.append(completed.stderr)

    return completed.returncode, "\n".join(output_parts).strip()


def python_command(module: str, *args: str) -> list[str]:
    return [sys.executable, "-m", module, *args]


def scan_python_compile(project_path: Path) -> tuple[ToolRun, list[ScanIssue]]:
    command = python_command("compileall", "-q", ".")
    command_text = "python -m compileall -q ."

    exit_code, output = run_command(command, cwd=project_path)

    if exit_code == 0:
        return (
            ToolRun(
                tool="compileall",
                command=command_text,
                status="passed",
                exit_code=exit_code,
                output=output,
            ),
            [],
        )

    issue = ScanIssue(
        id=str(uuid4()),
        tool="compileall",
        title="Python syntax or compile error",
        severity="high",
        details=output,
        command=command_text,
    )

    return (
        ToolRun(
            tool="compileall",
            command=command_text,
            status="failed",
            exit_code=exit_code,
            output=output,
        ),
        [issue],
    )


def scan_ruff(project_path: Path) -> tuple[ToolRun, list[ScanIssue]]:
    command = python_command("ruff", "check", ".")
    command_text = "python -m ruff check ."

    exit_code, output = run_command(command, cwd=project_path)

    if exit_code == 0:
        return (
            ToolRun(
                tool="ruff",
                command=command_text,
                status="passed",
                exit_code=exit_code,
                output=output,
            ),
            [],
        )

    if "No module named ruff" in output:
        issue = ScanIssue(
            id=str(uuid4()),
            tool="ruff",
            title="Ruff is not installed",
            severity="high",
            details=output,
            command=command_text,
        )

        return (
            ToolRun(
                tool="ruff",
                command=command_text,
                status="tool_missing",
                exit_code=exit_code,
                output=output,
            ),
            [issue],
        )

    issue = ScanIssue(
        id=str(uuid4()),
        tool="ruff",
        title="Ruff lint issues found",
        severity="medium",
        details=output,
        command=command_text,
    )

    return (
        ToolRun(
            tool="ruff",
            command=command_text,
            status="failed",
            exit_code=exit_code,
            output=output,
        ),
        [issue],
    )


def scan_pytest(project_path: Path) -> tuple[ToolRun, list[ScanIssue]]:
    command = python_command("pytest", "-q")
    command_text = "python -m pytest -q"

    exit_code, output = run_command(command, cwd=project_path)

    if exit_code == 0:
        return (
            ToolRun(
                tool="pytest",
                command=command_text,
                status="passed",
                exit_code=exit_code,
                output=output,
            ),
            [],
        )

    if "No module named pytest" in output:
        issue = ScanIssue(
            id=str(uuid4()),
            tool="pytest",
            title="Pytest is not installed",
            severity="high",
            details=output,
            command=command_text,
        )

        return (
            ToolRun(
                tool="pytest",
                command=command_text,
                status="tool_missing",
                exit_code=exit_code,
                output=output,
            ),
            [issue],
        )

    if exit_code == 5:
        issue = ScanIssue(
            id=str(uuid4()),
            tool="pytest",
            title="No tests collected",
            severity="low",
            details=output or "Pytest did not collect any tests.",
            command=command_text,
        )

        return (
            ToolRun(
                tool="pytest",
                command=command_text,
                status="no_tests",
                exit_code=exit_code,
                output=output,
            ),
            [issue],
        )

    issue = ScanIssue(
        id=str(uuid4()),
        tool="pytest",
        title="Pytest failures found",
        severity="high",
        details=output,
        command=command_text,
    )

    return (
        ToolRun(
            tool="pytest",
            command=command_text,
            status="failed",
            exit_code=exit_code,
            output=output,
        ),
        [issue],
    )


def scan_project(project_id: str, project_path: Path) -> ScanResult:
    tool_runs: list[ToolRun] = []
    issues: list[ScanIssue] = []

    for scanner in [
        scan_python_compile,
        scan_ruff,
        scan_pytest,
    ]:
        tool_run, found_issues = scanner(project_path)
        tool_runs.append(tool_run)
        issues.extend(found_issues)

    return ScanResult(
        project_id=project_id,
        tool_runs=tool_runs,
        issues=issues,
    )