"""
Generate one overall executive report from Breakfast, Lunch, and Dinner report contents.
Reads cached .txt content and sends to LLM to synthesize a single markdown report.
Requires GOOGLE_API_KEY or GEMINI_API_KEY (loaded from .env). Used by POST /api/reports/overall.
"""
import os

from dotenv import load_dotenv

from experiments.log_config import log

load_dotenv()


def generate_overall_report(reports: dict[str, str], model_name: str = "gemini-2.5-flash") -> str:
    """
    Send meal-period report contents to the LLM and return one synthesized overall report (markdown).
    reports: e.g. {"Breakfast": "...", "Lunch": "...", "Dinner": "..."}. Missing keys get "(No report)."
    """
    parts = []
    for period in ("Breakfast", "Lunch", "Dinner"):
        text = (reports.get(period) or "").strip()
        parts.append(f"## {period}\n{text if text else '(No report available for this period.)'}")
    context = "\n\n---\n\n".join(parts)

    prompt = """You are a menu analysis summarizer. Below are three meal-period reports (Breakfast, Lunch, Dinner) for a single station. They cover structure, playbook alignment, rotation, diversity, and recommendations per period.

Your task: Write ONE overall executive summary report in markdown that:
1. Synthesizes findings across all three meal periods.
2. States overall station health, playbook alignment, and any cross-period patterns (e.g. rotation, diversity).
3. Lists the most important recommendations across the day.
4. Uses clear headings (e.g. ## Overall summary, ## Key findings, ## Recommendations) and brief bullet points where appropriate.
5. Does not repeat long verbatim text from the inputs; summarize and consolidate.
6. Develop a premium, enterprise-grade report.

Output only the markdown report, no preamble."""

    full_message = f"{prompt}\n\n## Input reports\n\n{context}"

    log.info("[OVERALL] Calling LLM for overall report model={} input_len={}", model_name, len(full_message))
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "GOOGLE_API_KEY or GEMINI_API_KEY required for overall report. "
            "Set in environment or in a .env file in the backend directory."
        )
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        llm = ChatGoogleGenerativeAI(model=model_name, temperature=0, api_key=api_key)
        response = llm.invoke(full_message)
        content = response.content if hasattr(response, "content") else str(response)
        out = (content or "").strip()
        log.info("[OVERALL] LLM returned report_len={}", len(out))
        return out
    except Exception as e:
        log.exception("[OVERALL] LLM failed: {}", e)
        raise
