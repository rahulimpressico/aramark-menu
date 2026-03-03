"""
Filtered Graph Visualizer
=========================
normalize_graph/output/filtered_<Period>.json ko visualize karo.

3 outputs per period:
  1. <Period>_interactive.html  — pyvis browser graph (zoom/drag/hover/click-focus)
  2. <Period>_graph.png         — static network image
  3. <Period>_summary.png       — recipe cost + ingredient bar charts

Usage:
  python normalize_graph/viz/visualize_filtered.py --period Breakfast
  python normalize_graph/viz/visualize_filtered.py --period Dinner
  python normalize_graph/viz/visualize_filtered.py --all
"""

import argparse
import json
import sys
from pathlib import Path
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import networkx as nx
from pyvis.network import Network

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR    = PROJECT_ROOT / "normalize_graph" / "output"
OUTPUT_DIR   = Path(__file__).resolve().parent / "output"

ALL_PERIODS  = ["Breakfast", "Brunch", "Lunch", "Dinner", "All_Day"]

# ---------------------------------------------------------------------------
# Visual config
# ---------------------------------------------------------------------------

NODE_STYLES = {
    "Station":    {"color": "#E74C3C", "size": 48, "shape": "star",    "font_size": 22},
    "Week":       {"color": "#9B59B6", "size": 32, "shape": "diamond", "font_size": 18},
    "Day":        {"color": "#E67E22", "size": 26, "shape": "square",  "font_size": 15},
    "MealPeriod": {"color": "#F1C40F", "size": 22, "shape": "diamond", "font_size": 14},
    "Recipe":     {"color": "#2980B9", "size": 20, "shape": "dot",     "font_size": 13},
    "Ingredient": {"color": "#27AE60", "size": 11, "shape": "dot",     "font_size": 9},
    "Equipment":  {"color": "#E91E63", "size": 20, "shape": "triangle","font_size": 13},
}

EDGE_COLORS = {
    "HAS_WEEK":           "#9B59B6",
    "HAS_DAY":            "#E67E22",
    "HAS_PERIOD":         "#F1C40F",
    "SCHEDULED_ON":       "#E67E22",
    "BELONGS_TO_STATION": "#E74C3C",
    "SERVED_IN_PERIOD":   "#F1C40F",
    "HAS_INGREDIENT":     "#27AE60",
    "USES_EQUIPMENT":     "#E91E63",
}

PERIOD_COLORS = {
    "Breakfast": "#E67E22",
    "Brunch":    "#8E44AD",
    "Lunch":     "#2980B9",
    "Dinner":    "#C0392B",
    "All Day":   "#27AE60",
    "All_Day":   "#27AE60",
}

# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_filtered(period: str) -> dict:
    safe = period.replace(" ", "_")
    path = INPUT_DIR / f"filtered_{safe}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Filtered JSON not found: {path}\n"
            f"Pehle run karo:\n"
            f"  python menu_agent_analyzer.py --period '{period}' --dump-json"
        )
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def flatten_nodes(data: dict) -> list[dict]:
    """nodes dict (grouped by type) → flat list."""
    flat = []
    for node_type, nodes in data.get("nodes", {}).items():
        for n in nodes:
            n.setdefault("type", node_type)
            flat.append(n)
    return flat


def get_node_label(n: dict) -> str:
    return (
        n.get("day_name")
        or n.get("name")
        or n.get("description", "")[:35]
        or n.get("id", "")
    )


# ---------------------------------------------------------------------------
# 1. Interactive HTML
# ---------------------------------------------------------------------------

