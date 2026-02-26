"""
Stub implementations for all agent skills (first draft: LLM-based).
Inputs and outputs are strongly typed via experiments.tools.schemas so stubs can be
replaced by programmable logic when the PoC becomes the project.
Use MenuGraph as the parameter type where the tool operates on menu data.
"""
from __future__ import annotations

import json
from typing import Any

from experiments.log_config import log
from experiments.models.menu_graph import MenuGraph
from experiments.prompts import get_playbook_content
from experiments.tools.llm_runner import run_structured
from experiments.tools.schemas import (
    AggregatingGlobalStateInput,
    AggregatingGlobalStateOutput,
    CalculatingCpmRiskSwapsInput,
    CalculatingCpmRiskSwapsOutput,
    CalculatingDiversityIndexOutput,
    CheckingPlaybookBoundsInput,
    CheckingPlaybookBoundsOutput,
    DetectingPeriodOverlapOutput,
    EvaluatingSustainabilityMixOutput,
    FormattingExecutiveSlideOutput,
    RoutingTasksInput,
    RoutingTasksOutput,
    TrackingItemFrequencyInput,
    TrackingItemFrequencyOutput,
    TransformingMenuGraphInput,
    TransformingMenuGraphOutput,
)


def _extract_json_from_string(raw: str) -> dict[str, Any]:
    """Extract and parse menu graph JSON from string. Handles LLM-wrapped or truncated output."""
    s = raw.strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    for marker in ("```json", "```"):
        start = s.find(marker)
        if start != -1:
            start = s.find("\n", start) + 1
            if start == 0:
                start = len(marker)
            end = s.find("```", start)
            if end != -1:
                candidate = s[start:end].strip()
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    pass
    first = s.find("{")
    last = s.rfind("}")
    if first != -1 and last != -1 and last > first:
        try:
            return json.loads(s[first : last + 1])
        except json.JSONDecodeError:
            pass
    raise ValueError("Could not extract valid JSON from menu_graph string")


def _ensure_menu_graph(menu_graph: MenuGraph | dict[str, Any] | str) -> MenuGraph:
    """Coerce dict or JSON string to MenuGraph. Tolerates LLM-wrapped or truncated JSON."""
    if isinstance(menu_graph, MenuGraph):
        log.debug("menu_graph already MenuGraph instance")
        return menu_graph
    if isinstance(menu_graph, str):
        log.debug("Parsing menu_graph from string (len={})", len(menu_graph))
        data = _extract_json_from_string(menu_graph)
        return MenuGraph.model_validate(data)
    log.debug("Validating menu_graph from dict")
    return MenuGraph.model_validate(menu_graph)


def _graph_context(graph: MenuGraph, max_chars: int = 50000) -> str:
    """Serialize menu graph for LLM context (truncate if very large)."""
    raw = json.dumps(graph.model_dump(), indent=0)
    if len(raw) > max_chars:
        original_len = len(raw)
        raw = raw[:max_chars] + "\n... (truncated)"
        log.warning("Graph context truncated to {} characters (original: {})", max_chars, original_len)
    return raw


def _context_with_playbook(context: str, max_playbook_chars: int = 8000) -> str:
    """Prepend organization playbook to context so analysis is done against compliance."""
    playbook = get_playbook_content()
    if not playbook:
        return context
    if len(playbook) > max_playbook_chars:
        playbook = playbook[:max_playbook_chars] + "\n... (playbook truncated)"
    return f"## Organization Playbook (compliance reference)\n{playbook}\n\n---\n\n## Input / Menu data\n{context}"


# --- Orchestrator ---

def routing_tasks(
    payload: dict[str, Any],
    target_agent: str,
) -> RoutingTasksOutput:
    """Dispatches specific analytical payloads to specialized sub-agents. Use when delegating analysis to the Structure, Integrity, Rotation, or Cost agents."""
    log.info("[AGENT-TOOL] routing_tasks → delegating to subagent target_agent={} payload_keys={}", target_agent, list(payload.keys()) if isinstance(payload, dict) else "n/a")
    inp = RoutingTasksInput(payload=payload, target_agent=target_agent)
    context = _context_with_playbook(json.dumps(inp.model_dump(), indent=2))
    out = run_structured(
        task_description="You are routing a task to a sub-agent. Confirm the delegation in a professional manner: set success=True and provide a short task_id or confirmation message suitable for audit or logging.",
        context=context,
        output_model=RoutingTasksOutput,
    )
    log.info("[AGENT-TOOL] routing_tasks done success={}", out.success)
    return out


