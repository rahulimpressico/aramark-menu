"""
agent/rotation_recurrence/diversity_index.py
=============================================
Compute a 0–1 diversity index for the menu (rotation & recurrence).

Graph facts (from filtered JSON)
─────────────────────────────────
  SCHEDULED_ON  : Recipe → Day   (one edge per recipe per day it is served)
  SERVED_IN_PERIOD: Recipe → MealPeriod

What it measures  (ENTREES ONLY — sides/condiments are excluded)
────────────────────────────────────────────────────────────────
  Sides like "Sliced Tomatoes", "American Cheese", "Lettuce" repeat every
  day by design (they are the static toppings bar). Including them would
  artificially inflate the "repeated" count and deflate the diversity score.
  So we split ALL recipes into two buckets first:

    entrees = main items (burger, daily-feature, vegan, fries)
    sides   = toppings-bar / condiment / trim items (excluded from index)

  Then:
    entree_slots    = sum of SCHEDULED_ON edges for entree recipes
    unique_entrees  = number of distinct entree Recipe nodes
    diversity_index = unique_entrees / entree_slots  (0–1)
    repeated_static_count = entree_slots - unique_entrees

Thresholds (playbook):
  ≥ 0.6 → Good variety; low monotony risk.
  ≥ 0.3 → Moderate variety; consider rotating daily features.
  < 0.3 → Low diversity; high repetition — rotate per playbook.

Entry point:
    calculating_diversity_index(menu_graph)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("menu_agent.rotation_recurrence")


# ── Side / condiment keywords (name-only match — same logic as playbook_check) ──
_SIDE_KEYWORDS: tuple[str, ...] = (
    # Produce toppings
    "sliced tomato", "diced tomato", "sliced red onion", "sliced onion",
    "diced onion", "sliced mushroom", "bell pepper",
    # Standalone produce
    "lettuce", "spinach",
    # Cheese toppings
    "american cheese", "shredded cheddar", "shredded cheese",
    "feta cheese", "cheese crumble",
    # Pickle / brined
    "dill pickle", "pickle slice",
    # Protein add-ons
    "diced ham", "ham cubes",
    # Trim tray
    "trim salad",
    # Pure condiments
    "ketchup", "mustard", "relish", "coleslaw", "slaw",
    "mayonnaise", "mayo", "hot sauce", "salsa", "ranch",
    "sour cream", "guacamole", "avocado spread",
    # Buns / bread (served as sides)
    "hamburger bun", "slider bun", "brioche bun",
)


def _is_side(name: str) -> bool:
    n = name.lower()
    return any(k in n for k in _SIDE_KEYWORDS)


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class CalculatingDiversityIndexOutput:
    diversity_index:       float
    unique_entree_count:   int
    repeated_static_count: int
    entree_slots:          int   # total scheduled slots for entrees only
    total_slots:           int   # all recipes (entrees + sides)
    side_count:            int   # number of side/condiment recipes
    message:               str
    entree_serve_counts:   dict[str, int] = field(default_factory=dict)
    side_recipes:          list[str]      = field(default_factory=list)

    def to_diversity_json(self) -> dict:
        return {
            "diversity_index":       self.diversity_index,
            "unique_entree_count":   self.unique_entree_count,
            "repeated_static_count": self.repeated_static_count,
            "entree_slots":          self.entree_slots,
            "total_slots":           self.total_slots,
            "side_count":            self.side_count,
            "message":               self.message,
            "entree_serve_counts":   self.entree_serve_counts,
            "side_recipes":          self.side_recipes,
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
        raw  = menu_graph
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


def _scheduled_on_count(graph: Any, recipe_id: str) -> int:
    """Count SCHEDULED_ON (Recipe → Day) edges for this recipe."""
    return sum(
        1 for e in graph.get_edges_from(recipe_id)
        if e.relationship == "SCHEDULED_ON"
    )


# ---------------------------------------------------------------------------
# Core deterministic logic
# ---------------------------------------------------------------------------

def _calculate_diversity_index_deterministic(
    graph: Any,
) -> CalculatingDiversityIndexOutput:
    all_recipes = graph.get_recipes()
    if not all_recipes:
        return CalculatingDiversityIndexOutput(
            diversity_index=0.0,
            unique_entree_count=0,
            repeated_static_count=0,
            entree_slots=0,
            total_slots=0,
            side_count=0,
            message="No recipes found in graph.",
        )

    # ── Split recipes into entrees vs sides ──────────────────────────────────
    entrees: list[Any] = []
    sides:   list[Any] = []

    for r in all_recipes:
        if _is_side(r.name or ""):
            sides.append(r)
        else:
            entrees.append(r)

    # ── Count slots ─────────────────────────────────────────────────────────
    entree_counts: dict[str, int] = {}
    for r in entrees:
        c = _scheduled_on_count(graph, r.id)
        # Some station files miss period-qualified SCHEDULED_ON attributes; keep a 1-slot fallback.
        if c <= 0:
            c = 1
        entree_counts[(r.name or r.id)] = c

    side_slots   = sum(_scheduled_on_count(graph, r.id) for r in sides)
    entree_slots = sum(entree_counts.values())
    total_slots  = entree_slots + side_slots

    unique   = len(entree_counts)
    if entree_slots and unique > entree_slots:
        unique = entree_slots
    repeated = max(0, entree_slots - unique)
    diversity = round(unique / entree_slots, 2) if entree_slots else 0.0
    if diversity >= 0.6:
        msg = "Good entree variety; low monotony risk."
    elif diversity >= 0.3:
        msg = "Moderate entree variety; consider rotating daily features."
    else:
        msg = "Low diversity; high repetition — rotate entree offerings per playbook."

    return CalculatingDiversityIndexOutput(
        diversity_index       = diversity,
        unique_entree_count   = unique,
        repeated_static_count = repeated,
        entree_slots          = entree_slots,
        total_slots           = total_slots,
        side_count            = len(sides),
        message               = msg,
        entree_serve_counts   = entree_counts,
        side_recipes          = sorted(r.name or r.id for r in sides),
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def calculating_diversity_index(menu_graph: Any) -> CalculatingDiversityIndexOutput:
    """
    Compute diversity index for the menu (rotation & recurrence).
    Excludes sides/condiments so static toppings bar does not skew the score.
    Uses SCHEDULED_ON edges to count how many days each recipe appears.
    No LLM — graph traversal only.
    """
    log.info("[AGENT-TOOL] rotation-recurrence: calculating_diversity_index START")
    graph = _ensure_menu_graph(menu_graph)
    out   = _calculate_diversity_index_deterministic(graph)
    log.info(
        "[AGENT-TOOL] rotation-recurrence: calculating_diversity_index DONE  "
        "diversity_index=%.2f  unique_entrees=%d  entree_slots=%d  sides=%d",
        out.diversity_index, out.unique_entree_count,
        out.entree_slots, out.side_count,
    )
    return out
