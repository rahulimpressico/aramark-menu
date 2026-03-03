"""
Generate one overall executive report from Breakfast, Lunch, and Dinner period reports using Gemini.

Called by POST /api/reports/overall. Requires GEMINI_API_KEY or GOOGLE_API_KEY in env.
"""
import os
from pathlib import Path

_OVERALL_SYSTEM = """You are an expert menu analyst for collegiate dining. Your task is to write ONE concise overall executive report in Markdown that synthesizes the given Breakfast, Lunch, and Dinner period reports for a single station (e.g. Grill).

Rules:
- Write in clear, professional Markdown. Use ## for main sections, ** for emphasis, - for bullets.
- Structure: start with a 2–3 sentence executive summary, then 2–4 sections (e.g. Playbook compliance across the day, Rotation & variety, Nutrition/cost highlights, Top recommendations).
- Do not repeat long verbatim text from the inputs; summarize and highlight patterns, gaps, and actions.
- Call out specific meal periods (Breakfast/Lunch/Dinner) only when the finding is period-specific.
- End with 3–5 concrete recommended actions. Keep total length under 800 words."""

_OVERALL_USER_TEMPLATE = """Synthesize the following three meal-period reports for station "{station_name}" into one overall executive report.

---
## Breakfast
{breakfast}

---
## Lunch
{lunch}

---
## Dinner
{dinner}
---

Produce a single Markdown document: executive summary, then synthesized sections, then recommended actions. Do not include the raw input again."""


def generate_overall_report(reports: dict[str, str], station_name: str = "Grill") -> str:
    """
    Send Breakfast, Lunch, Dinner report text to Gemini and return one combined overall report (Markdown).
    reports: {"Breakfast": "...", "Lunch": "...", "Dinner": "..."}
    """
    breakfast = (reports.get("Breakfast") or "").strip() or "(No report content)"
    lunch = (reports.get("Lunch") or "").strip() or "(No report content)"
    dinner = (reports.get("Dinner") or "").strip() or "(No report content)"

    user_prompt = _OVERALL_USER_TEMPLATE.format(
        station_name=station_name,
        breakfast=breakfast,
        lunch=lunch,
        dinner=dinner,
    )

    try:
        from dotenv import load_dotenv
        _env = Path(__file__).resolve().parent.parent / ".env"
        load_dotenv(_env, override=False)
    except Exception:
        pass

    api_key = (
        os.environ.get("GEMINI_API_KEY", "")
        or os.environ.get("GOOGLE_API_KEY", "")
    ).strip()

    if not api_key or api_key == "your_api_key_here":
        raise EnvironmentError(
            "GEMINI_API_KEY or GOOGLE_API_KEY not set. Add to backend/.env"
        )

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=_OVERALL_SYSTEM,
            temperature=0.2,
            max_output_tokens=4096,
        ),
    )

    text = (response.text or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        inner = [l for l in lines[1:] if l.strip() != "```"]
        text = "\n".join(inner).strip()
    return text
