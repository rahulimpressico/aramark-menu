import os
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from loguru import logger

from app.routers import reports


def _configure_logging() -> None:
    level = (os.environ.get("LOG_LEVEL") or "DEBUG").upper()
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> — <level>{message}</level>",
    )


_configure_logging()

app = FastAPI(
    title="Menu Analysis API",
    description="Backend API for Aramark menu analysis and reports",
    version="0.1.0",
)

_cors_origins_raw = (os.environ.get("CORS_ALLOW_ORIGINS") or "*").strip()
if _cors_origins_raw == "*":
    _cors_allow_origins = ["*"]
    _cors_allow_credentials = False
else:
    _cors_allow_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
    _cors_allow_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allow_origins,
    allow_credentials=_cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(reports.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}


# Serve frontend static build when present
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.is_dir():
    _static_root = STATIC_DIR.resolve()
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    def _serve_spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        path = (_static_root / full_path).resolve()
        if path.is_file() and path.is_relative_to(_static_root):
            return FileResponse(path)
        return FileResponse(STATIC_DIR / "index.html")
else:
    @app.get("/")
    def _root():
        return {"message": "Menu Analysis API", "status": "ok"}
