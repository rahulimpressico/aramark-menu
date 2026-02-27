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
from experiments.models.menu_graph import recipe_id_from_node_id
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
    ItemFrequency,
    OverlapFinding,
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


def _graph_context(graph: MenuGraph, max_chars: int = 22000) -> str:
    """Serialize menu graph for LLM context (truncate if very large)."""
    raw = json.dumps(graph.model_dump(), indent=0)
    if len(raw) > max_chars:
        original_len = len(raw)
        raw = raw[:max_chars] + "\n... (truncated)"
        log.warning("Graph context truncated to {} characters (original: {})", max_chars, original_len)
    return raw


def _context_with_playbook(context: str, max_playbook_chars: int = 5000) -> str:
    """Prepend organization playbook to context so analysis is done against compliance."""
    playbook = get_playbook_content()
    if not playbook:
        return context
    if len(playbook) > max_playbook_chars:
        playbook = playbook[:max_playbook_chars] + "\n... (playbook truncated)"
    return f"## Organization Playbook (compliance reference)\n{playbook}\n\n---\n\n## Input / Menu data\n{context}"


# --- Deterministic helpers (no LLM) for speed ---

def _detect_period_overlap_deterministic(graph: MenuGraph) -> DetectingPeriodOverlapOutput:
    """Find recipe IDs that appear in more than one meal period on the same day (graph traversal only)."""
    overlaps: list[OverlapFinding] = []
    for day in graph.get_days_for_station():
        period_nodes = graph.get_periods_for_day(day.id)
        recipe_to_periods: dict[str, list[str]] = {}
        for p in period_nodes:
            for r in graph.get_recipes_for_period(p.id):
                rid = r.id
                recipe_to_periods.setdefault(rid, []).append(p.name)
        for rid, periods in recipe_to_periods.items():
            if len(periods) < 2:
                continue
            recipe_node = graph.get_recipe(rid)
            name = recipe_node.name if recipe_node else rid
            overlaps.append(OverlapFinding(
                recipe_id=recipe_id_from_node_id(rid),
                recipe_name=name,
                periods=periods,
                day=day.name,
                severity="high",
            ))
    message = f"Found {len(overlaps)} recipe(s) scheduled in multiple periods on the same day." if overlaps else "No overlapping period duplicates found."
    return DetectingPeriodOverlapOutput(overlaps=overlaps, total_count=len(overlaps), message=message)


def _calculate_diversity_index_deterministic(graph: MenuGraph) -> CalculatingDiversityIndexOutput:
    """Compute unique vs repeated recipe counts from graph (no LLM)."""
    recipes = graph.get_recipes()
    if not recipes:
        return CalculatingDiversityIndexOutput(
            diversity_index=0.0, unique_entree_count=0, repeated_static_count=0,
            message="No recipes in graph.",
        )
    total_slots = sum(graph.recipe_serve_count(r.id) for r in recipes)
    unique = len(recipes)
    repeated_static = max(0, total_slots - unique)
    diversity_index = unique / total_slots if total_slots else 0.0
    if diversity_index >= 0.6:
        msg = "Good variety; low monotony risk."
    elif diversity_index >= 0.3:
        msg = "Moderate variety; consider rotating daily features."
    else:
        msg = "Low diversity; high repetition—rotate offerings per playbook."
    return CalculatingDiversityIndexOutput(
        diversity_index=round(diversity_index, 2),
        unique_entree_count=unique,
        repeated_static_count=repeated_static,
        message=msg,
    )


def _recipe_text(r: Any) -> str:
    """Combined text for keyword classification (name + ingredients)."""
    parts = [getattr(r, "name", "") or ""]
    if hasattr(r, "ingredient_description") and r.ingredient_description:
        parts.extend(r.ingredient_description if isinstance(r.ingredient_description, list) else [])
    return " ".join(parts).lower()


