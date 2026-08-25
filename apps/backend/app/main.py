from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth as auth_routes
from app.api.routes import dashboard as dashboard_routes
from app.api.routes import inspections as inspections_routes
from app.api.routes import reports as reports_routes
from app.api.routes import rules as rules_routes
from app.api.routes import users as users_routes
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="LM-SCAN — AI-Assisted Online Legal Metrology Compliance Inspection System",
    description=(
        "Preliminary, AI-assisted compliance screening tool for packaged-commodity "
        "online listings under the Legal Metrology (Packaged Commodities) Rules, 2011. "
        "This system does NOT issue legally binding determinations; every automated "
        "finding requires verification by an authorized officer."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_prefix = settings.api_v1_prefix
app.include_router(auth_routes.router, prefix=api_prefix)
app.include_router(users_routes.router, prefix=api_prefix)
app.include_router(inspections_routes.router, prefix=api_prefix)
app.include_router(rules_routes.router, prefix=api_prefix)
app.include_router(dashboard_routes.router, prefix=api_prefix)
app.include_router(reports_routes.router, prefix=api_prefix)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "lm-scan-backend"}
