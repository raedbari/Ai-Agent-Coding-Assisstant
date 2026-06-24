from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RepairStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(description="Short title of the repair step")
    explanation: str = Field(description="Why this step is needed")
    suggested_change: str = Field(description="What should be changed")
    risk: Literal["low", "medium", "high"] = Field(description="Risk level of this step")


class ProposedFileChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_path: str = Field(description="Target file path")

    change_type: Literal["create", "modify", "dependency"] = Field(
        description="Type of file change supported by the patch builder"
    )

    reason: str = Field(description="Why this file change is needed")

    instructions: str = Field(
        description="Short human-readable instructions for the change"
    )

    old_text: str | None = Field(
        default=None,
        description="Exact text to find in the file for simple replacements",
    )

    new_text: str | None = Field(
        default=None,
        description="Exact text that should replace old_text",
    )

    target_line: int | None = Field(
        default=None,
        ge=1,
        description="Target line number if the issue points to a specific line",
    )

    replacement_snippet: str | None = Field(
        default=None,
        description="Optional code or text snippet to add, replace, or use for created files",
    )


class RepairPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

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