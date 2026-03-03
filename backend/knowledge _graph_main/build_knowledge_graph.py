"""
Knowledge Graph Script: Grill_station_only.xlsx se key entities use karke
knowledge graph banata hai aur JSON mein save karta hai.

Key entities: station_name, recipe_id, food_cost, std_period_id, recipe_name,
              assembly_instructions, special_instructions, ingredient_description
"""

import hashlib
import json
import pandas as pd
from pathlib import Path
from collections import defaultdict

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAIN_EXCEL_DIR = PROJECT_ROOT / "main_excel_file_dir"
GRILL_EXCEL = MAIN_EXCEL_DIR / "Grill_station_only.xlsx"
OUTPUT_JSON = Path(__file__).resolve().parent / "knowledge_graph.json"

KEY_COLUMNS = [
    "station_name",
    "recipe_id",
    "food_cost",
    "std_period_id",
    "recipe_name",
    "assembly_instructions",
    "special_instructions",
    "ingredient_description",
]


def build_knowledge_graph():
    """Excel se knowledge graph banata hai: nodes + edges, JSON output."""
    if not GRILL_EXCEL.exists():
        print(f"Error: File nahi mili: {GRILL_EXCEL}")
        return

    df = pd.read_excel(GRILL_EXCEL)
    for col in KEY_COLUMNS:
        if col not in df.columns:
            print(f"Warning: Column '{col}' nahi mila, skip.")

    # Recipe-level: ek recipe_id ke liye ek node, ingredients list
    recipe_rows = df.drop_duplicates(subset=["recipe_id"], keep="first")
    ingredients_by_recipe = (
        df.groupby("recipe_id")["ingredient_description"]
        .apply(lambda x: [str(v).strip() for v in x.dropna().unique().tolist()])
        .to_dict()
    )

    nodes = []
    edges = []
    node_ids = set()

    def add_node(nid, ntype, props):
        if nid in node_ids:
            return
        node_ids.add(nid)
        nodes.append({"id": nid, "type": ntype, **props})

    # 1) Station node (Grill)
    station_name = "Grill"
    add_node(station_name, "station", {"name": station_name})

    # 2) Std period nodes
    periods = df["std_period_id"].dropna().unique().tolist()
    for p in periods:
        pid = f"period_{str(p).strip()}"
        add_node(pid, "std_period", {"name": str(p).strip()})

    # 3) Recipe nodes + Ingredient nodes + edges
    for _, row in recipe_rows.iterrows():
        rid = str(row["recipe_id"]).strip()
        if not rid:
            continue

        recipe_props = {
            "recipe_name": _safe_str(row.get("recipe_name")),
            "food_cost": _safe_float(row.get("food_cost")),
            "assembly_instructions": _safe_str(row.get("assembly_instructions")),
            "special_instructions": _safe_str(row.get("special_instructions")),
        }
        add_node(rid, "recipe", recipe_props)

        # Edge: Recipe -> Station
        edges.append({"source": rid, "target": station_name, "type": "BELONGS_TO_STATION"})

        # Edge: Recipe -> StdPeriod
        sp = row.get("std_period_id")
        if pd.notna(sp) and str(sp).strip():
            pid = f"period_{str(sp).strip()}"
            edges.append({"source": rid, "target": pid, "type": "HAS_STD_PERIOD"})

        # Ingredients: nodes + edges
        for ing_desc in ingredients_by_recipe.get(rid, []):
            if not ing_desc:
                continue
            ing_id = "ing_" + hashlib.md5(ing_desc.encode("utf-8")).hexdigest()[:12]
            add_node(ing_id, "ingredient", {"description": ing_desc})
            edges.append({"source": rid, "target": ing_id, "type": "HAS_INGREDIENT"})

    kg = {
        "nodes": nodes,
        "edges": edges,
        "meta": {
            "source_file": str(GRILL_EXCEL.name),
            "station_name": station_name,
            "num_recipes": len(recipe_rows),
            "num_nodes": len(nodes),
            "num_edges": len(edges),
        },
    }

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(kg, f, indent=2, ensure_ascii=False)

    print(f"Knowledge graph saved: {OUTPUT_JSON}")
    print(f"  Nodes: {len(nodes)}, Edges: {len(edges)}")
    return kg


def _safe_str(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v).strip()


def _safe_float(v):
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    build_knowledge_graph()
