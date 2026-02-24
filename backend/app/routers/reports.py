"""Serve generated reports (e.g. menu_report.md) from backend directory."""
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/reports", tags=["reports"])

# backend dir: app/routers/reports.py -> app -> backend
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_MENU_REPORT_PATH = _BACKEND_DIR / "menu_report.md"


@router.get("/menu-report")
def get_menu_report():
    """Return menu_report.md content if the file exists in backend dir."""
    if not _MENU_REPORT_PATH.is_file():
        raise HTTPException(status_code=404, detail="Report not found")
    return {"content": _MENU_REPORT_PATH.read_text(encoding="utf-8")}
