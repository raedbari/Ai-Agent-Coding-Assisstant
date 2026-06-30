from __future__ import annotations

from langgraph.types import interrupt

from app.agent.schemas import ReviewPayload
from app.agent.state import AgentState


def review_fix_node(state: AgentState) -> AgentState:
    fix = state.get("fix")

    if not fix:
        return {
            **state,
            "error": "No fix is available for review.",
        }

    payload = ReviewPayload(
        project_id=state["project_id"],
        summary=fix.get("summary", ""),
        risk=fix.get("risk", "medium"),
        changed_files=fix.get("changed_files", []),
        diff=fix.get("diff", state.get("diff", "")),
    )

    decision = interrupt(payload.model_dump(mode="json"))

    approved = bool(decision.get("approved"))

    return {
        **state,
        "approval_status": "approved" if approved else "rejected",
        "approval_payload": {
            "approved": approved,
            "reason": decision.get("reason"),
        },
    }