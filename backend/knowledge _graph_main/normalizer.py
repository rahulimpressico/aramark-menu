"""
STEP 2 — NORMALIZER
Raw Excel rows ko clean, standardize, aur deduplicate karo.
Includes week_no + day_no → day_name schedule capture.

Key rules:
  - All string fields: strip + collapse internal whitespace
  - ingredient_description: UPPERCASE normalize
  - food_cost: per recipe_id, first non-null value
  - recipe_name: per recipe_id, most-frequent name (resolves same-id/diff-name issue)
  - schedule: per recipe_id, all unique (week_no, day_no, day_name, period) tuples
  - null handling: required fields missing → warning, optional → None
"""

import re
import hashlib
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional

from schema import DAY_NUMBER_TO_NAME

# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class ScheduleEntry:
    week_no:  int
    day_no:   int
    day_name: str       # resolved from day_no via DAY_NUMBER_TO_NAME
    period:   str       # std_period_id value


@dataclass
class NormalizedRecipe:
    recipe_id:              str
    recipe_name:            str
    food_cost:              float
    assembly_instructions:  str
    special_instructions:   Optional[str]
    ingredients:            list[str]       # normalized ingredient descriptions
    schedule:               list[ScheduleEntry]  # all (week, day, period) entries
    warnings:               list[str]


# ---------------------------------------------------------------------------
# String helpers
# ---------------------------------------------------------------------------

def clean_str(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return re.sub(r"\s+", " ", str(v).strip())


def normalize_ingredient(desc: str) -> str:
    return re.sub(r"\s+", " ", desc.strip().upper())


def make_ingredient_id(desc: str) -> str:
    normalized = normalize_ingredient(desc)
    return "ing_" + hashlib.md5(normalized.encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Recipe-level resolution helpers
# ---------------------------------------------------------------------------

def resolve_recipe_name(group: pd.DataFrame) -> str:
    counts = group["recipe_name"].apply(clean_str).value_counts()
    if len(counts) > 1:
        names = counts[counts == counts.max()].index.tolist()
        return sorted(names)[0]
    return counts.index[0] if len(counts) else ""


def resolve_food_cost(group: pd.DataFrame) -> float:
    valid = group["food_cost"].dropna()
    return float(valid.iloc[0]) if len(valid) else 0.0


def resolve_schedule(group: pd.DataFrame) -> list[ScheduleEntry]:
    """
    Collect unique (week_no, day_no, std_period_id) combos.
    day_no → day_name via DAY_NUMBER_TO_NAME.
    """
    seen: set[tuple] = set()
    entries: list[ScheduleEntry] = []
    for _, row in group[["week_no", "day_no", "std_period_id"]].drop_duplicates().iterrows():
        week_no = int(row["week_no"]) if pd.notna(row["week_no"]) else None
        day_no  = int(row["day_no"])  if pd.notna(row["day_no"])  else None
        period  = clean_str(row["std_period_id"])

        if week_no is None or day_no is None or not period:
            continue

        key = (week_no, day_no, period)
        if key in seen:
            continue
        seen.add(key)

        day_name = DAY_NUMBER_TO_NAME.get(day_no, f"Day{day_no}")
        entries.append(ScheduleEntry(
            week_no=week_no,
            day_no=day_no,
            day_name=day_name,
            period=period,
        ))

    return sorted(entries, key=lambda e: (e.week_no, e.day_no, e.period))


# ---------------------------------------------------------------------------
# Main normalization function
# ---------------------------------------------------------------------------

def normalize(df: pd.DataFrame) -> tuple[list[NormalizedRecipe], list[str]]:
    """
    Raw DataFrame → list[NormalizedRecipe] + global warnings.
    """
    global_warnings: list[str] = []
    recipes:         list[NormalizedRecipe] = []

    required_cols = {
        "station_name", "recipe_id", "food_cost",
        "std_period_id", "week_no", "day_no",
        "recipe_name", "assembly_instructions", "ingredient_description",
    }
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        global_warnings.append(f"Missing columns in source: {sorted(missing_cols)}")

    for recipe_id, group in df.groupby("recipe_id"):
        recipe_id = clean_str(recipe_id)
        if not recipe_id:
            global_warnings.append("Found a row with empty recipe_id — skipped.")
            continue

        row_warnings: list[str] = []

        # --- recipe_name: majority vote ---
        recipe_name = resolve_recipe_name(group)
        all_names   = group["recipe_name"].apply(clean_str).unique().tolist()
        if len(all_names) > 1:
            row_warnings.append(
                f"recipe_id '{recipe_id}' has {len(all_names)} different names; "
                f"resolved to: '{recipe_name}'. "
                f"Others: {[n for n in all_names if n != recipe_name]}"
            )
        if not recipe_name:
            row_warnings.append(f"recipe_id '{recipe_id}' has no recipe_name.")

        # --- food_cost ---
        food_cost = resolve_food_cost(group)
        if food_cost <= 0:
            row_warnings.append(f"recipe_id '{recipe_id}' has food_cost <= 0: {food_cost}")

        # --- assembly_instructions ---
        asm = clean_str(
            group["assembly_instructions"].dropna().iloc[0]
            if group["assembly_instructions"].notna().any() else ""
        )
        if not asm:
            row_warnings.append(f"recipe_id '{recipe_id}' has no assembly_instructions.")

        # --- special_instructions ---
        sp_series = group["special_instructions"].dropna()
        special   = clean_str(sp_series.iloc[0]) if len(sp_series) else None

        # --- ingredients ---
        raw_ings   = group["ingredient_description"].dropna().tolist()
        null_count = group["ingredient_description"].isna().sum()
        if null_count:
            row_warnings.append(
                f"recipe_id '{recipe_id}' has {null_count} rows with null ingredient_description."
            )
        ingredients = list(
            dict.fromkeys(normalize_ingredient(i) for i in raw_ings if str(i).strip())
        )
        if not ingredients:
            row_warnings.append(f"recipe_id '{recipe_id}' has no ingredients.")

        # --- schedule: week_no + day_no + period ---
        schedule = resolve_schedule(group)
        if not schedule:
            row_warnings.append(f"recipe_id '{recipe_id}' has no schedule entries.")

        recipes.append(NormalizedRecipe(
            recipe_id=recipe_id,
            recipe_name=recipe_name,
            food_cost=food_cost,
            assembly_instructions=asm,
            special_instructions=special if special else None,
            ingredients=ingredients,
            schedule=schedule,
            warnings=row_warnings,
        ))

    return recipes, global_warnings
