from typing import Any

from pydantic import BaseModel, Field


class RepairRequest(BaseModel):
    problem: str = Field(
        min_length=1,
        description="Error message, traceback, or coding task to analyze",
    )


class RepairResponse(BaseModel):
    context_report: str
    repair_plan: dict[str, Any]


class ProjectItem(BaseModel):
    id: str
    name: str
    description: str


class ToolRunItem(BaseModel):
    tool: str
    command: str
    status: str
    exit_code: int

    # Raw technical output kept for debugging / "Show details"
    output: str = ""

    # User-facing fields
    summary: str = ""
    suggested_action: str | None = None
    raw_output: str = ""


class ScanIssueItem(BaseModel):
    id: str
    tool: str
    title: str
    severity: str

    # Raw technical details kept for debugging / "Show details"
    details: str = ""

    command: str

    # User-facing fields
    summary: str = ""
    location: str | None = None
    suggested_action: str | None = None
    raw_details: str = ""


class ScanProjectResponse(BaseModel):
    project_id: str
    tool_runs: list[ToolRunItem]
    issues: list[ScanIssueItem]


class IssuesResponse(BaseModel):
    project_id: str
    issues: list[ScanIssueItem]


class ProposeFixResponse(BaseModel):
    project_id: str
    issue_id: str
    issue: ScanIssueItem
    context_report: str
    repair_plan: dict[str, Any]


class PatchDiffItem(BaseModel):
    file_path: str
    change_type: str
    diff: str
    can_apply: bool


class BuildDiffResponse(BaseModel):
    project_id: str
    issue_id: str
    patches: list[PatchDiffItem]


class ApplyPatchResponse(BaseModel):
    project_id: str
    issue_id: str
    applied_files: list[str]
    tool_runs: list[ToolRunItem]
    issues: list[ScanIssueItem]