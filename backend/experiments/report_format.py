"""
Single canonical report format: straightforward, eye-catching, minimal explanation.
Costing analysis is appended by the backend.
"""
MAX_REPORT_WORDS = 180


def truncate_report_to_max_words(text: str, max_words: int = 180) -> str:
    """Ensure report body is at most max_words. Trims to last complete line if cut mid-sentence."""
    if not text or not text.strip():
        return text
    words = text.split()
    if len(words) <= max_words:
        return text.strip()
    truncated = " ".join(words[:max_words])
    last_newline = truncated.rfind("\n")
    if last_newline > 0:
        return truncated[:last_newline].strip()
    last_bullet = truncated.rfind("- ")
    if last_bullet > 0:
        return truncated[:last_bullet].strip()
    return truncated.strip()


# Approximate Gemini 2.5 Flash USD per 1M tokens (adjust if using another model)
COST_INPUT_PER_1M = 0.30
COST_OUTPUT_PER_1M = 2.50


def estimate_cost_usd(input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD from token counts using COST_*_PER_1M."""
    return (input_tokens / 1_000_000 * COST_INPUT_PER_1M) + (output_tokens / 1_000_000 * COST_OUTPUT_PER_1M)


def format_costing_analysis_section(input_tokens: int, output_tokens: int, cost_usd: float | None = None) -> str:
    """Return the ## Costing analysis markdown block to append at the end of every report."""
    if cost_usd is None:
        cost_usd = estimate_cost_usd(input_tokens, output_tokens)
    return (
        "\n\n## Costing analysis\n"
        f"- **Input token count:** {input_tokens:,}\n"
        f"- **Output token count:** {output_tokens:,}\n"
        f"- **Cost:** ${cost_usd:.4f} USD"
    )

REPORT_FORMAT_SPEC = """
The report must have exactly two sections in English. Nothing else.

## These are the gaps in the menu week-wise
- [bullet] gap 1 (what is missing or wrong per playbook)
- [bullet] gap 2
(If no gaps: write "No gaps found.")

## What you should do instead (based on playbook)
- [bullet] do this instead for gap 1
- [bullet] do this instead for gap 2
(If no gaps: write "None.")

Use clear, simple English. No other headings.
""".strip()

OVERALL_REPORT_FORMAT_INSTRUCTION = (
    "Only: ## These are the gaps in the menu (bullets) and ## What you should do instead (based on playbook) (bullets). All in English."
)
