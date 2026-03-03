"""
agent/data_integrity/period_overlap.py
=======================================
Detect duplicate / overlapping recipes within the same meal period.

Graph facts (from filtered JSON)
─────────────────────────────────
  SCHEDULED_ON      : Recipe → Day   (which recipe is on which day)
  SERVED_IN_PERIOD  : Recipe → MealPeriod (recipe ↔ period summary)
  HAS_PERIOD        : Day → MealPeriod   (WARNING: can be missing for some days)
  Node IDs          : raw IDs like "A5763", "day_Friday" (no prefix)

Two checks
──────────
1. within_period  — same recipe appears 2+ times in the same period on the
                    same day (recipe_id collision).  Severity: high.
2. cross_period   — same recipe is scheduled on a day that belongs to 2+
                    different periods (only relevant in an unfiltered graph).
                    Severity: medium.

Note: the *filtered* graph always has exactly one MealPeriod node, so
cross_period findings will be empty for filtered graphs.

Entry point:
    detecting_period_overlap(menu_graph)
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("menu_agent.data_integrity")


# ---------------------------------------------------------------------------
# Output dataclasses
# ---------------------------------------------------------------------------

@dataclass
class OverlapFinding:
    recipe_id:    str
    recipe_name:  str
    periods:      list[str]
    day:          str
    overlap_type: str   # "within_period" | "cross_period"
    severity:     str   # "high" | "medium"

    def to_dict(self) -> dict:
        return {
            "recipe_id":    self.recipe_id,
            "recipe_name":  self.recipe_name,
            "periods":      self.periods,
            "day":          self.day,
            "overlap_type": self.overlap_type,
            "severity":     self.severity,
        }


@dataclass
class DetectingPeriodOverlapOutput:
    overlaps:    list[OverlapFinding] = field(default_factory=list)
    total_count: int = 0
    message:     str = ""

    def to_overlap_json(self) -> dict:
        return {
            "compliant":   self.total_count == 0,
            "total_count": self.total_count,
            "message":     self.message,
            "overlaps":    [o.to_dict() for o in self.overlaps],
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


def _day_label(node: Any) -> str:
    """Human-readable day label from a Day node."""
    return (
        getattr(node, "day_name", "")
        or getattr(node, "name",     "")
        or node.id
    )


def _period_label(node: Any) -> str:
    """Human-readable period label from a MealPeriod node."""
    return getattr(node, "name", "") or node.id


def _recipes_scheduled_on_day(graph: Any, day_id: str) -> list[str]:
    """
    Return list of recipe node-IDs that are SCHEDULED_ON this day.
    Reads all Recipe → SCHEDULED_ON → Day edges coming *into* day_id.
    """
    return [
        e.source
        for e in graph.get_edges_to(day_id)
        if e.relationship == "SCHEDULED_ON"
    ]


def _periods_for_recipe(graph: Any, recipe_id: str) -> list[str]:
    """
    Return list of MealPeriod node-IDs the recipe is SERVED_IN_PERIOD.
    """
    period_ids: list[str] = []
    for e in graph.get_edges_from(recipe_id):
        if e.relationship == "SERVED_IN_PERIOD":
            period_ids.append(e.target)
    return period_ids


# ---------------------------------------------------------------------------
# Core deterministic logic
# ---------------------------------------------------------------------------

def _detect_period_overlap_deterministic(
    graph: Any,
) -> DetectingPeriodOverlapOutput:
    findings: list[OverlapFinding] = []

    days = sorted(
        graph.get_nodes_by_type("Day"),
        key=lambda n: (getattr(n, "week_no", 0), getattr(n, "day_no", 0)),
    )
    if not days:
        return DetectingPeriodOverlapOutput(message="No Day nodes found in graph.")

    # Get all known periods once (for cross-period check)
    all_periods = graph.get_meal_periods()
    period_labels = {p.id: _period_label(p) for p in all_periods}

    for day in days:
        dname = _day_label(day)

        # ── Recipes actually scheduled on this day via SCHEDULED_ON ──────────
        scheduled_ids = _recipes_scheduled_on_day(graph, day.id)
        if not scheduled_ids:
            continue

        # ── Check 1: within-period duplicates ────────────────────────────────
        # Determine which period(s) are active on this day
        period_nodes = graph.get_periods_for_day(day.id)

        # Fallback: if HAS_PERIOD edge is missing for this day
        # (a known data gap e.g. Friday in the Dinner-filtered graph),
        # derive the period from SERVED_IN_PERIOD edges of scheduled recipes.
        if not period_nodes:
            inferred_period_ids: set[str] = set()
            for rid in scheduled_ids:
                inferred_period_ids.update(_periods_for_recipe(graph, rid))
            if inferred_period_ids:
                period_nodes = [
                    p for p in all_periods if p.id in inferred_period_ids
                ]

        for p in period_nodes:
            plabel = _period_label(p)

            # Recipes that are BOTH scheduled on this day AND served in this period
            period_recipe_ids = {
                r.id for r in graph.get_recipes_for_period(p.id)
            }
            active = [rid for rid in scheduled_ids if rid in period_recipe_ids]

            counter = Counter(active)
            for rid, cnt in counter.items():
                if cnt < 2:
                    continue
                rnode = graph.get_node(rid)
                rname = (rnode.name if rnode else "") or rid
                findings.append(OverlapFinding(
                    recipe_id    = rid,
                    recipe_name  = rname,
                    periods      = [plabel],
                    day          = dname,
                    overlap_type = "within_period",
                    severity     = "high",
                ))

        # ── Check 2: cross-period overlaps ───────────────────────────────────
        # (Only meaningful in unfiltered/multi-period graphs)
        if len(all_periods) < 2:
            continue

        for rid in scheduled_ids:
            recipe_period_ids = _periods_for_recipe(graph, rid)
            if len(recipe_period_ids) <= 1:
                continue
            rnode  = graph.get_node(rid)
            rname  = (rnode.name if rnode else "") or rid
            plabels = [period_labels.get(pid, pid) for pid in recipe_period_ids]
            findings.append(OverlapFinding(
                recipe_id    = rid,
                recipe_name  = rname,
                periods      = plabels,
                day          = dname,
                overlap_type = "cross_period",
                severity     = "medium",
            ))

    # De-duplicate (same recipe + day combo can produce one finding per period)
    seen: set[tuple] = set()
    unique_findings: list[OverlapFinding] = []
    for f in findings:
        key = (f.recipe_id, f.day, f.overlap_type)
        if key not in seen:
            seen.add(key)
            unique_findings.append(f)

    total = len(unique_findings)
    if total == 0:
        msg = "No period overlaps detected. Data integrity: OK."
    else:
        within  = sum(1 for f in unique_findings if f.overlap_type == "within_period")
        cross   = sum(1 for f in unique_findings if f.overlap_type == "cross_period")
        parts   = []
        if within: parts.append(f"{within} within-period duplicate(s)")
        if cross:  parts.append(f"{cross} cross-period overlap(s)")
        msg = f"Found {total} overlap(s): {', '.join(parts)}. Review data."

    return DetectingPeriodOverlapOutput(
        overlaps    = unique_findings,
        total_count = total,
        message     = msg,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def detecting_period_overlap(menu_graph: Any) -> DetectingPeriodOverlapOutput:
    """
    Detect recipe duplicates / overlaps across meal periods.
    Graph traversal only — no LLM required.
    """
    log.info("[AGENT-TOOL] data-integrity: detecting_period_overlap START")
    graph = _ensure_menu_graph(menu_graph)
    out   = _detect_period_overlap_deterministic(graph)
    log.info(
        "[AGENT-TOOL] data-integrity: detecting_period_overlap DONE  "
        "total=%d  compliant=%s",
        out.total_count, out.total_count == 0,
    )
    return out
