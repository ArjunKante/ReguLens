"""Central application configuration.

All configuration is loaded from environment variables (see /.env.example at
the repository root). Nothing here should be hard-coded per-deployment; this
keeps secrets out of source control and lets Docker / CI / local dev share
the same code with different .env files.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> str | None:
    """Walk up from this file looking for a repo-root .env.

    Locally this file lives at apps/backend/app/core/config.py, four levels
    below the repo root. Inside the backend Docker image the same file lands
    at /app/app/core/config.py (the build context is apps/backend, copied to
    /app), which doesn't have four parent directories and previously made
    `.parents[4]` raise IndexError before the app could even start. Walking
    up and returning None when no .env is found lets Docker (which already
    injects config via real environment variables through docker-compose's
    `env_file:`) start cleanly without one.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".env"
        if candidate.exists():
            return str(candidate)
    return None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_find_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    environment: str = "development"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"
    app_name: str = "LM-SCAN"

    # --- Database ---
    database_url: str = "postgresql+psycopg://lmscan:lmscan@localhost:5432/lmscan"

    # --- Auth ---
    jwt_secret_key: str = "insecure-dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # --- CORS ---
    cors_allowed_origins: str = "http://localhost:5173,http://localhost:3000"

    # --- Storage ---
    storage_root: str = "./storage"
    max_upload_size_mb: int = 15

    # --- Scraping ---
    scraper_user_agent: str = (
        "LM-SCAN-Inspection-Bot/1.0 (+contact: compliance-tooling@example.gov; "
        "automated preliminary inspection tool; respects robots.txt)"
    )
    scraper_request_timeout_seconds: int = 20
    scraper_min_request_interval_seconds: float = 2.0
    scraper_max_images_per_product: int = 8
    playwright_headless: bool = True

    # --- OCR ---
    ocr_engine: str = "tesseract"
    tesseract_cmd: str = "tesseract"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def storage_path(self) -> Path:
        p = Path(self.storage_root)
        if not p.is_absolute():
            # Resolve relative paths against the backend package root (apps/backend),
            # not the process's current working directory — otherwise running
            # commands (pytest, uvicorn, scripts) from different directories would
            # each create their own separate storage tree.
            p = Path(__file__).resolve().parents[2] / p
        p.mkdir(parents=True, exist_ok=True)
        (p / "uploads").mkdir(parents=True, exist_ok=True)
        (p / "reports").mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()
