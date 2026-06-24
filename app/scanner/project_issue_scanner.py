import re
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
    summary: str = ""
    suggested_action: str | None = None
    raw_output: str = ""


@dataclass
class ScanIssue:
    id: str
    tool: str
    title: str
    severity: str
    details: str
    command: str
    summary: str = ""
    location: str | None = None
    suggested_action: str | None = None
    raw_details: str = ""


@dataclass
class ScanResult:
    project_id: str
    tool_runs: list[ToolRun]
    issues: list[ScanIssue]


EXCLUDED_COMPILE_DIRS_PATTERN = (
    r"(?:^|[\\/])"
    r"(\.venv|venv|\.git|node_modules|__pycache__|dist|build)"
    r"(?:[\\/]|$)"
)


def run_command(command: list[str], cwd: Path, timeout_seconds: int = 60) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        output_parts = []

        if exc.stdout:
            output_parts.append(_safe_decode_process_output(exc.stdout))

        if exc.stderr:
            output_parts.append(_safe_decode_process_output(exc.stderr))

        output_parts.append(f"[interrupted: command timed out after {timeout_seconds} seconds]")

        return 124, "\n".join(output_parts).strip()

    output_parts = []

    if completed.stdout:
        output_parts.append(completed.stdout)

    if completed.stderr:
        output_parts.append(completed.stderr)

    return completed.returncode, "\n".join(output_parts).strip()


def _safe_decode_process_output(value: str | bytes) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")

    return value


def python_command(module: str, *args: str) -> list[str]:
    return [sys.executable, "-m", module, *args]


def make_tool_run(
    *,
    tool: str,
    command: str,
    status: str,
    exit_code: int,
    output: str,
    summary: str,
    suggested_action: str | None = None,
) -> ToolRun:
    return ToolRun(
        tool=tool,
        command=command,
        status=status,
        exit_code=exit_code,

        # Keep old UI readable.
        output=summary,

        # Keep full technical output for later "Show details".
        summary=summary,
        suggested_action=suggested_action,
        raw_output=output,
    )


def make_issue(
    *,
    tool: str,
    title: str,
    severity: str,
    details: str,
    command: str,
    summary: str,
    location: str | None = None,
    suggested_action: str | None = None,
) -> ScanIssue:
    compact_details = summary

    if location:
        compact_details += f"\nLocation: {location}"

    if suggested_action:
        compact_details += f"\nAction: {suggested_action}"

    return ScanIssue(
        id=str(uuid4()),
        tool=tool,
        title=title,
        severity=severity,

        # Keep old UI readable.
        details=compact_details,

        command=command,
        summary=summary,
        location=location,
        suggested_action=suggested_action,

        # Keep full technical details.
        raw_details=details,
    )


def extract_ruff_location(output: str) -> str | None:
    match = re.search(r"-->\s+(.+?):(\d+):(\d+)", output)

    if not match:
        return None

    file_path, line, column = match.groups()
    return f"{file_path}:{line}:{column}"


def extract_ruff_summary(output: str) -> str:
    first_non_empty_line = next(
        (line.strip() for line in output.splitlines() if line.strip()),
        "",
    )

    if not first_non_empty_line:
        return "Ruff found lint issues."

    if "F401" in first_non_empty_line and "imported but unused" in first_non_empty_line:
        return first_non_empty_line

    return first_non_empty_line


def ruff_suggested_action(output: str) -> str:
    if "F401" in output and "imported but unused" in output:
        return "Remove the unused import, or run Ruff autofix if the change is safe."

    if "[*]" in output:
        return "This issue is marked as fixable. Review the change, then consider running Ruff with --fix."

    return "Review the Ruff message and update the referenced file."


def extract_compile_location(output: str) -> str | None:
    match = re.search(r'File "(.+?)", line (\d+)', output)

    if not match:
        return None

    file_path, line = match.groups()
    return f"{file_path}:{line}"

def extract_compile_summary(output: str) -> str:
    syntax_match = re.search(r"(SyntaxError: .+)", output)

    if syntax_match:
        return syntax_match.group(1)

    first_error_line = next(
        (
            line.strip()
            for line in output.splitlines()
            if line.strip().startswith(("SyntaxError:", "IndentationError:", "NameError:"))
        ),
        "",
    )

    return first_error_line or "Python could not compile one or more files."


