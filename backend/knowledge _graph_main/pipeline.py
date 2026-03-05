"""
Station KG pipeline:
  1. Clean station Excel from main dataset
  2. Build station knowledge graph JSON from cleaned file

Example:
  python "knowledge _graph_main/pipeline.py" --station Grill
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from excel_clean_script.clean_excel import clean_station_excel
from build_knowledge_graph import build_knowledge_graph

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAIN_EXCEL = PROJECT_ROOT / "main_excel_file_dir" / "full dataset for CH residential.xlsx"


def station_slug(name: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in name.strip()).strip("_").lower()


def run_pipeline(station_name: str, source_excel: Path = MAIN_EXCEL) -> dict:
    slug = station_slug(station_name)
    cleaned_path = PROJECT_ROOT / "main_excel_file_dir" / f"{slug}_station_only.xlsx"
    graph_out = Path(__file__).resolve().parent / f"knowledge_graph_{slug}.json"

    print("=" * 60)
    print(f"Building station pipeline for: {station_name}")
    print("=" * 60)

    clean_station_excel(station_name=station_name, source_file=source_excel, output_file=cleaned_path)
    print(f"Cleaned station Excel: {cleaned_path}")

    kg = build_knowledge_graph(station_name=station_name, source_excel=cleaned_path, output_json=graph_out)
    print(f"Knowledge graph: {graph_out}")

    return {
        "station": station_name,
        "cleaned_excel": str(cleaned_path),
        "knowledge_graph": str(graph_out),
        "node_count": len(kg.get("nodes", [])),
        "edge_count": len(kg.get("edges", [])),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run station Excel clean + KG build pipeline")
    parser.add_argument("--station", required=True, help="Station name, e.g. Grill")
    parser.add_argument("--source", type=Path, default=MAIN_EXCEL, help="Main source Excel file")
    args = parser.parse_args()

    run_pipeline(args.station, args.source)


if __name__ == "__main__":
    main()
