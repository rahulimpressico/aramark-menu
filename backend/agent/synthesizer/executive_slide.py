"""
agent/synthesizer/executive_slide.py
======================================
Translate the aggregated output_json into a business-ready markdown report
using Gemini 2.5 Flash, fully aligned with the Collegiate Hospitality
Residential Menu & Station Playbook.

Setup
─────
  Add GEMINI_API_KEY to .env file in the project root:
    GEMINI_API_KEY=your_api_key_here

Flow
────
  formatting_executive_slide(output_json)
    ├─► Build playbook-aligned prompt from aggregated JSON
    ├─► Call Gemini 2.5 Flash
    ├─► Return markdown string
    └─► If Gemini fails / key missing → deterministic fallback

Playbook Reference  (Fresh & Fast / Grill Station)
────────────────────────────────────────────────────
  Core Offerings (static):
    • Burger (beef) — MAX 1/day
    • Chicken sandwich / hot dog
    • Fries — MIN 1/day
    • MTO Toppings Bar (condiments & garnishes)

  Enhancements (rotating):
    • Daily Feature (grilled chicken, hot dog, grilled cheese, etc.) — MAX 2/day, MUST ROTATE
    • Vegan Option — MIN 1/day
    • French Fry — MIN 1/day

  Menu Engineering / CPM:
    • Swap ≥1 beef burger/week for non-beef → lowers CPM by 18%
    • Diversify proteins: turkey burgers, chicken, fish sandwiches
    • MTO take-overs (Grilled Cheese) replace the beef burger slot on those days

  Climate Commitments:
    • 44% of entrees in the core menu template should be plant-based (Coolfood Pledge)
    • Net-Zero GHG by 2050; reduce food emissions 25% by 2030

  Ingredient Standards:
    • Cage-free eggs; responsibly sourced seafood (Monterey Bay); pork from group housing
    • Fresh seasonal produce daily; regional/global diversity
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

log = logging.getLogger("menu_agent.synthesizer")

_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class FormattingExecutiveSlideOutput:
    full_markdown: str = ""


# ---------------------------------------------------------------------------
# Playbook-aligned system prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a menu compliance analyst for Aramark Collegiate Hospitality.
Your job is simple: look at the menu data and clearly state what is NOT following the
Residential Playbook rules, and what the Playbook says about each issue.

PLAYBOOK RULES for Fresh & Fast (Grill Station):
- BURGER: Maximum 1 beef burger per day.
- DAILY FEATURE: Maximum 2 per day. Must rotate daily — same item every day is a violation.
- VEGAN: Minimum 1 plant-based main item per day.
- FRIES: Minimum 1 fried starch per day.
- MTO TOPPINGS BAR: Condiments and garnishes — NOT counted as entrees.
- PLANT-BASED: 44% of entrees should be plant-based (Aramark Coolfood Pledge).
- ROTATION: High repetition of any entree across multiple days signals poor rotation.
- CPM: Swapping 1 beef burger per week for a non-beef alternative lowers CPM by 18%.

OUTPUT FORMAT — follow exactly:

## Grill Station — [Meal Period] Playbook Review
**Status:** COMPLIANT  or  VIOLATION

---

## What Is Not Being Followed

For each violation, write:

**[Rule Name]**
- What the menu is doing: [exact count and recipe names]
- What the Playbook says: [exact rule in plain English]
- Gap: [one line explaining the difference]

---

## Rotation & Repetition Issues

### Diversity
- Diversity index: [value] ([unique entrees] unique / [slots] scheduled slots)
- Playbook says daily features must rotate. Items appearing on 4+ days:
    - [Recipe name]: [N] days ([day names])

### Plant-Based
- Current: [X%] of entrees are plant-based
- Playbook target: 44% (Aramark Coolfood Pledge)
- Gap: [X%] below target

---

## What the Playbook Recommends

Numbered list — one action per violation, cite the exact playbook rule:

1. [Specific action] — Playbook rule: "[quote the rule]"
2. ...

---

STRICT RULES:
- No emojis, no icons, no decorative symbols.
- No tables.
- Recipe names in **bold**.
- Numbers must be exact — taken directly from the data.
- Do not write about compliant items — focus only on what is wrong.
- Do not invent anything. Only use the data provided.
"""


