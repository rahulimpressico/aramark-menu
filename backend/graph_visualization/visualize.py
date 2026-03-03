"""
Graph Visualization — knowledge_graph.json ko 3 tarikon se visualize karo:

  1. interactive_graph.html  — pyvis (browser mein open karo, zoom/drag/hover)
  2. static_graph.png        — matplotlib + networkx (full overview image)
  3. recipe_summary.png      — bar chart: recipe vs ingredient count + food cost

Run karo:
  python graph_visualization/visualize.py

Output files: graph_visualization/output/
"""

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless (no display needed)
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import networkx as nx
from pyvis.network import Network

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT  = Path(__file__).resolve().parent.parent
KG_JSON       = PROJECT_ROOT / "knowledge _graph_main" / "knowledge_graph.json"
OUTPUT_DIR    = Path(__file__).resolve().parent / "output"

# ---------------------------------------------------------------------------
# Node type → visual style
# ---------------------------------------------------------------------------

NODE_STYLES = {
    "Station":    {"color": "#E74C3C", "size": 45, "shape": "star",    "font_size": 22},
    "Week":       {"color": "#9B59B6", "size": 32, "shape": "diamond", "font_size": 18},
    "Day":        {"color": "#E67E22", "size": 26, "shape": "square",  "font_size": 15},
    "MealPeriod": {"color": "#F1C40F", "size": 22, "shape": "diamond", "font_size": 14},
    "Recipe":     {"color": "#2980B9", "size": 18, "shape": "dot",     "font_size": 12},
    "Ingredient": {"color": "#27AE60", "size": 11, "shape": "dot",     "font_size": 9},
}

EDGE_COLORS = {
    "HAS_WEEK":           "#9B59B6",
    "HAS_DAY":            "#E67E22",
    "HAS_PERIOD":         "#F1C40F",
    "SCHEDULED_ON":       "#E67E22",
    "BELONGS_TO_STATION": "#E74C3C",
    "SERVED_IN_PERIOD":   "#F1C40F",
    "USES_INGREDIENT":    "#27AE60",
}


# ---------------------------------------------------------------------------
# Load graph
# ---------------------------------------------------------------------------

