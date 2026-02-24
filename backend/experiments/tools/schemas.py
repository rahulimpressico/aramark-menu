"""
Strongly typed input/output schemas for all menu analysis tools.
Use these so stubs can be swapped from LLM-based to logic-based implementation without changing call sites.
"""
from typing import Any

from pydantic import BaseModel, Field

# MenuGraph is used in several signatures; import at runtime to avoid circular deps
# from experiments.models import MenuGraph  # use TYPE_CHECKING or pass as dict and validate in stub


# --- Orchestrator ---

class RoutingTasksInput(BaseModel):
    """Input for routing an analytical payload to a sub-agent."""
    payload: dict[str, Any] = Field(description="Analytical payload to send (e.g. menu_graph, options)")
    target_agent: str = Field(description="Target agent: menu-structure, data-integrity, rotation-recurrence, nutrition-cost, synthesizer")


class RoutingTasksOutput(BaseModel):
    """Result of delegating a task to a sub-agent."""
    success: bool = Field(description="Whether the delegation was accepted")
    task_id: str | None = Field(default=None, description="Optional task/run identifier")
    message: str = Field(default="", description="Status or error message")


class AggregatingGlobalStateInput(BaseModel):
    """Input for aggregating sub-agent outputs into global state."""
    sub_agent_outputs: list[dict[str, Any]] = Field(description="List of structured outputs from completed sub-agents")


class AggregatingGlobalStateOutput(BaseModel):
    """Aggregated global state from all sub-agents."""
    aggregated: dict[str, Any] = Field(description="Single object merging all sub-agent outputs by key/source")
    sources: list[str] = Field(default_factory=list, description="List of agent names that contributed")


# --- Menu Structure ---

class TransformingMenuGraphInput(BaseModel):
    """Input for transforming raw menu data into a menu graph."""
    raw_menu_data: str = Field(description="Raw menu text (CSV, PDF text, or unstructured) spanning weeks/days/meal periods")


class TransformingMenuGraphOutput(BaseModel):
    """Output of transforming raw menu data into a structured graph."""
    success: bool = Field(description="Whether transformation succeeded")
    menu_graph_dict: dict[str, Any] | None = Field(default=None, description="Standardized menu graph as dict (validate with MenuGraph.model_validate)")
    error: str | None = Field(default=None, description="Error message if success is False")


class CheckingPlaybookBoundsInput(BaseModel):
    """Input for checking a meal period against Fresh & Fast Playbook bounds."""
    meal_period: str = Field(description="Meal period name (e.g. Lunch, Dinner)")
    day_key: str = Field(description="Day identifier (e.g. Monday or date string)")


class CheckingPlaybookBoundsOutput(BaseModel):
    """Playbook compliance for a single meal period."""
    compliant: bool = Field(description="True if within playbook bounds (1 burger, 2 features, 1 vegan, fries)")
    under_offered: list[str] = Field(default_factory=list, description="Missing required elements (e.g. vegan option)")
    over_offered: list[str] = Field(default_factory=list, description="Excess elements (e.g. 4+ hot sandwiches)")
    counts: dict[str, int] = Field(default_factory=dict, description="Counts used for evaluation (burgers, features, vegan, fries)")
    message: str = Field(default="", description="Human-readable summary")


# --- Data Integrity ---

class DetectingPeriodOverlapInput(BaseModel):
    """Input for overlap detection (menu graph passed separately as MenuGraph)."""
    pass  # Only menu_graph is needed; use this for future options e.g. severity_threshold


class OverlapFinding(BaseModel):
    """A single finding of duplicate recipe across periods."""
    recipe_id: str = Field(description="Recipe ID that appears in multiple periods")
    recipe_name: str = Field(default="", description="Recipe name")
    periods: list[str] = Field(description="Meal period names where this recipe appears on the same day")
    day: str = Field(description="Day (e.g. Monday or date)")
    severity: str = Field(default="high", description="high | medium | low")


