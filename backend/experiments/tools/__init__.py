"""
Stub tools for the menu analysis agents.
Implement each function in place; until then they raise NotImplementedError.
"""

from .stubs import (
    # Orchestrator
    routing_tasks,
    aggregating_global_state,
    # Menu Structure
    transforming_menu_graph,
    checking_playbook_bounds,
    # Data Integrity
    detecting_period_overlap,
    # Rotation & Recurrence
    calculating_diversity_index,
    tracking_item_frequency,
    # Nutrition & Cost
    evaluating_sustainability_mix,
    calculating_cpm_risk_swaps,
    # Synthesizer
    formatting_executive_slide,
)

__all__ = [
    "routing_tasks",
    "aggregating_global_state",
    "transforming_menu_graph",
    "checking_playbook_bounds",
    "detecting_period_overlap",
    "calculating_diversity_index",
    "tracking_item_frequency",
    "evaluating_sustainability_mix",
    "calculating_cpm_risk_swaps",
    "formatting_executive_slide",
]