# ---------------------------------------------------------------------------
# Prompt builder (playbook-aware, injects all relevant data)
# ---------------------------------------------------------------------------

def _build_prompt(state: dict[str, Any]) -> str:
    pb    = state.get("playbook_check",      {})
    di    = state.get("data_integrity",      {})
    rr    = state.get("rotation_recurrence", {})
    nc    = state.get("nutrition_cost",      {})

    meal_period = pb.get("meal_period", "Unknown")
    pb_status   = pb.get("status",      "UNKNOWN")
    categories  = pb.get("categories",  {})
    violations  = pb.get("violations",  [])
    sides       = pb.get("sides",       {})

    div         = rr.get("diversity_index", {})
    freq        = rr.get("item_frequency",  {})
    signals     = freq.get("recurrence_signals", [])
    frequencies = freq.get("frequencies", [])

    sustain     = nc.get("sustainability_mix", {})
    cpm         = nc.get("cpm_risk_swaps",     {})

    # ── Category table rows ───────────────────────────────────────────────────
    cat_rows = []
    for cat, meta in categories.items():
        recipes  = meta.get("recipes", [])
        rule     = meta.get("playbook_rule", "")
        count    = meta.get("count", 0)
        status   = meta.get("status", "ok")
        icon     = "✅ OK" if status == "ok" else "❌ FAIL"
        names    = ", ".join(recipes) if recipes else "—"
        cat_rows.append(
            f"  {cat.upper()}: count={count}, rule={rule}, status={icon}, recipes=[{names}]"
        )

    # ── High-repetition signal rows ───────────────────────────────────────────
    sig_rows = []
    for s in signals:
        matched_days: list[str] = []
        for fi in frequencies:
            if fi["recipe_name"] == s["recipe_name"]:
                matched_days = fi.get("days", [])
                break
        days_str = ", ".join(matched_days) if matched_days else "multiple days"
        sig_rows.append(
            f"  {s['recipe_name']} | {s['days']} days | {days_str}"
        )

    # ── Full frequency list (for table) ──────────────────────────────────────
    freq_rows = []
    for fi in frequencies[:10]:
        freq_rows.append(
            f"  {fi['recipe_name']} | {fi['appearance_count']} days | {', '.join(fi.get('days', []))}"
        )

    d_idx    = div.get("diversity_index", 0)
    pct      = sustain.get("plant_based_percent", 0)
    gap      = round(44 - pct, 1)
    cpm_recs = cpm.get("recommendations", [])
    station_name = aggregated_state.get("station_name") or pb.get("station_name") or "Station"

    prompt = f"""\
=== ANALYSIS DATA ===

STATION: {station_name}
MEAL PERIOD: {meal_period}
OVERALL STATUS: {pb_status}

--- PLAYBOOK COMPLIANCE ---
{chr(10).join(cat_rows)}

Violations: {violations if violations else "None"}

MTO Toppings Bar (static, NOT entrees): {sides.get("count",0)} items
  {", ".join(sides.get("recipes",[])) or "none"}

--- ROTATION & DIVERSITY ---
Diversity Index: {d_idx}
Unique entrees: {div.get("unique_entree_count",0)}
Scheduled slots: {div.get("entree_slots",0)}

High-repetition items (4+ days):
{chr(10).join(sig_rows) if sig_rows else "  None"}

All entrees by frequency:
{chr(10).join(freq_rows)}

--- PLANT-BASED ---
Plant-based %: {pct}%
Target: 44%
Gap: {gap}% below target
Plant-based recipes: {", ".join(sustain.get("plant_based_recipes",[])) or "none"}

=== END OF DATA ===

Now write the report following your instructions exactly.
Use only data above. No emojis. No icons. Bold recipe names.
"""
    return prompt


# ---------------------------------------------------------------------------
# Gemini call
# ---------------------------------------------------------------------------

