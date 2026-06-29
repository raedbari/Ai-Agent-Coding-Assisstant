from __future__ import annotations

from functools import lru_cache
from typing import Literal

from langgraph.graph import END, START, StateGraph

from app.agent.checkpointer import get_postgres_checkpointer
from app.agent.nodes import (
    apply_patch_to_github_node,
    collect_code_context_node,
    fetch_sonar_issues_node,
    filter_project_issues_node,
    generate_structured_fix_node,
    load_project_node,
    review_fix_node,
)
from app.agent.state import AgentState


RouteAfterIssueFilter = Literal["continue", "done"]
RouteAfterReview = Literal["apply_patch", "done"]


def route_after_issue_filter(state: AgentState) -> RouteAfterIssueFilter:
    if state.get("error"):
        return "done"

    if not state.get("selected_issues"):
        return "done"

    return "continue"


def route_after_review(state: AgentState) -> RouteAfterReview:
    if state.get("approval_status") == "approved":
        return "apply_patch"

    return "done"


@lru_cache(maxsize=1)
def build_repair_graph():
    builder = StateGraph(AgentState)

    builder.add_node("load_project", load_project_node)
    builder.add_node("fetch_sonar_issues", fetch_sonar_issues_node)
    builder.add_node("filter_project_issues", filter_project_issues_node)
    builder.add_node("collect_code_context", collect_code_context_node)
    builder.add_node("generate_structured_fix", generate_structured_fix_node)
    builder.add_node("review_fix", review_fix_node)
    builder.add_node("apply_patch_to_github", apply_patch_to_github_node)

    builder.add_edge(START, "load_project")
    builder.add_edge("load_project", "fetch_sonar_issues")
    builder.add_edge("fetch_sonar_issues", "filter_project_issues")

    builder.add_conditional_edges(
        "filter_project_issues",
        route_after_issue_filter,
        {
            "continue": "collect_code_context",
            "done": END,
        },
    )

    builder.add_edge("collect_code_context", "generate_structured_fix")
    builder.add_edge("generate_structured_fix", "review_fix")

    builder.add_conditional_edges(
        "review_fix",
        route_after_review,
        {
            "apply_patch": "apply_patch_to_github",
            "done": END,
        },
    )

    builder.add_edge("apply_patch_to_github", END)

    return builder.compile(checkpointer=get_postgres_checkpointer())



  
