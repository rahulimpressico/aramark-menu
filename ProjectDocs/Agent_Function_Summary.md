# Agent Functions (Simple Summary)

## run_analysis_fast()
- This is the main function that runs the full backend analysis.
- It loads station data, filters by meal period, runs all agent functions, and creates one final report.
- It also returns structured JSON and markdown output for frontend.

## checking_playbook_bounds()
- We created predefined lists of words for each playbook category, like "cheeseburger" for burger, "black bean burger" for vegan, "french fries" for fries, and "sliced tomato" for side.
- Then we set daily limits (burger max 1, vegan min 1, fries min 1, daily feature max 2) as per the playbook.
- The system counts recipe names and checks if the menu follows the playbook rules or not.
- It also gives day-wise count and violations.

## detecting_period_overlap()
- This checks if the same recipe is repeated wrongly in the same period/day or across multiple periods.
- It reads schedule edges from graph and flags overlap issues.
- Output tells whether data integrity is okay or not.

## calculating_diversity_index()
- This calculates variety score for entree items.
- Side/condiment items are excluded so score is fair.
- Formula used:
  - diversity_index = unique_entree_count / entree_slots
- Higher value means better variety and better rotation.

## tracking_item_frequency()
- This counts on how many different days each recipe appears.
- If one recipe appears on 4 or more days, it is flagged as high repetition.
- Helps in rotation check.

## evaluating_sustainability_mix()
- This checks plant-based percentage using keyword matching from recipe and ingredient text.
- Formula used:
  - plant_based_percent = (plant_based_count / total_offerings) * 100
- It compares result against 44% target.

## calculating_cpm_risk_swaps()
- This checks protein mix risk (beef vs alternatives like chicken/turkey/fish/plant-based).
- It counts:
  - beef_slots
  - alt_slots
- Main threshold logic:
  - beef_recurrence_high = beef_slots >= 3
  - non_beef_alternatives_diversified = alt_slots >= 2
- Based on this, it marks CPM risk as high/medium/low and gives swap recommendations.

## formatting_executive_slide()
- This function makes the final readable markdown report.
- It first tries Gemini output.
- If Gemini fails, it uses fallback deterministic report, so output is always generated.

## _call_gemini()
- This function sends prompt to Gemini 2.5 flash.
- It reads API key from env file.
- It returns clean markdown text for final report.

---

## Short Answer (as asked)

### Diversity Index
- diversity_index = unique_entree_count / entree_slots
- Only entree items are counted (not sides/condiments).

### CPM Risk
- Count beef slots and alternative slots.
- Apply threshold checks (`beef >= 3`, `alt >= 2`).
- Mark risk as high/medium/low and suggest swaps.
