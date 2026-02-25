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

from dotenv import load_dotenv
from deepagents import create_deep_agent

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

# Default path: Node Linked Data Model (knowledge graph)
EXPERIMENTS_DIR = Path(__file__).parent
DEFAULT_MENU_GRAPH_PATH = EXPERIMENTS_DIR / "menu_graph_v1.json"
REPORTS_DIR = EXPERIMENTS_DIR/"reports"
from dotenv import load_dotenv
load_dotenv()
# GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
# LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
# LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
# LANGFUSE_BASE_URL = os.getenv("LANGFUSE_BASE_URL")


def get_default_menu_graph() -> MenuGraph:
    """Load the Grill station knowledge graph from experiments/menu_graph_v1.json."""
    log.debug("Loading menu graph from path={}", DEFAULT_MENU_GRAPH_PATH)
    graph = MenuGraph.from_json_path(DEFAULT_MENU_GRAPH_PATH)
    log.info("Loaded MenuGraph nodes={} edges={}", len(graph.nodes), len(graph.edges))
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
    log.info("Creating menu analyzer agent model={}", model)
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


def main():
    """Create agent and run a single example invocation (optional)."""
    from experiments.log_config import configure_experiments_logging
    configure_experiments_logging()
    log.info("Starting menu analyzer agent main()")
    agent = create_menu_analyzer_agent(model="google_genai:gemini-2.5-flash")
    menu_graph_path = DEFAULT_MENU_GRAPH_PATH
    if not menu_graph_path.exists():
        print(f"Menu graph not found at {menu_graph_path}; use a query that provides menu data.")
        user_content = "Describe what analysis you would perform on a Grill station menu once the menu graph is loaded."
    else:
        graph = get_default_menu_graph()
        # Instruct orchestrator to use task tool only; include graph so it can pass to subagents
        user_content = (
            "Analyze the Grill station menu. Use your task tool to delegate in order: "
            "menu-structure-agent, then data-integrity-agent, rotation-recurrence-agent, nutrition-cost-agent, "
            "then synthesizer-agent. Pass the menu graph below in each task description as needed. "
            "Return the synthesizer's executive summary as your final response for UI.\n\n"
            "Menu graph (JSON):\n"
            + graph.model_dump_json()
        )
    log.debug("Invoking agent with user message len={}", len(user_content))
    # Langfuse tracing: pass callback so tool/LLM traces appear in Langfuse (set LANGFUSE_SECRET_KEY, LANGFUSE_PUBLIC_KEY, LANGFUSE_BASE_URL)
    config: dict = {}
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
    log.info("Agent invoke completed messages_count={}", len(messages))
    # Extract final assistant message (synthesizer output); content may be str or list of blocks
    from langchain_core.messages import AIMessage
    final_content = None
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            final_content = msg.content
            break
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


def _extract_markdown_from_content(content: str | list | None) -> str:
    """Extract plain markdown string from final message content (may be list of blocks)."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                return block.get("text") or ""
            if hasattr(block, "get") and block.get("type") == "text":
                return block.get("text") or ""
        return ""
    return str(content)


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


if __name__ == "__main__":
    main()
