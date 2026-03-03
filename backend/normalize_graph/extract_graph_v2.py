"""
Knowledge Graph Normalizer
==========================
Input  : knowledge_graph.json   (entities + relations format)
Output : knowledge_graph_normalized.json  (single normalized file)

Kya karta hai:
  1. Ingredients tokenize + clean (vendor/prep/unit tokens strip karo)
  2. Aliases apply karo (e.g. "MIX PANCAKE WAFFLE..." → "pancake mix")
  3. Near-duplicate ingredients auto-merge karo (similarity >= 0.88)
  4. Equipment nodes extract karo (assembly/special instructions se)
  5. Ek single clean JSON file nikalo

Usage:
  python normalize_graph/extract_graph_v2.py
  python normalize_graph/extract_graph_v2.py --input /path/to/knowledge_graph.json
  python normalize_graph/extract_graph_v2.py --output /path/to/output.json
"""

import argparse
import json
import re
import uuid
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT  = Path(__file__).resolve().parent.parent
DEFAULT_INPUT  = PROJECT_ROOT / "knowledge _graph_main" / "knowledge_graph.json"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "output" / "knowledge_graph_normalized.json"

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

HIGH_CONFIDENCE = 0.90   # auto-merge karo silently
REVIEW_FLOOR    = 0.88   # auto-merge with warning

# ---------------------------------------------------------------------------
# Domain vocabularies
# ---------------------------------------------------------------------------

ALIASES: dict[str, str] = {
    # Generic
    "beef gd patty":                                        "beef ground patty",
    "beef ground patty 75 25":                              "beef ground patty",
    "beef ground patty 75 25 angus":                        "beef ground patty",
    "pickle dill sliced":                                   "dill pickle slice",
    "sugar white granulated":                               "sugar granulated",
    "sugar granulated extra fine":                          "sugar granulated",
    "vegetable fresh lettuce iceberg ap shreds":            "lettuce iceberg shredded",
    "vegetable fresh lettuce iceberg heads cored shredded": "lettuce iceberg shredded",
    "vegetable fresh lettuce romaine cored cut":            "lettuce romaine",
    "vegetable fresh lettuce romaine shredded":             "lettuce romaine",
    "vegetable fresh lettuce better burgr ap whl leaves cut": "lettuce",
    "vegetable fresh onion yellow white peeled trimmed diced cooked": "onion yellow diced cooked",
    "vegetable fz onion diced cooked":                      "onion diced cooked",
    "vegetable fresh onion yellow trimmed diced raw":       "onion yellow diced",
    "vegetable fresh tomato cored diced raw":               "tomato diced",
    "vegetable fresh tomato cored sliced raw":              "tomato sliced",
    "vegetable fresh tomato utility cored diced raw":       "tomato diced",
    "vegetable fresh tomato utility cored sliced raw":      "tomato sliced",
    "vegetable fresh tomato 6 6 cored diced raw":           "tomato diced",
    "vegetable fresh tomato 6 6 cored sliced raw":          "tomato sliced",
    "cheese american yellow white ap slices":               "cheese american slice",
    "cheese american yellow rs ap sliced 160":              "cheese american slice",
    "cheese american white rs ap sliced 160":               "cheese american slice",
    "roll hamburger 4 white sliced 2 1":                    "roll hamburger",
    "roll bun hamburger potato 2":                          "roll hamburger",
    # Grill-specific
    "mix pancake waffle complete pearl milling":            "pancake mix",
    "mix pancake waffle complete":                          "pancake mix",
    "potato fz fries crinkle cut coat":                     "fries crinkle cut",
    "potato fz fries crinkle cut":                          "fries crinkle cut",
    "egg whole shell medium":                               "egg whole",
    "egg whole shell large":                                "egg whole",
    "oil vegetable blend":                                  "oil vegetable",
    "oil canola refined":                                   "oil canola",
    "bread white sandwich sliced":                          "bread white sliced",
    "bread wheat sandwich sliced":                          "bread wheat sliced",
    "cheese cheddar yellow shredded":                       "cheese cheddar shredded",
    "cheese cheddar white shredded":                        "cheese cheddar shredded",
}

