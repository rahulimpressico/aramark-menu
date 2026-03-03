# Aramark Menu Intelligence System

An end-to-end analysis pipeline for the Aramark Collegiate Hospitality Grill station — from raw Excel data to a playbook-compliant markdown report served via API.

---

## Project Overview

This system analyzes the weekly menu of the Grill station against the Aramark Residential Playbook. The pipeline runs in the following stages:

1. Filter raw Excel data (Grill station only)
2. Build a Knowledge Graph (entities + relationships)
3. Normalize the graph
4. Filter the graph by meal period
5. Run multiple deterministic analysis agents
6. Generate a markdown report via Gemini 2.5 Flash
7. Serve the report through a FastAPI endpoint

---

## Project Structure

```
advance-rahul-menu/
│
├── main_excel_file_dir/               # Raw input data
│   ├── full dataset for CH residential.xlsx
│   └── Grill_station_only.xlsx        # Filtered output
│
├── excel_clean_script/
│   └── clean_excel.py                 # Step 1: Filter Excel by station
│
├── knowledge _graph_main/             # Step 2: Knowledge Graph builder
│   ├── schema.py                      # Entity and Relation dataclasses
│   ├── normalizer.py                  # Data cleaning and normalization
│   ├── graph_builder.py               # Graph construction logic
│   ├── pipeline.py                    # End-to-end pipeline runner
│   ├── build_knowledge_graph.py       # Entry point
│   └── knowledge_graph.json           # Output: raw Knowledge Graph
│
├── normalize_graph/                   # Step 3: Graph normalization
│   ├── extract_graph_v2.py            # Normalizes graph, preserves edge attributes
│   └── viz/
│       └── visualize_filtered.py      # Interactive filtered graph visualization
│
├── graph_visualization/
│   └── visualize.py                   # Full graph interactive visualization
│
├── agent/                             # Step 5: Analysis agents
│   ├── menu_structure/
│   │   └── playbook_check.py          # Playbook compliance checker
│   ├── data_integrity/
│   │   └── period_overlap.py          # Duplicate and overlap detector
│   ├── rotation_recurrence/
│   │   ├── diversity_index.py         # Menu diversity score
│   │   └── item_frequency.py          # Recipe repetition tracker
│   ├── nutrition_cost/
│   │   ├── sustainability_mix.py      # Plant-based percentage calculator
│   │   └── cpm_risk_swaps.py          # CPM risk and swap recommendations
│   └── synthesizer/
│       └── executive_slide.py         # Gemini 2.5 Flash report generator
│
├── menu_agent_analyzer.py             # Steps 4+5+6: Main orchestrator
│
├── app/                               # Step 7: FastAPI application
│   ├── main.py                        # App entry point
│   └── routers/
│       └── reports.py                 # /api/reports/* endpoints
│
├── ProjectDocs/                       # Reference documents
│   ├── Playbook.md                    # Aramark Grill Station Playbook
│   └── ...
│
├── .env                               # API keys (GEMINI_API_KEY)
└── requirements.txt
```

---

## Step-by-Step Flow

### Step 1 — Excel Filter

**Script:** `excel_clean_script/clean_excel.py`

The raw Excel file contains data for all stations. This script filters rows where `station_name = "Grill"` and saves the result as `Grill_station_only.xlsx`.

```bash
python excel_clean_script/clean_excel.py
```

---

### Step 2 — Knowledge Graph Build

**Scripts:** `knowledge _graph_main/`

Builds a structured Knowledge Graph (JSON) from the filtered Excel file.

- **Nodes (Entities):** `Station`, `Recipe`, `Ingredient`, `Day`, `MealPeriod`, `Week`
- **Edges (Relations):** `SERVES`, `SCHEDULED_ON`, `SERVED_IN_PERIOD`, `HAS_INGREDIENT`, `HAS_PERIOD`, `IN_WEEK`