class DetectingPeriodOverlapOutput(BaseModel):
    """Output of period-overlap detection."""
    overlaps: list[OverlapFinding] = Field(default_factory=list, description="List of duplicate recipe findings")
    total_count: int = Field(default=0, description="Number of overlap findings")
    message: str = Field(default="", description="Summary for reporting")


# --- Rotation & Recurrence ---

class CalculatingDiversityIndexInput(BaseModel):
    """Input for diversity index (menu graph passed separately)."""
    pass


class CalculatingDiversityIndexOutput(BaseModel):
    """Grill Structural Diversity Index and related signals."""
    diversity_index: float = Field(description="Score (e.g. 0–1) from unique vs repeated items")
    unique_entree_count: int = Field(default=0, description="Count of unique entrées in cycle")
    repeated_static_count: int = Field(default=0, description="Count of repeated/static items")
    message: str = Field(default="", description="Interpretation (e.g. low monotony)")


class TrackingItemFrequencyInput(BaseModel):
    """Input for item frequency tracking."""
    recipe_ids: list[str] | None = Field(default=None, description="Specific recipe IDs to count; if None, analyze key proteins/items")


class ItemFrequency(BaseModel):
    """Frequency of one recipe across the cycle."""
    recipe_id: str = Field(description="Recipe ID")
    recipe_name: str = Field(default="", description="Recipe name")
    appearance_count: int = Field(description="Number of times scheduled in the cycle")
    days: list[str] = Field(default_factory=list, description="Days where it appears")


class TrackingItemFrequencyOutput(BaseModel):
    """Output of item frequency analysis."""
    frequencies: list[ItemFrequency] = Field(default_factory=list, description="Per-recipe counts")
    recurrence_signals: list[str] = Field(default_factory=list, description="e.g. High repetition of hamburger")
    message: str = Field(default="", description="Summary for Cost Agent")


# --- Nutrition & Cost ---

class EvaluatingSustainabilityMixInput(BaseModel):
    """Input for sustainability mix (menu graph passed separately)."""
    pass


class EvaluatingSustainabilityMixOutput(BaseModel):
    """44% plant-based compliance and mix metrics."""
    plant_based_percent: float = Field(description="Percentage of offerings that are plant-based")
    vegan_percent: float = Field(default=0.0, description="Percentage that are vegan")
    compliant_44: bool = Field(description="True if plant_based_percent >= 44")
    total_offerings: int = Field(default=0, description="Total recipe slots counted")
    plant_based_count: int = Field(default=0, description="Count of plant-based offerings")
    message: str = Field(default="", description="Compliance summary")


class CalculatingCpmRiskSwapsInput(BaseModel):
    """Input for CPM/beef-swap analysis."""
    recurrence_signals: dict[str, Any] | None = Field(default=None, description="Optional recurrence signals from Rotation agent")


class CalculatingCpmRiskSwapsOutput(BaseModel):
    """CPM risk and beef-swap recommendation."""
    beef_recurrence_high: bool = Field(description="True if beef appears too often")
    non_beef_alternatives_diversified: bool = Field(description="True if poultry/plant-based swaps are present")
    cpm_risk_level: str = Field(default="medium", description="low | medium | high")
    recommendations: list[str] = Field(default_factory=list, description="e.g. Swap one beef burger for turkey/black bean per week")
    message: str = Field(default="", description="Summary for Chef Tips")


# --- Synthesizer ---

class FormattingExecutiveSlideInput(BaseModel):
    """Input for executive slide formatting (aggregated state passed separately)."""
    pass


class FormattingExecutiveSlideOutput(BaseModel):
    """Executive summary as structured sections (can be rendered as markdown)."""
    overall_station_structure: str = Field(default="", description="Section 1: Overall Station Structure")
    alignment_whats_working: str = Field(default="", description="Section 2a: What you're doing well")
    alignment_needs_improvement: str = Field(default="", description="Section 2b: Where structure needs improvement")
    rotation_repetition_signals: str = Field(default="", description="Section 3: Rotation & Repetition Signals")
    recommended_structural_adjustments: str = Field(default="", description="Section 4: Recommended Structural Adjustments")
    full_markdown: str = Field(default="", description="Complete prose markdown for the slide")
