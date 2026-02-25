# Expose router submodules so main can use routers.health.router, routers.auth.router, routers.reports.router
from app.routers import health, auth, reports

__all__ = ["health", "auth", "reports"]
