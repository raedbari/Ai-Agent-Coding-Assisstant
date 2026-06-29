from __future__ import annotations

from langgraph.types import Command

from app.agent.graph import build_repair_graph


def main() -> None:
    graph = build_repair_graph()

    config = {
        "configurable": {
            "thread_id": "demo-security-issues-001",
        }
    }

    print("=== START GRAPH ===")

    for event in graph.stream(
        {"project_id": "security_issues"},
        config=config,
        stream_mode="updates",
    ):
        print(event)

    print("=== RESUME WITH APPROVAL ===")

    for event in graph.stream(
        Command(resume={"approved": True, "reason": "Approved from CLI test."}),
        config=config,
        stream_mode="updates",
    ):
        print(event)


if __name__ == "__main__":
    main()