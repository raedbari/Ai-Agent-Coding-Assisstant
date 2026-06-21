from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class IssueSeverity(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IssueType(StrEnum):
    SYNTAX_ERROR = "syntax_error"
    LINT_ERROR = "lint_error"
    TEST_ERROR = "test_error"
    IMPORT_ERROR = "import_error"
    NAME_ERROR = "name_error"
    ATTRIBUTE_ERROR = "attribute_error"
    UNKNOWN = "unknown"


class FileRole(StrEnum):
    PYTHON_SOURCE = "python_source"
    DEPENDENCY_MANIFEST = "dependency_manifest"
    TEST_FILE = "test_file"
    CONFIG_FILE = "config_file"


class FileRecord(BaseModel):
    relative_path: str
    suffix: str
    size_bytes: int
    role: FileRole


class IssueRecord(BaseModel):
    id: str
    type: IssueType
    severity: IssueSeverity
    checker: str
    message: str
    file_path: str | None = None
    line: int | None = None
    column: int | None = None
    code: str | None = None


class ScanReport(BaseModel):
    project_name: str
    project_root: str
    status: Literal["passed", "failed"]
    files_indexed: int = 0
    issues_count: int = 0
    issues: list[IssueRecord] = Field(default_factory=list)