"""
Collegiate Dining Menu Analyzer — Deep Agent (PoC).

Orchestrator + 5 subagents: Menu Structure, Data Integrity, Rotation & Recurrence,
Nutrition/Cost, Executive Synthesizer. Uses create_deep_agent from deepagents.
Tools take MenuGraph (or dict/JSON string) where applicable; see experiments.models.MenuGraph.

Run from backend directory:
  uv sync --extra experiments && uv run python -m experiments.menu_analyzer_agent

Or invoke programmatically with a loaded graph:
  from experiments.menu_analyzer_agent import create_menu_analyzer_agent, get_default_menu_graph
  agent = create_menu_analyzer_agent()
  graph = get_default_menu_graph()  # MenuGraph from menu_graph.json
  result = agent.invoke({"messages": [{"role": "user", "content": f"Analyze this Grill menu. Menu graph (JSON): {graph.model_dump_json()}"}]})  # graph is traversable (nodes/edges)
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from deepagents import create_deep_agent
from langchain_core.messages import AIMessage, ToolMessage

load_dotenv()

from experiments.log_config import log
from experiments.models.menu_graph import MenuGraph
from experiments.prompts import (
    get_orchestrator_prompt,
    get_menu_structure_prompt,
    get_data_integrity_prompt,
    get_rotation_recurrence_prompt,
    get_nutrition_cost_prompt,
    get_synthesizer_prompt,
)
from experiments.tools.stubs import (
    routing_tasks,
    aggregating_global_state,
    transforming_menu_graph,
    checking_playbook_bounds,
    detecting_period_overlap,
    calculating_diversity_index,
    tracking_item_frequency,
    evaluating_sustainability_mix,
    calculating_cpm_risk_swaps,
    formatting_executive_slide,
)

EXPERIMENTS_DIR = Path(__file__).parent
FALLBACK_GRAPH_PATHS = [
    EXPERIMENTS_DIR / "menu_graph_v2_extracted.json",
    EXPERIMENTS_DIR / "menu_graph_v1.json",
]
REPORTS_DIR = EXPERIMENTS_DIR / "reports"

# Caches to avoid repeated work (speeds up report generation)
_agent_cache: dict[str, Any] = {}
_graph_cache: MenuGraph | None = None
_filtered_payload_cache: dict[tuple[str, str], str] = {}  # (station, meal_period) -> JSON payload
_FILTERED_CACHE_MAX = 6  # keep last 6 (e.g. 3 meals × 2 stations)


def get_default_menu_graph(graph_path: Path | None = None) -> MenuGraph:
    """Load menu graph from given path, or first existing path in FALLBACK_GRAPH_PATHS."""
    path = graph_path
    if not path or not path.is_file():
        for fallback in FALLBACK_GRAPH_PATHS:
            if fallback.is_file():
                path = fallback
                log.info("[AGENT] Using menu graph from fallback: {}", path.name)
                break
    if not path or not path.is_file():
        raise FileNotFoundError("No menu graph file found. Place menu_graph_v1.json or menu_graph_v2_extracted.json in the experiments directory.")
    log.info("[AGENT] Loading menu graph from path={}", path)
    global _graph_cache
    if _graph_cache is not None and graph_path is None:
        return _graph_cache
    graph = MenuGraph.from_json_path(path)
    if graph_path is None:
        _graph_cache = graph
    log.info("[AGENT] Loaded MenuGraph nodes={} edges={}", len(graph.nodes), len(graph.edges))
    return graph


def create_menu_analyzer_agent(
    model: str | None = None,
    checkpointer=None,
):
    """
    Build the Menu Analyzer deep agent with orchestrator and 5 subagents.

    - Orchestrator: routes to Structure first, then Integrity/Rotation/Cost, then Synthesizer.
    - Menu Structure: transform menu → JSON, check playbook bounds.
    - Data Integrity: detect period overlaps (duplicate recipe IDs).
    - Rotation & Recurrence: diversity index, item frequency.
    - Nutrition & Cost: sustainability mix, CPM risk/swaps.
    - Synthesizer: format aggregated state into executive summary.
    """
    # Use google_genai: prefix so LangChain uses ChatGoogleGenerativeAI (Gemini Developer API),
    # not ChatVertexAI (Vertex AI). See GOOGLE_API_KEY in README.
    model = model or "google_genai:gemini-2.5-flash"
    log.info("[AGENT] Creating orchestrator + 5 subagents model={}", model)
    subagents = [
        {
            "name": "menu-structure-agent",
            "description": "Transforms raw menu data into a standardized JSON graph and validates structure against the Fresh & Fast Grill Playbook. Produces evidence-based counts, capacities, and template alignment for compliance reporting.",
            "system_prompt": get_menu_structure_prompt(),
            "tools": [transforming_menu_graph, checking_playbook_bounds],
            "model": model,
        },
        {
            "name": "data-integrity-agent",
            "description": "Identifies duplicate recipe IDs across overlapping meal periods (e.g. same item on All-Day and Lunch). Documents findings for forecasting integrity and pre-costing risk in the formal report.",
            "system_prompt": get_data_integrity_prompt(),
            "tools": [detecting_period_overlap],
            "model": model,
        },
        {
            "name": "rotation-recurrence-agent",
            "description": "Computes Grill Structural Diversity Index and item frequency across the cycle. Produces recurrence signals and variety assessment for the rotation section of the report.",
            "system_prompt": get_rotation_recurrence_prompt(),
            "tools": [calculating_diversity_index, tracking_item_frequency],
            "model": model,
        },
        {
            "name": "nutrition-cost-agent",
            "description": "Evaluates 44% plant-based compliance and beef-swap/CPM strategies against the playbook. Produces sustainability and cost-risk findings for the formal report.",
            "system_prompt": get_nutrition_cost_prompt(),
            "tools": [evaluating_sustainability_mix, calculating_cpm_risk_swaps],
            "model": model,
        },
        {
            "name": "synthesizer-agent",
            "description": "Produces a professional menu analysis report from aggregated outputs: Overall Structure, Playbook alignment, Rotation findings, and Recommended Adjustments (suitable for institutional or regulatory review).",
            "system_prompt": get_synthesizer_prompt(),
            "tools": [formatting_executive_slide],
            "model": model,
        },
    ]

    orchestrator_tools = [routing_tasks, aggregating_global_state]

    agent = create_deep_agent(
        name="menu-analyzer-orchestrator",
        model=model,
        system_prompt=get_orchestrator_prompt(),
        tools=orchestrator_tools,
        subagents=subagents,
        checkpointer=checkpointer,
    )
    log.debug("Menu analyzer agent created")
    # Save the agent graph visualization (LangGraph CompiledStateGraph has get_graph(), not visualize())
    try:
        agent.get_graph().draw_mermaid_png(output_file_path=str(EXPERIMENTS_DIR / "menu-analyzer-agent.png"))
    except Exception as e:
        log.warning("Could not save agent graph PNG: {}", e)
    return agent


def _get_or_create_agent(model: str):
    """Return cached agent for model to avoid recreating on every request."""
    global _agent_cache
    if model not in _agent_cache:
        _agent_cache[model] = create_menu_analyzer_agent(model=model)
        log.info("[AGENT] Cached agent for model={}", model)
    return _agent_cache[model]


def main():
    """Create agent and run a single example invocation (optional)."""
    from experiments.log_config import configure_experiments_logging
    configure_experiments_logging()
    log.info("[AGENT] main() START")
    agent = create_menu_analyzer_agent(model="google_genai:gemini-2.5-flash")
    try:
        graph = get_default_menu_graph()
    except Exception as e:
        log.warning("No menu graph found: {}", e)
        print("Menu graph not found; use a query that provides menu data.")
        user_content = "Describe what analysis you would perform on a Grill station menu once the menu graph is loaded."
    else:
        station_name = "Grill"
        meal_period = "Dinner"
        filtered = graph.filter_by_meal_period(meal_period)
        graph_payload = filtered.model_dump_json()
        user_content = (
            f'Analyze only station "{station_name}" and meal period "{meal_period}". '
            "Do not analyze any other station or meal period. "
            "Use your task tool to delegate in order: "
            "menu-structure-agent, then data-integrity-agent, rotation-recurrence-agent, nutrition-cost-agent, "
            "then synthesizer-agent. "
            "Return exactly one executive summary markdown report for this scope only. "
            "The report must clearly state the meal period and, for any finding, which day or week it refers to.\n\n"
            f"Scope:\n- station_name: {station_name}\n- meal_period: {meal_period}\n\n"
            "Menu graph (JSON) — full week schedule; pass this entire block to tools that need menu data:\n"
            + graph_payload
        )
    log.info("[AGENT] main() Invoking orchestrator user_message_len={}", len(user_content))
    # Langfuse tracing + recursion_limit so graph can run through all subagent steps
    config: dict = {"recursion_limit": 50}
    try:
        from langfuse.langchain import CallbackHandler
        langfuse_handler = CallbackHandler()
        config["callbacks"] = [langfuse_handler]
        log.info("Langfuse tracing enabled; traces will appear in Langfuse")
    except ImportError:
        log.debug("langfuse not installed; run with uv sync --extra experiments for tracing")
    except Exception as e:
        log.warning("Langfuse callback not used: {}", e)

    result = agent.invoke(
        {"messages": [{"role": "user", "content": user_content}]},
        config=config,
    )
    messages = result.get("messages", [])
    log.info("[AGENT] main() Invoke completed messages_count={}", len(messages))
    # Best report = longest content from AIMessage or ToolMessage (synthesizer often in tool result)
    candidate_contents = []
    for msg in messages:
        raw = None
        if isinstance(msg, AIMessage) and msg.content:
            raw = msg.content
        elif isinstance(msg, ToolMessage) and msg.content:
            raw = msg.content
        if raw is not None:
            ln = len(raw) if isinstance(raw, str) else sum(len(b.get("text", "") or "") for b in raw) if isinstance(raw, list) else 0
            if ln:
                candidate_contents.append((ln, raw))
    if candidate_contents:
        candidate_contents.sort(key=lambda x: x[0], reverse=True)
        final_content = candidate_contents[0][1]
    else:
        final_content = None
    markdown_text = _extract_markdown_from_content(final_content)
    if markdown_text:
        _save_report_to_filesystem(markdown_text)
        print("--- Final output for UI ---")
        print(markdown_text[:2000] + ("..." if len(markdown_text) > 2000 else ""))
    else:
        for msg in messages[-3:]:
            if hasattr(msg, "content") and msg.content:
                print(msg.content[:500] if len(str(msg.content)) > 500 else msg.content)
    return result


def _content_to_str(content: str | list | None) -> str:
    """Flatten any message content to a single string (str, list of blocks, Gemini/LangChain shapes)."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
                continue
            # Dict block (e.g. {"type": "text", "text": "..."} or {"content": "..."})
            if isinstance(block, dict):
                for key in ("text", "content", "input"):
                    val = block.get(key)
                    if val is not None and isinstance(val, str):
                        parts.append(val)
                        break
                else:
                    if block.get("type") == "text" and block.get("text"):
                        parts.append(block["text"])
                    elif "parts" in block and isinstance(block["parts"], list):
                        for p in block["parts"]:
                            if isinstance(p, str):
                                parts.append(p)
                            elif isinstance(p, dict) and p.get("text"):
                                parts.append(p["text"])
                continue
            # Object with .text or .content (LangChain content blocks)
            if hasattr(block, "text"):
                t = getattr(block, "text", None)
                if isinstance(t, str) and t.strip():
                    parts.append(t)
                    continue
            if hasattr(block, "content"):
                c = getattr(block, "content", None)
                if isinstance(c, str) and c.strip():
                    parts.append(c)
                    continue
            if hasattr(block, "get"):
                t = block.get("text") or block.get("content")
                if t and isinstance(t, str):
                    parts.append(t)
        return "\n\n".join(parts) if parts else ""
    # Fallback: stringify (e.g. for unexpected types)
    s = str(content)
    return s if s.strip() else ""


