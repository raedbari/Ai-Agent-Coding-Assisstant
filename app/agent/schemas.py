from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


RiskLevel = Literal["low", "medium", "high"]
ApprovalStatus = Literal["pending", "approved", "rejected"]


class StructuredFix(BaseModel):
    summary: str = Field(
        description="Short human-readable explanation of the proposed fix."
    )
    risk: RiskLevel = Field(
        description="Estimated risk of applying the patch."
    )
    changed_files: list[str] = Field(
        description="Repository-relative files changed by the unified diff."
    )
    diff: str = Field(
        description="Valid unified diff using repository-relative paths."
    )


class ReviewPayload(BaseModel):
    type: str = "review_diff"
    project_id: str
    summary: str
    risk: RiskLevel
    changed_files: list[str]
    diff: str


class ReviewDecision(BaseModel):
    approved: bool
    reason: str | None = None


class AgentRunResponse(BaseModel):
    thread_id: str
    status: str
    events: list[dict]