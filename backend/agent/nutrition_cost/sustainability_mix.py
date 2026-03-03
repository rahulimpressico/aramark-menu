"""
agent/nutrition_cost/sustainability_mix.py
==========================================
Compute plant-based / sustainability mix for the menu.

Graph facts (from filtered JSON)
─────────────────────────────────
  SCHEDULED_ON  : Recipe → Day   (one edge per recipe per day it is served)
  HAS_INGREDIENT: Recipe → Ingredient
  Node fields:
    Recipe      → name, assembly_instructions, special_instructions
    Ingredient  → name, description

What it measures
────────────────
  total_slots         = sum of SCHEDULED_ON edges across all recipes
  plant_based_count   = SCHEDULED_ON slots belonging to plant-based recipes
  plant_based_percent = (plant_based_count / total_slots) × 100
  compliant_44        = plant_based_percent ≥ 44%  (playbook sustainability goal)

Plant-based detection: recipe name + ingredient names matched against
a curated keyword list.  Name match takes priority; ingredient scan
is secondary.  Side/condiment items (cheese, pickle, tomato …) are
excluded so they don't inflate the plant-based count.

Entry point:
    evaluating_sustainability_mix(menu_graph)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("menu_agent.nutrition_cost")

# ── Plant-based keywords (recipe name OR ingredient name) ──────────────────
_PLANT_KEYWORDS: tuple[str, ...] = (
    "vegan",
    "plant-based",
    "plant based",
    "tofu",
    "black bean",
    "veggie burger",
    "veggie",
    "lentil",
    "tempeh",
    "seitan",
    "beyond",
    "impossible",
)

# ── Side / condiment names — excluded from main classification ─────────────
_SIDE_EXCLUDE: tuple[str, ...] = (
    "cheese",
    "pickle",
    "tomato",
    "lettuce",
    "onion",
    "sauce",
    "ketchup",
    "mustard",
    "mayo",
    "relish",
    "trim salad",
    "butter",
    "margarine",
    "dressing",
    "salt",
    "pepper",
    "spice",
    "water",
    "sugar",
    "flour",
    "oil",
)


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class EvaluatingSustainabilityMixOutput:
    plant_based_percent: float
    vegan_percent:       float          # same metric, separate label for JSON
    compliant_44:        bool
    total_offerings:     int            # total SCHEDULED_ON slots
    plant_based_count:   int            # SCHEDULED_ON slots that are plant-based
    message:             str
    plant_based_recipes: list[str] = field(default_factory=list)

    def to_sustainability_json(self) -> dict:
        return {
            "plant_based_percent": self.plant_based_percent,
            "vegan_percent":       self.vegan_percent,
            "compliant_44":        self.compliant_44,
            "total_offerings":     self.total_offerings,
            "plant_based_count":   self.plant_based_count,
            "message":             self.message,
            "plant_based_recipes": self.plant_based_recipes,
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


def _recipe_text(graph: Any, recipe_node: Any) -> str:
    """
    Build a lower-case search string from recipe name + assembly instructions
    + names of linked ingredients (via HAS_INGREDIENT edges).
    """
    parts = [
        recipe_node.name or "",
        recipe_node.assembly_instructions or "",
        recipe_node.special_instructions  or "",
    ]
    for e in graph.get_edges_from(recipe_node.id):
        if e.relationship != "HAS_INGREDIENT":
            continue
        ing = graph.get_node(e.target)
        if ing is not None:
            parts.append(ing.name or "")
            parts.append(ing.description or "")
    return " ".join(parts).lower()


def _is_side(name: str) -> bool:
    n = name.lower()
    return any(k in n for k in _SIDE_EXCLUDE)


def _is_plant_based(text: str) -> bool:
    return any(k in text for k in _PLANT_KEYWORDS)


# ---------------------------------------------------------------------------
# Core deterministic logic
# ---------------------------------------------------------------------------

def _evaluate_sustainability_mix_deterministic(
    graph: Any,
) -> EvaluatingSustainabilityMixOutput:
    recipes = graph.get_recipes()
    if not recipes:
        return EvaluatingSustainabilityMixOutput(
            plant_based_percent=0.0,
            vegan_percent=0.0,
            compliant_44=False,
            total_offerings=0,
            plant_based_count=0,
            message="No recipes found in graph.",
        )

    total_slots   = 0
    plant_count   = 0
    plant_recipes: list[str] = []

    for r in recipes:
        slots = _scheduled_on_count(graph, r.id)
        if slots == 0:
            # Recipe exists but not scheduled — count once
            slots = 1
        total_slots += slots

        # Skip obvious condiment / side items so they don't inflate %
        if _is_side(r.name or ""):
            continue

        text = _recipe_text(graph, r)
        if _is_plant_based(text):
            plant_count += slots
            plant_recipes.append(r.name or r.id)

    plant_pct = round((100.0 * plant_count / total_slots), 1) if total_slots else 0.0
    compliant  = plant_pct >= 44.0

    if compliant:
        msg = f"{plant_pct}% plant-based — meets the 44% sustainability target."
    else:
        gap = round(44.0 - plant_pct, 1)
        msg = f"{plant_pct}% plant-based — {gap}% below the 44% target. Add more plant-based options."

    return EvaluatingSustainabilityMixOutput(
        plant_based_percent=plant_pct,
        vegan_percent=plant_pct,
        compliant_44=compliant,
        total_offerings=total_slots,
        plant_based_count=plant_count,
        message=msg,
        plant_based_recipes=sorted(set(plant_recipes)),
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def evaluating_sustainability_mix(menu_graph: Any) -> EvaluatingSustainabilityMixOutput:
    """
    Compute plant-based / sustainability mix for the menu.
    Uses SCHEDULED_ON edges + recipe name / ingredient keywords.
    No LLM — graph traversal only.
    """
    log.info("[AGENT-TOOL] nutrition-cost: evaluating_sustainability_mix START")
    graph = _ensure_menu_graph(menu_graph)
    out   = _evaluate_sustainability_mix_deterministic(graph)
    log.info(
        "[AGENT-TOOL] nutrition-cost: evaluating_sustainability_mix DONE "
        "plant_based_percent=%.1f  compliant_44=%s",
        out.plant_based_percent, out.compliant_44,
    )
    return out