VENDOR_TOKENS: set[str] = {
    "sysco", "fz", "ap", "rs", "ct", "xl", "xxl",
    "bulk", "frozen", "bnls", "fc", "ftr", "whl",
    "pc", "refrig", "refrigerated", "kosher", "fresh",
}
PREP_TOKENS: set[str] = {
    "raw", "cooked", "thawed", "diced", "sliced", "shredded",
    "crumbled", "fried", "deep", "fat", "cut", "cored",
    "refuse", "removed",
}
UNIT_TOKENS: set[str] = {"oz", "g", "lb", "lbs", "kg", "ml", "ct", "inch", "in"}

EQUIPMENT_KEYWORDS: dict[str, str] = {
    "flat-top griddle": "griddle",
    "griddle":          "griddle",
    "char grill":       "grill",
    "grill":            "grill",
    "deep-fat fryer":   "fryer",
    "deep fat fryer":   "fryer",
    "fryer":            "fryer",
    "convection oven":  "oven",
    "oven":             "oven",
    "panini press":     "panini_press",
    "stockpot":         "stockpot",
    "skillet":          "skillet",
    "steam table":      "steam_table",
    "toaster":          "toaster",
    "salamander":       "salamander",
}


# ---------------------------------------------------------------------------
# Internal data types
# ---------------------------------------------------------------------------

@dataclass
class Node:
    id:         str
    node_type:  str
    props:      dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"id": self.id, "type": self.node_type, **self.props}


@dataclass
class Edge:
    source:       str
    target:       str
    relationship: str
    attributes:   dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {"source": self.source, "target": self.target, "relationship": self.relationship}
        if self.attributes:
            d["attributes"] = self.attributes
        return d


@dataclass
class IngredientRecord:
    raw_text:        str
    normalized_name: str
    quantity:        str | None
    states:          list[str]


# ---------------------------------------------------------------------------
# Step 1 — Load
# ---------------------------------------------------------------------------

