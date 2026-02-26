import json
import re
import uuid
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

EXPERIMENTS_DIR = Path(__file__).resolve().parents[1]
INPUT_PATH = EXPERIMENTS_DIR / "menu_graph_v1.json"
OUTPUT_PATH = EXPERIMENTS_DIR / "menu_graph_v2_extracted.json"
REVIEW_PATH = EXPERIMENTS_DIR / "ingredient_merge_review.json"

ALIASES = {
    "beef gd patty": "beef ground patty",
    "beef ground patty 75 25": "beef ground patty",
    "pickle dill sliced": "dill pickle slice",
}

VENDOR_PACKAGING_TOKENS = {
    "sysco",
    "fz",
    "ap",
    "rs",
    "ct",
    "oz",
    "lb",
    "lbs",
    "g",
    "kg",
    "ml",
    "xl",
    "xxl",
    "bulk",
    "fresh",
    "frozen",
}

PREP_STATE_TOKENS = {
    "raw",
    "cooked",
    "thawed",
    "diced",
    "sliced",
    "shredded",
    "crumbled",
    "fried",
    "deep",
    "fat",
    "cut",
    "cored",
    "refuse",
    "removed",
}

UNIT_TOKENS = {"oz", "g", "lb", "lbs", "kg", "ml", "ct", "inch", "in"}

UTENSIL_KEYWORDS = {
    "grill": "grill",
    "char grill": "grill",
    "griddle": "griddle",
    "fryer": "fryer",
    "deep fat fryer": "fryer",
    "convection oven": "oven",
    "oven": "oven",
    "panini press": "panini_press",
    "stockpot": "stockpot",
    "skillet": "skillet",
    "steam table": "steam_table",
}

HIGH_CONFIDENCE_THRESHOLD = 0.90
REVIEW_THRESHOLD = 0.75


@dataclass
class IngredientRecord:
    raw_text: str
    normalized_name: str
    quantity: str | None
    states: list[str]


def node_id(prefix: str, key: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_]+", "_", key.strip()).strip("_")
    return f"{prefix}_{safe}" if safe else f"{prefix}_{uuid.uuid4().hex[:8]}"