def _call_gemini(prompt: str) -> str:
    """Call Gemini 2.5 Flash. Returns markdown text. Raises on failure."""
    try:
        from dotenv import load_dotenv
        load_dotenv(_ENV_PATH, override=False)
    except ImportError:
        pass

    api_key = (
        os.environ.get("GEMINI_API_KEY", "")
        or os.environ.get("GOOGLE_API_KEY", "")
    ).strip()

    if not api_key or api_key == "your_api_key_here":
        raise EnvironmentError(
            "GEMINI_API_KEY not set. Add it to .env:\n"
            "  GEMINI_API_KEY=your_api_key_here"
        )

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            temperature=0.2,        # low temp = consistent, factual output
            max_output_tokens=4096,
        ),
    )

    text = (response.text or "").strip()

    # Strip markdown code fences if Gemini wrapped output in ```markdown ... ```
    if text.startswith("```"):
        lines = text.splitlines()
        inner = [l for l in lines[1:] if l.strip() != "```"]
        text = "\n".join(inner).strip()

    return text


# ---------------------------------------------------------------------------
# Deterministic fallback (no LLM needed)
# ---------------------------------------------------------------------------

def _section(title: str, bullets: list[str]) -> str:
    body = "\n".join(f"- {b}" for b in bullets) if bullets else "- N/A"
    return f"## {title}\n\n{body}"


