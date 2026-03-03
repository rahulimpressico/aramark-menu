"""
STEP 1 — SCHEMA
Define entity types, field types, cardinality, and allowed values.
This is the contract the rest of the pipeline must satisfy.
"""

from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# Allowed values (domain enumerations)
# ---------------------------------------------------------------------------

ALLOWED_NODE_TYPES = {"Station", "Week", "Day", "MealPeriod", "Recipe", "Ingredient"}

ALLOWED_MEAL_PERIODS = {"Breakfast", "Brunch", "Lunch", "Dinner", "All Day"}

DAY_NUMBER_TO_NAME = {
    1: "Monday",
    2: "Tuesday",
    3: "Wednesday",
    4: "Thursday",
    5: "Friday",
    6: "Saturday",
    7: "Sunday",
}

ALLOWED_RELATION_PREDICATES = {
    "HAS_WEEK",           # Station  → Week
    "HAS_DAY",            # Week     → Day
    "HAS_PERIOD",         # Day      → MealPeriod
    "SCHEDULED_ON",       # Recipe   → Day        (attrs: week_no, period)
    "BELONGS_TO_STATION", # Recipe   → Station
    "SERVED_IN_PERIOD",   # Recipe   → MealPeriod (summary, deduplicated)
    "USES_INGREDIENT",    # Recipe   → Ingredient
}

# ---------------------------------------------------------------------------
# Entity schemas
# ---------------------------------------------------------------------------

@dataclass
class StationEntity:
    id:        str
    name:      str
    node_type: str = "Station"

    def validate(self) -> list[str]:
        issues = []
        if not self.id.startswith("station_"):
            issues.append(f"Station id must start with 'station_', got: {self.id!r}")
        if not self.name.strip():
            issues.append("Station name is empty.")
        return issues


@dataclass
class WeekEntity:
    id:        str          # e.g. "week_3"
    week_no:   int
    node_type: str = "Week"

    def validate(self) -> list[str]:
        issues = []
        if not self.id.startswith("week_"):
            issues.append(f"Week id must start with 'week_', got: {self.id!r}")
        if self.week_no <= 0:
            issues.append(f"Week number must be > 0, got: {self.week_no}")
        return issues


@dataclass
class DayEntity:
    id:        str          # e.g. "day_Monday"
    day_name:  str          # e.g. "Monday"
    day_no:    int          # 1-7
    week_no:   int
    node_type: str = "Day"

    def validate(self) -> list[str]:
        issues = []
        if not self.id.startswith("day_"):
            issues.append(f"Day id must start with 'day_', got: {self.id!r}")
        if self.day_no not in DAY_NUMBER_TO_NAME:
            issues.append(f"day_no {self.day_no} is not valid (expected 1-7).")
        if self.day_name not in DAY_NUMBER_TO_NAME.values():
            issues.append(f"day_name '{self.day_name}' not in allowed values.")
        return issues


@dataclass
class MealPeriodEntity:
    id:        str          # e.g. "period_Breakfast"
    name:      str
    node_type: str = "MealPeriod"

    def validate(self) -> list[str]:
        issues = []
        if self.name not in ALLOWED_MEAL_PERIODS:
            issues.append(
                f"Unknown MealPeriod '{self.name}'. Allowed: {sorted(ALLOWED_MEAL_PERIODS)}"
            )
        return issues


@dataclass
class RecipeEntity:
    id:                     str
    name:                   str
    food_cost:              float
    assembly_instructions:  str
    special_instructions:   Optional[str] = None
    node_type:              str = "Recipe"

    def validate(self) -> list[str]:
        issues = []
        if not self.id.strip():
            issues.append("Recipe id is empty.")
        if not self.name.strip():
            issues.append(f"Recipe '{self.id}' has empty name.")
        if self.food_cost is None or self.food_cost <= 0:
            issues.append(f"Recipe '{self.id}' has invalid food_cost: {self.food_cost}")
        if not self.assembly_instructions.strip():
            issues.append(f"Recipe '{self.id}' has empty assembly_instructions.")
        return issues


@dataclass
class IngredientEntity:
    id:          str        # "ing_<md5[:12]>"
    description: str
    node_type:   str = "Ingredient"

    def validate(self) -> list[str]:
        issues = []
        if not self.id.startswith("ing_"):
            issues.append(f"Ingredient id must start with 'ing_', got: {self.id!r}")
        if not self.description.strip():
            issues.append(f"Ingredient '{self.id}' has empty description.")
        return issues


# ---------------------------------------------------------------------------
# Relation schema
# ---------------------------------------------------------------------------

@dataclass
class Relation:
    from_type:  str
    from_id:    str
    predicate:  str
    to_type:    str
    to_id:      str
    attributes: dict = None

    def validate(self) -> list[str]:
        issues = []
        if self.predicate not in ALLOWED_RELATION_PREDICATES:
            issues.append(f"Unknown predicate: {self.predicate!r}")
        valid_combos = {
            "HAS_WEEK":           ("Station", "Week"),
            "HAS_DAY":            ("Week",    "Day"),
            "HAS_PERIOD":         ("Day",     "MealPeriod"),
            "SCHEDULED_ON":       ("Recipe",  "Day"),
            "BELONGS_TO_STATION": ("Recipe",  "Station"),
            "SERVED_IN_PERIOD":   ("Recipe",  "MealPeriod"),
            "USES_INGREDIENT":    ("Recipe",  "Ingredient"),
        }
        expected = valid_combos.get(self.predicate)
        if expected and (self.from_type, self.to_type) != expected:
            issues.append(
                f"Relation {self.predicate}: expected ({expected[0]} → {expected[1]}), "
                f"got ({self.from_type} → {self.to_type})"
            )
        return issues