def compile_suggested_action(output: str) -> str:
    if "SyntaxError: expected ':'" in output:
        return "Add ':' at the end of the function, class, if, for, while, try, except, or with statement."

    if "IndentationError" in output:
        return "Fix the indentation in the referenced file."

    return "Open the referenced file and fix the Python syntax error."



def is_interrupted_output(output: str, exit_code: int) -> bool:
    lowered = output.lower()

    windows_ctrl_c_exit_codes = {
        3221225786,
        -1073741510,
    }

    return (
        exit_code == 124
        or exit_code in windows_ctrl_c_exit_codes
        or "interrupted" in lowered
        or "timed out" in lowered
        or "keyboardinterrupt" in lowered
    )


def scan_python_compile(project_path: Path) -> tuple[ToolRun, list[ScanIssue]]:
    command = python_command(
        "compileall",
        "-q",
        "-x",
        EXCLUDED_COMPILE_DIRS_PATTERN,
        ".",
    )
    command_text = (
        'python -m compileall -q -x '
        '"(?:^|[\\\\/])(\\.venv|venv|\\.git|node_modules|__pycache__|dist|build)(?:[\\\\/]|$)" .'
    )

    exit_code, output = run_command(command, cwd=project_path, timeout_seconds=60)

    if exit_code == 0:
        return (
            make_tool_run(
                tool="compileall",
                command=command_text,
                status="passed",
                exit_code=exit_code,
                output=output,
                summary="Python compile check passed.",
            ),
            [],
        )

    if is_interrupted_output(output, exit_code):
        issue = make_issue(
            tool="compileall",
            title="Compile check interrupted",
            severity="medium",
            details=output,
            command=command_text,
            summary="The Python compile check did not finish.",
            suggested_action=(
                "Exclude large generated folders, then run the scan again. "
                "The scanner already skips .venv, venv, .git, node_modules, __pycache__, dist, and build."
            ),
        )

        return (
            make_tool_run(
                tool="compileall",
                command=command_text,
                status="interrupted",
                exit_code=exit_code,
                output=output,
                summary="Python compile check was interrupted.",
                suggested_action="Run the scan again after excluding large generated folders.",
            ),
            [issue],
        )

    location = extract_compile_location(output)

    issue = make_issue(
        tool="compileall",
        title="Python syntax or compile error",
        severity="high",
        details=output,
        command=command_text,
        summary="Python could not compile one or more files.",
        location=location,
        suggested_action="Open the referenced file and fix the syntax error before running tests.",
    )

    return (
        make_tool_run(
            tool="compileall",
            command=command_text,
            status="failed",
            exit_code=exit_code,
            output=output,
            summary="Python compile check failed.",
            suggested_action="Fix the syntax error shown in the issue details.",
        ),
        [issue],
    )


def scan_ruff(project_path: Path) -> tuple[ToolRun, list[ScanIssue]]:
    command = python_command("ruff", "check", ".")
    command_text = "python -m ruff check ."

    exit_code, output = run_command(command, cwd=project_path, timeout_seconds=60)

    if exit_code == 0:
        return (
            make_tool_run(
                tool="ruff",
                command=command_text,
                status="passed",
                exit_code=exit_code,
                output=output,
                summary="Ruff passed. No lint issues found.",
            ),
            [],
        )

    if "No module named ruff" in output:
        issue = make_issue(
            tool="ruff",
            title="Ruff is not installed",
            severity="high",
            details=output,
            command=command_text,
            summary="Ruff could not run because it is not installed.",
            suggested_action="Install Ruff in the active environment, then run the scan again.",
        )

        return (
            make_tool_run(
                tool="ruff",
                command=command_text,
                status="tool_missing",
                exit_code=exit_code,
                output=output,
                summary="Ruff is missing.",
                suggested_action="Install Ruff in the active Python environment.",
            ),
            [issue],
        )

    location = extract_ruff_location(output)
    summary = extract_ruff_summary(output)
    suggested_action = ruff_suggested_action(output)

    issue = make_issue(
        tool="ruff",
        title="Ruff lint issues found",
        severity="medium",
        details=output,
        command=command_text,
        summary=summary,
        location=location,
        suggested_action=suggested_action,
    )

    return (
        make_tool_run(
            tool="ruff",
            command=command_text,
            status="failed",
            exit_code=exit_code,
            output=output,
            summary="Ruff found lint issues.",
            suggested_action="Review the listed issue and apply the suggested cleanup.",
        ),
        [issue],
    )