def _check_playbook_bounds_deterministic(graph: MenuGraph) -> CheckingPlaybookBoundsOutput:
    """Classify recipes by name/ingredient keywords and check 1 burger, 2 daily features, 1 vegan, fries."""
    under_offered: list[str] = []
    over_offered: list[str] = []
    counts = {"burger": 0, "daily_feature": 0, "vegan": 0, "fries": 0}
    for day in graph.get_days_for_station():
        period_nodes = graph.get_periods_for_day(day.id)
        day_burger = day_feature = day_vegan = day_fries = 0
        for p in period_nodes:
            for r in graph.get_recipes_for_period(p.id):
                t = _recipe_text(r)
                if "burger" in t and "vegan" not in t and "bean" not in t:
                    day_burger += 1
                elif "fries" in t or "french fry" in t or (t.startswith("fry") and "fry" in t):
                    day_fries += 1
                elif any(x in t for x in ("vegan", "plant-based", "plant based", "tofu", "black bean", "veggie")):
                    day_vegan += 1
                else:
                    day_feature += 1
        counts["burger"] += day_burger
        counts["daily_feature"] += day_feature
        counts["vegan"] += day_vegan
        counts["fries"] += day_fries
        if day_vegan < 1:
            under_offered.append(f"Missing vegan option ({day.name})")
        if day_burger > 1:
            over_offered.append(f"Too many burgers ({day.name})")
        if day_feature > 2:
            over_offered.append(f"Too many daily features ({day.name})")
    compliant = len(under_offered) == 0 and len(over_offered) == 0
    message = "Within playbook bounds." if compliant else "Check under_offered and over_offered."
    return CheckingPlaybookBoundsOutput(
        compliant=compliant,
        under_offered=under_offered,
        over_offered=over_offered,
        counts=counts,
        message=message,
    )


def _evaluate_sustainability_mix_deterministic(graph: MenuGraph) -> EvaluatingSustainabilityMixOutput:
    """Plant-based % from recipe name/ingredient keywords (no LLM)."""
    recipes = graph.get_recipes()
    if not recipes:
        return EvaluatingSustainabilityMixOutput(
            plant_based_percent=0.0, vegan_percent=0.0, compliant_44=False,
            total_offerings=0, plant_based_count=0, message="No recipes.",
        )
    total_slots = sum(graph.recipe_serve_count(r.id) for r in recipes)
    plant_keywords = ("vegan", "plant-based", "plant based", "tofu", "black bean", "veggie", "vegetable", "bean", "lentil")
    plant_count = 0
    for r in recipes:
        t = _recipe_text(r)
        if any(k in t for k in plant_keywords):
            plant_count += graph.recipe_serve_count(r.id)
    plant_based_percent = (100.0 * plant_count / total_slots) if total_slots else 0.0
    compliant_44 = plant_based_percent >= 44.0
    message = f"{plant_based_percent:.0f}% plant-based; {'compliant' if compliant_44 else 'below 44% target'}."
    return EvaluatingSustainabilityMixOutput(
        plant_based_percent=round(plant_based_percent, 1),
        vegan_percent=round(plant_based_percent, 1),
        compliant_44=compliant_44,
        total_offerings=total_slots,
        plant_based_count=plant_count,
        message=message,
    )


def _calculate_cpm_risk_swaps_deterministic(
    graph: MenuGraph,
    recurrence_signals: dict[str, Any] | None = None,
) -> CalculatingCpmRiskSwapsOutput:
    """Beef vs non-beef from recipe name keywords (no LLM)."""
    recipes = graph.get_recipes()
    beef_count = 0
    non_beef_count = 0
    for r in recipes:
        t = _recipe_text(r)
        n = graph.recipe_serve_count(r.id)
        if "beef" in t or "hamburger" in t or ("burger" in t and "turkey" not in t and "chicken" not in t and "bean" not in t):
            beef_count += n
        elif any(x in t for x in ("turkey", "chicken", "fish", "plant", "vegan", "tofu", "bean")):
            non_beef_count += n
    beef_recurrence_high = beef_count >= 3
    non_beef_alternatives_diversified = non_beef_count >= 2
    cpm_risk_level = "high" if beef_recurrence_high and not non_beef_alternatives_diversified else ("low" if non_beef_alternatives_diversified else "medium")
    recommendations = []
    if beef_recurrence_high:
        recommendations.append("Swap at least one beef burger for turkey, chicken, or plant-based option per week.")
    if not non_beef_alternatives_diversified:
        recommendations.append("Diversify with turkey, chicken, or fish options.")
    message = f"Beef slots={beef_count}, non-beef={non_beef_count}; CPM risk {cpm_risk_level}."
    return CalculatingCpmRiskSwapsOutput(
        beef_recurrence_high=beef_recurrence_high,
        non_beef_alternatives_diversified=non_beef_alternatives_diversified,
        cpm_risk_level=cpm_risk_level,
        recommendations=recommendations,
        message=message,
    )