def _extract_markdown_from_content(content: str | list | None) -> str:
    """Extract plain markdown string from final message content (may be str or list of blocks from Gemini)."""
    s = _content_to_str(content)
    return _normalize_report_markdown(s) if s else ""


def _normalize_report_markdown(text: str) -> str:
    """Fix common LLM markdown issues: tables with header and separator glued (| ... | | :--- |)."""
    if not text or not text.strip():
        return text
    import re
    # Fix: header row and separator row on same line: "| Day | ... | | :-------- |" -> newline before separator
    text = re.sub(r"\|\s*\|(\s*:[-|\s]+)", r"|\n|\1", text)
    # Same when separator follows without space: "| ... || :-- |"
    text = re.sub(r"\|(\s*)\|\s*\|(\s*:)", r"|\n|\2", text)
    return text.strip()


def _save_report_to_filesystem(markdown_text: str) -> None:
    """Write executive summary markdown to experiments/reports/ (timestamped + latest)."""
    if not markdown_text.strip():
        return
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path_ts = REPORTS_DIR / f"menu_report_{timestamp}.md"
    path_latest = REPORTS_DIR / "menu_report_latest.md"
    for path in (path_ts, path_latest):
        path.write_text(markdown_text, encoding="utf-8")
        log.info("Report saved to {}", path)


