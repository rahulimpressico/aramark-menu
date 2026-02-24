# Orchestrator Agent — Skills

Use the **`task`** tool to delegate work. Do not perform analysis yourself.

## Primary: `task` (subagent delegation)

- **subagent_type** (required): One of:
  - `operator-agent` — operations: structure, playbook, data integrity, rotation/variety (plans then executes with its tools)
  - `nutritionist-agent` — nutrition/sustainability: 44% plant-based, CPM/Chef Tips (plans then executes with its tools)
  - `synthesizer-agent` — format Operator + Nutritionist outputs into executive summary for UI
- **description**: Full task instructions plus the menu graph JSON (or for synthesizer, the aggregated JSON with keys `operator` and `nutrition_cost`). Be explicit so the subagent can plan and execute.

Call `task` in sequence: operator-agent → nutritionist-agent → synthesizer-agent. Pass the synthesizer’s output through as the final answer.

## Supporting tools

- **routing_tasks** — Optional: record or confirm delegation (payload, target_agent).
- **aggregating_global_state** — Optional: merge a list of sub-agent outputs into one object before passing to the synthesizer.
