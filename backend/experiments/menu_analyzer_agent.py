"""
Collegiate Dining Menu Analyzer — Deep Agent (PoC).

Orchestrator + 3 perspective-based subagents: Operator (operations), Nutritionist (nutrition/sustainability),
Synthesizer. Each sub-agent plans from its standpoint then executes with its tools. Uses create_deep_agent.
Tools take MenuGraph (or dict/JSON string) where applicable; see experiments.models.MenuGraph.

Run from backend directory:
  uv sync --extra experiments && uv run python -m experiments.menu_analyzer_agent

Or invoke programmatically with a loaded graph:
  from experiments.menu_analyzer_agent import create_menu_analyzer_agent, get_default_menu_graph
  agent = create_menu_analyzer_agent()
  graph = get_default_menu_graph()  # MenuGraph from menu_graph.json
  result = agent.invoke({"messages": [{"role": "user", "content": f"Analyze this Grill menu. Menu graph (JSON): {graph.model_dump_json()}"}]})  # graph is traversable (nodes/edges)
"""

from pathlib import Path
import os

from deepagents import create_deep_agent

from experiments.callbacks import AgentOutputLoggingCallback
from experiments.log_config import log
from experiments.models.menu_graph import MenuGraph
from experiments.prompts import (
    get_nutrition_cost_prompt,
    get_operator_prompt,
    get_orchestrator_prompt,
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
    Build the Menu Analyzer deep agent with orchestrator and 3 perspective-based subagents.

    - Orchestrator: delegates to Operator, then Nutritionist, then Synthesizer.
    - Operator: plans from operations standpoint (structure, playbook, integrity, rotation), then executes with its tools.
    - Nutritionist: plans from nutrition/sustainability standpoint, then executes with sustainability and CPM tools.
    - Synthesizer: plans what to emphasise, then formats aggregated outputs into executive summary markdown.
    """
    # Use google_genai: prefix so LangChain uses ChatGoogleGenerativeAI (Gemini Developer API),
    # not ChatVertexAI (Vertex AI). See GOOGLE_API_KEY in README.
    model = model or "google_genai:gemini-2.5-flash"
    log.info("Creating menu analyzer agent model={}", model)
    # Perspective-based sub-agents: each plans from its standpoint then executes with its tools.
    subagents = [
        {
            "name": "operator-agent",
            "description": "Analyses the menu from an operations standpoint: structure, playbook compliance, data integrity (overlap detection), and rotation/variety (diversity index, item frequency). Plans then executes using structure, playbook, overlap, diversity, and frequency tools.",
            "system_prompt": get_operator_prompt(),
            "tools": [
                transforming_menu_graph,
                checking_playbook_bounds,
                detecting_period_overlap,
                calculating_diversity_index,
                tracking_item_frequency,
            ],
            "model": model,
        },
        {
            "name": "nutritionist-agent",
            "description": "Analyses the menu from a nutrition and sustainability standpoint: 44% plant-based compliance, sustainability mix, and CPM/Chef Tips (e.g. beef swap). Plans then executes using sustainability and CPM tools.",
            "system_prompt": get_nutrition_cost_prompt(),
            "tools": [evaluating_sustainability_mix, calculating_cpm_risk_swaps],
            "model": model,
        },
        {
            "name": "synthesizer-agent",
            "description": "Turns aggregated Operator and Nutritionist outputs into a business-ready markdown summary: Overall Structure, Playbook alignment, Rotation signals, Recommended Adjustments. Plans what to emphasise then calls formatting tool.",
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
            "operator-agent (operations), then nutritionist-agent (nutrition/sustainability), "
            "then synthesizer-agent. Pass the menu graph below in each task description as needed. "
            "Return the synthesizer's executive summary as your final response for UI.\n\n"
            "Menu graph (JSON):\n"
            + graph.model_dump_json()
        )
    log.debug("Invoking agent with user message len={}", len(user_content))
    # Langfuse tracing + console log of each agent's output (first 50 words)
    config: dict = {}
    callbacks_list: list = []
    callbacks_list.append(AgentOutputLoggingCallback())
    try:
        from langfuse.langchain import CallbackHandler
        langfuse_handler = CallbackHandler()
        callbacks_list.append(langfuse_handler)
        log.info("Langfuse tracing enabled; traces will appear in Langfuse")
    except ImportError:
        log.debug("langfuse not installed; run with uv sync --extra experiments for tracing")
    except Exception as e:
        log.warning("Langfuse callback not used: {}", e)
    config["callbacks"] = callbacks_list

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
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path_ts = REPORTS_DIR / f"menu_report_{timestamp}.md"
    path_latest = REPORTS_DIR / "menu_report_latest.md"
    for path in (path_ts, path_latest):
        path.write_text(markdown_text, encoding="utf-8")
        log.info("Report saved to {}", path)


if __name__ == "__main__":
    main()
