# Orchestrator Agent — Skills

Use the **`task`** tool to delegate work. Do not perform analysis yourself.

## Primary: `task` (subagent delegation)

- **subagent_type** (required): One of:
  - `menu-structure-agent` — structure and playbook validation
  - `data-integrity-agent` — period overlap / duplicate recipe checks
  - `rotation-recurrence-agent` — diversity index and item frequency
  - `nutrition-cost-agent` — sustainability mix and CPM risk/swaps
  - `synthesizer-agent` — format all prior outputs into executive summary for UI
- **description**: Full task instructions plus the menu graph JSON (or aggregated outputs for synthesizer). Be explicit so the subagent can run its tools and return structured results.

Call `task` in sequence: Structure → Integrity → Rotation → Nutrition/Cost → Synthesizer. Pass the synthesizer’s output through as the final answer.

## Supporting tools

- **routing_tasks** — Optional: record or confirm delegation (payload, target_agent).
- **aggregating_global_state** — Optional: merge a list of sub-agent outputs into one object before passing to the synthesizer.