def aggregating_global_state(sub_agent_outputs: list[dict[str, Any]]) -> AggregatingGlobalStateOutput:
    """Collects the JSON outputs from all completed sub-agent tasks into a single object. Use when all sub-agents have successfully completed their delegated tasks."""
    keys_preview = [list(o.keys())[:5] if isinstance(o, dict) else type(o).__name__ for o in sub_agent_outputs[:5]] if sub_agent_outputs else []
    log.info("[AGENT-TOOL] aggregating_global_state ← merging n_outputs={} source_keys={}", len(sub_agent_outputs), keys_preview)
    inp = AggregatingGlobalStateInput(sub_agent_outputs=sub_agent_outputs)
    context = _context_with_playbook(json.dumps(inp.model_dump(), indent=2))
    return run_structured(
        task_description="Merge the list of sub-agent outputs into one aggregated structure suitable for the final report. List which analysis sources (agent names) contributed to each section, for traceability.",
        context=context,
        output_model=AggregatingGlobalStateOutput,
    )


# --- Menu Structure ---

def transforming_menu_graph(raw_menu_data: str) -> TransformingMenuGraphOutput:
    """Parses raw CSV or PDF menu data spanning weeks, days, and meal periods into a standardized JSON schema. Use when standardizing raw unstructured menu data."""
    log.info("[AGENT-TOOL] menu-structure: transforming_menu_graph START input_len={}", len(raw_menu_data))
    inp = TransformingMenuGraphInput(raw_menu_data=raw_menu_data)
    raw_context = inp.raw_menu_data[:15000] if len(inp.raw_menu_data) > 15000 else inp.raw_menu_data
    context = _context_with_playbook(raw_context)
    out = run_structured(
        task_description="Transform the raw menu text into a standardized menu graph JSON. Schema: station_name, menu_cycle, service_area, start_date, end_date, schedule (list of {day, date, meal_periods: {period_name: [{recipe_id, recipe_name, assembly_instructions, special_instructions, ingredient_description}]}}). If input is too vague or empty, set success=False and put an error message in error.",
        context=context,
        output_model=TransformingMenuGraphOutput,
    )
    log.info("[AGENT-TOOL] menu-structure: transforming_menu_graph DONE success={}", out.success)
    return out


def checking_playbook_bounds(
    menu_graph: MenuGraph | dict[str, Any] | str,
    meal_period: str,
    day_key: str,
) -> CheckingPlaybookBoundsOutput:
    """Compares a specific meal period against playbook maximum selections to identify under-offering or over-offering. Use when validating if a station meets core structural requirements."""
    log.info("[AGENT-TOOL] menu-structure: checking_playbook_bounds START meal_period={} day_key={}", meal_period, day_key)
    graph = _ensure_menu_graph(menu_graph)
    inp = CheckingPlaybookBoundsInput(meal_period=meal_period, day_key=day_key)
    context = _context_with_playbook(f"meal_period={meal_period}, day_key={day_key}\n\nMenu graph (excerpt):\n{_graph_context(graph)}")
    out = run_structured(
        task_description="Using the Organization Playbook (Station Guide: Fresh & Fast Grill), evaluate the menu against Recommended Maximum Selections: 1 Burger, 2 Daily Features, 1 Vegan Option, French Fry. Compare the given meal period to these bounds. Flag under_offered (e.g. missing vegan option) and over_offered (exceeding playbook maximum). Set compliant True only when within bounds. Report actual counts inferred from the menu data for use in the formal report.",
        context=context,
        output_model=CheckingPlaybookBoundsOutput,
    )
    log.info("[AGENT-TOOL] menu-structure: checking_playbook_bounds DONE compliant={}", out.compliant)
    return out