```bash
python "knowledge _graph_main/build_knowledge_graph.py"
```

Output: `knowledge _graph_main/knowledge_graph.json`

---

### Step 3 — Graph Normalization

**Script:** `normalize_graph/extract_graph_v2.py`

Normalizes the raw Knowledge Graph — deduplication, ID standardization, and most importantly, preserves the `period` attribute on `SCHEDULED_ON` edges so that meal period filtering works correctly downstream.

```bash
python normalize_graph/extract_graph_v2.py
```

Output: `knowledge_graph_normalized.json` (project root)

> **Note:** Skipping this step will cause incorrect meal period filtering because the `period` attribute will be missing from edges.

---

### Step 4+5+6 — Main Analysis Orchestrator

**Script:** `menu_agent_analyzer.py`

This is the main entry point for the entire analysis pipeline. It:

1. Loads `knowledge_graph_normalized.json`
2. Stores the graph in a `MenuGraph` class
3. Filters the graph by meal period using `filter_by_meal_period(meal_period)`
4. Runs all deterministic agents
5. Combines results into a single consolidated JSON
6. Calls `formatting_executive_slide()` to invoke Gemini
7. Returns the markdown report and analysis JSON

```bash
# Run from the command line
python menu_agent_analyzer.py --period Dinner
python menu_agent_analyzer.py --period Breakfast
python menu_agent_analyzer.py --period Lunch
python menu_agent_analyzer.py --list-periods
```

---

## Agents — What They Do and How

### Agent 1 — `agent/menu_structure/playbook_check.py`

**Function:** `checking_playbook_bounds(graph)`

Checks the menu against the Grill Station Playbook rules.

| Category | Playbook Rule | What It Checks |
|---|---|---|
| Burger | max 1 per day | Number of beef burgers scheduled |
| Daily Feature | max 2 per day, must rotate | Feature count and uniqueness across days |
| Vegan | min 1 per day | Presence of plant-based main items |
| Fries | min 1 per day | Presence of fried starch items |

Sides and MTO toppings (condiments, garnishes) are excluded from entree counts.

**Output:**
```json
{
  "meal_period": "Dinner",
  "status": "VIOLATION",
  "categories": {
    "daily_feature": { "count": 8, "playbook_rule": "max 2", "status": "fail", "recipes": [...] }
  },
  "violations": ["..."],
  "sides": { "count": 7, "recipes": [...] }
}
```

---

### Agent 2 — `agent/data_integrity/period_overlap.py`

**Function:** `detecting_period_overlap(graph)`

Detects if the same recipe appears in two different meal periods on the same day. This flags data entry errors or scheduling conflicts.

**Output:**
```json
{
  "compliant": true,
  "total_count": 0,
  "overlaps": [],
  "message": "No overlapping recipes detected."
}
```

---

### Agent 3 — `agent/rotation_recurrence/diversity_index.py`

**Function:** `calculating_diversity_index(graph)`

Measures menu variety using a 0–1 diversity index. Only entrees are counted — sides and condiments are excluded to avoid inflating the score with static topping bar items.

```
Diversity Index = unique entrees / total entree slots
```

- `1.0` = a different item every day (best rotation)
- `0.0` = the same item every day (no rotation)

**Output:**
```json
{
  "diversity_index": 0.59,
  "unique_entree_count": 10,
  "entree_slots": 17,
  "repeated_static_count": 2,
  "side_count": 7,
  "message": "Moderate diversity..."
}
```

---

### Agent 4 — `agent/rotation_recurrence/item_frequency.py`

**Function:** `tracking_item_frequency(graph)`

Counts how many days each recipe is scheduled across the menu cycle. Any non-side recipe that appears on 4 or more days is added to `recurrence_signals` as a rotation risk.

**Output:**
```json
{
  "frequencies": [
    { "recipe_name": "Crinkle French Fries", "appearance_count": 5, "days": ["Monday", "Tuesday", ...] }
  ],
  "recurrence_signals": [
    { "recipe_name": "Crinkle French Fries", "days": 5 }
  ]
}
```

