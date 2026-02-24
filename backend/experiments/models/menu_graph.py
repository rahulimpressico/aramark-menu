"""
MenuGraph as a knowledge graph (Node Linked Data Model).
Matches backend/experiments/menu_graph_v1.json. Traversable for agents to mine information.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, PrivateAttr, field_validator

from experiments.log_config import log


# --- Node types (discriminated by "type") ---

class StationNode(BaseModel):
    """Station node (e.g. Grill)."""
    id: str = Field(description="Node ID (e.g. Station_Grill)")
    type: Literal["Station"] = "Station"
    name: str = Field(description="Station name")


class DayNode(BaseModel):
    """Day node in the schedule."""
    id: str = Field(description="Node ID (e.g. Day_Monday)")
    type: Literal["Day"] = "Day"
    name: str = Field(description="Day name (e.g. Monday)")
    date: str = Field(description="Date string (e.g. 2026-02-23)")


class MealPeriodNode(BaseModel):
    """Meal period node (Breakfast, Lunch, Dinner, All Day)."""
    id: str = Field(description="Node ID (e.g. Period_Lunch)")
    type: Literal["MealPeriod"] = "MealPeriod"
    name: str = Field(description="Period name (e.g. Lunch)")


class RecipeNode(BaseModel):
    """Recipe node with full details."""
    id: str = Field(description="Node ID (e.g. Recipe_M8958)")
    type: Literal["Recipe"] = "Recipe"
    name: str = Field(description="Recipe display name")
    assembly_instructions: str = Field(default="", description="How to assemble/serve")
    special_instructions: str = Field(default="", description="IDDSI, portioning, etc.")
    ingredient_description: list[str] = Field(default_factory=list, description="Ingredient line items")


# Union of all node kinds (for parsing)
GraphNode = StationNode | DayNode | MealPeriodNode | RecipeNode


class GraphEdge(BaseModel):
    """Directed edge between two nodes."""
    source: str = Field(description="Source node ID")
    target: str = Field(description="Target node ID")
    relationship: str = Field(description="Relationship type (e.g. HAS_SCHEDULE, SERVES_RECIPE)")


class GraphMetadata(BaseModel):
    """Top-level graph metadata."""
    description: str = Field(default="", description="Graph description")
    version: str = Field(default="1.0", description="Schema version")
    cycle: str = Field(default="", description="Menu cycle identifier (e.g. FY25-26 - cycle 2 - week 3)")


def _parse_node(raw: dict[str, Any]) -> StationNode | DayNode | MealPeriodNode | RecipeNode:
    """Parse a raw node dict into the correct typed node."""
    t = raw.get("type")
    if t == "Station":
        return StationNode.model_validate(raw)
    if t == "Day":
        return DayNode.model_validate(raw)
    if t == "MealPeriod":
        return MealPeriodNode.model_validate(raw)
    if t == "Recipe":
        return RecipeNode.model_validate(raw)
    raise ValueError(f"Unknown node type: {t}")


class MenuGraph(BaseModel):
    """
    Knowledge graph of menu data: nodes (Station, Day, MealPeriod, Recipe) and edges.
    Traversable so agents can mine relevant information.
    """
    graph_metadata: GraphMetadata = Field(default_factory=GraphMetadata)
    nodes: list[StationNode | DayNode | MealPeriodNode | RecipeNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)

    @field_validator("nodes", mode="before")
    @classmethod
    def _parse_nodes(cls, v: Any) -> list[Any]:
        if isinstance(v, list):
            return [_parse_node(x) if isinstance(x, dict) else x for x in v]
        return v

    # Indexes for traversal (not persisted)
    _by_id: dict[str, StationNode | DayNode | MealPeriodNode | RecipeNode] = PrivateAttr(default_factory=dict)
    _by_type: dict[str, list[Any]] = PrivateAttr(default_factory=dict)
    _outgoing: dict[str, list[GraphEdge]] = PrivateAttr(default_factory=dict)
    _incoming: dict[str, list[GraphEdge]] = PrivateAttr(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        self._build_indexes()

    def _build_indexes(self) -> None:
        """Build lookup indexes for traversal."""
        log.debug("Building MenuGraph indexes nodes={} edges={}", len(self.nodes), len(self.edges))
        self._by_id = {}
        self._by_type = {}
        for n in self.nodes:
            self._by_id[n.id] = n
            t = n.type
            if t not in self._by_type:
                self._by_type[t] = []
            self._by_type[t].append(n)
        self._outgoing = {}
        self._incoming = {}
        for e in self.edges:
            if e.source not in self._outgoing:
                self._outgoing[e.source] = []
            self._outgoing[e.source].append(e)
            if e.target not in self._incoming:
                self._incoming[e.target] = []
            self._incoming[e.target].append(e)

    # --- Traversal / mining API ---

    def get_node(self, node_id: str) -> StationNode | DayNode | MealPeriodNode | RecipeNode | None:
        """Return the node with the given id, or None."""
        return self._by_id.get(node_id)

    def get_nodes_by_type(self, node_type: Literal["Station", "Day", "MealPeriod", "Recipe"]) -> list[Any]:
        """Return all nodes of the given type."""
        return self._by_type.get(node_type, [])

    def get_station(self) -> StationNode | None:
        """Return the single Station node, if any."""
        stations = self.get_nodes_by_type("Station")
        return stations[0] if stations else None

    def get_days(self) -> list[DayNode]:
        """Return all Day nodes (order preserved from graph)."""
        return list(self.get_nodes_by_type("Day"))

    def get_meal_periods(self) -> list[MealPeriodNode]:
        """Return all MealPeriod nodes."""
        return list(self.get_nodes_by_type("MealPeriod"))

    def get_recipes(self) -> list[RecipeNode]:
        """Return all Recipe nodes."""
        return list(self.get_nodes_by_type("Recipe"))

    def get_recipe(self, recipe_id: str) -> RecipeNode | None:
        """Return a Recipe node by id (e.g. Recipe_M8958 or M8958)."""
        if recipe_id in self._by_id:
            n = self._by_id[recipe_id]
            if n.type == "Recipe":
                return n
        # Allow lookup by short id
        candidate = f"Recipe_{recipe_id}" if not recipe_id.startswith("Recipe_") else recipe_id
        n = self._by_id.get(candidate)
        return n if n and getattr(n, "type", None) == "Recipe" else None

    def get_edges_from(self, source_id: str) -> list[GraphEdge]:
        """Return all edges whose source is the given node (outgoing)."""
        return list(self._outgoing.get(source_id, []))

    def get_edges_to(self, target_id: str) -> list[GraphEdge]:
        """Return all edges whose target is the given node (incoming)."""
        return list(self._incoming.get(target_id, []))

    def count_outgoing(self, node_id: str) -> int:
        """Total number of outgoing edges from the node."""
        return len(self._outgoing.get(node_id, []))

    def count_incoming(self, node_id: str) -> int:
        """Total number of incoming edges to the node."""
        return len(self._incoming.get(node_id, []))

    def recipe_serve_count(self, recipe_id: str) -> int:
        """
        How often a recipe is served (total incoming edges to that recipe node).
        Each incoming edge corresponds to one (day, meal period) where the recipe is offered.
        """
        node_id = recipe_id if recipe_id.startswith("Recipe_") else f"Recipe_{recipe_id}"
        return self.count_incoming(node_id)

    def period_variety_count(self, period_id: str) -> int:
        """
        Variety offered in a meal period (total outgoing edges from that period node).
        Each outgoing edge is one recipe served in that period.
        """
        return self.count_outgoing(period_id)

    def get_targets(self, source_id: str, relationship: str | None = None) -> list[str]:
        """Return target node ids for outgoing edges from source_id, optionally filtered by relationship."""
        out = self._outgoing.get(source_id, [])
        if relationship:
            out = [e for e in out if e.relationship == relationship]
        return [e.target for e in out]

    def get_sources(self, target_id: str, relationship: str | None = None) -> list[str]:
        """Return source node ids for incoming edges to target_id, optionally filtered by relationship."""
        inc = self._incoming.get(target_id, [])
        if relationship:
            inc = [e for e in inc if e.relationship == relationship]
        return [e.source for e in inc]

    def get_days_for_station(self) -> list[DayNode]:
        """Return Day nodes linked from the station via HAS_SCHEDULE."""
        station = self.get_station()
        if not station:
            return []
        day_ids = self.get_targets(station.id, "HAS_SCHEDULE")
        return [n for did in day_ids if (n := self.get_node(did)) is not None]

    def get_periods_for_day(self, day_id: str) -> list[MealPeriodNode]:
        """Return MealPeriod nodes linked from the day via HAS_PERIOD."""
        period_ids = self.get_targets(day_id, "HAS_PERIOD")
        return [n for pid in period_ids if (n := self.get_node(pid)) is not None and n.type == "MealPeriod"]

    def get_recipes_for_period(self, period_id: str) -> list[RecipeNode]:
        """Return Recipe nodes linked from the period via SERVES_RECIPE."""
        recipe_ids = self.get_targets(period_id, "SERVES_RECIPE")
        return [n for rid in recipe_ids if (n := self.get_node(rid)) is not None and n.type == "Recipe"]

    def get_recipes_for_day_and_period(self, day_id: str, period_name: str) -> list[RecipeNode]:
        """Return recipes served in a given day and period name (e.g. Monday, Lunch)."""
        periods = self.get_periods_for_day(day_id)
        for p in periods:
            if p.name == period_name:
                return self.get_recipes_for_period(p.id)
        return []

    def list_recipe_ids_in_period(self, period_id: str) -> list[str]:
        """List recipe node ids served in a period (for overlap/diversity logic)."""
        return [r.id for r in self.get_recipes_for_period(period_id)]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON or state (nodes + edges; indexes are not serialized)."""
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MenuGraph":
        """Build from a dict (e.g. from JSON). Validates and builds traversal indexes."""
        return cls.model_validate(data)

    @classmethod
    def from_json_path(cls, path: str | Path) -> "MenuGraph":
        """Load from a JSON file path (Node Linked Data Model, e.g. menu_graph_v1.json)."""
        path = Path(path)
        log.debug("Loading MenuGraph from path={}", path)
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        g = cls.model_validate(data)
        log.debug("MenuGraph loaded nodes={} edges={}", len(g.nodes), len(g.edges))
        return g


# --- Backward compatibility: recipe_id from Recipe node id (e.g. Recipe_M8958 -> M8958) ---

def recipe_id_from_node_id(node_id: str) -> str:
    """Extract short recipe id from Recipe node id (Recipe_M8958 -> M8958)."""
    if node_id.startswith("Recipe_"):
        return node_id[7:]
    return node_id