# --- Data Integrity ---

def detecting_period_overlap(menu_graph: MenuGraph | dict[str, Any] | str) -> DetectingPeriodOverlapOutput:
    """Scans the menu graph for identical recipe IDs scheduled in overlapping meal periods on the same day. Use when checking for forecasting and Pre-costing risks."""
    log.info("[AGENT-TOOL] data-integrity: detecting_period_overlap START")
    graph = _ensure_menu_graph(menu_graph)
    context = _context_with_playbook(_graph_context(graph))
    out = run_structured(
        task_description="Scan the menu graph for data integrity: for each day, identify recipe_id(s) that appear in more than one overlapping meal period (e.g. same recipe in Lunch and Dinner, or All-Day and Lunch). For each finding document recipe_id, recipe_name, affected periods, day, and severity (use high for duplicates that affect forecasting). Return an overlaps list and total_count suitable for inclusion in a compliance report.",
        context=context,
        output_model=DetectingPeriodOverlapOutput,
    )
    log.info("[AGENT-TOOL] data-integrity: detecting_period_overlap DONE total_count={}", out.total_count)
    return out


# --- Rotation & Recurrence ---

def calculating_diversity_index(menu_graph: MenuGraph | dict[str, Any] | str) -> CalculatingDiversityIndexOutput:
    """Computes a score based on the volume of unique feature items versus static daily items across a cycle. Use when evaluating a station for monotony or menu fatigue."""
    log.info("[AGENT-TOOL] rotation-recurrence: calculating_diversity_index START")
    graph = _ensure_menu_graph(menu_graph)
    context = _context_with_playbook(_graph_context(graph))
    out = run_structured(
        task_description="Using the playbook Core Offerings and Enhancements (e.g. Daily Feature rotation), compute the Grill Structural Diversity Index: the ratio of unique entrées to repeated static items. Output diversity_index (0-1), unique_entree_count, repeated_static_count, and a concise message suitable for the rotation and variety section of the final report.",
        context=context,
        output_model=CalculatingDiversityIndexOutput,
    )
    log.info("[AGENT-TOOL] rotation-recurrence: calculating_diversity_index DONE diversity_index={}", out.diversity_index)
    return out


def tracking_item_frequency(
    menu_graph: MenuGraph | dict[str, Any] | str,
    recipe_ids: list[str] | None = None,
) -> TrackingItemFrequencyOutput:
    """Analyzes the exact appearance count of specific recipe IDs across the week. Use when extracting recurrence patterns for key proteins."""
    log.info("[AGENT-TOOL] rotation-recurrence: tracking_item_frequency START recipe_ids={}", recipe_ids)
    graph = _ensure_menu_graph(menu_graph)
    inp = TrackingItemFrequencyInput(recipe_ids=recipe_ids)
    context = _context_with_playbook(f"recipe_ids filter: {inp.recipe_ids}\n\nMenu graph:\n{_graph_context(graph)}")
    out = run_structured(
        task_description="Using the playbook rotation and enhancements guidance, count how many times each recipe (or key protein/entrée if recipe_ids not specified) appears across the cycle. Fill frequencies with recipe_id, recipe_name, appearance_count, and days. Add recurrence_signals with evidence-based wording (e.g. High repetition of hamburger across lunch periods) for use in the nutrition-cost analysis and final report.",
        context=context,
        output_model=TrackingItemFrequencyOutput,
    )
    log.info("[AGENT-TOOL] rotation-recurrence: tracking_item_frequency DONE frequencies_count={}", len(out.frequencies))
    return out


# --- Nutrition & Cost ---