def build_interactive(data: dict, out_path: Path):
    period     = data.get("meal_period", "Unknown")
    all_nodes  = flatten_nodes(data)
    all_edges  = data.get("edges", [])

    # Node detail lookup for info panel
    node_details: dict[str, dict] = {}
    for n in all_nodes:
        ntype = n.get("type", "")
        d: dict = {"type": ntype}
        if ntype == "Recipe":
            d["label"]    = n.get("name", "")
            d["cost"]     = f"${n['food_cost']:.4f}" if n.get("food_cost") else "—"
            d["assembly"] = (n.get("assembly_instructions") or "")[:220]
            d["special"]  = (n.get("special_instructions")  or "")[:120]
            ing_ids = [e["target"] for e in all_edges
                       if e["source"] == n["id"] and e["relationship"] == "HAS_INGREDIENT"]
            d["ing_count"] = len(ing_ids)
            days = list({e["target"].replace("day_", "")
                         for e in all_edges
                         if e["source"] == n["id"] and e["relationship"] == "SCHEDULED_ON"})
            d["days"] = ", ".join(sorted(days)) or "—"
        elif ntype == "Day":
            d["label"]   = n.get("day_name", n["id"])
            d["day_no"]  = n.get("day_no", "")
            d["week_no"] = n.get("week_no", "")
        elif ntype == "Ingredient":
            d["label"] = n.get("name") or n.get("description", "")
        elif ntype == "Equipment":
            d["label"] = n.get("name") or n.get("equipment_type", "")
        elif ntype == "Week":
            d["label"] = f"Week {n.get('week_no', '')}"
        else:
            d["label"] = n.get("name", n.get("id", ""))
        node_details[n["id"]] = d

    net = Network(
        height="920px", width="100%",
        bgcolor="#1a1a2e", font_color="#ffffff",
        directed=True, notebook=False,
    )
    net.barnes_hut(gravity=-9000, central_gravity=0.35, spring_length=160)

    for n in all_nodes:
        ntype = n.get("type", "Recipe")
        style = NODE_STYLES.get(ntype, NODE_STYLES["Recipe"])
        label = get_node_label(n)
        if ntype == "Week":
            label = f"Week {n.get('week_no', '')}"

        tip = [f"<b>{ntype}</b>", f"ID: {n['id']}"]
        if n.get("name"):         tip.append(f"Name: {n['name']}")
        if n.get("food_cost"):    tip.append(f"Cost: ${n['food_cost']:.4f}")
        if n.get("description"):  tip.append(f"Desc: {n['description'][:60]}")
        if n.get("day_name"):     tip.append(f"Day: {n['day_name']} (#{n.get('day_no','')})")
        if n.get("equipment_type"): tip.append(f"Equipment: {n['equipment_type']}")

        net.add_node(
            n["id"],
            label=label,
            color=style["color"],
            size=style["size"],
            shape=style["shape"],
            font={"size": style["font_size"], "color": "#ffffff"},
            title="<br>".join(tip),
        )

    for e in all_edges:
        net.add_edge(
            e["source"], e["target"],
            title=e["relationship"],
            color=EDGE_COLORS.get(e["relationship"], "#666666"),
            arrows="to", width=1.2,
        )

    legend_html = """
    <div style="position:fixed;top:10px;right:10px;background:#12122a;
                border:1px solid #3a3a5c;padding:14px 16px;border-radius:10px;
                color:#e0e0ff;font-family:'Segoe UI',sans-serif;font-size:13px;z-index:9999;">
      <b style="color:#a78bfa">Nodes</b><br><br>
      <span style="color:#E74C3C">&#9733;</span> Station<br>
      <span style="color:#9B59B6">&#9670;</span> Week<br>
      <span style="color:#E67E22">&#9632;</span> Day<br>
      <span style="color:#F1C40F">&#9670;</span> MealPeriod<br>
      <span style="color:#2980B9">&#9679;</span> Recipe<br>
      <span style="color:#27AE60">&#9679;</span> Ingredient<br>
      <span style="color:#E91E63">&#9650;</span> Equipment<br><br>
      <hr style="border-color:#2d2d4e">
      <b style="color:#a78bfa">Edges</b><br><br>
      <span style="color:#E67E22">─</span> HAS_DAY / SCHEDULED_ON<br>
      <span style="color:#F1C40F">─</span> HAS_PERIOD / SERVED_IN_PERIOD<br>
      <span style="color:#E74C3C">─</span> BELONGS_TO_STATION<br>
      <span style="color:#27AE60">─</span> HAS_INGREDIENT<br>
      <span style="color:#E91E63">─</span> USES_EQUIPMENT<br>
    </div>
    """

    node_details_js = json.dumps(node_details, ensure_ascii=False)
    TYPE_COLORS_JS  = json.dumps({k: v["color"] for k, v in NODE_STYLES.items()})

    focus_js = f"""
<style>
#kg-panel {{
  position:fixed;top:10px;left:10px;width:270px;
  background:#12122a;border:1px solid #3a3a5c;border-radius:10px;
  padding:14px 16px;color:#e0e0ff;font-family:'Segoe UI',sans-serif;
  font-size:12.5px;z-index:9999;box-shadow:0 4px 24px rgba(0,0,0,.6);
  max-height:88vh;overflow-y:auto;
}}
#kg-panel h3  {{ margin:0 0 8px 0;font-size:14px;color:#a78bfa; }}
#kg-panel .badge {{ display:inline-block;padding:2px 8px;border-radius:12px;
  font-size:11px;font-weight:bold;margin-bottom:8px; }}
#kg-panel .row  {{ margin:5px 0;line-height:1.5; }}
#kg-panel .key  {{ color:#94a3b8; }}
#kg-panel .val  {{ color:#e2e8f0; }}
#kg-panel hr    {{ border-color:#2d2d4e;margin:8px 0; }}
#kg-panel .hint {{ color:#4a4a6a;font-size:11px;margin-top:10px; }}
#kg-title {{
  position:fixed;bottom:14px;left:50%;transform:translateX(-50%);
  background:#12122a;border:1px solid #3a3a5c;padding:6px 20px;
  border-radius:20px;color:#a78bfa;font-family:'Segoe UI',sans-serif;
  font-size:14px;font-weight:bold;z-index:9999;
}}
</style>

<script>
(function(){{
  var ND = {node_details_js};
  var TC = {TYPE_COLORS_JS};

  var panel = document.getElementById("kg-panel");
  function clearPanel(){{
    panel.innerHTML = "<div class='hint'>Click any node to explore</div>";
  }}
  function setPanel(id){{
    var d = ND[id]; if(!d) return;
    var c = TC[d.type]||"#888";
    var h = "<span class='badge' style='background:"+c+"22;color:"+c+";border:1px solid "+c+"55'>"+d.type+"</span>";
    h += "<h3>"+(d.label||id)+"</h3><hr>";
    h += "<div class='row'><span class='key'>ID: </span><span class='val'>"+id+"</span></div>";
    if(d.cost)      h+="<div class='row'><span class='key'>Food Cost: </span><span class='val'>"+d.cost+"</span></div>";
    if(d.ing_count) h+="<div class='row'><span class='key'>Ingredients: </span><span class='val'>"+d.ing_count+"</span></div>";
    if(d.days)      h+="<div class='row'><span class='key'>Scheduled: </span><span class='val'>"+d.days+"</span></div>";
    if(d.day_no)    h+="<div class='row'><span class='key'>Day No: </span><span class='val'>"+d.day_no+" (Week "+d.week_no+")</span></div>";
    if(d.assembly)  h+="<hr><div class='row'><span class='key'>Assembly:</span><br><span class='val'>"+d.assembly+"…</span></div>";
    if(d.special)   h+="<div class='row'><span class='key'>Special:</span><br><span class='val'>"+d.special+"</span></div>";
    h+="<div class='hint'>Click background to reset</div>";
    panel.innerHTML=h;
  }}
  clearPanel();

  network.once("stabilized",function(){{
    var oN={{}}, oE={{}};
    nodes.get().forEach(function(n){{ oN[n.id]={{color:n.color,size:n.size,font:n.font,bw:n.borderWidth||1}}; }});
    edges.get().forEach(function(e){{ oE[e.id]={{color:e.color,width:e.width||1.2}}; }});
    var active=false;

    network.on("selectNode",function(p){{
      var sel=p.nodes[0]; active=true;
      var nb=new Set(network.getConnectedNodes(sel));
      var ne=new Set(network.getConnectedEdges(sel));
      nb.add(sel);
      nodes.update(nodes.get().map(function(n){{
        if(nb.has(n.id)){{
          var o=oN[n.id], bg=typeof o.color==="string"?o.color:(o.color&&o.color.background)||"#aaa";
          return {{id:n.id,
            color:n.id===sel?{{background:bg,border:"#ffffff",highlight:{{background:bg,border:"#fff"}}}}:o.color,
            size:n.id===sel?(o.size||18)*1.45:(o.size||18),
            borderWidth:n.id===sel?4:2,font:{{color:"#ffffff",size:o.font?o.font.size:12}}}};
        }}
        return {{id:n.id,color:{{background:"#0d0d1a",border:"#1a1a2e"}},borderWidth:1,font:{{color:"#1a1a2e"}},size:oN[n.id].size}};
      }}));
      edges.update(edges.get().map(function(e){{
        if(ne.has(e.id)){{
          var oc=oE[e.id].color, c=typeof oc==="string"?oc:(oc&&oc.color)||"#888";
          return {{id:e.id,color:{{color:c,opacity:1}},width:(oE[e.id].width||1.2)*2.8}};
        }}
        return {{id:e.id,color:{{color:"#0d0d1a",opacity:0.08}},width:0.25}};
      }}));
      setPanel(sel);
    }});

    network.on("deselectNode",function(){{
      if(!active) return; active=false;
      nodes.update(nodes.get().map(function(n){{
        var o=oN[n.id];
        return {{id:n.id,color:o.color,size:o.size,borderWidth:o.bw,font:o.font||{{color:"#ffffff"}}}};
      }}));
      edges.update(edges.get().map(function(e){{
        return {{id:e.id,color:oE[e.id].color,width:oE[e.id].width}};
      }}));
      clearPanel();
    }});
  }});
}})();
</script>
"""

    net.save_graph(str(out_path))
    html = out_path.read_text(encoding="utf-8")
    panel_div  = '<div id="kg-panel"></div>'
    title_div  = f'<div id="kg-title">{period} — Grill Station</div>'
    html = html.replace("</body>", panel_div + title_div + legend_html + focus_js + "\n</body>")
    out_path.write_text(html, encoding="utf-8")
    print(f"  [1] Interactive HTML : {out_path.name}")


