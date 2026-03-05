"""
Create station-specific cleaned Excel from the main dataset.

Examples:
  python excel_clean_script/clean_excel.py --station Grill
  python excel_clean_script/clean_excel.py --station Pizza
"""

from pathlib import Path
import argparse
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAIN_EXCEL_DIR = PROJECT_ROOT / "main_excel_file_dir"
DEFAULT_SOURCE_FILE = MAIN_EXCEL_DIR / "full dataset for CH residential.xlsx"


def station_slug(name: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in name.strip()).strip("_").lower()


def clean_station_excel(station_name: str, source_file: Path, output_file: Path | None = None) -> Path:
    if not source_file.exists():
        raise FileNotFoundError(f"Source file not found: {source_file}")

    df = pd.read_excel(source_file)
    if "station_name" not in df.columns:
        raise ValueError("Excel does not contain required column: station_name")

    station_df = df[df["station_name"].astype(str).str.strip().str.lower() == station_name.strip().lower()].copy()

    if output_file is None:
      output_file = MAIN_EXCEL_DIR / f"{station_slug(station_name)}_station_only.xlsx"

    output_file.parent.mkdir(parents=True, exist_ok=True)
    station_df.to_excel(output_file, index=False)
    return output_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Create station-only cleaned Excel file")
    parser.add_argument("--station", required=True, help="Station name to filter, e.g. Grill")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE_FILE, help="Main source Excel path")
    parser.add_argument("--output", type=Path, default=None, help="Optional output .xlsx path")
    args = parser.parse_args()

    out = clean_station_excel(args.station, args.source, args.output)
    print(f"Created cleaned station file: {out}")


if __name__ == "__main__":
    main()
