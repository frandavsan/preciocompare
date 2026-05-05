"""
Telegram outbound dispatcher and notification helpers.

A single async worker drains a queue at ~1 message/second (Telegram's per-chat
rate limit), retries on 429, and HTML-escapes user content before formatting.
All public helpers are fire-and-forget enqueues — they never block the caller
and they never lose messages on burst load (queued, drained over a few seconds).

Lifecycle:
    start_worker()  — call from FastAPI startup; creates the queue + worker task
    stop_worker()   — call from FastAPI shutdown; cancels worker, closes client

Public helpers (sync, fire-and-forget):
    notify_login(email)
    notify_request(email, request_type, query=None)
    notify_canary_run(failures, total_checks)   # heartbeat: fires on success too
    alert_anomalies(anomalies)                  # backward-compat for service.py
    alert_canary_failures(failures)             # backward-compat for legacy callers

Inbound replies (used by the webhook handler):
    send_to_chat(chat_id, text)                 # direct send, no queue
"""

from __future__ import annotations

import asyncio
import html
import logging
from typing import Optional

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

_BOT_TOKEN: str = settings.telegram_bot_token
_CHAT_ID: str = settings.telegram_chat_id
_ENABLED: bool = settings.telegram_enabled

# Severity gating for anomaly alerts. "critical" → only critical;
# "warning" → warnings and critical.
_MIN_SEVERITY: str = settings.alert_min_severity
_SEVERITY_RANK: dict[str, int] = {"warning": 1, "critical": 2}
_MIN_SEVERITY_RANK: int = _SEVERITY_RANK.get(_MIN_SEVERITY, 2)

# Telegram per-chat send limit is ~1 msg/sec. The worker sleeps after each post
# to stay under the line; bursts are absorbed by the queue.
_SEND_INTERVAL_SECONDS = 1.0
_TELEGRAM_API = "https://api.telegram.org"

_queue: Optional[asyncio.Queue] = None
_worker_task: Optional[asyncio.Task] = None
_client: Optional[httpx.AsyncClient] = None


def _is_configured() -> bool:
    return _ENABLED and bool(_BOT_TOKEN) and bool(_CHAT_ID)


# ---------------------------------------------------------------------------
# Lifecycle (called from FastAPI startup/shutdown)
# ---------------------------------------------------------------------------


async def start_worker() -> None:
    """Initialize the queue, HTTP client, and background worker task."""
    global _queue, _worker_task, _client
    if _queue is not None:
        return
    _queue = asyncio.Queue()
    _client = httpx.AsyncClient(timeout=10.0)
    _worker_task = asyncio.create_task(_send_loop(), name="telegram-worker")
    if _is_configured():
        logger.info("Telegram worker started")
    else:
        logger.info("Telegram not fully configured — outbound messages will be dropped")


async def stop_worker() -> None:
    """Cancel the worker and close the HTTP client."""
    global _queue, _worker_task, _client
    if _worker_task is not None:
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
    if _client is not None:
        await _client.aclose()
    _queue = None
    _worker_task = None
    _client = None


# ---------------------------------------------------------------------------
# Internal queue + sender
# ---------------------------------------------------------------------------


def _enqueue(text: str) -> None:
    """Buffer a message for delivery. No-op when not configured or pre-startup."""
    if not _is_configured():
        return
    if _queue is None:
        logger.debug("Telegram queue not initialized; dropping message")
        return
    try:
        _queue.put_nowait(text)
    except asyncio.QueueFull:
        logger.warning("Telegram queue full; dropping message")


