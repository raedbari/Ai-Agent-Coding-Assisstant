import ast
import hashlib
import tokenize
from pathlib import Path

from app.scanner.models import (
    FileRecord,
    FileRole,
    IssueRecord,
    IssueSeverity,
    IssueType,
)


PYTHON_FILE_ROLES: set[FileRole] = {
    FileRole.PYTHON_SOURCE,
    FileRole.TEST_FILE,
}


def make_issue_id(
    issue_type: IssueType,
    file_path: str,
    line: int | None,
    message: str,
) -> str:
    raw_value = f"{issue_type}:{file_path}:{line}:{message}"
    digest = hashlib.sha1(raw_value.encode("utf-8")).hexdigest()[:10]
    return f"issue_{digest}"


def read_python_file(path: Path) -> str:
    with tokenize.open(path) as file:
        return file.read()


def check_python_syntax(
    project_root: str,
    files: list[FileRecord],
) -> list[IssueRecord]:
    root = Path(project_root).expanduser().resolve()
    issues: list[IssueRecord] = []

    for file_record in files:
        if file_record.role not in PYTHON_FILE_ROLES:
            continue

        file_path = root / file_record.relative_path

        try:
            resolved_file_path = file_path.resolve()
            resolved_file_path.relative_to(root)
        except ValueError:
            continue

        try:
            source_code = read_python_file(resolved_file_path)
            ast.parse(source_code, filename=file_record.relative_path)

        except SyntaxError as error:
            line = error.lineno
            column = error.offset
            message = error.msg
            code_line = error.text.strip() if error.text else None

            issues.append(
                IssueRecord(
                    id=make_issue_id(
                        issue_type=IssueType.SYNTAX_ERROR,
                        file_path=file_record.relative_path,
                        line=line,
                        message=message,
                    ),
                    type=IssueType.SYNTAX_ERROR,
                    severity=IssueSeverity.HIGH,
                    checker="syntax_checker",
                    message=message,
                    file_path=file_record.relative_path,
                    line=line,
                    column=column,
                    code=code_line,
                )
            )

        except (OSError, UnicodeDecodeError) as error:
            issues.append(
                IssueRecord(
                    id=make_issue_id(
                        issue_type=IssueType.UNKNOWN,
                        file_path=file_record.relative_path,
                        line=None,
                        message=str(error),
                    ),
                    type=IssueType.UNKNOWN,
                    severity=IssueSeverity.MEDIUM,
                    checker="syntax_checker",
                    message=f"Could not read file: {error}",
                    file_path=file_record.relative_path,
                )
            )

    return issues