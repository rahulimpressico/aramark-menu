"""Serve the latest menu analysis report (menu_report_latest.md or fallback menu_report.md)."""
from pathlib import Path

from fastapi import APIRouter

router = APIRouter(prefix="/reports", tags=["reports"])

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_MENU_REPORT_LATEST = _BACKEND_DIR / "experiments" / "reports" / "menu_report_latest.md"
_MENU_REPORT_FALLBACK = _BACKEND_DIR / "menu_report.md"

_PLACEHOLDER = """## Menu Analysis Report

No report has been generated yet.

**To generate a report:** from the backend directory run:

- `uv sync --extra experiments`
- `uv run python -m experiments.menu_analyzer_agent`

The report will be saved to `experiments/reports/menu_report_latest.md`.

You can also place a report at `backend/menu_report.md` to serve a static report.
"""


def _report_content() -> str:
    if _MENU_REPORT_LATEST.is_file():
        return _MENU_REPORT_LATEST.read_text(encoding="utf-8")
    if _MENU_REPORT_FALLBACK.is_file():
        return _MENU_REPORT_FALLBACK.read_text(encoding="utf-8")
    return _PLACEHOLDER


@router.get("/menu-report")
def get_menu_report():
    """Return menu_report_latest.md, menu_report.md, or placeholder content. Never 404."""
    return {"content": _report_content()}
