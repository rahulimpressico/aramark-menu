"""
STEP 3 — GRAPH BUILDER
NormalizedRecipe objects le kar deterministic knowledge graph banao.

Node types:  Station → Week → Day → MealPeriod
             Recipe  → Station (BELONGS_TO_STATION)
             Recipe  → Day     (SCHEDULED_ON, attrs: week_no, period)
             Recipe  → MealPeriod (SERVED_IN_PERIOD — summary, deduplicated)
             Recipe  → Ingredient (USES_INGREDIENT)

Determinism guarantees:
  - Same input → same node IDs
  - Nodes sorted by id before output
  - Relations sorted by (from_id, predicate, to_id)
"""

from schema import (
    StationEntity,
    WeekEntity,
    DayEntity,
    MealPeriodEntity,
    RecipeEntity,
    IngredientEntity,
    Relation,
    DAY_NUMBER_TO_NAME,
)
from normalizer import NormalizedRecipe, make_ingredient_id


# ---------------------------------------------------------------------------
# Graph container
# ---------------------------------------------------------------------------

class KnowledgeGraph:
    def __init__(self):
        self._stations:    dict[str, StationEntity]    = {}
        self._weeks:       dict[str, WeekEntity]       = {}
        self._days:        dict[str, DayEntity]        = {}
        self._periods:     dict[str, MealPeriodEntity] = {}
        self._recipes:     dict[str, RecipeEntity]     = {}
        self._ingredients: dict[str, IngredientEntity] = {}
        self._relations:   list[Relation]              = []
        self._rel_set:     set[tuple]                  = set()

    # --- node adders (idempotent) ---

    def add_station(self, name: str) -> str:
        nid = f"station_{name}"
        if nid not in self._stations:
            self._stations[nid] = StationEntity(id=nid, name=name)
        return nid

    def add_week(self, week_no: int) -> str:
        nid = f"week_{week_no}"
        if nid not in self._weeks:
            self._weeks[nid] = WeekEntity(id=nid, week_no=week_no)
        return nid

    def add_day(self, day_no: int, week_no: int) -> str:
        day_name = DAY_NUMBER_TO_NAME.get(day_no, f"Day{day_no}")
        nid = f"day_{day_name}"
        if nid not in self._days:
            self._days[nid] = DayEntity(
                id=nid, day_name=day_name, day_no=day_no, week_no=week_no
            )
        return nid

    def add_period(self, name: str) -> str:
        nid = f"period_{name}"
        if nid not in self._periods:
            self._periods[nid] = MealPeriodEntity(id=nid, name=name)
        return nid

    def add_recipe(self, r: NormalizedRecipe) -> str:
        nid = r.recipe_id
        if nid not in self._recipes:
            self._recipes[nid] = RecipeEntity(
                id=nid,
                name=r.recipe_name,
                food_cost=r.food_cost,
                assembly_instructions=r.assembly_instructions,
                special_instructions=r.special_instructions,
            )
        return nid

    def add_ingredient(self, description: str) -> str:
        nid = make_ingredient_id(description)
        if nid not in self._ingredients:
            self._ingredients[nid] = IngredientEntity(id=nid, description=description)
        return nid

    def add_relation(self, rel: Relation):
        key = (rel.from_id, rel.predicate, rel.to_id)
        if key not in self._rel_set:
            self._rel_set.add(key)
            self._relations.append(rel)

    # --- validation ---

    def validate(self) -> list[str]:
        issues = []
        all_ids = (
            set(self._stations) | set(self._weeks) | set(self._days)
            | set(self._periods) | set(self._recipes) | set(self._ingredients)
        )
        for node in list(self._stations.values()):    issues.extend(node.validate())
        for node in list(self._weeks.values()):       issues.extend(node.validate())
        for node in list(self._days.values()):        issues.extend(node.validate())
        for node in list(self._periods.values()):     issues.extend(node.validate())
        for node in list(self._recipes.values()):     issues.extend(node.validate())
        for node in list(self._ingredients.values()): issues.extend(node.validate())
        for rel in self._relations:
            issues.extend(rel.validate())
            if rel.from_id not in all_ids:
                issues.append(f"Dangling relation source: '{rel.from_id}'")
            if rel.to_id not in all_ids:
                issues.append(f"Dangling relation target: '{rel.to_id}'")
        return issues

    # --- serialization ---

    def to_dict(self) -> dict:
        def _node(e) -> dict:
            d = {"id": e.id, "type": e.node_type}
            if hasattr(e, "name"):            d["name"]            = e.name
            if hasattr(e, "week_no"):         d["week_no"]         = e.week_no
            if hasattr(e, "day_no"):          d["day_no"]          = e.day_no
            if hasattr(e, "day_name") and e.node_type == "Day":
                                              d["day_name"]        = e.day_name
            if hasattr(e, "recipe_name") and e.node_type == "Recipe":
                                              d["recipe_name"]     = e.recipe_name
            if hasattr(e, "food_cost"):       d["food_cost"]       = e.food_cost
            if hasattr(e, "assembly_instructions"):
                                              d["assembly_instructions"] = e.assembly_instructions
            if hasattr(e, "special_instructions") and e.special_instructions:
                                              d["special_instructions"] = e.special_instructions
            if hasattr(e, "description"):     d["description"]     = e.description
            return d

        def _rel(r: Relation) -> dict:
            d = {
                "from_type": r.from_type, "from_id": r.from_id,
                "predicate": r.predicate,
                "to_type":   r.to_type,   "to_id":   r.to_id,
            }
            if r.attributes:
                d["attributes"] = r.attributes
            return d

        return {
            "entities": {
                "Station":    [_node(e) for e in sorted(self._stations.values(),    key=lambda x: x.id)],
                "Week":       [_node(e) for e in sorted(self._weeks.values(),       key=lambda x: x.id)],
                "Day":        [_node(e) for e in sorted(self._days.values(),        key=lambda x: x.day_no)],
                "MealPeriod": [_node(e) for e in sorted(self._periods.values(),     key=lambda x: x.id)],
                "Recipe":     [_node(e) for e in sorted(self._recipes.values(),     key=lambda x: x.id)],
                "Ingredient": [_node(e) for e in sorted(self._ingredients.values(), key=lambda x: x.id)],
            },
            "relations": [
                _rel(r)
                for r in sorted(self._relations, key=lambda r: (r.from_id, r.predicate, r.to_id))
            ],
        }

    @property
    def counts(self) -> dict:
        return {
            "stations":    len(self._stations),
            "weeks":       len(self._weeks),
            "days":        len(self._days),
            "meal_periods": len(self._periods),
            "recipes":     len(self._recipes),
            "ingredients": len(self._ingredients),
            "relations":   len(self._relations),
        }