def run_analysis_fast(station_name: str, meal_period: str) -> dict:
    """
    Fast path: run all analysis with deterministic tools (no orchestrator), then one LLM call for the report.
    Returns dict with "content" (report markdown) and "usage". Typically completes in 1–2 minutes.
    """
    log.info("[AGENT] run_analysis_fast START station_name={} meal_period={}", station_name, meal_period)
    try:
        from experiments.tools.llm_runner import clear_usage, get_usage_summary
        clear_usage()
    except Exception:
        pass
    graph = get_default_menu_graph()
    filtered = graph.filter_by_meal_period(meal_period)
    log.info("[AGENT] run_analysis_fast filtered graph nodes={} edges={}", len(filtered.nodes), len(filtered.edges))

    menu_structure = checking_playbook_bounds(filtered, meal_period, "all")
    data_integrity = detecting_period_overlap(filtered)
    diversity = calculating_diversity_index(filtered)
    frequency = tracking_item_frequency(filtered)
    sustainability = evaluating_sustainability_mix(filtered)
    cpm = calculating_cpm_risk_swaps(filtered)

    aggregated_state = {
        "menu_structure": menu_structure.model_dump() if hasattr(menu_structure, "model_dump") else menu_structure,
        "data_integrity": data_integrity.model_dump() if hasattr(data_integrity, "model_dump") else data_integrity,
        "rotation_recurrence": {
            "diversity": diversity.model_dump() if hasattr(diversity, "model_dump") else diversity,
            "frequency": frequency.model_dump() if hasattr(frequency, "model_dump") else frequency,
        },
        "nutrition_cost": {
            "sustainability": sustainability.model_dump() if hasattr(sustainability, "model_dump") else sustainability,
            "cpm": cpm.model_dump() if hasattr(cpm, "model_dump") else cpm,
        },
        "scope": {"station_name": station_name, "meal_period": meal_period},
    }
    report_md = formatting_executive_slide(aggregated_state)
    try:
        usage = get_usage_summary()
    except Exception as e:
        log.warning("[AGENT] get_usage_summary failed: {}", e)
        usage = {"total_input_tokens": 0, "total_output_tokens": 0, "cost_usd": 0.0, "call_count": 0}
    log.info("[AGENT] run_analysis_fast END report_len={} usage={}", len(report_md or ""), usage)
    return {"content": report_md or "", "usage": usage}