def load_graph(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_nx_graph(kg: dict) -> nx.DiGraph:
    G = nx.DiGraph()
    for entity_type, nodes in kg["entities"].items():
        for n in nodes:
            label = (
                n.get("day_name")          # Day node
                or n.get("name")
                or n.get("recipe_name")
                or n.get("description", "")[:30]
            )
            if entity_type == "Week":
                label = f"Week {n.get('week_no', '')}"
            G.add_node(
                n["id"],
                label=label,
                node_type=entity_type,
                food_cost=n.get("food_cost"),
            )
    for rel in kg["relations"]:
        G.add_edge(rel["from_id"], rel["to_id"], predicate=rel["predicate"])
    return G


# ---------------------------------------------------------------------------
# 1. Interactive HTML (pyvis)
# ---------------------------------------------------------------------------

def build_interactive_html(kg: dict, out_path: Path):
    net = Network(
        height="900px",
        width="100%",
        bgcolor="#1a1a2e",
        font_color="#ffffff",
        directed=True,
        notebook=False,
    )
    net.barnes_hut(gravity=-8000, central_gravity=0.3, spring_length=150)

    for entity_type, nodes in kg["entities"].items():
        style = NODE_STYLES[entity_type]
        for n in nodes:
            label = (
                n.get("name")
                or n.get("recipe_name")
                or n.get("description", "")[:35]
            )
            tooltip_lines = [f"<b>{entity_type}</b>", f"ID: {n['id']}"]
            if n.get("recipe_name"):
                tooltip_lines.append(f"Name: {n['recipe_name']}")
            if n.get("food_cost") is not None:
                tooltip_lines.append(f"Food Cost: ${n['food_cost']:.4f}")
            if n.get("description"):
                tooltip_lines.append(f"Desc: {n['description'][:60]}")

            net.add_node(
                n["id"],
                label=label,
                color=style["color"],
                size=style["size"],
                shape=style["shape"],
                font={"size": style["font_size"], "color": "#ffffff"},
                title="<br>".join(tooltip_lines),
            )

    for rel in kg["relations"]:
        net.add_edge(
            rel["from_id"],
            rel["to_id"],
            title=rel["predicate"],
            color=EDGE_COLORS.get(rel["predicate"], "#888888"),
            arrows="to",
            width=1.2,
        )

    # Legend as extra HTML
    legend_html = """
    <div style="position:fixed;top:10px;right:10px;background:#1a1a2e;
                border:1px solid #444;padding:12px;border-radius:8px;
                color:#fff;font-family:sans-serif;font-size:13px;z-index:9999;">
      <b>Nodes</b><br><br>
      <span style="color:#E74C3C;">&#9733;</span> Station<br>
      <span style="color:#9B59B6;">&#9670;</span> Week<br>
      <span style="color:#E67E22;">&#9632;</span> Day<br>
      <span style="color:#F1C40F;">&#9670;</span> MealPeriod<br>
      <span style="color:#2980B9;">&#9679;</span> Recipe<br>
      <span style="color:#27AE60;">&#9679;</span> Ingredient<br><br>
      <hr style="border-color:#444">
      <b>Edges</b><br><br>
      <span style="color:#9B59B6;">─</span> HAS_WEEK<br>
      <span style="color:#E67E22;">─</span> HAS_DAY / SCHEDULED_ON<br>
      <span style="color:#F1C40F;">─</span> HAS_PERIOD / SERVED_IN_PERIOD<br>
      <span style="color:#E74C3C;">─</span> BELONGS_TO_STATION<br>
      <span style="color:#27AE60;">─</span> USES_INGREDIENT<br>
    </div>
    """

    net.save_graph(str(out_path))
    html = out_path.read_text(encoding="utf-8")

    # Build node-detail lookup for the info panel
    node_details: dict = {}
    for entity_type, nodes_list in kg["entities"].items():
        for n in nodes_list:
            detail = {"type": entity_type}
            if entity_type == "Recipe":
                detail["label"]    = n.get("name") or n.get("recipe_name", "")
                detail["cost"]     = f"${n['food_cost']:.4f}" if n.get("food_cost") else "—"
                detail["assembly"] = (n.get("assembly_instructions") or "")[:220]
                detail["special"]  = (n.get("special_instructions")  or "")[:120]
                # Count ingredients from relations
                ing_ids = [r["to_id"] for r in kg["relations"]
                           if r["from_id"] == n["id"] and r["predicate"] == "USES_INGREDIENT"]
                detail["ing_count"] = len(ing_ids)
                # Scheduled days
                sched_days = list({
                    r["to_id"].replace("day_", "")
                    for r in kg["relations"]
                    if r["from_id"] == n["id"] and r["predicate"] == "SCHEDULED_ON"
                })
                detail["days"] = ", ".join(sorted(sched_days)) or "—"
            elif entity_type == "Day":
                detail["label"]   = n.get("day_name", n["id"])
                detail["day_no"]  = n.get("day_no", "")
                detail["week_no"] = n.get("week_no", "")
            elif entity_type == "Ingredient":
                detail["label"] = n.get("description", "")
            elif entity_type == "Week":
                detail["label"] = f"Week {n.get('week_no', '')}"
            else:
                detail["label"] = n.get("name", n["id"])
            node_details[n["id"]] = detail

    focus_js = f"""
<style>
  #kg-info-panel {{
    position: fixed; top: 10px; left: 10px; width: 260px;
    background: #12122a; border: 1px solid #3a3a5c;
    border-radius: 10px; padding: 14px 16px;
    color: #e0e0ff; font-family: 'Segoe UI', sans-serif;
    font-size: 12.5px; z-index: 9999;
    box-shadow: 0 4px 24px rgba(0,0,0,0.6);
    max-height: 88vh; overflow-y: auto;
    transition: opacity 0.2s;
  }}
  #kg-info-panel h3 {{ margin: 0 0 8px 0; font-size: 14px; color: #a78bfa; }}
  #kg-info-panel .badge {{
    display: inline-block; padding: 2px 8px; border-radius: 12px;
    font-size: 11px; font-weight: bold; margin-bottom: 8px;
  }}
  #kg-info-panel .row {{ margin: 5px 0; line-height: 1.5; }}
  #kg-info-panel .key {{ color: #94a3b8; }}
  #kg-info-panel .val {{ color: #e2e8f0; }}
  #kg-info-panel hr {{ border-color: #2d2d4e; margin: 8px 0; }}
  #kg-info-panel .hint {{ color: #4a4a6a; font-size: 11px; margin-top: 10px; }}
</style>

<script>
(function() {{
  var NODE_DETAILS = {json.dumps(node_details, ensure_ascii=False)};
  var TYPE_COLORS  = {{
    "Station":"#E74C3C","Week":"#9B59B6","Day":"#E67E22",
    "MealPeriod":"#F1C40F","Recipe":"#2980B9","Ingredient":"#27AE60"
  }};

  // Info panel
  var panel = document.getElementById("kg-info-panel");

  function setPanel(nodeId) {{
    var d = NODE_DETAILS[nodeId];
    if (!d) {{ panel.innerHTML = "<div class='hint'>No info available.</div>"; return; }}
    var color  = TYPE_COLORS[d.type] || "#888";
    var html   = "<span class='badge' style='background:" + color + "22;color:" + color + ";border:1px solid " + color + "55'>" + d.type + "</span>";
    html += "<h3>" + (d.label || nodeId) + "</h3><hr>";
    html += "<div class='row'><span class='key'>ID: </span><span class='val'>" + nodeId + "</span></div>";
    if (d.cost)      html += "<div class='row'><span class='key'>Food Cost: </span><span class='val'>" + d.cost + "</span></div>";
    if (d.ing_count) html += "<div class='row'><span class='key'>Ingredients: </span><span class='val'>" + d.ing_count + "</span></div>";
    if (d.days)      html += "<div class='row'><span class='key'>Scheduled: </span><span class='val'>" + d.days + "</span></div>";
    if (d.day_no)    html += "<div class='row'><span class='key'>Day No: </span><span class='val'>" + d.day_no + " (Week " + d.week_no + ")</span></div>";
    if (d.assembly)  html += "<hr><div class='row'><span class='key'>Assembly:</span><br><span class='val'>" + d.assembly + "…</span></div>";
    if (d.special)   html += "<div class='row'><span class='key'>Special:</span><br><span class='val'>" + d.special + "</span></div>";
    html += "<div class='hint'>Click background to reset</div>";
    panel.innerHTML = html;
  }}

  function clearPanel() {{
    panel.innerHTML = "<div class='hint'>Click any node to explore</div>";
  }}

  clearPanel();

  // Focus-on-click
  network.once("stabilized", function() {{
    var origNode = {{}};
    var origEdge = {{}};
    nodes.get().forEach(function(n) {{
      origNode[n.id] = {{ color: n.color, size: n.size, font: n.font, borderWidth: n.borderWidth || 1 }};
    }});
    edges.get().forEach(function(e) {{
      origEdge[e.id] = {{ color: e.color, width: e.width || 1.2 }};
    }});

    var active = false;

    network.on("selectNode", function(params) {{
      var sel    = params.nodes[0];
      active     = true;
      var nbrs   = new Set(network.getConnectedNodes(sel));
      var nbEdge = new Set(network.getConnectedEdges(sel));
      nbrs.add(sel);

      nodes.update(nodes.get().map(function(n) {{
        if (nbrs.has(n.id)) {{
          var orig  = origNode[n.id];
          var isSel = (n.id === sel);
          var bg    = typeof orig.color === "string" ? orig.color : (orig.color && orig.color.background) || "#aaa";
          return {{
            id:          n.id,
            color:       isSel ? {{ background: bg, border: "#ffffff", highlight: {{ background: bg, border: "#fff" }} }} : orig.color,
            size:        isSel ? (orig.size || 18) * 1.45 : (orig.size || 18),
            borderWidth: isSel ? 4 : 2,
            font:        {{ color: "#ffffff", size: orig.font ? orig.font.size : 12 }},
          }};
        }} else {{
          return {{ id: n.id, color: {{ background: "#0d0d1a", border: "#1a1a2e" }},
                   borderWidth: 1, font: {{ color: "#1a1a2e" }}, size: origNode[n.id].size }};
        }}
      }}));

      edges.update(edges.get().map(function(e) {{
        if (nbEdge.has(e.id)) {{
          var oc = origEdge[e.id].color;
          var c  = typeof oc === "string" ? oc : (oc && oc.color) || "#888";
          return {{ id: e.id, color: {{ color: c, opacity: 1 }}, width: (origEdge[e.id].width || 1.2) * 2.8 }};
        }}
        return {{ id: e.id, color: {{ color: "#0d0d1a", opacity: 0.08 }}, width: 0.25 }};
      }}));

      setPanel(sel);
    }});

    network.on("deselectNode", function() {{
      if (!active) return;
      active = false;
      nodes.update(nodes.get().map(function(n) {{
        var o = origNode[n.id];
        return {{ id: n.id, color: o.color, size: o.size, borderWidth: o.borderWidth,
                 font: o.font || {{ color: "#ffffff" }} }};
      }}));
      edges.update(edges.get().map(function(e) {{
        var o = origEdge[e.id];
        return {{ id: e.id, color: o.color, width: o.width }};
      }}));
      clearPanel();
    }});
  }});
}})();
</script>
"""

    info_panel_html = '<div id="kg-info-panel"></div>'
    html = html.replace("</body>", info_panel_html + legend_html + focus_js + "\n</body>")
    out_path.write_text(html, encoding="utf-8")
    print(f"  [1] Interactive HTML: {out_path}")


# ---------------------------------------------------------------------------
# 2. Static PNG (networkx + matplotlib)
# ---------------------------------------------------------------------------

def build_static_png(kg: dict, out_path: Path):
    G = build_nx_graph(kg)

    # Separate layout: spring with heavy repulsion for clarity
    pos = nx.spring_layout(G, k=2.5, seed=42, iterations=60)

    fig, ax = plt.subplots(figsize=(24, 18))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#1a1a2e")

    # Draw by node type (layer-by-layer for z-order)
    for entity_type, style in NODE_STYLES.items():
        node_list = [
            n for n, d in G.nodes(data=True) if d.get("node_type") == entity_type
        ]
        nx.draw_networkx_nodes(
            G, pos, nodelist=node_list, ax=ax,
            node_color=style["color"],
            node_size=style["size"] * 40,
            alpha=0.9,
        )

    # Edge colors by predicate
    for predicate, ecolor in EDGE_COLORS.items():
        edge_list = [
            (u, v) for u, v, d in G.edges(data=True) if d.get("predicate") == predicate
        ]
        nx.draw_networkx_edges(
            G, pos, edgelist=edge_list, ax=ax,
            edge_color=ecolor, alpha=0.5,
            arrows=True, arrowsize=10, width=0.6,
            connectionstyle="arc3,rad=0.05",
        )

    # Labels only for Station, Week, Day, MealPeriod, Recipe (not ingredient — too many)
    label_nodes = {
        n: d["label"][:22]
        for n, d in G.nodes(data=True)
        if d.get("node_type") in {"Station", "Week", "Day", "MealPeriod", "Recipe"}
    }
    nx.draw_networkx_labels(
        G, pos, labels=label_nodes, ax=ax,
        font_size=6, font_color="#ffffff", font_weight="bold",
    )

    # Legend
    patches = [
        mpatches.Patch(color=v["color"], label=k)
        for k, v in NODE_STYLES.items()
    ]
    ax.legend(handles=patches, loc="upper left", facecolor="#2c2c54",
              edgecolor="#444", labelcolor="white", fontsize=10)

    ax.set_title(
        "Grill Station — Knowledge Graph",
        fontsize=18, color="white", pad=15, fontweight="bold",
    )
    ax.axis("off")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"  [2] Static PNG:       {out_path}")