# ---------------------------------------------------------------------------
# Build function
# ---------------------------------------------------------------------------

def build_graph(station_name: str, recipes: list[NormalizedRecipe]) -> KnowledgeGraph:
    """
    Deterministic: same input → same output regardless of order.

    Graph structure:
      Station ──HAS_WEEK──▶ Week ──HAS_DAY──▶ Day ──HAS_PERIOD──▶ MealPeriod
      Recipe  ──BELONGS_TO_STATION──▶ Station
      Recipe  ──SCHEDULED_ON──▶ Day        (attrs: week_no, period)
      Recipe  ──SERVED_IN_PERIOD──▶ MealPeriod  (summary)
      Recipe  ──USES_INGREDIENT──▶ Ingredient
    """
    kg = KnowledgeGraph()
    station_id = kg.add_station(station_name)

    for r in recipes:
        recipe_id = kg.add_recipe(r)

        # Recipe → Station
        kg.add_relation(Relation(
            from_type="Recipe", from_id=recipe_id,
            predicate="BELONGS_TO_STATION",
            to_type="Station",  to_id=station_id,
        ))

        # Schedule: Week → Day → MealPeriod hierarchy + Recipe → Day
        seen_periods: set[str] = set()
        for entry in r.schedule:
            # Week node + Station → Week
            week_id = kg.add_week(entry.week_no)
            kg.add_relation(Relation(
                from_type="Station", from_id=station_id,
                predicate="HAS_WEEK",
                to_type="Week",    to_id=week_id,
            ))

            # Day node + Week → Day
            day_id = kg.add_day(entry.day_no, entry.week_no)
            kg.add_relation(Relation(
                from_type="Week", from_id=week_id,
                predicate="HAS_DAY",
                to_type="Day",    to_id=day_id,
            ))

            # MealPeriod node + Day → MealPeriod
            period_id = kg.add_period(entry.period)
            kg.add_relation(Relation(
                from_type="Day",       from_id=day_id,
                predicate="HAS_PERIOD",
                to_type="MealPeriod",  to_id=period_id,
            ))

            # Recipe → Day (with week_no + period as attributes)
            kg.add_relation(Relation(
                from_type="Recipe", from_id=recipe_id,
                predicate="SCHEDULED_ON",
                to_type="Day",      to_id=day_id,
                attributes={"week_no": entry.week_no, "period": entry.period},
            ))

            # Recipe → MealPeriod (summary, deduplicated)
            if entry.period not in seen_periods:
                seen_periods.add(entry.period)
                kg.add_relation(Relation(
                    from_type="Recipe",     from_id=recipe_id,
                    predicate="SERVED_IN_PERIOD",
                    to_type="MealPeriod",   to_id=period_id,
                ))

        # Recipe → Ingredient
        for ing_desc in r.ingredients:
            ing_id = kg.add_ingredient(ing_desc)
            kg.add_relation(Relation(
                from_type="Recipe",     from_id=recipe_id,
                predicate="USES_INGREDIENT",
                to_type="Ingredient",   to_id=ing_id,
            ))

    return kg