def run_analysis(
    station_name: str,
    meal_period: str,
    model: str = "google_genai:gemini-2.5-flash",
) -> dict:
    """
    Run the menu analyzer for the given station_name and meal_period.
    Returns dict with "content" (report markdown) and "usage" (total_input_tokens, total_output_tokens, cost_usd).
    """
    log.info("[AGENT] run_analysis START station_name={} meal_period={} model={}", station_name, meal_period, model)
    try:
        from experiments.tools.llm_runner import clear_usage
        clear_usage()
    except Exception:
        pass
    global _filtered_payload_cache
    cache_key = (station_name.strip().lower(), meal_period.strip().lower())
    if cache_key in _filtered_payload_cache:
        graph_payload = _filtered_payload_cache[cache_key]
        log.info("[AGENT] Using cached filtered payload len={}", len(graph_payload))
    else:
        graph = get_default_menu_graph()
        filtered = graph.filter_by_meal_period(meal_period)
        log.info("[AGENT] Filtered by meal_period={} → nodes={} edges={}", meal_period, len(filtered.nodes), len(filtered.edges))
        graph_payload = filtered.model_dump_json()
        if len(_filtered_payload_cache) >= _FILTERED_CACHE_MAX:
            _filtered_payload_cache.pop(next(iter(_filtered_payload_cache)))
        _filtered_payload_cache[cache_key] = graph_payload
        log.info("[AGENT] Serialized graph as JSON len={}", len(graph_payload))
    # Cap payload size to reduce latency (orchestrator + subagents parse this)
    _max_payload_chars = 28_000
    if len(graph_payload) > _max_payload_chars:
        graph_payload = graph_payload[:_max_payload_chars] + "\n...(truncated)"
        log.info("[AGENT] Truncated graph payload to {} chars", _max_payload_chars)
    agent = _get_or_create_agent(model)
    user_content = (
        f'Analyze only station "{station_name}" and meal period "{meal_period}". '
        "Do not analyze any other station or meal period. "
        "Delegate: menu-structure-agent first; then data-integrity-agent, rotation-recurrence-agent, nutrition-cost-agent (you may call these three in parallel in one round); then synthesizer-agent with aggregated results. "
        "Return exactly one executive summary markdown report for this scope only. "
        "The report must clearly state the meal period and, for any finding or issue, which day (e.g. Monday, Tuesday) or week it refers to.\n\n"
        f"Scope:\n- station_name: {station_name}\n- meal_period: {meal_period}\n\n"
        "Menu graph (JSON) for this meal period — full week schedule; pass this block to tools that need menu data:\n"
        + graph_payload
    )
    log.info("[AGENT] Invoking orchestrator (user_message_len={})", len(user_content))
    config = {"recursion_limit": 50}
    max_tries = 2  # Retry once if we get partial run (e.g. timeout → only 2 messages, empty report)
    report = ""
    for attempt in range(max_tries):
        if attempt > 0:
            log.warning("[AGENT] Retrying run_analysis (attempt {}): previous run had messages_count={} report_len=0", attempt + 1, len(messages))
        result = agent.invoke({"messages": [{"role": "user", "content": user_content}]}, config=config)
        log.info("[AGENT] Invoke result keys: {}", list(result.keys()) if isinstance(result, dict) else type(result).__name__)
        messages = result.get("messages", [])
        log.info("[AGENT] Invoke done messages_count={}", len(messages))
        candidate_strs: list[tuple[int, int, str]] = []
        for i, msg in enumerate(messages):
            kind = type(msg).__name__
            raw = getattr(msg, "content", None)
            if raw is None or (isinstance(raw, list) and not raw):
                extra = getattr(msg, "additional_kwargs", None) or {}
                if isinstance(extra, dict):
                    raw = extra.get("content") or extra.get("text")
                if raw is None and hasattr(msg, "response_metadata"):
                    meta = getattr(msg, "response_metadata", {}) or {}
                    raw = meta.get("content") if isinstance(meta, dict) else None
            # ToolMessage sometimes has content as list with one string (tool result)
            if (raw is None or (isinstance(raw, list) and len(raw) == 1)) and kind == "ToolMessage":
                c = getattr(msg, "content", None)
                if isinstance(c, list) and len(c) == 1:
                    first = c[0]
                    if isinstance(first, str):
                        raw = first
                    elif isinstance(first, dict) and (first.get("content") or first.get("text")):
                        raw = first.get("content") or first.get("text")
            if raw is None:
                has_tool_calls = getattr(msg, "tool_calls", None) or []
                log.info("[AGENT] message[{}] {} no content tool_calls={}", i, kind, len(has_tool_calls) if has_tool_calls else 0)
                continue
            text = _content_to_str(raw)
            if not text.strip():
                log.info("[AGENT] message[{}] {} content empty after flatten", i, kind)
                continue
            log.info("[AGENT] message[{}] {} content_len={} preview={!r}", i, kind, len(text), text[:120].replace("\n", " "))
            if "Analyze only station" in text and ("Menu graph" in text or "graph_metadata" in text):
                continue
            report_like = 1 if any(m in text for m in ("##", "**Meal period", "**What's working", "Playbook Alignment", "Overall Station", "Recommended Adjustments")) else 0
            candidate_strs.append((report_like, len(text), text))
        final_content = None
        if candidate_strs:
            candidate_strs.sort(key=lambda x: (x[0], x[1]), reverse=True)
            final_content = candidate_strs[0][2]
            log.info("[AGENT] Picked message report_like={} content_len={}", candidate_strs[0][0], candidate_strs[0][1])
        else:
            # Fallback: use longest non-user content (report often in last ToolMessage)
            for i in range(len(messages) - 1, -1, -1):
                msg = messages[i]
                if type(msg).__name__ == "HumanMessage":
                    continue
                raw = getattr(msg, "content", None)
                text = _content_to_str(raw) if raw else ""
                if text.strip() and len(text.strip()) > 100:
                    final_content = text
                    log.info("[AGENT] Fallback: using message[{}] content_len={}", i, len(text))
                    break
        report = _extract_markdown_from_content(final_content)
        log.info("[AGENT] run_analysis attempt={} report_len={}", attempt + 1, len(report or ""))
        if report and len(report.strip()) > 0:
            break
        if attempt == 0 and len(messages) <= 2:
            log.warning("[AGENT] Partial run (messages_count={}); will retry once", len(messages))
    try:
        from experiments.tools.llm_runner import get_usage_summary
        usage = get_usage_summary()
    except Exception as e:
        log.warning("[AGENT] get_usage_summary failed: {}", e)
        usage = {"total_input_tokens": 0, "total_output_tokens": 0, "cost_usd": 0.0, "call_count": 0}
    report = (report or "").strip()
    log.info("[AGENT] run_analysis END report_len={} usage={}", len(report or ""), usage)
    return {"content": report or "", "usage": usage}


if __name__ == "__main__":
    main()
