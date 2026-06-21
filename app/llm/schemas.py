from pydantic import BaseModel, Field


class RepairPlan(BaseModel):
    summary: str = Field(
        description="Short explanation of the detected issue."
    )
    root_cause: str = Field(
        description="Likely cause based only on provided context."
    )
    confidence: str = Field(
        pattern="^(low|medium|high)$",
        description="Confidence level: low, medium, or high.",
    )
    target_file: str | None = Field(
        default=None,
        description="The file that should be changed.",
    )
    proposed_change: str = Field(
        description="Short description of the minimal change."
    )
    patch_strategy: str = Field(
        description="replace_line, replace_block, or manual_review."
    )
    needs_more_context: bool = Field(
        default=False,
        description="True if the provided context is insufficient.",
    )
    risk_notes: str = Field(
        default="",
        description="Any risk or warning before applying the change.",
    )