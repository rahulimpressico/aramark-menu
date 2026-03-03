"""
agent/nutrition_cost/cpm_risk_swaps.py
=======================================
Assess CPM (Contribution-Per-Meal) protein mix and suggest swaps.

Graph facts (from filtered JSON)
─────────────────────────────────
  SCHEDULED_ON  : Recipe → Day   (one edge per recipe per day it is served)
  Node fields   : Recipe.name, Recipe.assembly_instructions

What it measures
────────────────
  Classifies each recipe as beef / non-beef alternative / neutral
  using name keywords only (name is cleaner than assembly text for protein type).

  beef_slots     = SCHEDULED_ON slots for beef recipes
  alt_slots      = SCHEDULED_ON slots for non-beef protein alternatives
  cpm_risk_level = "high"   → beef dominant, few alternatives
                   "medium" → some alternatives, but not diversified
                   "low"    → good mix of alternatives

CPM thresholds (playbook-aligned):
  ≥ 3 beef slots         → beef_recurrence_high = True
  ≥ 2 alternative slots  → non_beef_alternatives_diversified = True

Swap recommendations are generated deterministically from those flags.

Entry point:
    calculating_cpm_risk_swaps(menu_graph, recurrence_signals=None)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("menu_agent.nutrition_cost")

# ── Beef keywords (name-only) ──────────────────────────────────────────────
_BEEF_KEYWORDS: tuple[str, ...] = (
    "beef",
    "hamburger",
    "cheeseburger",
    "smash burger",
    "double burger",
)
# "burger" alone only counts if NOT an alternative or a side/trim item
_BURGER_EXCLUDE: tuple[str, ...] = (
    "turkey", "chicken", "bean", "veggie", "vegan",
    "plant", "beyond", "impossible", "fish",
    # Side/trim items that contain "burger" in their label
    "trim", "salad", "sdw", "topping", "condiment",
)

# ── Non-beef alternative keywords (name-only) ─────────────────────────────
_ALT_KEYWORDS: tuple[str, ...] = (
    "turkey",
    "chicken",
    "fish",
    "plant-based",
    "plant based",
    "vegan",
    "tofu",
    "black bean",
    "beyond",
    "impossible",
    "veggie burger",
)


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class CalculatingCpmRiskSwapsOutput:
    beef_recurrence_high:            bool
    non_beef_alternatives_diversified: bool
    cpm_risk_level:                  str            # "high" | "medium" | "low"
    beef_slots:                      int
    alt_slots:                       int
    recommendations:                 list[str] = field(default_factory=list)
    beef_recipes:                    list[str] = field(default_factory=list)
    alt_recipes:                     list[str] = field(default_factory=list)
    message:                         str = ""

    def to_cpm_json(self) -> dict:
        return {
            "cpm_risk_level":                    self.cpm_risk_level,
            "beef_recurrence_high":              self.beef_recurrence_high,
            "non_beef_alternatives_diversified": self.non_beef_alternatives_diversified,
            "beef_slots":                        self.beef_slots,
            "alt_slots":                         self.alt_slots,
            "beef_recipes":                      self.beef_recipes,
            "alt_recipes":                       self.alt_recipes,
            "recommendations":                   self.recommendations,
            "message":                           self.message,
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


def _is_beef(name: str) -> bool:
    n = name.lower()
    if any(k in n for k in _BEEF_KEYWORDS):
        return True
    # "burger" only counts as beef if no alternative marker present
    if "burger" in n and not any(ex in n for ex in _BURGER_EXCLUDE):
        return True
    return False


def _is_alt(name: str) -> bool:
    n = name.lower()
    return any(k in n for k in _ALT_KEYWORDS)


# ---------------------------------------------------------------------------
# Core deterministic logic
# ---------------------------------------------------------------------------

# def _calculate_cpm_risk_swaps_deterministic(
#     graph: Any,
#     recurrence_signals: dict[str, Any] | None = None,
# ) -> CalculatingCpmRiskSwapsOutput:
#     recipes = graph.get_recipes()
#     if not recipes:
#         return CalculatingCpmRiskSwapsOutput(
#             beef_recurrence_high=False,
#             non_beef_alternatives_diversified=False,
#             cpm_risk_level="low",
#             beef_slots=0,
#             alt_slots=0,
#             message="No recipes found in graph.",
#         )

#     beef_slots  = 0
#     alt_slots   = 0
#     beef_names: list[str] = []
#     alt_names:  list[str] = []

#     for r in recipes:
#         name  = r.name or ""
#         slots = _scheduled_on_count(graph, r.id)
#         if slots == 0:
#             slots = 1

#         if _is_beef(name):
#             beef_slots += slots
#             beef_names.append(name)
#         elif _is_alt(name):
#             alt_slots += slots
#             alt_names.append(name)

#     beef_high  = beef_slots >= 3
#     alt_divers = alt_slots  >= 2

#     if beef_high and not alt_divers:
#         risk = "high"
#     elif alt_divers:
#         risk = "low"
#     else:
#         risk = "medium"

#     # Recommendations
#     recs: list[str] = []
#     if beef_high:
#         recs.append(
#             "Swap at least one beef item for a turkey, chicken, or plant-based option per week."
#         )
#     if not alt_divers:
#         recs.append(
#             "Diversify protein alternatives — add turkey, chicken, fish, or plant-based options."
#         )
#     if not beef_high and alt_divers:
#         recs.append(
#             "Good protein mix. Continue rotating beef and plant-based items per playbook."
#         )

#     # Factor in recurrence signals if provided
#     if recurrence_signals:
#         high_rep = recurrence_signals.get("recurrence_signals", [])
#         beef_rep = [s for s in high_rep if _is_beef(s.get("recipe_name", ""))]
#         if beef_rep:
#             names = ", ".join(s["recipe_name"] for s in beef_rep)
#             recs.append(
#                 f"High-repetition beef item(s) detected ({names}): "
#                 "prioritise swapping these first."
#             )

#     msg = (
#         f"Beef slots={beef_slots}, non-beef alt slots={alt_slots}; "
#         f"CPM risk: {risk.upper()}."
#     )

#     return CalculatingCpmRiskSwapsOutput(
#         beef_recurrence_high=beef_high,
#         non_beef_alternatives_diversified=alt_divers,
#         cpm_risk_level=risk,
#         beef_slots=beef_slots,
#         alt_slots=alt_slots,
#         recommendations=recs,
#         beef_recipes=sorted(set(beef_names)),
#         alt_recipes=sorted(set(alt_names)),
#         message=msg,
#     )

# ---------------------------------------------------------------------------
# Core deterministic logic (FIXED VERSION)
# ---------------------------------------------------------------------------

def _calculate_cpm_risk_swaps_deterministic(
    graph: Any,
    recurrence_signals: dict[str, Any] | None = None,
) -> CalculatingCpmRiskSwapsOutput:

    recipes = graph.get_recipes()
    if not recipes:
        return CalculatingCpmRiskSwapsOutput(
            beef_recurrence_high=False,
            non_beef_alternatives_diversified=False,
            cpm_risk_level="low",
            beef_slots=0,
            alt_slots=0,
            message="No recipes found in graph.",
        )

    beef_slots = 0
    alt_slots = 0
    beef_names: list[str] = []
    alt_names: list[str] = []

    for r in recipes:
        name = (r.name or "").strip()
        if not name:
            continue

        slots = _scheduled_on_count(graph, r.id)

        # 🚫 DO NOT artificially inflate slots
        if slots <= 0:
            continue

        # ✅ IMPORTANT: check alternative first
        if _is_alt(name):
            alt_slots += slots
            alt_names.append(name)
            continue

        if _is_beef(name):
            beef_slots += slots
            beef_names.append(name)
            continue

    # ------------------------------------------------------------------
    # Threshold flags
    # ------------------------------------------------------------------

    beef_high = beef_slots >= 3
    alt_divers = alt_slots >= 2

    # ------------------------------------------------------------------
    # Improved CPM risk matrix
    # ------------------------------------------------------------------

    if beef_slots >= 5 and alt_slots <= 1:
        risk = "high"

    elif beef_high and not alt_divers:
        risk = "high"

    elif beef_high and alt_divers:
        risk = "medium"

    elif not beef_high and alt_divers:
        risk = "low"

    else:
        risk = "medium"

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------

    recs: list[str] = []

    if beef_high:
        recs.append(
            "Reduce beef exposure: swap at least one recurring beef item with turkey, chicken, or plant-based."
        )

    if not alt_divers:
        recs.append(
            "Increase protein diversity: add at least two non-beef alternatives weekly."
        )

    if not beef_high and alt_divers:
        recs.append(
            "Healthy protein rotation detected. Maintain balanced beef and alternative scheduling."
        )

    # ------------------------------------------------------------------
    # Recurrence signal integration (safe handling)
    # ------------------------------------------------------------------

    if recurrence_signals and isinstance(recurrence_signals, dict):
        high_rep = recurrence_signals.get("recurrence_signals", [])
        beef_rep = [
            s for s in high_rep
            if isinstance(s, dict) and _is_beef(s.get("recipe_name", ""))
        ]

        if beef_rep:
            names = ", ".join(
                s.get("recipe_name", "")
                for s in beef_rep
                if s.get("recipe_name")
            )
            recs.append(
                f"High-repetition beef items detected ({names}). Prioritise these for swaps."
            )

    msg = (
        f"Beef slots={beef_slots}, "
        f"Non-beef alternative slots={alt_slots}; "
        f"CPM risk level={risk.upper()}."
    )

    return CalculatingCpmRiskSwapsOutput(
        beef_recurrence_high=beef_high,
        non_beef_alternatives_diversified=alt_divers,
        cpm_risk_level=risk,
        beef_slots=beef_slots,
        alt_slots=alt_slots,
        recommendations=recs,
        beef_recipes=sorted(set(beef_names)),
        alt_recipes=sorted(set(alt_names)),
        message=msg,
    )

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def calculating_cpm_risk_swaps(
    menu_graph: Any,
    recurrence_signals: dict[str, Any] | None = None,
) -> CalculatingCpmRiskSwapsOutput:
    """
    Assess CPM protein mix and suggest swaps (nutrition & cost).
    Uses SCHEDULED_ON edges + recipe name keywords.
    Optional recurrence_signals (from tracking_item_frequency) can
    influence recommendations.
    No LLM — graph traversal only.
    """
    log.info("[AGENT-TOOL] nutrition-cost: calculating_cpm_risk_swaps START")
    graph = _ensure_menu_graph(menu_graph)
    out   = _calculate_cpm_risk_swaps_deterministic(graph, recurrence_signals)
    log.info(
        "[AGENT-TOOL] nutrition-cost: calculating_cpm_risk_swaps DONE "
        "cpm_risk_level=%s  beef_slots=%d  alt_slots=%d",
        out.cpm_risk_level, out.beef_slots, out.alt_slots,
    )
    return out
