"""
Centralized configuration via environment variables.

Every deployment-relevant setting lives here. Pydantic Settings reads
from env vars automatically (case-insensitive), so ``DATA_DIR=...`` in
the environment maps to ``settings.data_dir``.

In production (Docker, Railway, etc.) env vars are injected directly.
For local development, a ``backend/.env`` file is loaded if present —
gitignored, so secrets never leak.
"""

import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.join(
            os.path.normpath(os.path.join(os.path.dirname(__file__), "..")),
            ".env",
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # -- Database --
    # Absolute path, or relative to project root.
    data_dir: str = os.path.join(
        os.path.normpath(os.path.join(os.path.dirname(__file__), "..")),
        "data",
    )

    # -- Auth --
    # Project URL used to fetch JWKS for ES256/RS256 verification.
    supabase_url: str = ""
    # Legacy HS256 shared secret. Only required for projects still on symmetric signing.
    supabase_jwt_secret: str = ""

    # -- CORS --
    # Comma-separated origins in the env var, e.g. "https://app.example.com,https://staging.example.com"
    cors_origins: list[str] = []

    # -- Logging --
    log_level: str = "INFO"

    # -- Telegram alerts --
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_enabled: bool = True
    alert_min_severity: str = "critical"

    # -- Scheduler --
    scheduler_enabled: bool = True
    # Cron expression fields: minute hour day month day_of_week
    refresh_cron: str = "0 8 * * *"       # daily at 08:00 UTC
    canary_interval_hours: int = 4        # every 4 hours


settings = Settings()
