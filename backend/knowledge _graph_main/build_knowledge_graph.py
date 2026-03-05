"""
Build station knowledge graph JSON from a cleaned station Excel file.

This uses the canonical pipeline:
  Excel rows -> normalize.py -> graph_builder.py -> entities/relations JSON
so output stays compatible with normalize_graph/extract_graph_v2.py.
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

GRAPH_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = GRAPH_DIR.parent
MAIN_EXCEL_DIR = PROJECT_ROOT / "main_excel_file_dir"

if str(GRAPH_DIR) not in sys.path:
    sys.path.insert(0, str(GRAPH_DIR))

from graph_builder import build_graph
from normalizer import normalize


def station_slug(name: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in name.strip()).strip("_").lower()


def build_knowledge_graph(station_name: str, source_excel: Path | None = None, output_json: Path | None = None):
    slug = station_slug(station_name)
    if source_excel is None:
        source_excel = MAIN_EXCEL_DIR / f"{slug}_station_only.xlsx"
    if output_json is None:
        output_json = GRAPH_DIR / f"knowledge_graph_{slug}.json"

    if not source_excel.exists():
        raise FileNotFoundError(f"Cleaned station file not found: {source_excel}")

    df = pd.read_excel(source_excel)
    recipes, warnings = normalize(df)
    kg = build_graph(station_name=station_name, recipes=recipes)
    issues = kg.validate()

    payload = kg.to_dict()
    payload["schema_version"] = "1.0.0"
    payload["meta"] = {
        "source_file": source_excel.name,
        "station_name": station_name,
        "warnings_count": len(warnings),
        "validation_issues_count": len(issues),
    }
    if warnings:
        payload["meta"]["normalizer_warnings"] = warnings
    if issues:
        payload["meta"]["validation_issues"] = issues

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    counts = kg.counts
    print(f"Knowledge graph saved: {output_json}")
    print(
        "  Stations: {stations}, Weeks: {weeks}, Days: {days}, Periods: {meal_periods}, "
        "Recipes: {recipes}, Ingredients: {ingredients}, Relations: {relations}".format(**counts)
    )
    if warnings:
        print(f"  Normalizer warnings: {len(warnings)}")
    if issues:
        print(f"  Validation issues: {len(issues)}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build station knowledge graph from cleaned Excel")
    parser.add_argument("--station", required=True, help="Station name, e.g. Grill")
    parser.add_argument("--source", type=Path, default=None, help="Cleaned station Excel path")
    parser.add_argument("--output", type=Path, default=None, help="Output graph JSON path")
    args = parser.parse_args()

    build_knowledge_graph(args.station, args.source, args.output)


if __name__ == "__main__":
    main()