def _fallback_report(state: dict[str, Any]) -> str:
    pb   = state.get("playbook_check",      {})
    rr   = state.get("rotation_recurrence", {})
    nc   = state.get("nutrition_cost",      {})

    meal_period = pb.get("meal_period", "Unknown")
    pb_status   = pb.get("status",      "UNKNOWN")
    station_name = state.get("station_name") or pb.get("station_name") or "Station"
    categories  = pb.get("categories",  {})
    div_data    = rr.get("diversity_index", {})
    freq_data   = rr.get("item_frequency",  {})
    sustain     = nc.get("sustainability_mix", {})

    lines: list[str] = []
    lines.append(f"## {station_name} Station — {meal_period} Playbook Review")
    lines.append(f"**Status:** {pb_status}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## What Is Not Being Followed")
    lines.append("")

    has_violation = False
    for cat, meta in categories.items():
        if meta.get("status") == "ok":
            continue
        has_violation = True
        label   = cat.replace("_", " ").upper()
        count   = meta.get("count", 0)
        rule    = meta.get("playbook_rule", "")
        recipes = meta.get("recipes", [])
        names   = ", ".join(f"**{r}**" for r in recipes) if recipes else "none"
        parts = rule.split()
        rule_kind = parts[0].lower() if parts else ""
        rule_limit = int(parts[1]) if len(parts) > 1 and str(parts[1]).isdigit() else None
        if rule_kind == "max" and rule_limit is not None:
            viol = f"Exceeded by {max(0, count - rule_limit)} (got {count}, max {rule_limit})"
        elif rule_kind == "min" and rule_limit is not None:
            viol = f"Short by {max(0, rule_limit - count)} (got {count}, min {rule_limit})"
        else:
            viol = f"{count} offered, rule is {rule}"
        lines.append(f"**{label}**")
        menu_doing = f"{count} offered — {names}" if len(recipes) == count else f"{count} on at least one day ({len(recipes)} distinct in period) — {names}"
        lines.append(f"- What the menu is doing: {menu_doing}")
        lines.append(f"- Gap: {viol}")
        lines.append("")

    pct = sustain.get("plant_based_percent", 0.0)
    if not sustain.get("compliant_44"):
        has_violation = True
        gap = round(44.0 - pct, 1)
        pb_names = ", ".join(f"**{r}**" for r in sustain.get("plant_based_recipes", [])) or "none"
        lines.append("**PLANT-BASED**")
        lines.append(f"- What the menu is doing: {pct}% plant-based — {pb_names}")
        lines.append("- What the Playbook says: 44% of entrees should be plant-based (Aramark Coolfood Pledge).")
        lines.append(f"- Gap: {gap}% below the 44% target.")
        lines.append("")

    if not has_violation:
        lines.append("No violations found. Menu is compliant with all Playbook rules.")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Rotation & Repetition Issues")
    lines.append("")

    d_idx       = div_data.get("diversity_index", 0.0)
    unique      = div_data.get("unique_entree_count", 0)
    slots       = div_data.get("entree_slots", 0)
    signals     = freq_data.get("recurrence_signals", [])
    frequencies = freq_data.get("frequencies", [])

    lines.append("### Diversity")
    lines.append(f"- Diversity index: {d_idx} ({unique} unique entrees / {slots} scheduled slots)")
    if signals:
        lines.append("- Playbook says daily features must rotate. Items appearing on 4+ days:")
        for s in signals:
            matched_days: list[str] = []
            for fi in frequencies:
                if fi["recipe_name"] == s["recipe_name"]:
                    matched_days = fi.get("days", [])
                    break
            days_str = ", ".join(matched_days) if matched_days else "multiple days"
            lines.append(f"    - **{s['recipe_name']}**: {s['days']} days ({days_str})")
    else:
        lines.append("- No high-repetition items. Good rotation.")
    lines.append("")
    lines.append("### Plant-Based")
    lines.append(f"- Current: {pct}% of entrees are plant-based")
    lines.append("- Playbook target: 44% (Aramark Coolfood Pledge)")
    if not sustain.get("compliant_44"):
        lines.append(f"- Gap: {round(44.0-pct,1)}% below target")
    else:
        lines.append("- Status: Target met.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## What the Playbook Recommends")
    lines.append("")

    recs: list[str] = []
    for cat, meta in categories.items():
        if meta.get("status") == "ok":
            continue
        rule  = meta.get("playbook_rule", "")
        count = meta.get("count", 0)
        label = cat.replace("_", " ").title()
        if rule.startswith("max"):
            recs.append(f'Reduce **{label}** from {count} to the maximum allowed — Playbook rule: "{label}: {rule} per day. Must rotate daily."')
        elif rule.startswith("min"):
            recs.append(f'Add at least one **{label}** item — Playbook rule: "{label}: {rule} per day."')
    if not sustain.get("compliant_44"):
        recs.append(f'Increase plant-based offerings from {pct}% toward 44% — Playbook rule: "44% of entrees should be plant-based (Aramark Coolfood Pledge)."')
    if signals:
        sig_names = ", ".join(f'**{s["recipe_name"]}**' for s in signals[:2])
        recs.append(f'Rotate {sig_names} — Playbook rule: "Daily Features must rotate daily. High repetition across multiple days signals poor rotation."')
    for i, rec in enumerate(recs, 1):
        lines.append(f"{i}. {rec}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def formatting_executive_slide(aggregated_state: dict[str, Any]) -> str:
    """
    Translate the aggregated output_json into a playbook-aligned markdown report.
    Tries Gemini 2.5 Flash; falls back to deterministic markdown builder.
    """
    log.info(
        "[AGENT-TOOL] synthesizer: formatting_executive_slide START  keys=%s",
        list(aggregated_state.keys()) if isinstance(aggregated_state, dict) else "n/a",
    )

    try:
        prompt   = _build_prompt(aggregated_state)
        markdown = _call_gemini(prompt).strip()

        if len(markdown) >= 200:
            log.info(
                "[AGENT-TOOL] synthesizer: Gemini response OK  len=%d", len(markdown)
            )
            return markdown

        log.warning(
            "[AGENT-TOOL] synthesizer: Gemini response too short (len=%d), using fallback",
            len(markdown),
        )

    except EnvironmentError as e:
        log.warning("[AGENT-TOOL] synthesizer: %s — using fallback", e)
    except Exception as e:
        log.warning(
            "[AGENT-TOOL] synthesizer: Gemini call failed (%s: %s) — using fallback",
            type(e).__name__, e,
        )

    result = _fallback_report(aggregated_state)
    log.info(
        "[AGENT-TOOL] synthesizer: deterministic fallback used  len=%d", len(result)
    )
    return result
