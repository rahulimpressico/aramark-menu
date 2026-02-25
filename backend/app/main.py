from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app import routers
from app.auth_store import seed_on_startup


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_on_startup()
    yield


app = FastAPI(
    title="Menu Analysis API",
    description="Backend API for menu analysis and reports",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes (health at /api and /api/health so GET / is free for the frontend)
app.include_router(routers.health.router, prefix="/api")
app.include_router(routers.auth.router)
app.include_router(routers.reports.router, prefix="/api")

# Serve frontend when static/ is present (e.g. Docker deploy: frontend build copied to backend/static)
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
