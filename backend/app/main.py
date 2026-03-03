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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    def _serve_spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        path = STATIC_DIR / full_path
        if path.is_file() and not full_path.startswith(".."):
            return FileResponse(path)
        return FileResponse(STATIC_DIR / "index.html")
else:
    @app.get("/")
    def _root():
        return {"message": "Menu Analysis API", "status": "ok"}