# ---------------------------------------------------------------------------
# 2. Static PNG
# ---------------------------------------------------------------------------

def build_static_png(data: dict, out_path: Path):
    period    = data.get("meal_period", "Unknown")
    all_nodes = flatten_nodes(data)
    all_edges = data.get("edges", [])

    G = nx.DiGraph()
    for n in all_nodes:
        label = get_node_label(n)
        if n.get("type") == "Week":
            label = f"Week {n.get('week_no', '')}"
        G.add_node(n["id"], label=label, node_type=n.get("type", "Recipe"),
                   food_cost=n.get("food_cost"))
    for e in all_edges:
        G.add_edge(e["source"], e["target"], predicate=e["relationship"])

    pos = nx.spring_layout(G, k=2.8, seed=42, iterations=70)

    fig, ax = plt.subplots(figsize=(24, 18))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#1a1a2e")

    for ntype, style in NODE_STYLES.items():
        nl = [n for n, d in G.nodes(data=True) if d.get("node_type") == ntype]
        if nl:
            nx.draw_networkx_nodes(G, pos, nodelist=nl, ax=ax,
                                   node_color=style["color"],
                                   node_size=style["size"] * 42, alpha=0.92)

    for rel, ec in EDGE_COLORS.items():
        el = [(u, v) for u, v, d in G.edges(data=True) if d.get("predicate") == rel]
        if el:
            nx.draw_networkx_edges(G, pos, edgelist=el, ax=ax,
                                   edge_color=ec, alpha=0.5, arrows=True,
                                   arrowsize=10, width=0.7,
                                   connectionstyle="arc3,rad=0.05")

    label_nodes = {
        n: d["label"][:24]
        for n, d in G.nodes(data=True)
        if d.get("node_type") in {"Station", "Week", "Day", "MealPeriod", "Recipe", "Equipment"}
    }
    nx.draw_networkx_labels(G, pos, labels=label_nodes, ax=ax,
                            font_size=6, font_color="#ffffff", font_weight="bold")

    patches = [mpatches.Patch(color=v["color"], label=k) for k, v in NODE_STYLES.items()
               if any(d.get("node_type") == k for _, d in G.nodes(data=True))]
    ax.legend(handles=patches, loc="upper left", facecolor="#2c2c54",
              edgecolor="#444", labelcolor="white", fontsize=10)
    ax.set_title(f"Grill Station — {period}", fontsize=18, color="white",
                 pad=15, fontweight="bold")
    ax.axis("off")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"  [2] Static PNG       : {out_path.name}")


