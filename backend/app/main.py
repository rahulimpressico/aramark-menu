from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import routers
from app.auth_store import seed_on_startup


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_on_startup()
    yield


app = FastAPI(
    title="Ecommerce API",
    description="Backend API for the ecommerce project",
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

app.include_router(routers.health.router)
app.include_router(routers.auth.router)
app.include_router(routers.reports.router, prefix="/api")
