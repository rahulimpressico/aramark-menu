"""Serve menu analysis reports: static .md or generate via agent and save to station_name_response."""

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response
from loguru import logger
from pydantic import BaseModel, Field

router = APIRouter(prefix="/reports", tags=["reports"])
log = logger


class ReportRequest(BaseModel):
    """Payload for report-by-station-and-period API."""

    station_name: str = Field(..., description="Station name (e.g. Grill)")
    meal_period: str = Field(
        ..., description="Meal period (e.g. Breakfast, Lunch, Dinner)"
    )
    use_fast: bool = Field(
        default=True,
        description="Use fast path (1 LLM call). Set false for full agent pipeline.",
    )


class OverallReportRequest(BaseModel):
    """Payload for overall report API (synthesizes breakfast + lunch + dinner .txt via LLM)."""

    station_name: str = Field(default="Grill", description="Station name (e.g. Grill)")


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


_STATION_ALIASES = {
    "vegan": "Simply Vegan",
    "simply vegan": "Simply Vegan",
    "true balan": "True Balance",
    "true balance": "True Balance",
    "halal stree": "Halal Street Eats",
    "halal street eats": "Halal Street Eats",
    "saladbar": "Salad Bar",
    "salad bar": "Salad Bar",
}


def _canonical_station_name(name: str) -> str:
    key = re.sub(r"[^a-z0-9]+", " ", (name or "").strip().lower()).strip()
    return _STATION_ALIASES.get(key, name.strip())


def _legacy_station_slugs(station_slug: str) -> list[str]:
    if station_slug == "true_balance":
        return ["true_balan"]
    return []


def _resolve_station_dir_for_read(station_slug: str) -> Path:
    direct = _STATION_RESPONSE_DIR / station_slug
    if direct.is_dir():
        return direct
    for legacy in _legacy_station_slugs(station_slug):
        legacy_dir = _STATION_RESPONSE_DIR / legacy
        if legacy_dir.is_dir():
            return legacy_dir
    return direct


def _merge_legacy_station_cache(station_slug: str) -> None:
    target_dir = _STATION_RESPONSE_DIR / station_slug
    target_dir.mkdir(parents=True, exist_ok=True)
    for legacy in _legacy_station_slugs(station_slug):
        legacy_dir = _STATION_RESPONSE_DIR / legacy
        if not legacy_dir.is_dir():
            continue
        for p in legacy_dir.glob("*"):
            dest = target_dir / p.name
            if dest.exists():
                continue
            p.rename(dest)


def _ensure_station_artifacts(station_name: str) -> Path:
    """Generate cleaned Excel + station KG + normalized KG if missing."""
    station_slug = _slug(station_name)
    source_excel = (
        _BACKEND_DIR / "main_excel_file_dir" / "full dataset for CH residential.xlsx"
    )
    cleaned_excel = (
        _BACKEND_DIR / "main_excel_file_dir" / f"{station_slug}_station_only.xlsx"
    )
    station_kg = (
        _BACKEND_DIR / "knowledge _graph_main" / f"knowledge_graph_{station_slug}.json"
    )
    normalized_kg = (
        _BACKEND_DIR
        / "normalize_graph"
        / "output"
        / f"knowledge_graph_normalized_{station_slug}.json"
    )

    if normalized_kg.is_file():
        return normalized_kg

    if not source_excel.is_file():
        raise RuntimeError(f"Main Excel source not found: {source_excel}")
    cmds = [
        [
            sys.executable,
            str(_BACKEND_DIR / "excel_clean_script" / "clean_excel.py"),
            "--station",
            station_name,
            "--source",
            str(source_excel),
            "--output",
            str(cleaned_excel),
        ],
        [
            sys.executable,
            str(_BACKEND_DIR / "knowledge _graph_main" / "build_knowledge_graph.py"),
            "--station",
            station_name,
            "--source",
            str(cleaned_excel),
            "--output",
            str(station_kg),
        ],
        [
            sys.executable,
            str(_BACKEND_DIR / "normalize_graph" / "extract_graph_v2.py"),
            "--input",
            str(station_kg),
            "--output",
            str(normalized_kg),
        ],
    ]

    for cmd in cmds:
        proc = subprocess.run(
            cmd, cwd=str(_BACKEND_DIR), capture_output=True, text=True
        )
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip()
            raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{err}")

    if not normalized_kg.is_file():
        raise RuntimeError(f"Normalized station graph was not created: {normalized_kg}")
    return normalized_kg


