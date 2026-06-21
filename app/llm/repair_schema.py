from typing import Literal
from pydantic import BaseModel, Field


class RepairStep(BaseModel):
    title: str = Field(description="Short title of the repair step")
    explanation: str = Field(description="Why this step is needed")
    suggested_change: str = Field(description="What should be changed")
    risk: Literal["low", "medium", "high"] = Field(description="Risk level of this step")


class ProposedFileChange(BaseModel):
    file_path: str = Field(description="Target file path")
    change_type: Literal["create", "modify", "delete", "dependency", "none"] = Field(
        description="Type of file change"
    )
    reason: str = Field(description="Why this file change is needed")
    instructions: str = Field(description="Human-readable instructions for the change")
    replacement_snippet: str | None = Field(
        default=None,
        description="Optional code or text snippet to add or replace",
    )


class RepairPlan(BaseModel):
    summary: str = Field(description="Short summary of the problem")
    suspected_root_cause: str = Field(description="Most likely root cause")

    files_to_inspect: list[str] = Field(default_factory=list)
    missing_referenced_files: list[str] = Field(default_factory=list)
    context_warnings: list[str] = Field(default_factory=list)
    missing_optional_files: list[str] = Field(default_factory=list)
    steps: list[RepairStep] = Field(default_factory=list)
    proposed_file_changes: list[ProposedFileChange] = Field(default_factory=list)
    commands_to_run: list[str] = Field(default_factory=list)

    confidence: Literal["low", "medium", "high"]
    needs_human_review: bool