async def _send_loop() -> None:
    """Drains the queue, posting one message every _SEND_INTERVAL_SECONDS."""
    assert _queue is not None
    while True:
        try:
            text = await _queue.get()
            await _post_with_retry(text)
            await asyncio.sleep(_SEND_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Telegram worker error; continuing")
            await asyncio.sleep(_SEND_INTERVAL_SECONDS)


async def _post_with_retry(text: str) -> None:
    """Posts a single message with one retry on 429 (Telegram rate limit)."""
    if _client is None or not _BOT_TOKEN or not _CHAT_ID:
        return
    url = f"{_TELEGRAM_API}/bot{_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": _CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    for attempt in range(2):
        try:
            resp = await _client.post(url, json=payload)
            if resp.status_code == 429:
                retry_after = 2.0
                try:
                    retry_after = float(
                        resp.json().get("parameters", {}).get("retry_after", 2.0)
                    )
                except Exception:
                    pass
                logger.warning("Telegram 429; sleeping %.1fs before retry", retry_after)
                await asyncio.sleep(retry_after)
                continue
            if not resp.is_success:
                logger.warning(
                    "Telegram send failed: HTTP %d %s",
                    resp.status_code,
                    resp.text[:200],
                )
                return
            return
        except httpx.HTTPError as exc:
            logger.warning("Telegram send failed: %s", exc)
            return


async def send_to_chat(chat_id: int, text: str) -> None:
    """Direct send to a specific chat — used by webhook command replies, bypasses
    the outbound queue (replies are user-triggered, not bulk telemetry)."""
    if not _ENABLED or not _BOT_TOKEN:
        return
    if _client is None:
        # Webhook fired before startup completed — open a one-shot client.
        async with httpx.AsyncClient(timeout=10.0) as client:
            await _do_send(client, chat_id, text)
        return
    await _do_send(_client, chat_id, text)


async def _do_send(client: httpx.AsyncClient, chat_id: int, text: str) -> None:
    url = f"{_TELEGRAM_API}/bot{_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        resp = await client.post(url, json=payload)
        if not resp.is_success:
            logger.warning(
                "Telegram reply failed: HTTP %d %s",
                resp.status_code,
                resp.text[:200],
            )
    except httpx.HTTPError as exc:
        logger.warning("Telegram reply failed: %s", exc)


# ---------------------------------------------------------------------------
# Public notification helpers
# ---------------------------------------------------------------------------


def _esc(value: object) -> str:
    return html.escape(str(value or ""), quote=False)


def notify_login(email: str) -> None:
    _enqueue(f"<b>New login</b>\nUser: {_esc(email)}")


def notify_request(
    email: Optional[str], request_type: str, query: Optional[str] = None
) -> None:
    lines = [
        "<b>New request</b>",
        f"User: {_esc(email or 'unknown')}",
        f"Type: {_esc(request_type)}",
    ]
    if query:
        lines.append(f"Query: {_esc(query)}")
    _enqueue("\n".join(lines))


def notify_access_request(
    name: str,
    email: str,
    business_name: str,
    website_or_instagram: str,
    category: str,
) -> None:
    """Public-form access-request submission. Fire-and-forget — the frontend
    never waits for Telegram delivery, only for the endpoint's 200."""
    lines = [
        "<b>New signup!</b>",
        f"Nombre: {_esc(name)}",
        f"Email: {_esc(email)}",
        f"Negocio: {_esc(business_name)}",
        f"Sitio web o Instagram: {_esc(website_or_instagram)}",
        f"Categoría principal: {_esc(category)}",
    ]
    _enqueue("\n".join(lines))


def notify_canary_run(failures: list[dict], total_checks: int) -> None:
    """Heartbeat-style canary notification: fires whether or not there were failures."""
    if not failures:
        _enqueue(
            f"<b>Canary OK</b>\n{total_checks}/{total_checks} stores responding"
        )
        return
    lines = [
        "<b>Canary FAILURES</b>",
        f"{len(failures)}/{total_checks} stores failed",
    ]
    for f in failures:
        store = _esc(f.get("store", "unknown"))
        reason = _esc(f.get("failure_reason", "unknown"))
        lines.append(f"- {store}: {reason}")
    _enqueue("\n".join(lines))


# ---------------------------------------------------------------------------
# Backward-compat anomaly + canary alerts (existing callers)
# ---------------------------------------------------------------------------


def _passes_threshold(severity: str) -> bool:
    return _SEVERITY_RANK.get(severity, 0) >= _MIN_SEVERITY_RANK


def _fmt_anomaly(a: dict) -> str:
    label = "[CRITICAL]" if a.get("severity") == "critical" else "[WARNING]"
    lines = [
        f"<b>{label} {_esc(a.get('anomaly_type', 'anomaly'))}</b>",
        f"Store: {_esc(a.get('store', '?'))}  Query: {_esc(a.get('query', '?'))}",
    ]
    for k, v in (a.get("details") or {}).items():
        lines.append(f"- {_esc(k)}: {_esc(v)}")
    return "\n".join(lines)


async def alert_anomalies(anomalies: list[dict]) -> None:
    """Enqueues one message per anomaly that meets the severity threshold.
    Kept async for backward compatibility with `asyncio.create_task` callers."""
    for a in anomalies:
        if _passes_threshold(a.get("severity", "")):
            _enqueue(_fmt_anomaly(a))


async def alert_canary_failures(failures: list[dict]) -> None:
    """Backward-compat: failures-only alert. New callers should prefer
    notify_canary_run() so successful runs also produce a heartbeat message."""
    if not failures:
        return
    notify_canary_run(failures, total_checks=len(failures))