# ---------------------------------------------------------------------------
# 3. Recipe Summary Bar Chart
# ---------------------------------------------------------------------------

def build_recipe_summary_chart(kg: dict, out_path: Path):
    recipes = kg["entities"].get("Recipe", [])
    relations = kg.get("relations", [])

    # Ingredient count per recipe
    ing_count: dict[str, int] = {}
    for rel in relations:
        if rel["predicate"] == "USES_INGREDIENT":
            ing_count[rel["from_id"]] = ing_count.get(rel["from_id"], 0) + 1

    # Meal period per recipe
    period_map: dict[str, str] = {}
    for rel in relations:
        if rel["predicate"] == "SERVED_IN_PERIOD":
            period_map[rel["from_id"]] = rel["to_id"].replace("period_", "")

    period_colors = {
        "Breakfast": "#E67E22",
        "Brunch":    "#8E44AD",
        "Lunch":     "#2980B9",
        "Dinner":    "#C0392B",
        "All Day":   "#27AE60",
    }

    # Sort by food_cost
    data = sorted(
        [
            {
                "id":     r["id"],
                "name":   r.get("recipe_name", r["id"])[:28],
                "cost":   r.get("food_cost") or 0.0,
                "ings":   ing_count.get(r["id"], 0),
                "period": period_map.get(r["id"], "Unknown"),
            }
            for r in recipes
        ],
        key=lambda x: x["cost"],
        reverse=True,
    )

    names    = [d["name"] for d in data]
    costs    = [d["cost"] for d in data]
    ings     = [d["ings"] for d in data]
    periods  = [d["period"] for d in data]
    colors   = [period_colors.get(p, "#95A5A6") for p in periods]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(18, 14))
    fig.patch.set_facecolor("#1a1a2e")
    for ax in (ax1, ax2):
        ax.set_facecolor("#16213e")
        ax.tick_params(colors="white")
        ax.spines[:].set_color("#444")
        for label in ax.get_xticklabels() + ax.get_yticklabels():
            label.set_color("white")

    # --- Bar 1: Food Cost ---
    bars = ax1.barh(names, costs, color=colors, edgecolor="#2c2c54", height=0.7)
    ax1.set_xlabel("Food Cost ($)", color="white", fontsize=11)
    ax1.set_title("Recipe Food Cost (sorted) — colored by Meal Period",
                  color="white", fontsize=13, fontweight="bold")
    ax1.invert_yaxis()
    for bar, cost in zip(bars, costs):
        ax1.text(bar.get_width() + 0.03, bar.get_y() + bar.get_height() / 2,
                 f"${cost:.2f}", va="center", color="white", fontsize=8)

    # Legend
    legend_patches = [
        mpatches.Patch(color=c, label=p) for p, c in period_colors.items()
    ]
    ax1.legend(handles=legend_patches, loc="lower right",
               facecolor="#2c2c54", edgecolor="#444", labelcolor="white", fontsize=9)

    # --- Bar 2: Ingredient Count ---
    ax2.barh(names, ings, color="#2980B9", edgecolor="#1a1a2e", height=0.7)
    ax2.set_xlabel("Number of Ingredients", color="white", fontsize=11)
    ax2.set_title("Ingredient Count per Recipe",
                  color="white", fontsize=13, fontweight="bold")
    ax2.invert_yaxis()
    for i, (name, count) in enumerate(zip(names, ings)):
        ax2.text(count + 0.2, i, str(count), va="center", color="white", fontsize=8)

    plt.tight_layout(pad=3)
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"  [3] Summary Chart:    {out_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not KG_JSON.exists():
        print(f"Error: knowledge_graph.json not found at {KG_JSON}")
        print("Pehle pipeline.py chalao:")
        print("  python 'knowledge _graph_main/pipeline.py'")
        sys.exit(1)

    print("Loading knowledge graph...")
    kg = load_graph(KG_JSON)

    entities  = kg.get("entities", {})
    total_nodes = sum(len(v) for v in entities.values())
    print(f"  Nodes: {total_nodes}, Relations: {len(kg.get('relations', []))}")
    print("\nGenerating visualizations...")

    build_interactive_html(kg, OUTPUT_DIR / "interactive_graph.html")
    build_static_png(kg,      OUTPUT_DIR / "static_graph.png")
    build_recipe_summary_chart(kg, OUTPUT_DIR / "recipe_summary.png")

    print(f"\nDone! Output folder: {OUTPUT_DIR}")
    print("  → Browser mein open karo: output/interactive_graph.html")


if __name__ == "__main__":
    main()
