# Menu Analysis PoC — Experiments

This folder is the **proof-of-concept** for the Collegiate Dining Agentic AI Menu Analyzer. Once the experiment reaches conclusion, implementation will move into the main backend app.

## Layout

- **`agents/`** — One folder per agent, each with:
  - `system_prompt.txt` — XML-style system prompt
  - `SKILLS.md` — Skill names and when to use them (no implementation here)
- **`tools/`** — Stub tools for all skills; implement in `tools/stubs.py` one by one.
- **`prompts.py`** — Loads system prompts from `agents/*/system_prompt.txt`.
- **`menu_analyzer_agent.py`** — Main entry: `create_deep_agent` with orchestrator + 5 subagents.
- **`notebooks/MenuGraph_Visualisation.ipynb`** — Tree visualisation: **Grill → Days → Meal periods (Breakfast, Lunch, Dinner, All Day) → Recipes**. Uses **`menu_graph.json`** as source (no data loss). Helper: `notebooks/menu_tree_loader.py`.
- **`menu_graph_v1.json`** — Grill station as a **knowledge graph** (Node Linked Data Model): `graph_metadata`, `nodes` (Station, Day, MealPeriod, Recipe), `edges` (HAS_SCHEDULE, HAS_PERIOD, SERVES_RECIPE). The **`MenuGraph`** class in `models/menu_graph.py` loads this and is **traversable** so agents can mine it (e.g. `get_days()`, `get_periods_for_day()`, `get_recipes_for_period()`).

## Agents (from Project Implementation Plan)

1. **Orchestrator** — Routes to Structure first, then Integrity / Rotation / Cost, then Synthesizer; aggregates state.
2. **Menu Structure** — Transform raw menu → JSON; check Fresh & Fast Playbook bounds.
3. **Data Integrity** — Detect recipe ID overlaps across meal periods.
4. **Rotation & Recurrence** — Diversity index and item frequency.
5. **Nutrition & Cost** — Sustainability mix (44% plant-based), CPM/beef-swap checks.
6. **Synthesizer** — Format aggregated JSON into executive markdown summary.

## Logging

Logging uses **loguru**. Call `configure_experiments_logging()` (e.g. in `main()`) to set level and format; otherwise the default handler is used. Set **`LOG_LEVEL`** (e.g. `DEBUG`, `INFO`, `WARNING`, `ERROR`) to control verbosity. Logs are emitted from `menu_analyzer_agent`, `tools/stubs`, `tools/llm_runner`, and `models/menu_graph` for debugging.

## Run

From `backend` (dependencies managed by uv):

```bash
cd backend
uv sync --extra experiments   # install app + experiment deps
uv run python -m experiments.menu_analyzer_agent
```

Or use programmatically:

```python
from experiments.menu_analyzer_agent import create_menu_analyzer_agent
agent = create_menu_analyzer_agent()
result = agent.invoke({"messages": [{"role": "user", "content": "Analyze the Grill menu."}]})
```

## MenuGraph as a knowledge graph

`MenuGraph` (from `menu_graph_v1.json`) is a **traversable** graph. Use it to mine information:

- **By type:** `get_station()`, `get_days()`, `get_meal_periods()`, `get_recipes()`, `get_recipe(recipe_id)`
- **By structure:** `get_days_for_station()`, `get_periods_for_day(day_id)`, `get_recipes_for_period(period_id)`, `get_recipes_for_day_and_period(day_id, period_name)`
- **Edges:** `get_edges_from(source_id)`, `get_edges_to(target_id)`, `get_targets(source_id, relationship)`, `get_sources(target_id, relationship)`

Agents (or programmable logic) can use these instead of scanning raw JSON.

## Implementing skills

Stubs in `tools/stubs.py` use LLM calls for a first draft; inputs/outputs are strongly typed in `tools/schemas.py`. Replace with programmable logic that uses the same types and the `MenuGraph` traversal API when moving from PoC to production.
