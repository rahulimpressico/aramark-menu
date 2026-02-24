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
    CalculatingDiversityIndexInput,
    CalculatingDiversityIndexOutput,
    CheckingPlaybookBoundsInput,
    CheckingPlaybookBoundsOutput,
    DetectingPeriodOverlapOutput,
    EvaluatingSustainabilityMixInput,
    EvaluatingSustainabilityMixOutput,
    FormattingExecutiveSlideOutput,
    RoutingTasksInput,
    RoutingTasksOutput,
    TrackingItemFrequencyInput,
    TrackingItemFrequencyOutput,
    TransformingMenuGraphInput,
    TransformingMenuGraphOutput,
)


def _ensure_menu_graph(menu_graph: MenuGraph | dict[str, Any] | str) -> MenuGraph:
    """Coerce dict or JSON string to MenuGraph for use inside stubs."""
    if isinstance(menu_graph, MenuGraph):
        log.debug("menu_graph already MenuGraph instance")
        return menu_graph
    if isinstance(menu_graph, str):
        log.debug("Parsing menu_graph from JSON string (len={})", len(menu_graph))
        return MenuGraph.model_validate(json.loads(menu_graph))
    log.debug("Validating menu_graph from dict")
    return MenuGraph.model_validate(menu_graph)


def _graph_context(graph: MenuGraph, max_chars: int = 50000) -> str:
    """Serialize menu graph for LLM context (truncate if very large)."""
    raw = json.dumps(graph.model_dump(), indent=0)
    if len(raw) > max_chars:
        raw = raw[:max_chars] + "\n... (truncated)"
        log.warning("Graph context truncated to {} characters. Total length was {} characters", max_chars, len(raw))
    return raw


def _context_with_playbook(context: str, max_playbook_chars: int = 8000) -> str:
    """Prepend organisation playbook to context so analysis is done against compliance."""
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
    log.info("Tool routing_tasks invoked target_agent={} payload_keys={}", target_agent, list(payload.keys()) if isinstance(payload, dict) else "n/a")
    inp = RoutingTasksInput(payload=payload, target_agent=target_agent)
    context = _context_with_playbook(json.dumps(inp.model_dump(), indent=2))
    out = run_structured(
        task_description="You are routing a task to a sub-agent. Confirm the delegation: set success=True, set a short task_id or message.",
        context=context,
        output_model=RoutingTasksOutput,
    )
    log.debug("routing_tasks result success={}", out.success)
    return out


def aggregating_global_state(sub_agent_outputs: list[dict[str, Any]]) -> AggregatingGlobalStateOutput:
    """Collects the JSON outputs from all completed sub-agent tasks into a single object. Use when all sub-agents have successfully completed their delegated tasks."""
    keys_preview = [list(o.keys())[:5] if isinstance(o, dict) else type(o).__name__ for o in sub_agent_outputs[:5]] if sub_agent_outputs else []
    log.info("Tool aggregating_global_state invoked n_outputs={} source_keys={}", len(sub_agent_outputs), keys_preview)
    inp = AggregatingGlobalStateInput(sub_agent_outputs=sub_agent_outputs)
    context = _context_with_playbook(json.dumps(inp.model_dump(), indent=2))
    return run_structured(
        task_description="Merge the list of sub-agent outputs into one aggregated dict. List which sources (agent names) contributed.",
        context=context,
        output_model=AggregatingGlobalStateOutput,
    )


# --- Menu Structure ---

def transforming_menu_graph(raw_menu_data: str) -> TransformingMenuGraphOutput:
    """Parses raw CSV or PDF menu data spanning weeks, days, and meal periods into a standardized JSON schema. Use when standardizing raw unstructured menu data."""
    log.info("Tool transforming_menu_graph invoked input_len={}", len(raw_menu_data))
    inp = TransformingMenuGraphInput(raw_menu_data=raw_menu_data)
    raw_context = inp.raw_menu_data[:15000] if len(inp.raw_menu_data) > 15000 else inp.raw_menu_data
    context = _context_with_playbook(raw_context)
    return run_structured(
        task_description="Transform the raw menu text into a standardized menu graph JSON. Schema: station_name, menu_cycle, service_area, start_date, end_date, schedule (list of {day, date, meal_periods: {period_name: [{recipe_id, recipe_name, assembly_instructions, special_instructions, ingredient_description}]}}). If input is too vague or empty, set success=False and put an error message in error.",
        context=context,
        output_model=TransformingMenuGraphOutput,
    )


