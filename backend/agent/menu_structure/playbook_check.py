"""
agent/menu_structure/playbook_check.py
=======================================
Deterministic playbook-compliance check for a Grill-station MenuGraph.

Based on the official Grill Station Playbook
─────────────────────────────────────────────
Offerings Structure
  Core Offerings (static):
    • Burger (beef)
    • Chicken sandwich / hot dog
    • Fries
    • MTO Toppings Bar (condiments / garnishes)
    • Additional proteins per client demand

  Enhancements (rotating):
    • Daily Feature  — grilled chicken, hot dog, grilled cheese, etc.
    • Vegan Option
    • French Fry

Recommended Maximum Selections (per day)
  • max 1   Burger (beef)
  • max 2   Daily Features (rotate)
  • min 1   Vegan Option
  • min 1   French Fry

Chef Tips / Menu Engineering
  • Swap ≥1 beef burger/week for non-beef alternative (turkey, chicken, fish)
    → lowers CPM by 18 % without decreasing satisfaction.
  • Diversify proteins: turkey burgers, chicken, fish sandwiches count as
    Daily Features, NOT as the Burger slot.
  • MTO take-overs (e.g. Grilled Cheese) replace the Burger slot on those days.
  • MTO station: simplified menu + condiment/toppings bar for speed of service.

Entry point:
    checking_playbook_bounds(menu_graph, meal_period, day_key)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("menu_agent.playbook")

# ---------------------------------------------------------------------------
# Keyword lists  (all matched against recipe NAME only — never assembly text)
#
# Playbook category definitions
# ──────────────────────────────
# BURGER        → Beef burger (max 1/day). Non-beef alternatives (turkey, chicken,
#                 fish, veggie) are NOT burgers — they count as Daily Features or Vegan.
# DAILY_FEATURE → Rotating enhancements: grilled chicken, hot dog/corn dog,
#                 grilled cheese, chicken sandwich, turkey burger, fish sandwich,
#                 wraps, soups, sliders, snackers, pancakes, etc.
# VEGAN         → Plant-based main item (min 1/day): black bean burger, beyond,
#                 impossible, plant-based patty, etc.
# FRIES         → French fry / fried starch (min 1/day).
# SIDE          → MTO Toppings Bar items: toppings, garnishes, condiments.
# ---------------------------------------------------------------------------

# ── BURGER  (beef only, max 1/day) ──────────────────────────────────────────
# Specific phrases first, then the broad "burger" catch-all.
# The classifier guards against vegan + non-beef alternatives via _BURGER_EXCLUDE.
_PLAYBOOK_BURGER_KEYWORDS: tuple[str, ...] = (
    "double burger",
    "smash burger",
    "cheeseburger",
    "hamburger",
    "beef burger",
    "burger",           # broad catch-all — exclusion guard applied at classify time
)

# Non-beef alternatives that contain "burger" → go to VEGAN or DAILY_FEATURE instead
_BURGER_EXCLUDE_KEYWORDS: tuple[str, ...] = (
    "black bean burger",
    "veggie burger",
    "vegan burger",
    "turkey burger",
    "chicken burger",
    "fish burger",
    "plant-based burger",
    "beyond burger",
    "impossible burger",
    "plant-based",
    "plant based",
    "vegan",
    "black bean",
)

# ── FRIES  (french fry / fried starch, min 1/day) ───────────────────────────
# Uses full phrases to avoid matching cooking verbs like "fry" in assembly text.
_PLAYBOOK_FRIES_KEYWORDS: tuple[str, ...] = (
    "french fries",
    "crinkle french",       # "Crinkle French Fries"
    "crinkle fries",
    "waffle fries",
    "steak fries",
    "sweet potato fries",
    "tater tots",
    "hash brown",
    "onion rings",
    "fries",
)

# ── VEGAN  (plant-based main item, min 1/day) ────────────────────────────────
# Chef Tip: non-beef burgers (turkey, chicken, fish) are Daily Features, not Vegan.
# Only dedicated plant-based items count here.
_PLAYBOOK_VEGAN_KEYWORDS: tuple[str, ...] = (
    "black bean burger",
    "veggie burger",
    "vegan burger",
    "plant-based burger",
    "beyond burger",
    "impossible burger",
    "vegan",
    "plant-based",
    "plant based",
)

# ── DAILY_FEATURE  (rotating enhancements, max 2/day) ───────────────────────
# Anything not matching burger / fries / vegan / side is a Daily Feature.
# Examples from playbook: grilled chicken, hot dog, grilled cheese, chicken
# sandwich, turkey burger, fish sandwich, wraps, soups, sliders, snackers.
# No explicit keyword list needed — this is the default / fallback category.

# ── SIDE / MTO TOPPINGS BAR ──────────────────────────────────────────────────
# Playbook: "MTO Toppings Bar" — individual ingredients served as condiments.
# Classification rules:
#   • Use multi-word phrases where a single word would over-match
#     (e.g. "sliced tomato" not bare "tomato" → "Creamy Tomato Basil Soup" is safe)
#   • Standalone ingredient names (lettuce, egg) are safe as single words
#     because a recipe named only "Lettuce" or "Egg" is clearly a bar topping.
_SIDE_OR_CONDIMENT_KEYWORDS: tuple[str, ...] = (
    # ── Produce toppings (sliced / diced → specific phrases) ──
    "sliced tomato",
    "diced tomato",
    "sliced red onion",
    "sliced onion",
    "diced onion",
    "sliced mushroom",
    "chopped fresh spinach",
    "sliced mixed bell pepper",
    "bell pepper",
    # ── Standalone produce (recipe name IS the ingredient) ────
    "lettuce",
    "spinach",
    # ── Cheese toppings ───────────────────────────────────────
    "american cheese",
    "shredded cheddar",
    "shredded cheese",
    "feta cheese",
    "cheese crumble",
    # ── Pickle / brined condiment ─────────────────────────────
    "dill pickle",
    "pickle slice",
    # ── Protein add-ons / garnishes ───────────────────────────
    "diced ham",
    "ham cubes",
    "crumbled plant-based",     # plant-based chorizo topping (not a main item)
    # ── Standalone eggs (pancake / breakfast bar topping) ─────
    "eggs",
    "egg",
    # ── Burger / sandwich trim tray ───────────────────────────
    "trim salad",
    # ── Pure condiments ───────────────────────────────────────
    "ketchup",
    "mustard",
    "relish",
    "coleslaw",
    "slaw",
    "mayonnaise",
    "mayo",
)

# ---------------------------------------------------------------------------
# Playbook limits  (per day) — from "Recommended Maximum Selections"
# ---------------------------------------------------------------------------

_PLAYBOOK_PER_DAY: dict[str, int] = {
    "burger":        1,   # max 1 beef burger
    "daily_feature": 2,   # max 2 rotating daily features
    "vegan":         1,   # min 1 vegan option
    "fries":         1,   # min 1 french fry offering
}

# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class CheckingPlaybookBoundsOutput:
    compliant:              bool
    under_offered:          list[str]      = field(default_factory=list)
    over_offered:           list[str]      = field(default_factory=list)
    counts:                 dict[str, int] = field(default_factory=dict)
    playbook_limits:        dict           = field(default_factory=dict)
    message:                str            = ""
    per_day:                list[dict]     = field(default_factory=list)
    day_recipe_counts:      list[dict]     = field(default_factory=list)
    day_period_recipes:     list[dict]     = field(default_factory=list)
    recipe_classifications: list[dict]     = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "compliant":              self.compliant,
            "under_offered":          self.under_offered,
            "over_offered":           self.over_offered,
            "counts":                 self.counts,
            "playbook_limits":        self.playbook_limits,
            "message":                self.message,
            "per_day":                self.per_day,
            "day_recipe_counts":      self.day_recipe_counts,
            "day_period_recipes":     self.day_period_recipes,
            "recipe_classifications": self.recipe_classifications,
        }

    def to_playbook_json(self, meal_period: str = "") -> dict:
        """
        Return a clean, caller-ready JSON dict with:
          meal_period, compliant, status, categories (count + rule + status + recipes),
          violations, sides.
        """
        cat_names: dict[str, list[str]] = {}
        for rc in self.recipe_classifications:
            cat_names.setdefault(rc["category"], []).append(rc["name"])

        return {
            "meal_period": meal_period,
            "compliant":   self.compliant,
            "status":      "COMPLIANT" if self.compliant else "VIOLATION",
            "categories": {
                cat: {
                    "count":         self.counts.get(cat, 0),
                    "playbook_rule": f"{meta['rule']} {meta['limit']}",
                    "status": "ok" if (
                        self.counts.get(cat, 0) <= meta["limit"]
                        if meta["rule"] == "max"
                        else self.counts.get(cat, 0) >= meta["limit"]
                    ) else "FAIL",
                    "recipes": cat_names.get(cat, []),
                }
                for cat, meta in self.playbook_limits.items()
            },
            "violations": self.over_offered + self.under_offered,
            "sides": {
                "count":   len(cat_names.get("side", [])),
                "recipes": cat_names.get("side", []),
            },
        }

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _recipe_name(recipe: Any) -> str:
    """Return the recipe name (lower-cased). Classification uses NAME ONLY to avoid
    false matches from cooking verbs in assembly text (e.g. 'fry', 'tomato', 'onion')."""
    return (getattr(recipe, "name", "") or "").lower()


def _text_matches_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(kw in text for kw in keywords)


def _is_side_or_condiment(name: str) -> bool:
    """Return True if the recipe name indicates a topping / condiment / garnish."""
    return _text_matches_any(name, _SIDE_OR_CONDIMENT_KEYWORDS)


def _ensure_menu_graph(menu_graph: Any) -> Any:
    """
    Accept MenuGraph object, a raw dict (normalized JSON), or a file path string.
    Returns a MenuGraph-compatible object.

    For dict / path, we lazy-import get_default_menu_graph from menu_agent_analyzer
    to avoid circular imports at module load time.
    """
    if isinstance(menu_graph, (str,)):
        from pathlib import Path as _Path
        import sys, importlib
        _mod = importlib.import_module("menu_agent_analyzer")
        return _mod.get_default_menu_graph(_Path(menu_graph))

    if isinstance(menu_graph, dict):
        import sys, importlib
        _mod = importlib.import_module("menu_agent_analyzer")
        # Re-hydrate from raw dict
        from menu_agent_analyzer import GraphMetadata, Node, Edge, MenuGraph
        meta_raw = menu_graph.get("graph_metadata", {})
        meta = GraphMetadata(
            description=meta_raw.get("description", ""),
            version=meta_raw.get("version", ""),
            cycle=meta_raw.get("cycle", ""),
        )
        nodes = [Node.from_dict(n) for n in menu_graph.get("nodes", [])]
        edges = [Edge.from_dict(e) for e in menu_graph.get("edges", [])]
        return MenuGraph(graph_metadata=meta, nodes=nodes, edges=edges)

    # Already a MenuGraph (or duck-typed object with required methods)
    return menu_graph

# ---------------------------------------------------------------------------
# Core deterministic check
# ---------------------------------------------------------------------------

def _check_playbook_bounds_deterministic(graph: Any) -> CheckingPlaybookBoundsOutput:
    """
    Classify recipes by keyword and check playbook limits.

    Graph has Period → Recipe (no day-level breakdown per recipe),
    so we count each unique recipe once per period and treat that
    as the "per day" offering (same lineup each day).

    Playbook:
        max 1 burger, max 2 daily features, min 1 vegan, min 1 fries per day.
    """
    under_offered:    list[str] = []
    over_offered:     list[str] = []
    counts = {"burger": 0, "daily_feature": 0, "vegan": 0, "fries": 0}
    per_day:          list[dict] = []
    day_period_recipes: list[dict] = []

    # Collect each unique recipe once (across all periods in the filtered graph).
    # Classification is done on recipe NAME ONLY to avoid false matches from
    # cooking verbs / ingredients mentioned in assembly instructions.
    seen_recipe_ids: set[str] = set()
    recipe_classifications: list[dict] = []   # for debug / transparency

    for period in graph.get_meal_periods():
        for r in graph.get_recipes_for_period(period.id):
            if r.id in seen_recipe_ids:
                continue
            seen_recipe_ids.add(r.id)
            name = _recipe_name(r)

            if _is_side_or_condiment(name):
                recipe_classifications.append({"id": r.id, "name": r.name, "category": "side"})
                continue

            # Vegan check first — takes priority over burger catch-all
            if _text_matches_any(name, _PLAYBOOK_VEGAN_KEYWORDS):
                counts["vegan"] += 1
                recipe_classifications.append({"id": r.id, "name": r.name, "category": "vegan"})
            # Beef burger: matches burger keywords AND not excluded as non-beef
            elif (
                _text_matches_any(name, _PLAYBOOK_BURGER_KEYWORDS)
                and not _text_matches_any(name, _BURGER_EXCLUDE_KEYWORDS)
            ):
                counts["burger"] += 1
                recipe_classifications.append({"id": r.id, "name": r.name, "category": "burger"})
            elif _text_matches_any(name, _PLAYBOOK_FRIES_KEYWORDS):
                counts["fries"] += 1
                recipe_classifications.append({"id": r.id, "name": r.name, "category": "fries"})
            else:
                # Everything else = Daily Feature (rotating enhancements)
                # Playbook examples: grilled chicken, hot dog, grilled cheese,
                # chicken sandwich, turkey burger, fish sandwich, wraps, soups, etc.
                counts["daily_feature"] += 1
                recipe_classifications.append({"id": r.id, "name": r.name, "category": "daily_feature"})

    log.debug("[PLAYBOOK] Recipe classifications: %s", recipe_classifications)

    # Build category → recipe name lookup (for per-day display)
    cat_to_names: dict[str, list[str]] = {
        "burger": [], "fries": [], "vegan": [], "daily_feature": [], "side": []
    }
    for rc in recipe_classifications:
        cat_to_names[rc["category"]].append(rc["name"])

    # Per-day breakdown using SCHEDULED_ON edges for actual day-wise recipe counts.
    # SCHEDULED_ON: Recipe → Day  (with attributes: week_no, period)
    # Build: day_id → set of recipe ids actually scheduled on that day
    day_id_to_recipe_ids: dict[str, set] = {}
    for e in graph.get_edges_by_rel("SCHEDULED_ON"):
        day_id_to_recipe_ids.setdefault(e.source if False else e.target, set())
        # edge is Recipe → Day, so e.target is day, e.source is recipe
        day_id_to_recipe_ids.setdefault(e.target, set()).add(e.source)

    day_burger  = counts["burger"]
    day_feature = counts["daily_feature"]
    day_vegan   = counts["vegan"]
    day_fries   = counts["fries"]

    day_recipe_counts: list[dict] = []
    days = graph.get_days_for_station()
    for day in days:
        day_name = getattr(day, "day_name", "") or getattr(day, "name", "")
        week_no  = getattr(day, "week_no", "")

        # Recipes actually scheduled on this day (via SCHEDULED_ON)
        scheduled_ids = day_id_to_recipe_ids.get(day.id, set())
        total_on_day  = len(scheduled_ids)

        # Classify the scheduled recipes for this day using recipe_classifications.
        # Note: recipe_classifications includes sides (category="side").
        day_cats: dict[str, int] = {"burger": 0, "fries": 0, "vegan": 0, "daily_feature": 0, "side": 0}
        day_recipe_names: list[str] = []
        for rc in recipe_classifications:
            if rc["id"] in scheduled_ids:
                day_cats[rc["category"]] += 1
                if rc["category"] != "side":
                    day_recipe_names.append(rc["name"])
        total_main = day_cats["burger"] + day_cats["fries"] + day_cats["vegan"] + day_cats["daily_feature"]

        day_recipe_counts.append({
            "day":           day_name,
            "week_no":       week_no,
            "total":         total_on_day,
            "main_items":    total_main,
            "sides":         day_cats["side"],
            "burger":        day_cats["burger"],
            "daily_feature": day_cats["daily_feature"],
            "vegan":         day_cats["vegan"],
            "fries":         day_cats["fries"],
            "recipe_names":  day_recipe_names,
        })

        per_day.append({
            "day":                    day_name,
            "burger":                 day_burger,
            "daily_feature":          day_feature,
            "vegan":                  day_vegan,
            "fries":                  day_fries,
            "playbook_burger":        _PLAYBOOK_PER_DAY["burger"],
            "playbook_daily_feature": _PLAYBOOK_PER_DAY["daily_feature"],
            "playbook_vegan":         _PLAYBOOK_PER_DAY["vegan"],
            "playbook_fries":         _PLAYBOOK_PER_DAY["fries"],
        })

        period_nodes = graph.get_periods_for_day(day.id)
        period_names = [getattr(p, "name", "") for p in period_nodes]

        # Fallback: if no HAS_PERIOD link exists for this day but there ARE
        # scheduled recipes (SCHEDULED_ON edges), infer the period from the
        # single MealPeriod node in the filtered graph (one period per filtered graph).
        if not period_names and scheduled_ids:
            period_names = [getattr(p, "name", "") for p in graph.get_meal_periods()]

        # Build recipe name lists: main items first (sorted by name), then sides
        _cat_lookup = {rc["id"]: rc["category"] for rc in recipe_classifications}
        main_names  = sorted(
            getattr(graph.get_node(rid), "name", "") or rid
            for rid in scheduled_ids
            if _cat_lookup.get(rid, "side") != "side" and graph.get_node(rid)
        )
        side_names  = sorted(
            getattr(graph.get_node(rid), "name", "") or rid
            for rid in scheduled_ids
            if _cat_lookup.get(rid, "side") == "side" and graph.get_node(rid)
        )

        day_period_recipes.append({
            "day":     day_name,
            "periods": [
                {
                    "period":       pname,
                    "main_names":   main_names,
                    "side_names":   side_names,
                    "recipe_names": main_names + side_names,   # backwards compat
                    "total":        len(main_names) + len(side_names),
                    "main_count":   len(main_names),
                    "side_count":   len(side_names),
                }
                for pname in period_names
            ],
        })

    # Compliance checks
    if day_vegan < 1:
        under_offered.append("Missing vegan option")
    if day_fries < 1:
        under_offered.append("Missing fries option")
    if day_burger > _PLAYBOOK_PER_DAY["burger"]:
        over_offered.append(f"Too many burgers (got {day_burger}, max {_PLAYBOOK_PER_DAY['burger']})")
    if day_feature > _PLAYBOOK_PER_DAY["daily_feature"]:
        over_offered.append(f"Too many daily features (got {day_feature}, max {_PLAYBOOK_PER_DAY['daily_feature']})")

    compliant = (len(under_offered) == 0 and len(over_offered) == 0)

    summary_line = (
        f"burger={day_burger} (max {_PLAYBOOK_PER_DAY['burger']}), "
        f"daily_feature={day_feature} (max {_PLAYBOOK_PER_DAY['daily_feature']}), "
        f"vegan={day_vegan} (min {_PLAYBOOK_PER_DAY['vegan']}), "
        f"fries={day_fries} (min {_PLAYBOOK_PER_DAY['fries']})."
    )
    status_prefix = "Within playbook bounds. " if compliant else "PLAYBOOK VIOLATION. "
    message = (
        status_prefix
        + "Per-day vs playbook (same lineup each day; graph has no day-level recipe assignment). "
        + summary_line
    )

    return CheckingPlaybookBoundsOutput(
        compliant=compliant,
        under_offered=under_offered,
        over_offered=over_offered,
        counts=counts,
        playbook_limits={
            "burger":        {"limit": _PLAYBOOK_PER_DAY["burger"],        "rule": "max"},
            "daily_feature": {"limit": _PLAYBOOK_PER_DAY["daily_feature"], "rule": "max"},
            "vegan":         {"limit": _PLAYBOOK_PER_DAY["vegan"],         "rule": "min"},
            "fries":         {"limit": _PLAYBOOK_PER_DAY["fries"],         "rule": "min"},
        },
        message=message,
        per_day=per_day,
        day_recipe_counts=day_recipe_counts,
        day_period_recipes=day_period_recipes,
        recipe_classifications=recipe_classifications,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def checking_playbook_bounds(
    menu_graph: Any,
    meal_period: str,
    day_key: str,
) -> CheckingPlaybookBoundsOutput:
    """
    Compares meal period against playbook bounds (deterministic, keyword-based).

    Args:
        menu_graph  : MenuGraph object, raw-dict (normalized JSON), or file path string.
        meal_period : e.g. "Dinner", "Breakfast", "Lunch"
        day_key     : e.g. "Monday" or "all" (informational; used in logging).

    Returns:
        CheckingPlaybookBoundsOutput with compliant flag, violations, counts, per_day breakdown.
    """
    log.info(
        "[AGENT-TOOL] menu-structure: checking_playbook_bounds START  meal_period=%s  day_key=%s",
        meal_period,
        day_key,
    )
    graph = _ensure_menu_graph(menu_graph)
    out   = _check_playbook_bounds_deterministic(graph)
    log.info(
        "[AGENT-TOOL] menu-structure: checking_playbook_bounds DONE  compliant=%s",
        out.compliant,
    )
    return out
