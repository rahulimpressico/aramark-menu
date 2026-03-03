"""
agent/rotation_recurrence/item_frequency.py
============================================
Track how often each recipe appears across the menu cycle.

Graph facts (from filtered JSON)
─────────────────────────────────
  SCHEDULED_ON    : Recipe → Day   (one edge per recipe per day it is served)
  Day.day_name    : "Monday", "Tuesday", …
  Node IDs        : raw IDs like "A5763", "M8170" (no prefix)

What it measures
────────────────
  appearance_count = number of unique days the recipe is SCHEDULED_ON
  days             = sorted list of day_names it appears on
  recurrence_signal = recipe appears on ≥ _HIGH_REPETITION_THRESHOLD days

Entry point:
    tracking_item_frequency(menu_graph)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("menu_agent.rotation_recurrence")

_HIGH_REPETITION_THRESHOLD: int = 4   # flag if scheduled on ≥ 4 distinct days

# ── Side / condiment keywords — excluded from recurrence signals ──────────
# Sides repeat every day by design (toppings bar); flagging them as
# "high repetition" is misleading for the rotation analysis.
_SIDE_KEYWORDS: tuple[str, ...] = (
    "sliced tomato", "diced tomato", "sliced red onion", "sliced onion",
    "diced onion", "sliced mushroom", "bell pepper",
    "lettuce", "spinach",
    "american cheese", "shredded cheddar", "shredded cheese",
    "feta cheese", "cheese crumble",
    "dill pickle", "pickle slice",
    "diced ham", "ham cubes",
    "trim salad",
    "ketchup", "mustard", "relish", "coleslaw", "slaw",
    "mayonnaise", "mayo", "hot sauce", "salsa", "ranch",
    "sour cream", "guacamole", "avocado spread",
    "hamburger bun", "slider bun", "brioche bun",
)


def _is_side(name: str) -> bool:
    n = name.lower()
    return any(k in n for k in _SIDE_KEYWORDS)


# ---------------------------------------------------------------------------
# Output dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ItemFrequency:
    recipe_id:        str
    recipe_name:      str
    appearance_count: int
    days:             list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "recipe_id":        self.recipe_id,
            "recipe_name":      self.recipe_name,
            "appearance_count": self.appearance_count,
            "days":             self.days,
        }


@dataclass
class TrackingItemFrequencyOutput:
    frequencies:        list[ItemFrequency]
    recurrence_signals: list[dict]
    message:            str

    def to_frequency_json(self) -> dict:
        return {
            "total_recipes":      len(self.frequencies),
            "recurrence_signals": self.recurrence_signals,
            "message":            self.message,
            "frequencies":        [f.to_dict() for f in self.frequencies],
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_menu_graph(menu_graph: Any) -> Any:
    if isinstance(menu_graph, str):
        import importlib
        return importlib.import_module("menu_agent_analyzer").get_default_menu_graph()
    if isinstance(menu_graph, dict):
        from menu_agent_analyzer import GraphMetadata, Node, Edge, MenuGraph
        raw = menu_graph
        meta = GraphMetadata(
            description=raw.get("graph_metadata", {}).get("description", ""),
            version=raw.get("graph_metadata", {}).get("version", ""),
        )
        return MenuGraph(
            graph_metadata=meta,
            nodes=[Node.from_dict(n) for n in raw.get("nodes", [])],
            edges=[Edge.from_dict(e) for e in raw.get("edges", [])],
        )
    return menu_graph


def _scheduled_days_for_recipe(graph: Any, recipe_id: str) -> list[str]:
    """
    Return sorted list of day_names the recipe is SCHEDULED_ON.
    Uses SCHEDULED_ON (Recipe → Day) edges; reads Day.day_name.
    """
    day_names: set[str] = set()
    for e in graph.get_edges_from(recipe_id):
        if e.relationship != "SCHEDULED_ON":
            continue
        day_node = graph.get_node(e.target)
        if day_node is None:
            continue
        # Day node stores the name in day_name field (not name)
        dname = getattr(day_node, "day_name", "") or getattr(day_node, "name", "") or day_node.id
        if dname:
            day_names.add(dname)

    _DAY_ORDER = {
        "Monday": 1, "Tuesday": 2, "Wednesday": 3, "Thursday": 4,
        "Friday": 5, "Saturday": 6, "Sunday": 7,
    }
    return sorted(day_names, key=lambda d: _DAY_ORDER.get(d, 99))


# ---------------------------------------------------------------------------
# Core deterministic logic
# ---------------------------------------------------------------------------

def _track_item_frequency_deterministic(
    graph:      Any,
    recipe_ids: list[str] | None = None,
) -> TrackingItemFrequencyOutput:
    recipes = graph.get_recipes()
    if not recipes:
        return TrackingItemFrequencyOutput(
            frequencies=[],
            recurrence_signals=[],
            message="No recipes found in graph.",
        )

    # Filter to specific recipe_ids if provided (use raw IDs as-is)
    if recipe_ids:
        id_set  = set(recipe_ids)
        recipes = [r for r in recipes if r.id in id_set]

    frequencies:        list[ItemFrequency] = []
    recurrence_signals: list[dict]          = []

    for r in recipes:
        days  = _scheduled_days_for_recipe(graph, r.id)
        count = len(days)

        freq = ItemFrequency(
            recipe_id        = r.id,
            recipe_name      = r.name or r.id,
            appearance_count = count,
            days             = days,
        )
        frequencies.append(freq)

        # Only flag entrees as high-repetition — sides repeat daily by design
        if count >= _HIGH_REPETITION_THRESHOLD and not _is_side(r.name or ""):
            recurrence_signals.append({
                "recipe_id":   r.id,
                "recipe_name": r.name or r.id,
                "days":        count,
                "signal":      f"High repetition: scheduled on {count} days ({', '.join(days)})",
            })

    # Sort by descending appearance count, then alphabetically by name
    frequencies.sort(key=lambda f: (-f.appearance_count, f.recipe_name))

    if recurrence_signals:
        sig_names = [s["recipe_name"] for s in recurrence_signals]
        msg = (
            f"{len(recurrence_signals)} recipe(s) appear ≥ {_HIGH_REPETITION_THRESHOLD} days "
            f"({', '.join(sig_names)}). Consider rotating to improve variety."
        )
    else:
        msg = f"No high-repetition items (threshold: {_HIGH_REPETITION_THRESHOLD} days). Good rotation."

    return TrackingItemFrequencyOutput(
        frequencies=frequencies,
        recurrence_signals=recurrence_signals,
        message=msg,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def tracking_item_frequency(
    menu_graph: Any,
    recipe_ids: list[str] | None = None,
) -> TrackingItemFrequencyOutput:
    """
    Track how often each recipe appears across the menu cycle.
    Uses SCHEDULED_ON (Recipe → Day) edges — no LLM required.

    Args:
        menu_graph : a MenuGraph instance, dict (raw JSON), or path string.
        recipe_ids : optional list of raw recipe node IDs to limit scope.
    """
    log.info("[AGENT-TOOL] rotation-recurrence: tracking_item_frequency START")
    graph = _ensure_menu_graph(menu_graph)
    out   = _track_item_frequency_deterministic(graph, recipe_ids)
    log.info(
        "[AGENT-TOOL] rotation-recurrence: tracking_item_frequency DONE  "
        "total=%d  signals=%d",
        len(out.frequencies), len(out.recurrence_signals),
    )
    return out