def _track_item_frequency_deterministic(
    graph: MenuGraph,
    recipe_ids: list[str] | None = None,
) -> TrackingItemFrequencyOutput:
    """Count how often each recipe appears across the cycle (graph traversal only)."""
    recipes = graph.get_recipes()
    if recipe_ids:
        recipe_ids_set = {r if r.startswith("Recipe_") else f"Recipe_{r}" for r in recipe_ids}
        recipes = [r for r in recipes if r.id in recipe_ids_set or recipe_id_from_node_id(r.id) in recipe_ids]
    frequencies: list[ItemFrequency] = []
    recurrence_signals: list[str] = []
    for r in recipes:
        count = graph.recipe_serve_count(r.id)
        period_sources = graph.get_sources(r.id, "SERVES_RECIPE")
        day_names: list[str] = []
        for pid in period_sources:
            for did in graph.get_sources(pid, "HAS_PERIOD"):
                node = graph.get_node(did)
                if node and getattr(node, "name", None):
                    day_names.append(node.name)
        day_names = sorted(set(day_names))
        frequencies.append(ItemFrequency(
            recipe_id=recipe_id_from_node_id(r.id),
            recipe_name=r.name,
            appearance_count=count,
            days=day_names,
        ))
        if count >= 4:
            recurrence_signals.append(f"High repetition of {r.name} ({count} times across cycle).")
    frequencies.sort(key=lambda x: (-x.appearance_count, x.recipe_id))
    message = f"Tracked {len(frequencies)} recipe(s). " + ("; ".join(recurrence_signals[:3]) if recurrence_signals else "No high-repetition signals.")
    return TrackingItemFrequencyOutput(frequencies=frequencies, recurrence_signals=recurrence_signals, message=message)


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
    """Compares meal period against playbook bounds (deterministic, keyword-based)."""
    log.info("[AGENT-TOOL] menu-structure: checking_playbook_bounds START meal_period={} day_key={}", meal_period, day_key)
    graph = _ensure_menu_graph(menu_graph)
    out = _check_playbook_bounds_deterministic(graph)
    log.info("[AGENT-TOOL] menu-structure: checking_playbook_bounds DONE compliant={}", out.compliant)
    return out


# --- Data Integrity ---

def detecting_period_overlap(menu_graph: MenuGraph | dict[str, Any] | str) -> DetectingPeriodOverlapOutput:
    """Scans the menu graph for identical recipe IDs scheduled in overlapping meal periods on the same day (deterministic, no LLM)."""
    log.info("[AGENT-TOOL] data-integrity: detecting_period_overlap START")
    graph = _ensure_menu_graph(menu_graph)
    out = _detect_period_overlap_deterministic(graph)
    log.info("[AGENT-TOOL] data-integrity: detecting_period_overlap DONE total_count={}", out.total_count)
    return out


# --- Rotation & Recurrence ---

def calculating_diversity_index(menu_graph: MenuGraph | dict[str, Any] | str) -> CalculatingDiversityIndexOutput:
    """Computes diversity index from unique vs repeated recipe counts (deterministic, no LLM)."""
    log.info("[AGENT-TOOL] rotation-recurrence: calculating_diversity_index START")
    graph = _ensure_menu_graph(menu_graph)
    out = _calculate_diversity_index_deterministic(graph)
    log.info("[AGENT-TOOL] rotation-recurrence: calculating_diversity_index DONE diversity_index={}", out.diversity_index)
    return out


def tracking_item_frequency(
    menu_graph: MenuGraph | dict[str, Any] | str,
    recipe_ids: list[str] | None = None,
) -> TrackingItemFrequencyOutput:
    """Counts recipe appearance across the cycle (deterministic, no LLM)."""
    log.info("[AGENT-TOOL] rotation-recurrence: tracking_item_frequency START recipe_ids={}", recipe_ids)
    graph = _ensure_menu_graph(menu_graph)
    out = _track_item_frequency_deterministic(graph, recipe_ids)
    log.info("[AGENT-TOOL] rotation-recurrence: tracking_item_frequency DONE frequencies_count={}", len(out.frequencies))
    return out


# --- Nutrition & Cost ---

def evaluating_sustainability_mix(menu_graph: MenuGraph | dict[str, Any] | str) -> EvaluatingSustainabilityMixOutput:
    """Plant-based % from recipe keywords (deterministic, no LLM)."""
    log.info("[AGENT-TOOL] nutrition-cost: evaluating_sustainability_mix START")
    graph = _ensure_menu_graph(menu_graph)
    out = _evaluate_sustainability_mix_deterministic(graph)
    log.info("[AGENT-TOOL] nutrition-cost: evaluating_sustainability_mix DONE plant_based_percent={} compliant_44={}", out.plant_based_percent, out.compliant_44)
    return out


