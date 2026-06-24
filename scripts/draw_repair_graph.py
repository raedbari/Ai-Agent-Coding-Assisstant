import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agent.graph import build_repair_graph  # noqa: E402


OUTPUT_DIR = PROJECT_ROOT / "docs" / "images"
OUTPUT_FILE = OUTPUT_DIR / "repair_graph.png"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    graph = build_repair_graph()
    png_data = graph.get_graph().draw_mermaid_png()

    OUTPUT_FILE.write_bytes(png_data)

    print(f"Graph image created: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()