# ---------------------------------------------------------------------------
# 3. Summary charts
# ---------------------------------------------------------------------------

def build_summary_charts(data: dict, out_path: Path):
    period  = data.get("meal_period", "Unknown")
    recipes = data.get("nodes", {}).get("Recipe", [])
    edges   = data.get("edges", [])

    # Ingredient count per recipe
    ing_count: dict[str, int] = Counter(
        e["source"] for e in edges if e["relationship"] == "HAS_INGREDIENT"
    )
    # Equipment per recipe
    equip_map: dict[str, list[str]] = {}
    equip_nodes = {n["id"]: n.get("name") or n.get("equipment_type", "?")
                   for n in data.get("nodes", {}).get("Equipment", [])}
    for e in edges:
        if e["relationship"] == "USES_EQUIPMENT":
            equip_map.setdefault(e["source"], []).append(equip_nodes.get(e["target"], "?"))

    # Sort recipes by food_cost desc
    sorted_r = sorted(recipes, key=lambda r: r.get("food_cost") or 0, reverse=True)
    names    = [r.get("name", r["id"])[:28] for r in sorted_r]
    costs    = [r.get("food_cost") or 0.0    for r in sorted_r]
    ings     = [ing_count.get(r["id"], 0)    for r in sorted_r]
    eq_tags  = ["⚙ " + ", ".join(equip_map[r["id"]]) if r["id"] in equip_map else ""
                for r in sorted_r]

    p_color = PERIOD_COLORS.get(period, "#2980B9")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(22, max(8, len(recipes) * 0.55 + 2)))
    fig.patch.set_facecolor("#1a1a2e")
    fig.suptitle(f"Grill Station — {period}", fontsize=16,
                 color="white", fontweight="bold", y=1.01)

    for ax in (ax1, ax2):
        ax.set_facecolor("#16213e")
        ax.tick_params(colors="white")
        ax.spines[:].set_color("#444")
        for lbl in ax.get_xticklabels() + ax.get_yticklabels():
            lbl.set_color("white")

    # ── Food cost ──────────────────────────────────────────
    bars1 = ax1.barh(names, costs, color=p_color, edgecolor="#0d0d1a", height=0.65, alpha=0.9)
    ax1.set_xlabel("Food Cost ($)", color="white", fontsize=11)
    ax1.set_title("Food Cost (descending)", color="white", fontsize=12, fontweight="bold")
    ax1.invert_yaxis()
    for bar, cost, tag in zip(bars1, costs, eq_tags):
        txt = f"  ${cost:.2f}  {tag}"
        ax1.text(bar.get_width() + 0.02, bar.get_y() + bar.get_height() / 2,
                 txt, va="center", color="white", fontsize=8)
    ax1.tick_params(axis="y", labelsize=9)

    # ── Ingredient count ───────────────────────────────────
    bars2 = ax2.barh(names, ings, color="#27AE60", edgecolor="#0d0d1a", height=0.65, alpha=0.9)
    ax2.set_xlabel("Number of Ingredients", color="white", fontsize=11)
    ax2.set_title("Ingredient Count", color="white", fontsize=12, fontweight="bold")
    ax2.invert_yaxis()
    for bar, count in zip(bars2, ings):
        ax2.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                 str(count), va="center", color="white", fontsize=9)
    ax2.tick_params(axis="y", labelsize=9)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"  [3] Summary Chart    : {out_path.name}")