---

### Agent 5 — `agent/nutrition_cost/sustainability_mix.py`

**Function:** `evaluating_sustainability_mix(graph)`

Calculates what percentage of entrees are plant-based and compares against the Aramark Coolfood Pledge target of 44%.

Plant-based items are identified using keywords: `black bean`, `veggie`, `beyond`, `impossible`, `plant`, `vegan`, etc.

**Output:**
```json
{
  "plant_based_percent": 9.5,
  "plant_based_recipes": ["Grilled Black Bean Burger"],
  "total_entree_slots": 17,
  "compliant_44": false,
  "message": "Plant-based mix is 34.5% below the 44% Coolfood Pledge target."
}
```

---

### Agent 6 — `agent/nutrition_cost/cpm_risk_swaps.py`

**Function:** `calculating_cpm_risk_swaps(graph)`

Assesses the beef vs. non-beef protein mix and determines CPM (Contribution-Per-Meal) risk level.

| Risk Level | Condition |
|---|---|
| High | Beef slots > 60% of all protein slots |
| Medium | Beef slots between 30–60% |
| Low | Beef slots < 30% |

Also generates actionable swap recommendations (e.g., replacing 1 beef burger per week with a turkey burger reduces CPM by 18%).

**Output:**
```json
{
  "beef_slots": 2,
  "alt_slots": 4,
  "cpm_risk_level": "medium",
  "alt_recipes": ["Grilled Black Bean Burger", "Crispy Chicken Sandwich"],
  "recommendations": ["Consider replacing 1 beef burger slot with a non-beef alternative..."]
}
```

---

### Agent 7 — `agent/synthesizer/executive_slide.py`

**Function:** `formatting_executive_slide(aggregated_state)`

Takes the combined JSON output from all agents and generates a clean, playbook-aligned markdown report using Gemini 2.5 Flash. Falls back to a deterministic report builder if the API call fails.

**Internal flow:**
```
aggregated_state (dict with all agent outputs)
    → _build_prompt()       Converts JSON into a structured text prompt
    → _call_gemini()        Calls Gemini 2.5 Flash (temperature=0.2, max_tokens=4096)
    → markdown string       Clean report with no icons or decorative elements
    → _fallback_report()    Used if Gemini is unavailable
```

**Report sections:**
- `## What Is Not Being Followed` — each violation with the playbook rule cited
- `## Rotation & Repetition Issues` — diversity index, high-repetition items, plant-based gap
- `## What the Playbook Recommends` — numbered actions with quoted playbook rules

---

## API — FastAPI Endpoints

**Start the server:**
```bash
uvicorn app.main:app --reload
```

---

### POST `/api/reports/report`

Run the menu analysis for a given station and meal period.

**Request:**
```json
{
  "station_name": "Grill",
  "meal_period": "Dinner"
}
```

**Response:**
```json
{
  "station_name": "Grill",
  "meal_period": "Dinner",
  "content": "## Grill Station — Dinner Playbook Review\n...",
  "analysis_json": { ... },
  "generated_at": "2026-03-02T10:00:00Z",
  "total_input_tokens": 1200,
  "total_output_tokens": 800
}
```

The report is automatically saved to:
- `experiments/station_name_response/grill/dinner.json`
- `experiments/station_name_response/grill/dinner.txt`

---

### GET `/api/reports/report/{station_slug}/{meal_slug}`

Returns a previously generated cached report without triggering a new LLM call.

```
GET /api/reports/report/grill/dinner
```

---

### POST `/api/reports/overall`

Combines the cached Breakfast, Lunch, and Dinner reports for a station into a single overall executive report via LLM.

```json
{ "station_name": "Grill" }
```

> All three per-period reports must be generated before calling this endpoint.

---

### GET `/api/health`

```json
{ "status": "ok" }
```