def calculating_cpm_risk_swaps(
    menu_graph: MenuGraph | dict[str, Any] | str,
    recurrence_signals: dict[str, Any] | None = None,
) -> CalculatingCpmRiskSwapsOutput:
    """Beef vs non-beef from recipe keywords (deterministic, no LLM)."""
    log.info("[AGENT-TOOL] nutrition-cost: calculating_cpm_risk_swaps START")
    graph = _ensure_menu_graph(menu_graph)
    out = _calculate_cpm_risk_swaps_deterministic(graph, recurrence_signals)
    log.info("[AGENT-TOOL] nutrition-cost: calculating_cpm_risk_swaps DONE cpm_risk_level={}", out.cpm_risk_level)
    return out


# --- Synthesizer ---


def _fallback_report_from_aggregated(aggregated_state: dict[str, Any]) -> str:
    """Build a minimal report when the LLM returns empty, so the API never returns blank content."""
    scope = aggregated_state.get("scope") or {}
    meal = (scope.get("meal_period") or "Meal").capitalize()
    station = scope.get("station_name") or "Station"
    ms = aggregated_state.get("menu_structure") or {}
    msg = (ms.get("message") or "").strip()
    under = ms.get("under_offered") or []
    over = ms.get("over_offered") or []
    counts = ms.get("counts") or {}
    lines = [
        f"## Overall Station Structure",
        f"- **{meal}** at **{station}**: counts {json.dumps(counts)[:200]}.",
        "",
        "## Playbook Alignment",
        "**Where to improve:**",
        f"> {msg}" if msg else "> Review playbook limits for this station.",
    ]
    if under:
        lines.append("> - Under-offered: " + ", ".join(str(x) for x in under[:5]))
    if over:
        lines.append("> - Over-offered: " + ", ".join(str(x) for x in over[:5]))
    lines.extend(["", "## Rotation & Repetition", "- Review variety and repetition from data.", "", "## Recommended Adjustments", "- Align offerings with playbook limits.", "- Rotate items where needed."])
    return "\n".join(lines)


def formatting_executive_slide(aggregated_state: dict[str, Any]) -> str:
    """Translates the aggregated global JSON state into specific markdown presentation blocks. Use when generating the final business-ready summary for the user."""
    log.info("[AGENT-TOOL] synthesizer: formatting_executive_slide START aggregated_state_keys={}", list(aggregated_state.keys()) if isinstance(aggregated_state, dict) else "n/a")
    context = _context_with_playbook(json.dumps(aggregated_state, indent=2)[:12000])
    try:
        out: FormattingExecutiveSlideOutput = run_structured(
            task_description="Produce one FDA-suitable markdown report. Use proper markdown (MD) tags: ## for each section heading, - or * for bullet lists, ** for bold text, > for blockquotes. Put the COMPLETE report (all four sections, with bullets) in the full_markdown field—do not return only a title or one line. (1) State meal period (Breakfast/Lunch/Dinner) from scope.meal_period. (2) Exactly four sections: ## Overall Station Structure (1–2 bullets: meal name, what is offered, counts). ## Playbook Alignment with **Where to improve:** only—one blockquote (>) with 3–4 bullets naming specific items (e.g. **Burger** — limit to 1; **Vegan option** — add one; **Fries** — ensure one slot). Use menu_structure (under_offered, over_offered, counts) from context. ## Rotation & Repetition (1–2 bullets). ## Recommended Adjustments (2–3 bullets, action verbs). Bold meal name and item names with **. No 'What's working'. Output the full report as full_markdown.",
            context=context,
            output_model=FormattingExecutiveSlideOutput,
        )
        combined = out.full_markdown or f"{out.overall_station_structure or ''}\n\n{out.alignment_whats_working or ''}\n\n{out.alignment_needs_improvement or ''}\n\n{out.rotation_repetition_signals or ''}\n\n{out.recommended_structural_adjustments or ''}".strip()
    except Exception as e:
        log.warning("[AGENT-TOOL] synthesizer: run_structured failed, using fallback: {}", e)
        combined = ""
    combined = (combined or "").strip()
    # Treat very short responses (e.g. only a heading) as failure → use full fallback report
    if not combined or len(combined) < 250:
        if combined:
            log.warning("[AGENT-TOOL] synthesizer: LLM returned too short (len={}), using fallback", len(combined))
        else:
            log.warning("[AGENT-TOOL] synthesizer: LLM returned empty report, using fallback from aggregated_state")
        combined = _fallback_report_from_aggregated(aggregated_state)
    log.info("[AGENT-TOOL] synthesizer: formatting_executive_slide DONE full_markdown_len={}", len(combined))
    return combined
