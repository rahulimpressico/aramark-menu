"""
menu_agent_analyzer.py
======================
Grill station ke menu ka intelligent analysis agent.

Flow:
  knowledge_graph_normalized.json
       ↓  get_default_menu_graph()
  MenuGraph  →  filter_by_meal_period(meal_period)
       ↓  run_analysis_tools()  (deterministic, no LLM)
  AnalysisResult  →  call_llm()  (one LLM call for report)
       ↓
  {"content": <markdown report>, "usage": {...}}

Usage:
  python menu_agent_analyzer.py --station Grill --period Breakfast
  python menu_agent_analyzer.py --station Grill --period Dinner
  python menu_agent_analyzer.py --list-periods
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    format="%(asctime)s  %(levelname)-7s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
)
log = logging.getLogger("menu_agent")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT   = Path(__file__).resolve().parent
NORMALIZED_KG  = PROJECT_ROOT / "normalize_graph" / "output" / "knowledge_graph_normalized.json"

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class GraphMetadata:
    description: str = ""
    version:     str = "2.4-normalized"
    cycle:       str = ""


@dataclass
class Node:
    id:        str
    node_type: str
    # Common
    name:      str = ""
    # Recipe
    food_cost:              float  = 0.0
    assembly_instructions:  str    = ""
    special_instructions:   str    = ""
    # Day
    day_no:    int = 0
    day_name:  str = ""
    week_no:   int = 0
    # Ingredient / Equipment
    description:    str = ""
    equipment_type: str = ""

    @staticmethod
    def from_dict(d: dict) -> "Node":
        return Node(
            id                    = d["id"],
            node_type             = d["type"],
            name                  = d.get("name", ""),
            food_cost             = float(d["food_cost"]) if d.get("food_cost") else 0.0,
            assembly_instructions = d.get("assembly_instructions", ""),
            special_instructions  = d.get("special_instructions",  ""),
            day_no                = int(d["day_no"])   if d.get("day_no")   else 0,
            day_name              = d.get("day_name",  ""),
            week_no               = int(d["week_no"])  if d.get("week_no")  else 0,
            description           = d.get("description", ""),
            equipment_type        = d.get("equipment_type", ""),
        )

    @property
    def label(self) -> str:
        """Human-readable label for any node type."""
        return (
            self.name
            or self.day_name
            or self.description
            or self.id
        )


@dataclass
class Edge:
    source:       str
    target:       str
    relationship: str
    attributes:   dict = field(default_factory=dict)

    @staticmethod
    def from_dict(d: dict) -> "Edge":
        return Edge(
            source       = d["source"],
            target       = d["target"],
            relationship = d["relationship"],
            attributes   = d.get("attributes") or {},
        )


# ---------------------------------------------------------------------------
# MenuGraph — main graph container
# ---------------------------------------------------------------------------

class MenuGraph:
    def __init__(
        self,
        graph_metadata: GraphMetadata,
        nodes: list[Node],
        edges: list[Edge],
    ):
        self.graph_metadata = graph_metadata
        self.nodes  = nodes
        self.edges  = edges

        # Fast-lookup indexes
        self._by_id:   dict[str, Node]         = {n.id: n for n in nodes}
        self._by_type: dict[str, list[Node]]   = defaultdict(list)
        self._from:    dict[str, list[Edge]]   = defaultdict(list)
        self._to:      dict[str, list[Edge]]   = defaultdict(list)

        for n in nodes:
            self._by_type[n.node_type].append(n)
        for e in edges:
            self._from[e.source].append(e)
            self._to[e.target].append(e)

    # --- Node queries -------------------------------------------------------

    def get_node(self, node_id: str) -> Optional[Node]:
        return self._by_id.get(node_id)

    def get_nodes_by_type(self, node_type: str) -> list[Node]:
        return list(self._by_type.get(node_type, []))

    def get_meal_periods(self) -> list[Node]:
        return self.get_nodes_by_type("MealPeriod")

    def get_recipes(self) -> list[Node]:
        return self.get_nodes_by_type("Recipe")

    def get_ingredients(self) -> list[Node]:
        return self.get_nodes_by_type("Ingredient")

    def get_equipment(self) -> list[Node]:
        return self.get_nodes_by_type("Equipment")

    # --- Edge queries -------------------------------------------------------

    def get_edges_from(self, node_id: str) -> list[Edge]:
        return list(self._from.get(node_id, []))

    def get_edges_to(self, node_id: str) -> list[Edge]:
        return list(self._to.get(node_id, []))

    def get_edges_by_rel(self, relationship: str) -> list[Edge]:
        return [e for e in self.edges if e.relationship == relationship]

    # --- Domain queries -----------------------------------------------------

    def get_recipes_for_period(self, period_id: str) -> list[Node]:
        """All Recipe nodes that have SERVED_IN_PERIOD → period_id."""
        recipe_ids = {
            e.source for e in self.get_edges_to(period_id)
            if e.relationship == "SERVED_IN_PERIOD"
        }
        return [n for n in self.nodes if n.id in recipe_ids and n.node_type == "Recipe"]

    def get_ingredients_for_recipe(self, recipe_id: str) -> list[tuple[Node, dict]]:
        """Returns list of (Ingredient node, edge attributes)."""
        result = []
        for e in self.get_edges_from(recipe_id):
            if e.relationship == "HAS_INGREDIENT":
                ing = self.get_node(e.target)
                if ing:
                    result.append((ing, e.attributes))
        return result

    def get_equipment_for_recipe(self, recipe_id: str) -> list[Node]:
        return [
            self.get_node(e.target)
            for e in self.get_edges_from(recipe_id)
            if e.relationship == "USES_EQUIPMENT" and self.get_node(e.target)
        ]

    def get_scheduled_days(self, recipe_id: str) -> list[tuple[Node, str]]:
        """Returns list of (Day node, period) for a recipe."""
        result = []
        for e in self.get_edges_from(recipe_id):
            if e.relationship == "SCHEDULED_ON":
                day = self.get_node(e.target)
                if day:
                    result.append((day, e.attributes.get("period", "")))
        return sorted(result, key=lambda x: x[0].day_no)

    def get_days_for_station(self) -> list[Node]:
        """All Day nodes in this graph (single station assumed)."""
        return sorted(self.get_nodes_by_type("Day"), key=lambda n: (n.week_no, n.day_no))

    def get_periods_for_day(self, day_id: str) -> list[Node]:
        """All MealPeriod nodes connected to a Day via HAS_PERIOD."""
        period_ids = {
            e.target for e in self.get_edges_from(day_id)
            if e.relationship == "HAS_PERIOD"
        }
        return [n for n in self.nodes if n.id in period_ids and n.node_type == "MealPeriod"]

    # --- Filter -------------------------------------------------------------

    def filter_by_meal_period(self, period_name: str) -> "MenuGraph":
        """
        Return a new graph containing only nodes/edges for the given meal period.
        Station, Days, that MealPeriod, Recipes served in it, their Ingredients + Equipment.
        Matching is case-insensitive.
        """
        period_name_lower = period_name.strip().lower()
        period_node = next(
            (n for n in self.get_meal_periods()
             if (n.name or "").strip().lower() == period_name_lower),
            None,
        )
        if not period_node:
            log.warning("Meal period %r not found; returning empty graph", period_name)
            return MenuGraph(
                graph_metadata=GraphMetadata(
                    description=f"Filtered for {period_name} (not found)"
                ),
                nodes=[],
                edges=[],
            )

        keep_ids: set[str] = set()

        for n in self.get_nodes_by_type("Station"):
            keep_ids.add(n.id)
        for n in self.get_nodes_by_type("Week"):
            keep_ids.add(n.id)

        keep_ids.add(period_node.id)

        recipe_ids_set = {r.id for r in self.get_recipes_for_period(period_node.id)}
        keep_ids.update(recipe_ids_set)

        # Ingredients + Equipment add karo — dusre MealPeriod nodes skip karo
        for rid in recipe_ids_set:
            for e in self.get_edges_from(rid):
                target_node = self.get_node(e.target)
                if target_node and target_node.node_type == "MealPeriod":
                    continue   # sirf filtered period hi keep_ids mein hai
                # SCHEDULED_ON edges: sirf woh days rakho jahan recipe IS period mein hai
                # "All Day" period = har meal period mein include hota hai
                if e.relationship == "SCHEDULED_ON":
                    edge_period = (e.attributes.get("period") or "").strip()
                    if edge_period and edge_period.lower() not in (
                        period_name_lower, "all day",
                    ):
                        continue   # yeh edge dusre period ka hai — skip
                keep_ids.add(e.target)

        # Only keep Day nodes that were added via SCHEDULED_ON (correct period)
        # Remove any Day that has no recipe scheduled on it for this period
        day_ids_with_recipes: set[str] = set()
        for rid in recipe_ids_set:
            for e in self.get_edges_from(rid):
                if e.relationship == "SCHEDULED_ON" and e.target in keep_ids:
                    day_ids_with_recipes.add(e.target)

        # Keep only days that actually have recipes for this period
        for n in self.get_nodes_by_type("Day"):
            if n.id in day_ids_with_recipes:
                keep_ids.add(n.id)

        # Edge filter — SCHEDULED_ON edges: only those in keep_ids AND correct period
        def _keep_edge(e: "Edge") -> bool:
            if e.source not in keep_ids or e.target not in keep_ids:
                return False
            if e.relationship == "SCHEDULED_ON":
                ep = (e.attributes.get("period") or "").strip().lower()
                if ep and ep not in (period_name_lower, "all day"):
                    return False
            return True

        new_edges = [e for e in self.edges if _keep_edge(e)]
        new_nodes = [n for n in self.nodes if n.id in keep_ids]

        meta = GraphMetadata(
            description=(
                f"{self.graph_metadata.description}; "
                f"filtered for meal period: {period_name}"
            ),
            version=self.graph_metadata.version,
            cycle=self.graph_metadata.cycle,
        )
        log.info(
            "[AGENT] filter_by_meal_period  period=%s  recipes=%d → nodes=%d edges=%d",
            period_name, len(recipe_ids_set), len(new_nodes), len(new_edges),
        )
        return MenuGraph(graph_metadata=meta, nodes=new_nodes, edges=new_edges)

    # --- Summary ------------------------------------------------------------

    def summary(self) -> dict:
        return {
            t: len(v) for t, v in self._by_type.items()
        }


# ---------------------------------------------------------------------------
# Graph loader
# ---------------------------------------------------------------------------

def get_default_menu_graph(path: Path = NORMALIZED_KG) -> MenuGraph:
    if not path.exists():
        raise FileNotFoundError(
            f"Normalized graph not found: {path}\n"
            "Pehle run karo:  python normalize_graph/extract_graph_v2.py"
        )
    raw = json.loads(path.read_text(encoding="utf-8"))
    meta_raw = raw.get("graph_metadata", {})
    meta = GraphMetadata(
        description=meta_raw.get("description", ""),
        version=meta_raw.get("version", ""),
        cycle=meta_raw.get("cycle", ""),
    )
    nodes = [Node.from_dict(n) for n in raw.get("nodes", [])]
    edges = [Edge.from_dict(e) for e in raw.get("edges", [])]
    log.info("[GRAPH] Loaded %d nodes, %d edges from %s", len(nodes), len(edges), path.name)
    return MenuGraph(graph_metadata=meta, nodes=nodes, edges=edges)


# ---------------------------------------------------------------------------
# Analysis tools  (deterministic — no LLM)
# ---------------------------------------------------------------------------

def run_analysis_tools(station_name: str, meal_period: str, filtered: MenuGraph) -> dict:
    """
    Run all deterministic analysis on the filtered graph.
    Returns a structured dict ready for the LLM report generator.
    """
    recipes = filtered.get_recipes_for_period(
        next((n.id for n in filtered.get_meal_periods()), "")
    )
    if not recipes:
        # fallback: just use all recipes in filtered graph
        recipes = filtered.get_recipes()

    # ---- Food cost stats ---------------------------------------------------
    costs = [r.food_cost for r in recipes if r.food_cost > 0]
    cost_stats = {}
    if costs:
        cost_stats = {
            "min":    round(min(costs),  4),
            "max":    round(max(costs),  4),
            "mean":   round(statistics.mean(costs), 4),
            "median": round(statistics.median(costs), 4),
            "total":  round(sum(costs),  4),
        }

    # ---- Top / bottom cost recipes -----------------------------------------
    sorted_recipes = sorted(recipes, key=lambda r: r.food_cost, reverse=True)
    top_expensive = [
        {"id": r.id, "name": r.label, "food_cost": r.food_cost}
        for r in sorted_recipes[:5]
    ]
    top_affordable = [
        {"id": r.id, "name": r.label, "food_cost": r.food_cost}
        for r in sorted_recipes[-5:][::-1]
    ]

    # ---- Ingredient analysis -----------------------------------------------
    all_ingredients: list[str] = []
    recipe_ing_counts: list[tuple[str, int]] = []

    for r in recipes:
        ings = filtered.get_ingredients_for_recipe(r.id)
        all_ingredients.extend(i.name or i.description for i, _ in ings)
        recipe_ing_counts.append((r.label, len(ings)))

    ing_freq   = Counter(all_ingredients)
    top_ings   = [{"name": n, "count": c} for n, c in ing_freq.most_common(10)]
    unique_ings = len(ing_freq)

    # Per-recipe ingredient count stats
    if recipe_ing_counts:
        ing_counts_only = [c for _, c in recipe_ing_counts]
        ing_count_stats = {
            "min":    min(ing_counts_only),
            "max":    max(ing_counts_only),
            "mean":   round(statistics.mean(ing_counts_only), 1),
        }
    else:
        ing_count_stats = {}

    # Recipes with most ingredients
    most_ings = sorted(recipe_ing_counts, key=lambda x: x[1], reverse=True)[:5]

    # ---- Equipment ----------------------------------------------------------
    all_equip: set[str] = set()
    equip_by_recipe: dict[str, list[str]] = {}
    for r in recipes:
        eq = [e.name or e.equipment_type for e in filtered.get_equipment_for_recipe(r.id)]
        if eq:
            equip_by_recipe[r.label] = eq
            all_equip.update(eq)

    # ---- Schedule summary --------------------------------------------------
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    schedule: dict[str, list[str]] = defaultdict(list)
    for r in recipes:
        for day, period in filtered.get_scheduled_days(r.id):
            if period.lower() == meal_period.lower():
                schedule[day.day_name].append(r.label)

    schedule_sorted = {
        d: sorted(schedule[d]) for d in day_order if d in schedule
    }

    return {
        "station_name":    station_name,
        "meal_period":     meal_period,
        "recipe_count":    len(recipes),
        "cost_stats":      cost_stats,
        "top_expensive":   top_expensive,
        "top_affordable":  top_affordable,
        "unique_ingredients": unique_ings,
        "top_ingredients": top_ings,
        "ing_count_stats": ing_count_stats,
        "most_ingredients_recipes": [{"name": n, "count": c} for n, c in most_ings],
        "equipment":       sorted(all_equip),
        "equipment_by_recipe": equip_by_recipe,
        "schedule":        schedule_sorted,
        "all_recipes":     [
            {
                "id":         r.id,
                "name":       r.label,
                "food_cost":  r.food_cost,
                "ing_count":  len(filtered.get_ingredients_for_recipe(r.id)),
                "equipment":  [e.name for e in filtered.get_equipment_for_recipe(r.id)],
            }
            for r in sorted_recipes
        ],
    }


# ---------------------------------------------------------------------------
# LLM runner  (stub — replace with OpenAI / Groq call)
# ---------------------------------------------------------------------------

def call_llm(prompt: str) -> dict:
    """
    Stub: replace this body with a real LLM API call.

    Example (OpenAI):
        import openai
        resp = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        return {
            "content": resp.choices[0].message.content,
            "usage":   resp.usage.model_dump(),
        }

    Example (Groq):
        from groq import Groq
        client = Groq()
        resp = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
        )
        return {
            "content": resp.choices[0].message.content,
            "usage":   resp.usage.model_dump(),
        }
    """
    log.info("[LLM] call_llm called (stub) — prompt length: %d chars", len(prompt))
    return {
        "content": _stub_report_from_prompt(prompt),
        "usage":   {"model": "stub", "prompt_tokens": len(prompt) // 4, "completion_tokens": 0},
    }


def _stub_report_from_prompt(prompt: str) -> str:
    """Extracts the pre-built markdown from the prompt when LLM is not available."""
    marker = "--- ANALYSIS DATA ---"
    if marker in prompt:
        return prompt.split(marker, 1)[1].strip()
    return prompt


# ---------------------------------------------------------------------------
# Report builder  (builds LLM prompt + fallback report)
# ---------------------------------------------------------------------------

def build_report_prompt(analysis: dict) -> str:
    a = analysis
    station     = a["station_name"]
    period      = a["meal_period"]
    cs          = a["cost_stats"]
    ts          = a.get("ing_count_stats", {})

    md_lines = [
        f"# {station} Station — {period} Menu Analysis",
        f"*Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*",
        "",
        "---",
        "",
        "## Overview",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total recipes | **{a['recipe_count']}** |",
        f"| Unique ingredients | **{a['unique_ingredients']}** |",
        f"| Equipment needed | **{len(a['equipment'])}** types |",
    ]
    if cs:
        md_lines += [
            f"| Avg food cost | **${cs['mean']:.4f}** |",
            f"| Min food cost | ${cs['min']:.4f} |",
            f"| Max food cost | ${cs['max']:.4f} |",
            f"| Median food cost | ${cs['median']:.4f} |",
        ]
    if ts:
        md_lines += [
            f"| Avg ingredients / recipe | {ts['mean']} |",
            f"| Min ingredients / recipe | {ts['min']} |",
            f"| Max ingredients / recipe | {ts['max']} |",
        ]

    md_lines += ["", "---", "", "## All Recipes (by food cost)"]
    md_lines.append("| # | Recipe | Cost | Ingredients |")
    md_lines.append("|---|--------|------|-------------|")
    for i, r in enumerate(a["all_recipes"], 1):
        eq_tag = f" ⚙ {', '.join(r['equipment'])}" if r["equipment"] else ""
        md_lines.append(
            f"| {i} | {r['name']} `{r['id']}` | ${r['food_cost']:.4f} | {r['ing_count']}{eq_tag} |"
        )

    md_lines += ["", "---", "", "## Cost Insights"]
    if a["top_expensive"]:
        md_lines += ["", "**Top 5 most expensive recipes:**"]
        for r in a["top_expensive"]:
            md_lines.append(f"- `{r['id']}` **{r['name']}** — ${r['food_cost']:.4f}")
    if a["top_affordable"]:
        md_lines += ["", "**Top 5 most affordable recipes:**"]
        for r in a["top_affordable"]:
            md_lines.append(f"- `{r['id']}` **{r['name']}** — ${r['food_cost']:.4f}")

    md_lines += ["", "---", "", "## Top 10 Most-Used Ingredients"]
    md_lines.append("| Ingredient | Used in N recipes |")
    md_lines.append("|------------|-------------------|")
    for ing in a["top_ingredients"]:
        md_lines.append(f"| {ing['name']} | {ing['count']} |")

    md_lines += ["", "---", "", "## Recipes with Most Ingredients"]
    for r in a["most_ingredients_recipes"]:
        md_lines.append(f"- **{r['name']}** — {r['count']} ingredients")

    if a["equipment"]:
        md_lines += ["", "---", "", "## Equipment Required"]
        for eq in a["equipment"]:
            recipes_using = [
                name for name, eqs in a["equipment_by_recipe"].items() if eq in eqs
            ]
            md_lines.append(f"- **{eq}** → {len(recipes_using)} recipe(s): {', '.join(recipes_using[:4])}")

    if a["schedule"]:
        md_lines += ["", "---", "", f"## Weekly Schedule — {period}"]
        for day, recipes_list in a["schedule"].items():
            md_lines.append(f"\n**{day}** ({len(recipes_list)} recipes)")
            for rname in recipes_list:
                md_lines.append(f"  - {rname}")

    report = "\n".join(md_lines)

    prompt = (
        f"You are a food service analyst. Below is structured data for {station} station "
        f"during {period}. Using only the data provided, write a concise, insightful "
        f"professional analysis report in Markdown. Highlight cost patterns, operational "
        f"complexity, ingredient reuse, and any notable observations.\n\n"
        f"--- ANALYSIS DATA ---\n{report}"
    )
    return prompt


# ---------------------------------------------------------------------------
# Usage tracking (lightweight stub)
# ---------------------------------------------------------------------------

_usage_log: list[dict] = []

def clear_usage():
    _usage_log.clear()

def get_usage_summary() -> dict:
    total_prompt = sum(u.get("prompt_tokens", 0)     for u in _usage_log)
    total_compl  = sum(u.get("completion_tokens", 0) for u in _usage_log)
    return {
        "calls":             len(_usage_log),
        "total_prompt_tokens":     total_prompt,
        "total_completion_tokens": total_compl,
        "calls_detail":      list(_usage_log),
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_analysis_fast(station_name: str, meal_period: str) -> dict:
    """
    Fast path: run all analysis with deterministic tools (no orchestrator),
    then one LLM call for the report.
    Returns dict with "content" (report markdown) and "usage".
    Typically completes in 1-2 seconds (stub) or 5-15s (real LLM).
    """
    log.info("[AGENT] run_analysis_fast START  station=%s  period=%s", station_name, meal_period)

    clear_usage()

    # Step 1 — Load graph
    graph = get_default_menu_graph()

    # Step 2 — Filter by meal period
    filtered = graph.filter_by_meal_period(meal_period)

    if not filtered.get_recipes():
        log.warning("[AGENT] No recipes found for period=%s", meal_period)
        return {
            "content": f"# No data found\nNo recipes found for station **{station_name}** / period **{meal_period}**.",
            "usage":   get_usage_summary(),
        }

    # Step 3 — Run deterministic analysis tools
    log.info("[AGENT] Running analysis tools...")
    analysis = run_analysis_tools(station_name, meal_period, filtered)

    # Step 3b — Playbook compliance check
    from agent.menu_structure.playbook_check import checking_playbook_bounds
    playbook_result = checking_playbook_bounds(filtered, meal_period, "all")

    # Step 3c — Data integrity: period overlap check
    from agent.data_integrity.period_overlap import detecting_period_overlap
    overlap_result = detecting_period_overlap(filtered)

    # Step 3d — Rotation & Recurrence: diversity index
    from agent.rotation_recurrence.diversity_index import calculating_diversity_index
    diversity_result = calculating_diversity_index(filtered)

    # Step 3e — Rotation & Recurrence: item frequency
    from agent.rotation_recurrence.item_frequency import tracking_item_frequency
    frequency_result = tracking_item_frequency(filtered)

    # Step 3f — Nutrition & Cost: sustainability mix
    from agent.nutrition_cost.sustainability_mix import evaluating_sustainability_mix
    sustainability_result = evaluating_sustainability_mix(filtered)

    # Step 3g — Nutrition & Cost: CPM risk swaps
    from agent.nutrition_cost.cpm_risk_swaps import calculating_cpm_risk_swaps
    cpm_result = calculating_cpm_risk_swaps(
        filtered,
        recurrence_signals=frequency_result.to_frequency_json(),
    )

    output_json = {
        "playbook_check":      playbook_result.to_playbook_json(meal_period),
        "data_integrity":      overlap_result.to_overlap_json(),
        "rotation_recurrence": {
            "diversity_index":  diversity_result.to_diversity_json(),
            "item_frequency":   frequency_result.to_frequency_json(),
        },
        "nutrition_cost": {
            "sustainability_mix": sustainability_result.to_sustainability_json(),
            "cpm_risk_swaps":     cpm_result.to_cpm_json(),
        },
    }

    # Step 3h — Synthesizer: format into executive markdown slide
    from agent.synthesizer.executive_slide import formatting_executive_slide
    slide = formatting_executive_slide(output_json)

    print(json.dumps(output_json, indent=2, ensure_ascii=False))
    print("\n" + "=" * 70)
    print(slide)
    print("=" * 70)

    log.info("[AGENT] run_analysis_fast DONE")
    return {
        "content":       slide,          # Gemini markdown report
        "analysis_json": output_json,    # full deterministic JSON for API consumers
        "usage":         get_usage_summary(),
        "analysis":      analysis,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli_list_periods():
    graph = get_default_menu_graph()
    periods = [n.name for n in graph.get_meal_periods()]
    print("Available meal periods:")
    for p in sorted(periods):
        recipes = graph.get_recipes_for_period(
            next(n.id for n in graph.get_meal_periods() if n.name == p)
        )
        print(f"  • {p}  ({len(recipes)} recipes)")


# ---------------------------------------------------------------------------
# Filtered graph → JSON dump
# ---------------------------------------------------------------------------

def dump_filtered_graph(meal_period: str, output_path: Optional[Path] = None) -> Path:
    """
    knowledge_graph_normalized.json load karo, meal_period se filter karo,
    aur ek single JSON file save karo.

    Args:
        meal_period : e.g. "Breakfast", "Lunch", "Dinner", "Brunch", "All Day"
        output_path : optional custom path; default → filtered_<Period>.json

    Returns:
        Path to the saved JSON file.
    """
    graph    = get_default_menu_graph()
    filtered = graph.filter_by_meal_period(meal_period)

    if not filtered.nodes:
        log.warning("[DUMP] No data for period=%s", meal_period)

    # Build clean output dict
    # Nodes grouped by type for readability
    nodes_by_type: dict[str, list[dict]] = defaultdict(list)
    for n in filtered.nodes:
        d: dict = {"id": n.id, "type": n.node_type}
        if n.name:                   d["name"]                   = n.name
        if n.food_cost:              d["food_cost"]              = n.food_cost
        if n.assembly_instructions:  d["assembly_instructions"]  = n.assembly_instructions
        if n.special_instructions:   d["special_instructions"]   = n.special_instructions
        if n.day_name:               d["day_name"]               = n.day_name
        if n.day_no:                 d["day_no"]                 = n.day_no
        if n.week_no:                d["week_no"]                = n.week_no
        if n.description:            d["description"]            = n.description
        if n.equipment_type:         d["equipment_type"]         = n.equipment_type
        nodes_by_type[n.node_type].append(d)

    edges_out = []
    for e in filtered.edges:
        ed: dict = {
            "source":       e.source,
            "target":       e.target,
            "relationship": e.relationship,
        }
        if e.attributes:
            ed["attributes"] = e.attributes
        edges_out.append(ed)

    output = {
        "meal_period": meal_period,
        "summary": {t: len(v) for t, v in nodes_by_type.items()},
        "nodes":   nodes_by_type,
        "edges":   edges_out,
    }

    # Default path
    if output_path is None:
        safe_name = re.sub(r"[^A-Za-z0-9]+", "_", meal_period.strip())
        output_path = PROJECT_ROOT / "normalize_graph" / "output" / f"filtered_{safe_name}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("[DUMP] Saved filtered graph → %s", output_path)
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Menu Agent Analyzer")
    parser.add_argument("--station", "-s", default="Grill",
                        help="Station name (default: Grill)")
    parser.add_argument("--period",  "-p", default=None,
                        help="Meal period (Breakfast / Lunch / Dinner / Brunch / All Day)")
    parser.add_argument("--list-periods", action="store_true",
                        help="List available meal periods and exit")
    parser.add_argument("--dump-json", action="store_true",
                        help="Sirf filtered graph JSON save karo (no report)")
    parser.add_argument("--output", "-o", type=Path, default=None,
                        help="Save report/json to this file (optional)")
    args = parser.parse_args()

    if args.list_periods:
        _cli_list_periods()
        return

    if not args.period:
        print("Error: --period is required. Use --list-periods to see options.")
        sys.exit(1)

    # --dump-json mode: sirf filtered JSON output
    if args.dump_json:
        out_path = dump_filtered_graph(args.period, args.output)
        print(f"Saved → {out_path}")
        return

    # Full analysis + playbook JSON
    run_analysis_fast(args.station, args.period)


if __name__ == "__main__":
    main()