def evaluating_sustainability_mix(menu_graph: MenuGraph | dict[str, Any] | str) -> EvaluatingSustainabilityMixOutput:
    """Calculates the percentage of plant-based and vegan recipes programmed into the core menu template. Use when checking compliance with the 44 percent plant-based mandate."""
    log.info("[AGENT-TOOL] nutrition-cost: evaluating_sustainability_mix START")
    graph = _ensure_menu_graph(menu_graph)
    context = _context_with_playbook(_graph_context(graph))
    out = run_structured(
        task_description="Using the playbook Plant-Forward Goal (by 2025, 44% of core menu template offerings must be plant-based), compute plant_based_percent and vegan_percent for the menu. Set compliant_44=(plant_based_percent>=44), report total_offerings and plant_based_count, and provide a short message suitable for the sustainability section of the formal report.",
        context=context,
        output_model=EvaluatingSustainabilityMixOutput,
    )
    log.info("[AGENT-TOOL] nutrition-cost: evaluating_sustainability_mix DONE plant_based_percent={} compliant_44={}", out.plant_based_percent, out.compliant_44)
    return out


def calculating_cpm_risk_swaps(
    menu_graph: MenuGraph | dict[str, Any] | str,
    recurrence_signals: dict[str, Any] | None = None,
) -> CalculatingCpmRiskSwapsOutput:
    """Identifies high-cost beef recurrence and checks if poultry or plant-based alternatives have been diversified. Use when evaluating cost-saving protein strategies."""
    log.info("[AGENT-TOOL] nutrition-cost: calculating_cpm_risk_swaps START")
    graph = _ensure_menu_graph(menu_graph)
    inp = CalculatingCpmRiskSwapsInput(recurrence_signals=recurrence_signals)
    context = _context_with_playbook(f"recurrence_signals: {json.dumps(inp.recurrence_signals or {})}\n\nMenu graph:\n{_graph_context(graph)}")
    out = run_structured(
        task_description="Using the playbook Chef Tips (Menu Engineering): swap at least one beef burger for a non-beef alternative each week to lower CPM by 18%; diversify with turkey, chicken, fish, MTO take-overs. Evaluate and report: beef_recurrence_high, non_beef_alternatives_diversified, cpm_risk_level (low/medium/high), a list of actionable recommendations, and a short message suitable for the cost section of the formal report.",
        context=context,
        output_model=CalculatingCpmRiskSwapsOutput,
    )
    log.info("[AGENT-TOOL] nutrition-cost: calculating_cpm_risk_swaps DONE cpm_risk_level={}", out.cpm_risk_level)
    return out


# --- Synthesizer ---

def formatting_executive_slide(aggregated_state: dict[str, Any]) -> str:
    """Translates the aggregated global JSON state into specific markdown presentation blocks. Use when generating the final business-ready summary for the user."""
    log.info("[AGENT-TOOL] synthesizer: formatting_executive_slide START aggregated_state_keys={}", list(aggregated_state.keys()) if isinstance(aggregated_state, dict) else "n/a")
    context = _context_with_playbook(json.dumps(aggregated_state, indent=2)[:15000])
    out: FormattingExecutiveSlideOutput = run_structured(
        task_description="Produce a SHORT, premium-style markdown report. Rules: (1) Use ## for main sections and **bold** for subheadings and key terms (e.g. **What's working**, **Needs improvement**, **Compliant**). (2) Keep all text concise: 1–3 sentences per paragraph; prefer bullet points. (3) Use blockquote (>) for the two alignment callouts: one blockquote for **What's working** with 3–5 bullets, one for **Where to improve** with 3–5 bullets. (4) Structure: ## Overall Station Structure (2–3 sentences or bullets), ## Playbook Alignment (two blockquotes), ## Rotation & Repetition (bullets), ## Recommended Adjustments (short bullet list). (5) Bold important metrics and findings (e.g. **44% plant-based**, **duplicate recipe IDs**). Output one coherent full_markdown: crisp, scannable, premium feel.",
        context=context,
        output_model=FormattingExecutiveSlideOutput,
    )
    md_len = len(out.full_markdown or "")
    log.info("[AGENT-TOOL] synthesizer: formatting_executive_slide DONE full_markdown_len={}", md_len)
    return out.full_markdown or f"{out.overall_station_structure}\n\n{out.alignment_whats_working}\n\n{out.alignment_needs_improvement}\n\n{out.rotation_repetition_signals}\n\n{out.recommended_structural_adjustments}"