def checking_playbook_bounds(
    menu_graph: MenuGraph | dict[str, Any] | str,
    meal_period: str,
    day_key: str,
) -> CheckingPlaybookBoundsOutput:
    """Compares a specific meal period against playbook maximum selections to identify under-offering or over-offering. Use when validating if a station meets core structural requirements."""
    log.info("Tool checking_playbook_bounds invoked meal_period={} day_key={}", meal_period, day_key)
    graph = _ensure_menu_graph(menu_graph)
    inp = CheckingPlaybookBoundsInput(meal_period=meal_period, day_key=day_key)
    context = _context_with_playbook(f"meal_period={meal_period}, day_key={day_key}\n\nMenu graph (excerpt):\n{_graph_context(graph)}")
    return run_structured(
        task_description="Use the Organization Playbook (Station Guide: Fresh & Fast Grill). Recommended Maximum Selections: 1 Burger, 2 Daily Features, 1 Vegan Option, French Fry. Compare the menu to these bounds. Flag under_offered (e.g. missing vegan option) and over_offered (exceeding playbook max). Set compliant True only if within bounds. Fill counts with actual numbers you infer.",
        context=context,
        output_model=CheckingPlaybookBoundsOutput,
    )


# --- Data Integrity ---

def detecting_period_overlap(menu_graph: MenuGraph | dict[str, Any] | str) -> DetectingPeriodOverlapOutput:
    """Scans the menu graph for identical recipe IDs scheduled in overlapping meal periods on the same day. Use when checking for forecasting and Pre-costing risks."""
    log.info("Tool detecting_period_overlap invoked")
    graph = _ensure_menu_graph(menu_graph)
    context = _context_with_playbook(_graph_context(graph))
    return run_structured(
        task_description="Scan the menu graph: for each day, find recipe_id(s) that appear in more than one meal period (e.g. same recipe in Lunch and Dinner, or All-Day and Lunch). For each finding list recipe_id, recipe_name, periods, day, severity=high. Return overlaps list and total_count.",
        context=context,
        output_model=DetectingPeriodOverlapOutput,
    )


# --- Rotation & Recurrence ---

def calculating_diversity_index(menu_graph: MenuGraph | dict[str, Any] | str) -> CalculatingDiversityIndexOutput:
    """Computes a score based on the volume of unique feature items versus static daily items across a cycle. Use when evaluating a station for monotony or menu fatigue."""
    log.info("Tool calculating_diversity_index invoked")
    graph = _ensure_menu_graph(menu_graph)
    context = _context_with_playbook(_graph_context(graph))
    return run_structured(
        task_description="Using the playbook's Core Offerings and Enhancements (e.g. Daily Feature rotation), compute Grill Structural Diversity Index: ratio of unique entrées vs repeated static items. Output diversity_index (0-1), unique_entree_count, repeated_static_count, and a short message.",
        context=context,
        output_model=CalculatingDiversityIndexOutput,
    )


