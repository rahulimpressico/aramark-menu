"""
Filter menu_graph_v2_extracted.json by meal period and save one JSON per period in a single directory.

Run from backend:
  uv run python -m experiments.scripts.filter_graph_by_meal_period

Output: experiments/reports/graphs/breakfast.json, lunch.json, dinner.json
"""

from pathlib import Path

EXPERIMENTS_DIR = Path(__file__).resolve().parents[1]
MAIN_GRAPH_PATH = EXPERIMENTS_DIR / "menu_graph_v2_extracted.json"
OUTPUT_DIR = EXPERIMENTS_DIR / "reports" / "graphs"
MEAL_PERIODS = ("Breakfast", "Lunch", "Dinner")


def main() -> None:
    from experiments.models.menu_graph import MenuGraph

    if not MAIN_GRAPH_PATH.is_file():
        print(f"Main graph not found: {MAIN_GRAPH_PATH}")
        return
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    graph = MenuGraph.from_json_path(MAIN_GRAPH_PATH)
    print(f"Loaded {len(graph.nodes)} nodes, {len(graph.edges)} edges from {MAIN_GRAPH_PATH.name}")

    for period in MEAL_PERIODS:
        filtered = graph.filter_by_meal_period(period)
        out_path = OUTPUT_DIR / f"{period.lower()}.json"
        import json
        out_path.write_text(json.dumps(filtered.model_dump(mode="json"), indent=2), encoding="utf-8")
        print(f"  {period}: {len(filtered.nodes)} nodes, {len(filtered.edges)} edges -> {out_path}")

    print(f"Done. Filtered graphs in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
