"""
Telegram alert dispatcher for anomalies and canary failures.

Credentials are read from environment variables first; the hardcoded values
serve as defaults so the bot works out of the box without any configuration.

To suppress sending (e.g. local testing, CI):
    set TELEGRAM_ENABLED=false

To override credentials in a deployment environment:
    set TELEGRAM_BOT_TOKEN=<token>
    set TELEGRAM_CHAT_ID=<chat_id>

To widen the alert threshold to include warnings (default: critical only):
    set ALERT_MIN_SEVERITY=warning

Public API:
    async alert_anomalies(anomalies: list[dict]) -> None
        Sends one message per anomaly that meets the minimum severity threshold.

    async alert_canary_failures(failures: list[dict]) -> None
        Sends a single batched message summarising all canary failures.
"""

import asyncio
import logging
import os

import httpx

logger = logging.getLogger(__name__)

_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "8715732280:AAGguAAemvZ1-PuIGOenlytGa3Aaz2_pCX4")
_CHAT_ID: str   = os.getenv("TELEGRAM_CHAT_ID",   "-5243473656")
_ENABLED: bool  = os.getenv("TELEGRAM_ENABLED", "true").lower() not in ("false", "0", "no")

# Minimum severity level that triggers a Telegram message.
# "critical" → only critical anomalies; "warning" → warnings and critical.
_MIN_SEVERITY: str = os.getenv("ALERT_MIN_SEVERITY", "critical")

_SEVERITY_RANK: dict[str, int] = {"warning": 1, "critical": 2}
_MIN_SEVERITY_RANK: int = _SEVERITY_RANK.get(_MIN_SEVERITY, 2)

# Dedicated client for Telegram — kept separate from the search clients in
# core.py to avoid a monitoring → fetching circular import.
_client = httpx.AsyncClient(timeout=10)


def _passes_threshold(severity: str) -> bool:
    return _SEVERITY_RANK.get(severity, 0) >= _MIN_SEVERITY_RANK


async def _post(text: str) -> None:
    """Sends a single Telegram message. Errors are always suppressed."""
    if not _ENABLED:
        logger.debug("Telegram disabled — suppressing message: %s", text[:80])
        return
    try:
        url = f"https://api.telegram.org/bot{_BOT_TOKEN}/sendMessage"
        resp = await _client.post(
            url,
            json={"chat_id": _CHAT_ID, "text": text, "parse_mode": "HTML"},
        )
        resp.raise_for_status()
    except Exception:
        logger.debug("Telegram send failed", exc_info=True)


def _fmt_anomaly(a: dict) -> str:
    icon = "🔴" if a["severity"] == "critical" else "⚠️"
    lines = [
        f"{icon} <b>{a['anomaly_type']}</b>",
        f"Store: <code>{a['store']}</code>  |  Query: <code>{a['query']}</code>",
    ]
    for k, v in (a.get("details") or {}).items():
        lines.append(f"  • {k}: {v}")
    return "\n".join(lines)


async def alert_anomalies(anomalies: list[dict]) -> None:
    """Sends one Telegram message per anomaly that meets the severity threshold."""
    tasks = [
        _post(_fmt_anomaly(a))
        for a in anomalies
        if _passes_threshold(a.get("severity", ""))
    ]
    if tasks:
        await asyncio.gather(*tasks)


async def alert_canary_failures(failures: list[dict]) -> None:
    """Sends a single batched Telegram message summarising all canary failures."""
    if not failures:
        return
    lines = ["🚨 <b>Canary failures</b>"]
    for f in failures:
        lines.append(
            f"  • <code>{f['store']}</code> [{f['query']}]: {f['failure_reason']}"
        )
    await _post("\n".join(lines))