---

## Environment Setup

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Add your Gemini API key to .env
echo "GEMINI_API_KEY=your_key_here" > .env
```

**Dependencies in `requirements.txt`:**
- `fastapi`, `uvicorn` — API server
- `pandas`, `openpyxl` — Excel processing
- `google-genai` — Gemini 2.5 Flash
- `python-dotenv` — .env file loading
- `loguru` — structured logging
- `pyvis`, `networkx` — graph visualization

---

## Consolidated Output JSON Structure

The `analysis_json` returned by `run_analysis_fast()` has the following structure:

```json
{
  "meal_period": "Dinner",
  "station": "Grill",
  "playbook_check": {
    "status": "VIOLATION",
    "categories": {
      "daily_feature": { "count": 8, "playbook_rule": "max 2", "status": "fail", "recipes": ["..."] },
      "burger":        { "count": 1, "playbook_rule": "max 1", "status": "ok",   "recipes": ["..."] }
    },
    "violations": ["The menu offers 8 daily features, exceeding the maximum of 2."],
    "sides": { "count": 7, "recipes": ["American Cheese", "Lettuce", "..."] }
  },
  "data_integrity": {
    "compliant": true,
    "total_count": 0,
    "overlaps": []
  },
  "rotation_recurrence": {
    "diversity_index": {
      "diversity_index": 0.59,
      "unique_entree_count": 10,
      "entree_slots": 17
    },
    "item_frequency": {
      "frequencies": [
        { "recipe_name": "Crinkle French Fries", "appearance_count": 5, "days": ["Monday", "Tuesday", "..."] }
      ],
      "recurrence_signals": [
        { "recipe_name": "Crinkle French Fries", "days": 5 }
      ]
    }
  },
  "nutrition_cost": {
    "sustainability_mix": {
      "plant_based_percent": 9.5,
      "compliant_44": false
    },
    "cpm_risk_swaps": {
      "cpm_risk_level": "medium",
      "beef_slots": 2,
      "alt_slots": 4
    }
  }
}
```

---

## Data Flow Diagram

```
full dataset for CH residential.xlsx
            |
            v
   clean_excel.py  ──────────────────────>  Grill_station_only.xlsx
            |
            v
  build_knowledge_graph.py  ─────────────>  knowledge_graph.json
            |
            v
  extract_graph_v2.py  ──────────────────>  knowledge_graph_normalized.json
            |
            v
  menu_agent_analyzer.py
    |
    |── filter_by_meal_period(meal_period)
    |
    |── [Agent 1] playbook_check        ──>  compliance violations
    |── [Agent 2] period_overlap        ──>  duplicate detection
    |── [Agent 3] diversity_index       ──>  rotation score (0–1)
    |── [Agent 4] item_frequency        ──>  repetition signals
    |── [Agent 5] sustainability_mix    ──>  plant-based percentage
    |── [Agent 6] cpm_risk_swaps        ──>  protein cost risk
    |
    |── [Synthesizer] executive_slide
            |── _build_prompt()
            |── Gemini 2.5 Flash API
            └── markdown report
            |
            v
      FastAPI  ──>  POST /api/reports/report
            |
            v
      experiments/station_name_response/grill/dinner.json
      experiments/station_name_response/grill/dinner.txt
```

---

## Reference Documents

| File | Purpose |
|---|---|
| `ProjectDocs/Playbook.md` | Aramark Grill Station Playbook — source of all rules |
| `ProjectDocs/Project_Goal.txt` | Original project objective |
| `ProjectDocs/Project_Implementation_Plan.txt` | Implementation plan |
| `ProjectDocs/Breakfast grill.pdf` | Breakfast menu reference |
| `ProjectDocs/Lunch grill.pdf` | Lunch menu reference |
| `ProjectDocs/Dinner grill.pdf` | Dinner menu reference |
| `ProjectDocs/All day grill.pdf` | All-day menu reference |