# ---------------------------------------------------------------------------
# Single period runner
# ---------------------------------------------------------------------------

def visualize_period(period: str):
    safe = period.replace(" ", "_")
    print(f"\n{'='*55}")
    print(f"  Period: {period}")
    print(f"{'='*55}")

    data = load_filtered(period)
    summary = data.get("summary", {})
    print(f"  Nodes: {summary}  |  Edges: {len(data.get('edges', []))}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    build_interactive(   data, OUTPUT_DIR / f"{safe}_interactive.html")
    build_static_png(    data, OUTPUT_DIR / f"{safe}_graph.png")
    build_summary_charts(data, OUTPUT_DIR / f"{safe}_summary.png")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Visualize filtered period JSON from normalize_graph/output/"
    )
    parser.add_argument("--period", "-p", default=None,
                        help="Meal period: Breakfast / Lunch / Dinner / Brunch / 'All Day'")
    parser.add_argument("--all", "-a", action="store_true",
                        help="Sab periods ke liye visualizations generate karo")
    args = parser.parse_args()

    if args.all:
        all_files = sorted(INPUT_DIR.glob("filtered_*.json"))
        if not all_files:
            print(f"No filtered_*.json files found in {INPUT_DIR}")
            print("Pehle run karo: python menu_agent_analyzer.py --period Breakfast --dump-json")
            sys.exit(1)
        for f in all_files:
            period = f.stem.replace("filtered_", "").replace("_", " ")
            try:
                visualize_period(period.replace(" ", "_"))
            except Exception as ex:
                print(f"  [SKIP] {period}: {ex}")
    elif args.period:
        visualize_period(args.period)
    else:
        parser.print_help()
        print("\nExamples:")
        print("  python normalize_graph/viz/visualize_filtered.py --period Breakfast")
        print("  python normalize_graph/viz/visualize_filtered.py --all")
        sys.exit(0)

    print(f"\nDone!  Output folder: {OUTPUT_DIR}")
    print("  → Browser mein open karo: output/<Period>_interactive.html")


if __name__ == "__main__":
    main()