def tracking_item_frequency(
    menu_graph: MenuGraph | dict[str, Any] | str,
    recipe_ids: list[str] | None = None,
) -> TrackingItemFrequencyOutput:
    """Analyzes the exact appearance count of specific recipe IDs across the week. Use when extracting recurrence patterns for key proteins."""
    log.info("Tool tracking_item_frequency invoked recipe_ids={}", recipe_ids)
    graph = _ensure_menu_graph(menu_graph)
    inp = TrackingItemFrequencyInput(recipe_ids=recipe_ids)
    context = _context_with_playbook(f"recipe_ids filter: {inp.recipe_ids}\n\nMenu graph:\n{_graph_context(graph)}")
    return run_structured(
        task_description="Using the playbook (rotation, enhancements), count how many times each recipe (or key protein/entrée if recipe_ids not specified) appears. Fill frequencies with recipe_id, recipe_name, appearance_count, days. Add recurrence_signals (e.g. High repetition of hamburger) for the Cost Agent.",
        context=context,
        output_model=TrackingItemFrequencyOutput,
    )


# --- Nutrition & Cost ---

def evaluating_sustainability_mix(menu_graph: MenuGraph | dict[str, Any] | str) -> EvaluatingSustainabilityMixOutput:
    """Calculates the percentage of plant-based and vegan recipes programmed into the core menu template. Use when checking compliance with the 44 percent plant-based mandate."""
    log.info("Tool evaluating_sustainability_mix invoked")
    graph = _ensure_menu_graph(menu_graph)
    context = _context_with_playbook(_graph_context(graph))
    return run_structured(
        task_description="Use the playbook's Plant-Forward Goal: by 2025, 44% of core menu template offerings must be plant-based. Compute plant_based_percent and vegan_percent for the menu; set compliant_44=(plant_based_percent>=44), total_offerings, plant_based_count, and a short message.",
        context=context,
        output_model=EvaluatingSustainabilityMixOutput,
    )


def calculating_cpm_risk_swaps(
    menu_graph: MenuGraph | dict[str, Any] | str,
    recurrence_signals: dict[str, Any] | None = None,
) -> CalculatingCpmRiskSwapsOutput:
    """Identifies high-cost beef recurrence and checks if poultry or plant-based alternatives have been diversified. Use when evaluating cost-saving protein strategies."""
    log.info("Tool calculating_cpm_risk_swaps invoked")
    graph = _ensure_menu_graph(menu_graph)
    inp = CalculatingCpmRiskSwapsInput(recurrence_signals=recurrence_signals)
    context = _context_with_playbook(f"recurrence_signals: {json.dumps(inp.recurrence_signals or {})}\n\nMenu graph:\n{_graph_context(graph)}")
    return run_structured(
        task_description="Use the playbook Chef Tips (Menu Engineering): swap at least one beef burger for non-beef each week to lower CPM by 18%; diversify with turkey, chicken, fish, MTO take-overs. Evaluate: beef_recurrence_high, non_beef_alternatives_diversified, cpm_risk_level (low/medium/high), recommendations list, message.",
        context=context,
        output_model=CalculatingCpmRiskSwapsOutput,
    )


# --- Synthesizer ---

def formatting_executive_slide(aggregated_state: dict[str, Any]) -> str:
    """Translates the aggregated global JSON state into specific markdown presentation blocks. Use when generating the final business-ready summary for the user."""
    log.info("Tool formatting_executive_slide invoked aggregated_state_keys={}", list(aggregated_state.keys()) if isinstance(aggregated_state, dict) else "n/a")
    context = _context_with_playbook(json.dumps(aggregated_state, indent=2)[:15000])
    out: FormattingExecutiveSlideOutput = run_structured(
        task_description="Turn the aggregated analysis into an executive summary. Frame compliance and recommendations against the Organization Playbook (Fresh & Fast Grill, 44% plant-based, Chef Tips, Core/Enhancements). Write in clear prose. Output: 1) Overall Station Structure, 2a) What you're doing well, 2b) Where structure needs improvement, 3) Rotation & Repetition Signals, 4) Recommended Structural Adjustments. Combine into full_markdown as one coherent document.",
        context=context,
        output_model=FormattingExecutiveSlideOutput,
    )
    return out.full_markdown or f"{out.overall_station_structure}\n\n{out.alignment_whats_working}\n\n{out.alignment_needs_improvement}\n\n{out.rotation_repetition_signals}\n\n{out.recommended_structural_adjustments}"
