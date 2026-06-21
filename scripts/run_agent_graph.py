import json
import sys
from pathlib import Path

from app.agent.graph import build_repair_graph


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_FILE = PROJECT_ROOT / "demo_projects" / "current_error.txt"


def resolve_input_file() -> Path:
    if len(sys.argv) >= 2:
        input_path = Path(sys.argv[1])

        if not input_path.is_absolute():
            input_path = PROJECT_ROOT / input_path

        return input_path

    return DEFAULT_INPUT_FILE


def main() -> None:
    input_file = resolve_input_file()

    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    problem = input_file.read_text(encoding="utf-8").strip()

    if not problem:
        raise ValueError(f"Input file is empty: {input_file}")

    graph = build_repair_graph()

    result = graph.invoke(
        {
            "problem": problem,
        }
    )

    print(result.get("context_report", ""))

    print(json.dumps(
        result["repair_plan"],
        indent=2,
        ensure_ascii=False,
    ))


if __name__ == "__main__":
    main()