"""
STEP 4 — PIPELINE  (entry point)
Sab steps ko wire karta hai:

  1. Load    — Excel padhna
  2. Normalize — raw rows clean karna (normalizer.py)
  3. Build    — deterministic graph banana (graph_builder.py)
  4. Validate — schema rules check karna (schema.py)
  5. Emit     — knowledge_graph.json likhna

Bonus: llm_reasoning() stub — future mein OpenAI/Groq ke saath connect karo.
"""

import json
import sys
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path

# Ensure the package directory is on the path when called from outside
sys.path.insert(0, str(Path(__file__).resolve().parent))

from normalizer import normalize
from graph_builder import build_graph

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT  = Path(__file__).resolve().parent.parent
SOURCE_EXCEL  = PROJECT_ROOT / "main_excel_file_dir" / "Grill_station_only.xlsx"
OUTPUT_JSON   = Path(__file__).resolve().parent / "knowledge_graph.json"
STATION_NAME  = "Grill"


# ---------------------------------------------------------------------------
# Step 1 — Load
# ---------------------------------------------------------------------------

def load_excel(path: Path) -> pd.DataFrame:
    print(f"[1/5] Loading: {path.name}")
    if not path.exists():
        raise FileNotFoundError(f"Source file not found: {path}")
    df = pd.read_excel(path)
    print(f"      Rows: {len(df)}, Columns: {len(df.columns)}")
    return df


# ---------------------------------------------------------------------------
# Step 5 — LLM reasoning (stub)
# ---------------------------------------------------------------------------

def llm_reasoning(graph_dict: dict) -> dict:
    """
    Stub for LLM-based reasoning layer.

    Future mein yahan OpenAI / Groq call add karo, e.g.:
      - Recipe ke assembly_instructions summarize karo
      - Ingredients se allergen tags generate karo
      - Food cost anomalies explain karo

    Abhi sirf placeholder data return karta hai.
    """
    recipes = graph_dict["entities"].get("Recipe", [])
    enrichments = []
    for r in recipes:
        enrichments.append({
            "recipe_id":   r["id"],
            "recipe_name": r.get("recipe_name", ""),
            # TODO: replace with real LLM output
            "llm_tags":    [],
            "llm_summary": f"[LLM STUB] Recipe '{r.get('recipe_name','')}' — not yet enriched.",
        })
    return {"llm_enrichments": enrichments, "llm_model": "stub"}


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_pipeline(include_llm: bool = False):
    print("=" * 60)
    print("  Knowledge Graph Pipeline")
    print("=" * 60)

    # Step 1 — Load
    df = load_excel(SOURCE_EXCEL)

    # Step 2 — Normalize
    print("[2/5] Normalizing data...")
    recipes, global_warnings = normalize(df)
    all_warnings = list(global_warnings)
    for r in recipes:
        all_warnings.extend(r.warnings)
    print(f"      Recipes normalized: {len(recipes)}")
    if global_warnings:
        for w in global_warnings:
            print(f"      WARN: {w}")

    # Step 3 — Build graph
    print("[3/5] Building deterministic graph...")
    kg = build_graph(STATION_NAME, recipes)
    counts = kg.counts
    print(f"      {counts}")

    # Step 4 — Validate
    print("[4/5] Validating against schema...")
    validation_issues = kg.validate()
    if validation_issues:
        for issue in validation_issues:
            print(f"      ISSUE: {issue}")
    else:
        print("      All schema checks passed.")

    # Compose output
    graph_dict = kg.to_dict()

    output = {
        "schema_version": "1.0.0",
        **graph_dict,
        "validation_report": {
            "passed": len(validation_issues) == 0,
            "issue_count": len(validation_issues),
            "issues": validation_issues,
        },
        "data_quality_warnings": {
            "total": len(all_warnings),
            "warnings": all_warnings,
        },
        "meta": {
            "source_file":   SOURCE_EXCEL.name,
            "station_name":  STATION_NAME,
            "built_at_utc":  datetime.now(timezone.utc).isoformat(),
            "counts":        counts,
        },
    }

    # Step 4b — Optional LLM enrichment
    if include_llm:
        print("[4b] Running LLM reasoning (stub)...")
        output["llm_layer"] = llm_reasoning(graph_dict)

    # Step 5 — Emit JSON
    print("[5/5] Writing JSON...")
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n  Output: {OUTPUT_JSON}")
    print(f"  ├─ Stations:    {counts['stations']}")
    print(f"  ├─ Weeks:       {counts['weeks']}")
    print(f"  ├─ Days:        {counts['days']}")
    print(f"  ├─ MealPeriods: {counts['meal_periods']}")
    print(f"  ├─ Recipes:     {counts['recipes']}")
    print(f"  ├─ Ingredients: {counts['ingredients']}")
    print(f"  ├─ Relations:   {counts['relations']}")
    print(f"  └─ Validation:  {'PASS' if not validation_issues else 'FAIL (' + str(len(validation_issues)) + ' issues)'}")
    print("=" * 60)
    return output


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Build Grill Knowledge Graph")
    parser.add_argument("--llm", action="store_true", help="Include LLM reasoning stub")
    args = parser.parse_args()
    run_pipeline(include_llm=args.llm)