def load(path: Path) -> tuple[list[Node], list[Edge], dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    nodes: list[Node] = []
    edges: list[Edge] = []

    for entity_type, items in data.get("entities", {}).items():
        for e in items:
            props = {k: v for k, v in e.items() if k not in ("id", "type")}
            nodes.append(Node(id=e["id"], node_type=entity_type, props=props))

    # Rename USES_INGREDIENT → HAS_INGREDIENT for internal consistency
    pred_remap = {"USES_INGREDIENT": "HAS_INGREDIENT"}
    for r in data.get("relations", []):
        rel   = pred_remap.get(r["predicate"], r["predicate"])
        attrs = r.get("attributes", {}) or {}
        edges.append(Edge(source=r["from_id"], target=r["to_id"], relationship=rel, attributes=attrs))

    meta = {
        "schema_version": data.get("schema_version", "1.0.0"),
        "source_file":    path.name,
        "original_meta":  data.get("meta", {}),
    }
    return nodes, edges, meta


# ---------------------------------------------------------------------------
# Step 2 — Tokenize & normalize
# ---------------------------------------------------------------------------

def _safe_id(prefix: str, key: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_]+", "_", key.strip()).strip("_")
    return f"{prefix}_{safe}" if safe else f"{prefix}_{uuid.uuid4().hex[:8]}"


def _singularize(tok: str) -> str:
    if len(tok) <= 3:
        return tok
    if tok.endswith("ies"):
        return tok[:-3] + "y"
    if tok.endswith("ses"):
        return tok[:-2]
    if tok.endswith("s") and not tok.endswith("ss"):
        return tok[:-1]
    return tok


def _tokenize(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[^a-z0-9/\s-]", " ", text).replace("-", " ")
    out = []
    for tok in re.split(r"\s+", text.strip()):
        if not tok:
            continue
        if re.fullmatch(r"\d+(\.\d+)?(x\d+)?", tok):
            continue
        if tok in UNIT_TOKENS | VENDOR_TOKENS | PREP_TOKENS:
            continue
        out.append(_singularize(tok))
    return out


def _normalize_name(raw: str) -> str:
    base = re.split(r"\s*/\s*", raw.strip())[0]
    tokens = _tokenize(base)
    if not tokens:
        return ""
    name = " ".join(sorted(tokens))
    return ALIASES.get(name, name)


def _parse_quantity(raw: str) -> str | None:
    m = re.search(r"\b(\d+(?:\.\d+)?)\s*(oz|g|lb|lbs|kg|ml)\b", raw, re.IGNORECASE)
    return f"{m.group(1)} {m.group(2).upper()}" if m else None


def _parse_states(raw: str) -> list[str]:
    parts = re.split(r"\s*/\s*", raw)
    return sorted({s.strip().lower() for s in parts[1:] if s.strip()}) if len(parts) > 1 else []


def _normalize_ingredient(raw: str) -> IngredientRecord:
    return IngredientRecord(
        raw_text=raw,
        normalized_name=_normalize_name(raw),
        quantity=_parse_quantity(raw),
        states=_parse_states(raw),
    )


# ---------------------------------------------------------------------------
# Step 3 — Canonicalize (auto-merge near-duplicates)
# ---------------------------------------------------------------------------

def _similarity(a: str, b: str) -> float:
    seq   = SequenceMatcher(None, a, b).ratio()
    as_, bs_ = set(a.split()), set(b.split())
    jac   = len(as_ & bs_) / len(as_ | bs_) if (as_ and bs_) else 0.0
    cont  = 1.0 if (a in b or b in a) else 0.0
    return 0.50 * seq + 0.35 * jac + 0.15 * cont


def _canonicalize(names: list[str]) -> tuple[dict[str, str], int]:
    """
    Returns (canonical_map, num_auto_merged).
    Merges are applied silently for score >= REVIEW_FLOOR.
    """
    counts  = Counter(names)
    ordered = sorted(counts.keys(), key=lambda n: (-counts[n], len(n), n))

    canon_map: dict[str, str] = {}
    clusters:  list[str]      = []
    merged = 0

    for name in ordered:
        best, score = None, 0.0
        for c in clusters:
            s = _similarity(name, c)
            if s > score:
                score, best = s, c

        if best and score >= REVIEW_FLOOR:
            canon_map[name] = best
            merged += 1
        else:
            canon_map[name] = name
            clusters.append(name)

    return canon_map, merged


# ---------------------------------------------------------------------------
# Step 4 — Equipment extraction
# ---------------------------------------------------------------------------

def _extract_equipment(text: str) -> list[str]:
    found = set()
    lower = (text or "").lower()
    for kw, eq in EQUIPMENT_KEYWORDS.items():
        if kw in lower:
            found.add(eq)
    return sorted(found)


# ---------------------------------------------------------------------------
# Step 5 — Normalize full graph
# ---------------------------------------------------------------------------

def normalize_graph(nodes: list[Node], edges: list[Edge]) -> tuple[list[Node], list[Edge], dict]:
    recipe_nodes = [n for n in nodes if n.node_type == "Recipe"]

    # ingredient_id → raw description lookup
    ing_desc: dict[str, str] = {
        n.id: n.props.get("description", "")
        for n in nodes if n.node_type == "Ingredient"
    }

    # per-recipe ingredient lists (from HAS_INGREDIENT edges)
    recipe_ings: dict[str, list[str]] = {r.id: [] for r in recipe_nodes}
    for e in edges:
        if e.relationship == "HAS_INGREDIENT" and e.source in recipe_ings:
            desc = ing_desc.get(e.target, "")
            if desc:
                recipe_ings[e.source].append(desc)

    # Normalize
    all_records: list[IngredientRecord] = []
    recipe_records: dict[str, list[IngredientRecord]] = {}
    for rid, descs in recipe_ings.items():
        recs = [r for r in (_normalize_ingredient(d) for d in descs) if r.normalized_name]
        recipe_records[rid] = recs
        all_records.extend(recs)

    # Canonicalize
    canon_map, num_merged = _canonicalize([r.normalized_name for r in all_records])

    # Build canonical Ingredient nodes
    canon_nodes: dict[str, Node] = {}
    for rec in all_records:
        canon = canon_map[rec.normalized_name]
        nid   = _safe_id("Ingredient", canon)
        if nid not in canon_nodes:
            canon_nodes[nid] = Node(id=nid, node_type="Ingredient", props={"name": canon})

    # Build Equipment nodes + edges
    equip_nodes: dict[str, Node] = {}
    equip_edges: list[Edge]      = []
    equip_seen:  set[tuple]      = set()

    for recipe in recipe_nodes:
        text = " ".join(filter(None, [
            recipe.props.get("assembly_instructions", ""),
            recipe.props.get("special_instructions",  ""),
        ]))
        for eq in _extract_equipment(text):
            eid = _safe_id("Equipment", eq)
            if eid not in equip_nodes:
                equip_nodes[eid] = Node(id=eid, node_type="Equipment",
                                        props={"name": eq, "equipment_type": eq})
            if (recipe.id, eid) not in equip_seen:
                equip_seen.add((recipe.id, eid))
                equip_edges.append(Edge(source=recipe.id, target=eid,
                                        relationship="USES_EQUIPMENT"))

    # Build normalized HAS_INGREDIENT edges
    norm_ing_edges: list[Edge] = []
    for rid, recs in recipe_records.items():
        for rec in recs:
            canon = canon_map[rec.normalized_name]
            nid   = _safe_id("Ingredient", canon)
            norm_ing_edges.append(Edge(
                source=rid, target=nid, relationship="HAS_INGREDIENT",
                attributes={
                    "raw_text":        rec.raw_text,
                    "normalized_name": rec.normalized_name,
                    "canonical_name":  canon,
                    "quantity":        rec.quantity,
                    "states":          rec.states,
                },
            ))

    # Assemble final graph
    base_nodes = [n for n in nodes if n.node_type not in ("Ingredient", "Equipment")]
    base_edges = [e for e in edges if e.relationship not in ("HAS_INGREDIENT", "USES_EQUIPMENT", "USES_UTENSIL")]

    final_nodes = base_nodes + list(canon_nodes.values()) + list(equip_nodes.values())
    final_edges = base_edges + norm_ing_edges + equip_edges

    stats = {
        "base_nodes":         len(base_nodes),
        "ingredient_nodes":   len(canon_nodes),
        "equipment_nodes":    len(equip_nodes),
        "total_nodes":        len(final_nodes),
        "total_edges":        len(final_edges),
        "ingredients_merged": num_merged,
    }
    return final_nodes, final_edges, stats


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalize knowledge_graph.json → knowledge_graph_normalized.json"
    )
    parser.add_argument("--input",  "-i", type=Path, default=DEFAULT_INPUT,
                        help="Input knowledge_graph.json")
    parser.add_argument("--output", "-o", type=Path, default=DEFAULT_OUTPUT,
                        help="Output normalized JSON (default: output/knowledge_graph_normalized.json)")
    args = parser.parse_args()

    print("=" * 55)
    print("  Knowledge Graph Normalizer")
    print("=" * 55)

    if not args.input.exists():
        raise SystemExit(f"Input not found: {args.input}")

    print(f"  Input  : {args.input}")
    print(f"  Output : {args.output}")
    print()

    # Load
    print("[1/3] Loading...")
    nodes, edges, meta = load(args.input)
    print(f"      {len(nodes)} nodes, {len(edges)} edges")

    # Normalize
    print("[2/3] Normalizing...")
    norm_nodes, norm_edges, stats = normalize_graph(nodes, edges)
    print(f"      Ingredient nodes (canonical) : {stats['ingredient_nodes']}")
    print(f"      Equipment nodes              : {stats['equipment_nodes']}")
    print(f"      Ingredients auto-merged      : {stats['ingredients_merged']}")
    print(f"      Total nodes                  : {stats['total_nodes']}")
    print(f"      Total edges                  : {stats['total_edges']}")

    # Write single output
    print("[3/3] Writing output...")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "graph_metadata": {
            "version":     "2.4-normalized",
            "description": "Normalized graph: canonical ingredients + equipment nodes. Auto-merged near-duplicates.",
            "source":      meta,
            "stats":       stats,
        },
        "nodes": [n.to_dict() for n in norm_nodes],
        "edges": [e.to_dict() for e in norm_edges],
    }
    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    print()
    print(f"  Done → {args.output}")
    print("=" * 55)


if __name__ == "__main__":
    main()