def _report_content() -> str:
    if _MENU_REPORT_LATEST.is_file():
        return _MENU_REPORT_LATEST.read_text(encoding="utf-8")
    if _MENU_REPORT_FALLBACK.is_file():
        return _MENU_REPORT_FALLBACK.read_text(encoding="utf-8")
    return _PLACEHOLDER


def _station_period_paths(station_name: str, meal_period: str) -> tuple[Path, Path]:
    """Return (json_path, txt_path) for station_name_response/<station>/<meal_period>."""
    station_slug = _slug(station_name)
    _merge_legacy_station_cache(station_slug)
    station_dir = _STATION_RESPONSE_DIR / station_slug
    base = _slug(meal_period)
    station_dir.mkdir(parents=True, exist_ok=True)
    return station_dir / f"{base}.json", station_dir / f"{base}.txt"


def _save_station_period_response(
    station_name: str, meal_period: str, response: dict
) -> Path:
    """Save response to station_name_response/<station>/<meal_period>.json and markdown to .txt."""
    json_path, txt_path = _station_period_paths(station_name, meal_period)
    # Save full response JSON (includes analysis_json + markdown content)
    json_path.write_text(
        json.dumps(response, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    # Save markdown slide separately for quick reading
    content = response.get("content") or ""
    txt_path.write_text(content, encoding="utf-8")
    log.info(
        "[REPORTS] Saved report station={} meal_period={} json={} txt={} content_len={}",
        station_name,
        meal_period,
        json_path.name,
        txt_path.name,
        len(content),
    )
    return json_path


@router.get("/report/{station_slug}/{meal_slug}")
def get_cached_report(station_slug: str, meal_slug: str):
    """
    Return cached report from saved .txt or .json. 404 if neither exists or content empty.
    Includes token/cost from saved JSON when available so the UI can show them.
    FE can fall back to POST /report to generate.
    """
    log.info(
        "[REPORTS] GET cached report station_slug={} meal_slug={}",
        station_slug,
        meal_slug,
    )
    station_dir = _resolve_station_dir_for_read(station_slug)
    txt_path = station_dir / f"{meal_slug}.txt"
    json_path = station_dir / f"{meal_slug}.json"
    content = None
    generated_at = None
    usage = {}
    analysis = {}
    if txt_path.is_file():
        content = txt_path.read_text(encoding="utf-8").strip()
        log.debug("[REPORTS] Read from .txt path={} len={}", txt_path, len(content))
    if not content and json_path.is_file():
        data = json.loads(json_path.read_text(encoding="utf-8"))
        content = (data.get("content") or "").strip()
        generated_at = data.get("generated_at")
        usage = {
            "total_input_tokens": data.get("total_input_tokens", 0),
            "total_output_tokens": data.get("total_output_tokens", 0),
            "cost_usd": data.get("cost_usd"),
        }
        analysis = data.get("analysis") or {}
        log.debug(
            "[REPORTS] Read from .json path={} content_len={}", json_path, len(content)
        )
    if content and json_path.is_file() and not usage:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        usage = {
            "total_input_tokens": data.get("total_input_tokens", 0),
            "total_output_tokens": data.get("total_output_tokens", 0),
            "cost_usd": data.get("cost_usd"),
        }
        analysis = data.get("analysis") or {}
    if not content:
        log.info("[REPORTS] No cached report found → 404")
        return Response(status_code=404)
    log.info("[REPORTS] Returning cached report content_len={}", len(content))
    out = {
        "content": content,
        "station_name": station_slug,
        "meal_period": meal_slug,
        "generated_at": generated_at,
    }
    out["total_input_tokens"] = usage.get("total_input_tokens", 0)
    out["total_output_tokens"] = usage.get("total_output_tokens", 0)
    out["cost_usd"] = usage.get("cost_usd")
    out["analysis"] = analysis
    return out


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
    canonical_station = _canonical_station_name(payload.station_name)
    log.info(
        "[REPORTS] POST /report station_name={} (canonical={}) meal_period={} → starting run_analysis",
        payload.station_name,
        canonical_station,
        payload.meal_period,
    )
    try:
        import sys, os

        # Ensure project root is on path so menu_agent_analyzer can be imported
        _project_root = str(Path(__file__).resolve().parents[2])
        if _project_root not in sys.path:
            sys.path.insert(0, _project_root)
        from menu_agent_analyzer import run_analysis_fast
    except ImportError as e:
        log.warning("[REPORTS] menu_agent_analyzer not available: {}", e)
        raise HTTPException(
            status_code=503,
            detail=f"Menu analyzer not available: {e}",
        ) from e

    try:
        _ensure_station_artifacts(canonical_station)
    except Exception as e:
        log.warning(
            "[REPORTS] Station preparation failed station={} err={}",
            canonical_station,
            e,
        )
        raise HTTPException(
            status_code=503,
            detail=f"Station data preparation failed for {canonical_station}: {e}",
        ) from e

    log.info("[REPORTS] Using run_analysis_fast (deterministic + Gemini slide)")
    result = run_analysis_fast(canonical_station, payload.meal_period)

    if result.get("no_data"):
        detail = (
            result.get("error_detail")
            or f"No data found for station {canonical_station} and meal period {payload.meal_period}."
        )
        raise HTTPException(status_code=404, detail=detail)

    content = result.get("content") or ""  # Gemini markdown slide
    analysis_json = result.get("analysis_json") or {}  # full deterministic JSON
    analysis = result.get("analysis") or {}  # source data used for report
    usage = result.get("usage") or {}
    log.info(
        "[REPORTS] run_analysis completed content_len={} usage={}", len(content), usage
    )

    if not content.strip():
        log.warning(
            "[REPORTS] Report empty for station={} meal={}; returning 503",
            payload.station_name,
            payload.meal_period,
        )
        raise HTTPException(
            status_code=503,
            detail="Report could not be generated. Please try again.",
        )

    response = {
        "station_name": canonical_station,
        "meal_period": payload.meal_period,
        "content": content,
        "analysis_json": analysis_json,
        "analysis": analysis,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_input_tokens": usage.get("total_input_tokens", 0),
        "total_output_tokens": usage.get("total_output_tokens", 0),
        "cost_usd": usage.get("cost_usd"),
    }
    saved_path = _save_station_period_response(
        canonical_station, payload.meal_period, response
    )
    response["_saved_path"] = str(saved_path)
    return response


def _read_cached_report_text(station_slug: str, meal_slug: str) -> str:
    """Return cached report body from .txt or .json for station/meal. Empty string if missing."""
    station_dir = _resolve_station_dir_for_read(station_slug)
    txt_path = station_dir / f"{meal_slug}.txt"
    if txt_path.is_file():
        return txt_path.read_text(encoding="utf-8").strip()
    json_path = station_dir / f"{meal_slug}.json"
    if json_path.is_file():
        data = json.loads(json_path.read_text(encoding="utf-8"))
        return (data.get("content") or "").strip()
    return ""


def _read_cached_report_json(station_slug: str, meal_slug: str) -> dict:
    """Return full cached report dict from .json for station/meal. Empty dict if missing."""
    station_dir = _resolve_station_dir_for_read(station_slug)
    json_path = station_dir / f"{meal_slug}.json"
    if json_path.is_file():
        try:
            return json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


@router.get("/combined/{station_slug}", response_model=dict)
def get_combined_report(station_slug: str):
    """
    Return combined report for a station: Breakfast + Lunch + Dinner in one response.
    Reads cached .txt/.json per meal period. No LLM call. 404 if no cached reports.
    """
    log.info("[REPORTS] GET combined report station_slug={}", station_slug)
    periods = [("breakfast", "Breakfast"), ("lunch", "Lunch"), ("dinner", "Dinner")]
    sections: dict[str, str] = {}
    usage_total = {"total_input_tokens": 0, "total_output_tokens": 0, "cost_usd": 0.0}
    for slug, label in periods:
        content = _read_cached_report_text(station_slug, slug)
        sections[label] = content
        data = _read_cached_report_json(station_slug, slug)
        if data:
            usage_total["total_input_tokens"] += data.get("total_input_tokens") or 0
            usage_total["total_output_tokens"] += data.get("total_output_tokens") or 0
            usage_total["cost_usd"] += float(data.get("cost_usd") or 0)

    if not any(sections[k].strip() for k in sections):
        log.info("[REPORTS] No cached reports for combined → 404")
        raise HTTPException(
            status_code=404,
            detail="No cached reports found for this station. Generate Breakfast, Lunch, and Dinner reports first.",
        )

    combined_parts = []
    for label in ("Breakfast", "Lunch", "Dinner"):
        body = sections[label].strip()
        if body:
            combined_parts.append(f"## {label}\n\n{body}")
    combined_content = "\n\n---\n\n".join(combined_parts)

    log.info(
        "[REPORTS] Returning combined report content_len={}", len(combined_content)
    )
    return {
        "content": combined_content,
        "sections": sections,
        "station_name": station_slug,
        "total_input_tokens": usage_total["total_input_tokens"],
        "total_output_tokens": usage_total["total_output_tokens"],
        "cost_usd": round(usage_total["cost_usd"], 4),
    }


@router.post("/overall", response_model=dict)
def get_overall_report(payload: OverallReportRequest):
    """
    Read breakfast.txt, lunch.txt, dinner.txt for the station; send their content to an LLM
    to produce one overall executive report. Returns that report in the response.
    Requires cached reports (generate per-period reports first). Needs GOOGLE_API_KEY.
    """
    canonical_station = _canonical_station_name(payload.station_name)
    log.info(
        "[REPORTS] POST /overall station_name={} (canonical={})",
        payload.station_name,
        canonical_station,
    )
    station_slug = _slug(canonical_station)
    reports = {
        "Breakfast": _read_cached_report_text(station_slug, "breakfast"),
        "Lunch": _read_cached_report_text(station_slug, "lunch"),
        "Dinner": _read_cached_report_text(station_slug, "dinner"),
    }
    if not any(reports[k].strip() for k in reports):
        log.warning("[REPORTS] No cached reports for station={} → 404", station_slug)
        raise HTTPException(
            status_code=404,
            detail="No cached reports found for this station. Generate Breakfast, Lunch, and Dinner reports first (e.g. from the meal-period pages).",
        )
    try:
        import sys

        _project_root = str(Path(__file__).resolve().parents[2])
        if _project_root not in sys.path:
            sys.path.insert(0, _project_root)
        from experiments.overall_report import generate_overall_report
    except ImportError as e:
        log.warning("[REPORTS] Overall report not available (experiments): {}", e)
        raise HTTPException(
            status_code=503,
            detail="Overall report requires experiments (uv sync --extra experiments) and GEMINI_API_KEY or GOOGLE_API_KEY in .env.",
        ) from e
    except EnvironmentError as e:
        log.warning("[REPORTS] Overall report API key missing: {}", e)
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY or GOOGLE_API_KEY not set. Add to backend/.env",
        ) from e
    content = generate_overall_report(reports, station_name=payload.station_name)
    if not content.strip():
        raise HTTPException(
            status_code=503,
            detail="LLM returned an empty overall report. Try again.",
        )
    return {
        "content": content,
        "station_name": canonical_station,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