def singularize(token: str) -> str:
    if len(token) <= 3:
        return token
    if token.endswith("ies"):
        return token[:-3] + "y"
    if token.endswith("ses"):
        return token[:-2]
    if token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def tokenize(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[^a-z0-9/\\s-]", " ", text)
    text = text.replace("-", " ")
    tokens = re.split(r"\s+", text.strip())
    cleaned: list[str] = []
    for tok in tokens:
        if not tok:
            continue
        if tok.isdigit():
            continue
        if re.fullmatch(r"\d+x\d+", tok):
            continue
        if re.fullmatch(r"\d+(\.\d+)?", tok):
            continue
        if tok in UNIT_TOKENS:
            continue
        if tok in VENDOR_PACKAGING_TOKENS:
            continue
        if tok in PREP_STATE_TOKENS:
            continue
        cleaned.append(singularize(tok))
    return cleaned


def normalize_name(raw: str) -> str:
    parts = re.split(r"\s*/\s*", raw.strip())
    base = parts[0] if parts else raw
    tokens = tokenize(base)
    if not tokens:
        return ""
    stable = sorted(tokens)
    name = " ".join(stable)
    return ALIASES.get(name, name)


def parse_quantity(raw: str) -> str | None:
    match = re.search(r"\b(\d+(?:\.\d+)?)\s*(oz|g|lb|lbs|kg|ml)\b", raw, re.IGNORECASE)
    if not match:
        return None
    unit = match.group(2).upper()
    return f"{match.group(1)} {unit}"


def parse_states(raw: str) -> list[str]:
    state_part = re.split(r"\s*/\s*", raw)
    if len(state_part) <= 1:
        return []
    states = [s.strip().lower() for s in state_part[1:] if s.strip()]
    return sorted(set(states))


def normalize_ingredient(raw: str) -> IngredientRecord:
    return IngredientRecord(
        raw_text=raw,
        normalized_name=normalize_name(raw),
        quantity=parse_quantity(raw),
        states=parse_states(raw),
    )


def text_similarity(a: str, b: str) -> float:
    seq = SequenceMatcher(None, a, b).ratio()
    a_set = set(a.split())
    b_set = set(b.split())
    if not a_set or not b_set:
        token_overlap = 0.0
    else:
        token_overlap = len(a_set & b_set) / len(a_set | b_set)
    containment = 1.0 if (a in b or b in a) else 0.0
    return 0.55 * seq + 0.35 * token_overlap + 0.10 * containment


def canonicalize_names(names: list[str]) -> tuple[dict[str, str], list[dict]]:
    counts = Counter(names)
    ordered = sorted(counts.keys(), key=lambda n: (-counts[n], len(n), n))

    canonical_map: dict[str, str] = {}
    clusters: list[str] = []
    review: list[dict] = []

    for name in ordered:
        best_match = None
        best_score = 0.0
        for candidate in clusters:
            score = text_similarity(name, candidate)
            if score > best_score:
                best_score = score
                best_match = candidate

        if best_match and best_score >= HIGH_CONFIDENCE_THRESHOLD:
            canonical_map[name] = best_match
        else:
            canonical_map[name] = name
            clusters.append(name)
            if best_match and best_score >= REVIEW_THRESHOLD:
                review.append(
                    {
                        "candidate": name,
                        "closest_canonical": best_match,
                        "score": round(best_score, 4),
                        "action": "not_merged_auto",
                    }
                )

    return canonical_map, review


def extract_utensils(text: str) -> list[str]:
    found = set()
    lower_text = (text or "").lower()
    for keyword, utensil in UTENSIL_KEYWORDS.items():
        if keyword in lower_text:
            found.add(utensil)
    return sorted(found)


def ensure_full_week_period_edges(
    base_nodes: list[dict], base_edges: list[dict]
) -> list[dict]:
    """
    Ensure every Day (linked via HAS_SCHEDULE from a station) has HAS_PERIOD
    edges to all MealPeriod nodes. Fills in missing edges so the full week
    is represented (e.g. for visualization and agents).
    """
    day_ids = {n["id"] for n in base_nodes if n.get("type") == "Day"}
    period_ids = [n["id"] for n in base_nodes if n.get("type") == "MealPeriod"]
    if not day_ids or not period_ids:
        return base_edges

    # Days that are scheduled (target of HAS_SCHEDULE from any station)
    scheduled_days = set()
    for e in base_edges:
        if e.get("relationship") == "HAS_SCHEDULE" and e.get("target") in day_ids:
            scheduled_days.add(e["target"])

    # Existing HAS_PERIOD edges (source=day, target=period)
    existing = {(e["source"], e["target"]) for e in base_edges if e.get("relationship") == "HAS_PERIOD"}

    added = []
    for day_id in sorted(scheduled_days):
        for period_id in period_ids:
            if (day_id, period_id) not in existing:
                added.append({
                    "source": day_id,
                    "target": period_id,
                    "relationship": "HAS_PERIOD",
                })
                existing.add((day_id, period_id))

    if added:
        print(f"Ensured full week: added {len(added)} HAS_PERIOD edges for {len(scheduled_days)} days × {len(period_ids)} periods")
    return base_edges + added


def main() -> None:
    data = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    base_nodes = data["nodes"]
    base_edges = data["edges"]
    base_edges = ensure_full_week_period_edges(base_nodes, base_edges)
    recipe_nodes = [n for n in base_nodes if n.get("type") == "Recipe"]

    normalized_records: list[IngredientRecord] = []
    for recipe in recipe_nodes:
        for raw in recipe.get("ingredient_description", []) or []:
            rec = normalize_ingredient(raw)
            if rec.normalized_name:
                normalized_records.append(rec)

    canonical_map, review = canonicalize_names([r.normalized_name for r in normalized_records])

    ingredient_nodes: dict[str, dict] = {}
    utensil_nodes: dict[str, dict] = {}
    new_edges: list[dict] = []

    for recipe in recipe_nodes:
        rid = recipe["id"]
        assembly = recipe.get("assembly_instructions", "") or ""
        special = recipe.get("special_instructions", "") or ""

        for utensil in extract_utensils(f"{assembly}\n{special}"):
            if utensil not in utensil_nodes:
                utensil_nodes[utensil] = {
                    "id": node_id("Utensil", utensil),
                    "type": "Equipment",
                    "name": utensil,
                    "equipment_type": utensil,
                }
            new_edges.append(
                {
                    "source": rid,
                    "target": utensil_nodes[utensil]["id"],
                    "relationship": "USES_UTENSIL",
                }
            )

        for raw in recipe.get("ingredient_description", []) or []:
            record = normalize_ingredient(raw)
            if not record.normalized_name:
                continue
            canonical = canonical_map[record.normalized_name]
            if canonical not in ingredient_nodes:
                ingredient_nodes[canonical] = {
                    "id": node_id("Ingredient", canonical),
                    "type": "Ingredient",
                    "name": canonical,
                }
            new_edges.append(
                {
                    "source": rid,
                    "target": ingredient_nodes[canonical]["id"],
                    "relationship": "HAS_INGREDIENT",
                    "attributes": {
                        "raw_text": record.raw_text,
                        "normalized_name": record.normalized_name,
                        "canonical_name": canonical,
                        "quantity": record.quantity,
                        "states": record.states,
                    },
                }
            )

    out = {
        "graph_metadata": {
            **data.get("graph_metadata", {}),
            "version": "2.3-normalized",
            "description": "Enriched graph with normalized Ingredient and Utensil nodes only",
        },
        "nodes": base_nodes + list(ingredient_nodes.values()) + list(utensil_nodes.values()),
        "edges": base_edges + new_edges,
    }

    OUTPUT_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")
    REVIEW_PATH.write_text(json.dumps(review, indent=2), encoding="utf-8")
    print(f"Saved graph: {OUTPUT_PATH}")
    print(f"Saved review list: {REVIEW_PATH}")
    print(f"Added ingredient nodes: {len(ingredient_nodes)}")
    print(f"Added utensil nodes: {len(utensil_nodes)}")
    print(f"Added edges: {len(new_edges)}")


if __name__ == "__main__":
    main()
