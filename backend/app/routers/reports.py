"""Serve menu analysis reports: static .md or generate via agent and save to station_name_response."""
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

router = APIRouter(prefix="/reports", tags=["reports"])
log = logger


class ReportRequest(BaseModel):
    """Payload for report-by-station-and-period API."""
    station_name: str = Field(..., description="Station name (e.g. Grill)")
    meal_period: str = Field(..., description="Meal period (e.g. Breakfast, Lunch, Dinner)")


_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_EXPERIMENTS_DIR = _BACKEND_DIR / "experiments"
_STATION_RESPONSE_DIR = _EXPERIMENTS_DIR / "station_name_response"
_MENU_REPORT_LATEST = _EXPERIMENTS_DIR / "reports" / "menu_report_latest.md"
_MENU_REPORT_FALLBACK = _BACKEND_DIR / "menu_report.md"

_PLACEHOLDER = """## Menu Analysis Report

No report has been generated yet.

**To generate a report:** from the backend directory run:

- `uv sync --extra experiments`
- `uv run python -m experiments.menu_analyzer_agent`

Or call POST /api/reports/report with station_name and meal_period to generate and store per-period reports.
"""


def _slug(s: str) -> str:
    """Safe directory/file name from station or meal period."""
    out = re.sub(r"[^\w\s-]", "", s.strip())
    out = re.sub(r"[-\s]+", "_", out).strip("_")
    return out.lower() or "unknown"


def _report_content() -> str:
    if _MENU_REPORT_LATEST.is_file():
        return _MENU_REPORT_LATEST.read_text(encoding="utf-8")
    if _MENU_REPORT_FALLBACK.is_file():
        return _MENU_REPORT_FALLBACK.read_text(encoding="utf-8")
    return _PLACEHOLDER


def _station_period_paths(station_name: str, meal_period: str) -> tuple[Path, Path]:
    """Return (json_path, txt_path) for station_name_response/<station>/<meal_period>."""
    _STATION_RESPONSE_DIR.mkdir(parents=True, exist_ok=True)
    station_dir = _STATION_RESPONSE_DIR / _slug(station_name)
    station_dir.mkdir(parents=True, exist_ok=True)
    base = _slug(meal_period)
    return station_dir / f"{base}.json", station_dir / f"{base}.txt"


def _save_station_period_response(station_name: str, meal_period: str, response: dict) -> Path:
    """Save response to station_name_response/<station>/<meal_period>.json and report body to .txt."""
    import json
    json_path, txt_path = _station_period_paths(station_name, meal_period)
    json_path.write_text(json.dumps(response, indent=2), encoding="utf-8")
    content = response.get("content") or ""
    txt_path.write_text(content, encoding="utf-8")
    log.info(
        "[REPORTS] Saved report station={} meal_period={} json={} txt={} content_len={}",
        station_name, meal_period, json_path.name, txt_path.name, len(content),
    )
    return json_path


def _get_cached_report(station_name: str, meal_period: str) -> str | None:
    """Return cached report text from .txt if it exists and is non-empty, else None."""
    _, txt_path = _station_period_paths(station_name, meal_period)
    if not txt_path.is_file():
        return None
    text = txt_path.read_text(encoding="utf-8").strip()
    return text if text else None


@router.get("/report/{station_slug}/{meal_slug}")
def get_cached_report(station_slug: str, meal_slug: str):
    """
    Return cached report from saved .txt or .json. 404 if neither exists or content empty.
    FE can fall back to POST /report to generate.
    """
    import json
    log.info("[REPORTS] GET cached report station_slug={} meal_slug={}", station_slug, meal_slug)
    station_dir = _STATION_RESPONSE_DIR / station_slug
    txt_path = station_dir / f"{meal_slug}.txt"
    json_path = station_dir / f"{meal_slug}.json"
    content = None
    generated_at = None
    if txt_path.is_file():
        content = txt_path.read_text(encoding="utf-8").strip()
        log.debug("[REPORTS] Read from .txt path={} len={}", txt_path, len(content))
    if not content and json_path.is_file():
        data = json.loads(json_path.read_text(encoding="utf-8"))
        content = (data.get("content") or "").strip()
        generated_at = data.get("generated_at")
        log.debug("[REPORTS] Read from .json path={} content_len={}", json_path, len(content))
    if not content:
        log.info("[REPORTS] No cached report found → 404")
        from fastapi import Response
        return Response(status_code=404)
    log.info("[REPORTS] Returning cached report content_len={}", len(content))
    return {"content": content, "station_name": station_slug, "meal_period": meal_slug, "generated_at": generated_at}


@router.get("/menu-report")
def get_menu_report():
    """Return menu_report_latest.md, menu_report.md, or placeholder content. Never 404."""
    return {"content": _report_content()}


@router.post("/report", response_model=dict)
def get_report_by_station_and_period(payload: ReportRequest):
    """
    Run the menu analyzer for the given station_name and meal_period; return the report in the response.
    Response is also saved to station_name_response/<station_name>/<meal_period>.json and .txt.
    """
    log.info("[REPORTS] POST /report station_name={} meal_period={} → starting run_analysis", payload.station_name, payload.meal_period)
    try:
        from experiments.menu_analyzer_agent import run_analysis
    except ImportError as e:
        log.warning("[REPORTS] Menu analyzer not available (experiments): {}", e)
        raise HTTPException(
            status_code=503,
            detail="Menu analyzer not available. Install with: uv sync --extra experiments",
        ) from e

    content = run_analysis(payload.station_name, payload.meal_period)
    log.info("[REPORTS] run_analysis completed content_len={}", len(content or ""))
    if not (content and content.strip()):
        log.warning("[REPORTS] Report empty for station={} meal={}; returning 503", payload.station_name, payload.meal_period)
        raise HTTPException(
            status_code=503,
            detail="Report could not be generated for this meal period. The analysis may have timed out or returned no content. Please try again.",
        )
    response = {
        "station_name": payload.station_name,
        "meal_period": payload.meal_period,
        "content": content,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    saved_path = _save_station_period_response(
        payload.station_name, payload.meal_period, response
    )
    response["_saved_path"] = str(saved_path)
    return response
