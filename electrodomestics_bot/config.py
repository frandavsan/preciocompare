"""
Centralized configuration via environment variables.

Every deployment-relevant setting lives here. Pydantic Settings reads
from env vars automatically (case-insensitive), so ``DATA_DIR=...`` in
the environment maps to ``settings.data_dir``.

No .env file is needed — env vars are injected by Docker, Railway,
or whatever host runs the service.
"""

import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # -- Database --
    # Absolute path, or relative to project root.
    data_dir: str = os.path.join(
        os.path.normpath(os.path.join(os.path.dirname(__file__), "..")),
        "data",
    )

    # -- Auth --
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
