from langgraph.graph import END, START, StateGraph

from app.agent.nodes import collect_context_node, create_repair_plan_node
from app.agent.state import AgentState


def build_repair_graph():
    builder = StateGraph(AgentState)

    builder.add_node("collect_context", collect_context_node)
    builder.add_node("create_repair_plan", create_repair_plan_node)

    builder.add_edge(START, "collect_context")
    builder.add_edge("collect_context", "create_repair_plan")
    builder.add_edge("create_repair_plan", END)

    return builder.compile()