def scan_pytest(project_path: Path) -> tuple[ToolRun, list[ScanIssue]]:
    command = python_command("pytest", "-q")
    command_text = "python -m pytest -q"

    exit_code, output = run_command(command, cwd=project_path, timeout_seconds=120)

    if exit_code == 0:
        passed_summary = extract_pytest_passed_summary(output)

        return (
            make_tool_run(
                tool="pytest",
                command=command_text,
                status="passed",
                exit_code=exit_code,
                output=output,
                summary=passed_summary,
            ),
            [],
        )

    if "No module named pytest" in output:
        issue = make_issue(
            tool="pytest",
            title="Pytest is not installed",
            severity="high",
            details=output,
            command=command_text,
            summary="Pytest could not run because it is not installed.",
            suggested_action="Install pytest in the active environment, then run the scan again.",
        )

        return (
            make_tool_run(
                tool="pytest",
                command=command_text,
                status="tool_missing",
                exit_code=exit_code,
                output=output,
                summary="Pytest is missing.",
                suggested_action="Install pytest in the active Python environment.",
            ),
            [issue],
        )

    if exit_code == 5:
        issue = make_issue(
            tool="pytest",
            title="No tests collected",
            severity="low",
            details=output or "Pytest did not collect any tests.",
            command=command_text,
            summary="Pytest ran, but no tests were collected.",
            suggested_action="Add tests or check your pytest discovery configuration.",
        )

        return (
            make_tool_run(
                tool="pytest",
                command=command_text,
                status="no_tests",
                exit_code=exit_code,
                output=output,
                summary="Pytest found no tests.",
                suggested_action="Add tests or check the test file naming.",
            ),
            [issue],
        )
    location = extract_compile_location(output)
    compile_summary = extract_compile_summary(output)
    suggested_action = compile_suggested_action(output)

    issue = make_issue(
     tool="compileall",
     title="Python syntax or compile error",
     severity="high",
     details=output,
     command=command_text,
     summary=compile_summary,
     location=location,
     suggested_action=suggested_action,
)

    return (
        make_tool_run(
            tool="pytest",
            command=command_text,
            status="failed",
            exit_code=exit_code,
            output=output,
            summary=compile_summary,
            suggested_action=suggested_action,
        ),
        [issue],
    )


def extract_pytest_passed_summary(output: str) -> str:
    match = re.search(r"(\d+)\s+passed", output)

    if match:
        count = match.group(1)
        return f"Pytest passed. {count} test(s) passed."

    return "Pytest passed."


def extract_pytest_failure_summary(output: str) -> str:
    failed_match = re.search(r"(\d+)\s+failed", output)
    passed_match = re.search(r"(\d+)\s+passed", output)

    parts = []

    if failed_match:
        parts.append(f"{failed_match.group(1)} test(s) failed")

    if passed_match:
        parts.append(f"{passed_match.group(1)} test(s) passed")

    if parts:
        return "Pytest result: " + ", ".join(parts) + "."

    first_error_line = next(
        (
            line.strip()
            for line in output.splitlines()
            if line.strip() and not line.startswith("=")
        ),
        "",
    )

    return first_error_line or "Pytest found failing tests."
def scan_project(project_id: str, project_path: Path) -> ScanResult:
    tool_runs: list[ToolRun] = []
    issues: list[ScanIssue] = []

    compile_run, compile_issues = scan_python_compile(project_path)
    tool_runs.append(compile_run)
    issues.extend(compile_issues)

    # If Python cannot compile or the compile check was interrupted,
    # do not run downstream tools. They would only add noise.
    if compile_run.status in {"failed", "interrupted", "tool_missing"}:
        return ScanResult(
            project_id=project_id,
            tool_runs=tool_runs,
            issues=issues,
        )

    for scanner in [
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