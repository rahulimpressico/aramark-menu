"""
Script: main_excel_file_dir se Excel padho, sirf station_name = 'Grill' wali rows
filter karke nayi Excel file banao.
"""

import pandas as pd
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAIN_EXCEL_DIR = PROJECT_ROOT / "main_excel_file_dir"
SOURCE_FILE = MAIN_EXCEL_DIR / "full dataset for CH residential.xlsx"
OUTPUT_FILE = MAIN_EXCEL_DIR / "Grill_station_only.xlsx"


def create_grill_excel():
    """Sirf Grill station_name wali rows ke saath nayi Excel file create karta hai."""
    if not SOURCE_FILE.exists():
        print(f"Error: Source file nahi mili: {SOURCE_FILE}")
        return

    print(f"Reading: {SOURCE_FILE}")
    df = pd.read_excel(SOURCE_FILE)

    if "station_name" not in df.columns:
        print("Error: Excel mein 'station_name' column nahi hai.")
        return

    grill_df = df[df["station_name"] == "Grill"].copy()
    print(f"Grill rows: {len(grill_df)}")

    grill_df.to_excel(OUTPUT_FILE, index=False)
    print(f"Created: {OUTPUT_FILE}")


if __name__ == "__main__":
    create_grill_excel()
