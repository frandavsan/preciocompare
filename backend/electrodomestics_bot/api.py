import asyncio
import logging
import re
import time
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .auth import require_auth
from .config import settings
from .fetching import cache as _cache
from .fetching.adapters import ADAPTERS
from .models import ProductResponse, SearchResponse, StoreStatusResponse
from .fetching.service import search_products
from .pricing import generate_pricing_excel
from .monitoring import storage as _storage
from .monitoring.alerts import (
    notify_access_request,
    notify_login,
    notify_request,
    send_to_chat,
    start_worker as _start_telegram,
    stop_worker as _stop_telegram,
)
from . import scheduler as _scheduler

# Wall-clock when the process booted — used by the /health Telegram command.
_started_at = time.monotonic()

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(
    title="ElectrodomesticsBot API",
    description=(
        "Searches multiple Argentine electronics stores simultaneously and returns "
        "structured, comparable product data. All /search and /stores endpoints "
        "require a valid Supabase JWT in the Authorization header."
    ),
    version="1.0.0",
)
app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def _startup():
    await _start_telegram()
    _scheduler.start()


@app.on_event("shutdown")
async def _shutdown():
    _scheduler.stop()
    await _stop_telegram()


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    # Both rate-limited endpoints use a 1-minute window, so the worst-case wait
    # is always ≤60s. Advertise the full window as Retry-After so the client can
    # safely countdown without overshooting; the next request is accepted as
    # soon as the actual window slot frees, regardless of the advertised value.
    retry_after = 60
    return JSONResponse(
        status_code=429,
        content={"error": "Too many requests", "retry_after": retry_after},
        headers={"Retry-After": str(retry_after)},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled error on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(status_code=500, content={"error": "Internal server error"})


@app.get(
    "/search",
    response_model=SearchResponse,
    summary="Search all stores",
    description=(
        "Searches all configured stores concurrently for the given query and returns "
        "products grouped by store, plus per-store status metadata.\n\n"
        "**detail=false** (default): fast mode — installments show count and amount, "
        "no card names.\n\n"
        "**detail=true**: slow mode — extra requests per product for full card/bank names "
        "on installments. Roughly 2x slower."
    ),
    responses={
        401: {"description": "Missing or invalid Supabase JWT"},
        429: {"description": "Rate limit exceeded (10 requests/minute per IP)"},
        503: {"description": "Search failed — all stores errored or timed out"},
    },
)
@limiter.limit("10/minute")
async def search(
    request: Request,
    q: str = Query(description="Product model name or SKU (e.g. 'Samsung S26', 'PS5', '55PUD7310')"),
    detail: bool = Query(False, description="When true, fetches full card/bank names for installments (slower)"),
    # Argentine postal codes are either a 4-digit legacy code ("1425") or an 8-char CPA
    # ("A1425AAB": 1 letter + 4 digits + 3 letters). FastAPI rejects non-matching input
    # with 422, which is critical: self.postal_code is interpolated into a GraphQL query
    # string in platforms/fravega.py (_fetch_free_shipping). The regex gate is the only
    # thing keeping that path safe from injection.
    postal_code: Optional[str] = Query(
        None,
        pattern=r"^[A-Z]?\d{4}[A-Z]{0,3}$",
        description=(
            "Optional postal code for shipping simulation. When omitted, each adapter "
            "uses its default (CABA '1425' for VTEX/Fravega). Non-CABA codes bypass "
            "the cache. Format: 4 digits (e.g. '1425') or 8-char CPA (e.g. 'A1425AAB')."
        ),
    ),
    user: dict = Depends(require_auth),
):
    """Search all stores for a product model or SKU."""
    notify_request(user.get("email"), "Search", query=q)
    try:
        raw = await search_products(q, detail, postal_code=postal_code)
        results = {}
        store_status = {}
        for store, ssr in raw.items():
            results[store] = [ProductResponse.from_dataclass(p) for p in ssr.products]
            store_status[store] = StoreStatusResponse(
                status=ssr.status,
                result_count=len(ssr.products),
                error_detail=ssr.error_detail,
                duration_ms=ssr.duration_ms,
            )
        return SearchResponse(query=q, results=results, store_status=store_status)
    except Exception as e:
        logger.error("Search failed for query '%s': %s", q, e)
        raise HTTPException(status_code=503, detail="Search failed")


@app.get(
    "/stores",
    summary="List configured stores",
    description="Returns every store the API searches, with its name, base URL, and platform type.",
    responses={
        401: {"description": "Missing or invalid Supabase JWT"},
        429: {"description": "Rate limit exceeded (20 requests/minute per IP)"},
    },
)
@limiter.limit("20/minute")
async def stores(request: Request, user: dict = Depends(require_auth)):
    """List all configured stores with their platform."""
    return [
        {
            "name": a.name,
            "base_url": a.base_url,
            "platform": type(a).__bases__[0].__name__,
        }
        for a in ADAPTERS
    ]


@app.get(
    "/pricing/excel",
    summary="Generate and download payment-plan Excel",
    description=(
        "Searches the pricing stores (Cetrogar, OnCity, Castillo, Montes Hermanos), "
        "fetches every payment plan, fills the template spreadsheet, and returns "
        "the resulting `.xlsx` as an attachment. Heavier than `/search` — capped "
        "at 5 requests/minute per IP."
    ),
    responses={
        200: {
            "content": {
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}
            },
            "description": "Filled spreadsheet returned as a download.",
        },
        401: {"description": "Missing or invalid Supabase JWT"},
        404: {"description": "No products found in any pricing store"},
        429: {"description": "Rate limit exceeded (5 requests/minute per IP)"},
        503: {"description": "Pricing pipeline failed (template missing, fetch errors, etc.)"},
    },
)
@limiter.limit("5/minute")
async def pricing_excel(
    request: Request,
    # min_length=3 mirrors the CLI's pricing guard — anything shorter fans out
    # to every store and plan-fetch path with no chance of a useful match.
    q: str = Query(min_length=3, description="Product model name or SKU (e.g. 'Samsung S26', 'PS5')"),
    commerce_name: str | None = Query(
        default=None,
        max_length=120,
        description="Commerce name to place in the generated workbook.",
    ),
    user: dict = Depends(require_auth),
):
    """Run the pricing pipeline and stream the filled Excel as a download."""
    notify_request(user.get("email"), "Price analysis")
    try:
        output_path = await generate_pricing_excel(q, commerce_name=commerce_name)
    except FileNotFoundError as e:
        logger.error("Pricing template missing: %s", e)
        raise HTTPException(status_code=503, detail="Pricing template not configured")
    except Exception as e:
        logger.error("Pricing generation failed for '%s': %s", q, e, exc_info=True)
        raise HTTPException(status_code=503, detail="Pricing generation failed")

    if output_path is None:
        raise HTTPException(status_code=404, detail="No products found in pricing stores")

    return FileResponse(
        path=output_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=output_path.name,
    )


@app.get("/health", summary="Health check (public)")
async def health():
    """Public liveness probe — returns minimal status for load balancers and uptime monitors."""
    return {"status": "ok", "stores": len(ADAPTERS)}


@app.get(
    "/health/detail",
    summary="Detailed health check",
    description="Full operational health: scheduler state, canary results, last refresh summary, and monitoring DB size.",
    responses={401: {"description": "Missing or invalid Supabase JWT"}},
)
async def health_detail(user: dict = Depends(require_auth)):
    """Returns full system health — requires authentication."""
    canary_status = _storage.get_last_canary_per_store()
    last_refresh = _storage.get_last_refresh()
    db_size_mb = _storage.get_db_size_mb()

    return {
        "status": "ok",
        "stores": len(ADAPTERS),
        "scheduler": _scheduler.get_status(),
        "canary": {
            store: {
                "passed": bool(data["passed"]),
                "actual_count": data["actual_count"],
                "expected_min": data["expected_min"],
                "timestamp": data["timestamp"],
                "failure_reason": data.get("failure_reason"),
            }
            for store, data in canary_status.items()
        },
        "last_refresh": last_refresh,
        "monitoring_db_size_mb": round(db_size_mb, 2),
    }


@app.get(
    "/health/anomalies",
    summary="List open anomalies",
    responses={401: {"description": "Missing or invalid Supabase JWT"}},
)
async def health_anomalies(user: dict = Depends(require_auth)):
    """Returns all unacknowledged anomalies (null prices, zero results, installment drops) from the monitoring DB."""
    anomalies = _storage.get_open_anomalies()
    return {"count": len(anomalies), "anomalies": anomalies}


@app.post(
    "/health/anomalies/{anomaly_id}/acknowledge",
    summary="Acknowledge an anomaly",
    responses={
        401: {"description": "Missing or invalid Supabase JWT"},
        404: {"description": "Anomaly ID not found"},
    },
)
async def acknowledge_anomaly(anomaly_id: int, user: dict = Depends(require_auth)):
    """Marks a single anomaly as acknowledged so it no longer appears in /health/anomalies."""
    updated = _storage.acknowledge_anomaly(anomaly_id)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Anomaly {anomaly_id} not found")
    return {"acknowledged": True, "id": anomaly_id}


# ---------------------------------------------------------------------------
# Telemetry + Telegram bot
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Public access-request form (landing page)
# ---------------------------------------------------------------------------


_ALLOWED_CATEGORIES = {
    "Electrónica",
    "Electrodomésticos",
    "Informática",
    "Celulares",
    "Otro",
}
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_URL_OR_IG_RE = re.compile(
    r"^@[a-zA-Z0-9._]{1,30}$|^(https?://)?([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(/[^\s]*)?$"
)


class AccessRequest(BaseModel):
    """Public access-request payload from the landing page form. Field aliases
    match the camelCase keys the form sends."""

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=120)
    email: str = Field(..., min_length=1, max_length=180)
    business_name: str = Field(
        ..., alias="businessName", min_length=1, max_length=160
    )
    website_or_instagram: str = Field(
        ..., alias="websiteOrInstagram", min_length=1, max_length=220
    )
    category: str = Field(..., min_length=1, max_length=40)

    @field_validator("email")
    @classmethod
    def _validate_email(cls, v: str) -> str:
        if not _EMAIL_RE.match(v):
            raise ValueError("Usá un email válido.")
        return v

    @field_validator("website_or_instagram")
    @classmethod
    def _validate_url(cls, v: str) -> str:
        if not _URL_OR_IG_RE.match(v):
            raise ValueError("Ingresá una URL válida o un @ de Instagram.")
        return v

    @field_validator("category")
    @classmethod
    def _validate_category(cls, v: str) -> str:
        if v not in _ALLOWED_CATEGORIES:
            raise ValueError("Elegí una categoría válida.")
        return v


@app.post(
    "/access-request",
    summary="Public access-request form (landing page)",
    description=(
        "Receives the access-request form submitted from the landing page and "
        "fires a Telegram notification. No auth — public endpoint, rate-limited "
        "to 5 requests per minute per IP."
    ),
    responses={
        400: {"description": "Validation failed"},
        429: {"description": "Rate limit exceeded"},
    },
    status_code=200,
)
@limiter.limit("5/minute")
async def access_request(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400, content={"error": "Completá todos los campos."}
        )

    try:
        payload = AccessRequest.model_validate(body)
    except ValidationError as exc:
        # Surface the first user-facing message; deeper details go to logs only.
        msg = "Completá todos los campos."
        for err in exc.errors():
            ctx_msg = err.get("msg") or ""
            if ctx_msg and not ctx_msg.startswith("Value error, "):
                msg = ctx_msg
                break
            if ctx_msg.startswith("Value error, "):
                msg = ctx_msg.removeprefix("Value error, ")
                break
        return JSONResponse(status_code=400, content={"error": msg})

    notify_access_request(
        name=payload.name,
        email=payload.email,
        business_name=payload.business_name,
        website_or_instagram=payload.website_or_instagram,
        category=payload.category,
    )
    return {"ok": True}


@app.post(
    "/telemetry/login",
    summary="Record a successful sign-in (frontend telemetry)",
    description=(
        "Called by the frontend right after `signInWithPassword` succeeds. "
        "Fires a Telegram notification with the user's email. Returns 204."
    ),
    responses={
        401: {"description": "Missing or invalid Supabase JWT"},
        429: {"description": "Rate limit exceeded (10 requests/minute per IP)"},
    },
    status_code=204,
)
@limiter.limit("10/minute")
async def telemetry_login(request: Request, user: dict = Depends(require_auth)):
    notify_login(user.get("email") or "unknown")
    return Response(status_code=204)


@app.post("/telegram/webhook", include_in_schema=False)
async def telegram_webhook(request: Request):
    """Inbound endpoint for Telegram bot updates.

    Validates Telegram's secret-token header, ignores anything outside the
    configured chat, and dispatches /commands. The only command today is
    /health, which replies with a backend + frontend status snapshot."""
    expected = settings.telegram_webhook_secret
    if not expected:
        # Webhook intentionally disabled until a secret is configured.
        raise HTTPException(403, "Webhook disabled")
    received = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if received != expected:
        raise HTTPException(403, "Invalid webhook secret")

    try:
        update = await request.json()
    except Exception:
        return {"ok": False}

    message = update.get("message") or update.get("edited_message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()

    if not chat_id or not text:
        return {"ok": True}

    # Only respond inside the configured group — prevents random users who
    # discover the bot from triggering commands.
    if str(chat_id) != str(settings.telegram_chat_id):
        return {"ok": True}

    # "/health" or "/health@MyBot" → strip both the args and the @suffix.
    cmd = text.split()[0].split("@")[0].lower()

    if cmd == "/health":
        report = await _build_health_report()
        await send_to_chat(chat_id, report)

    return {"ok": True}


def _format_until(iso_str: Optional[str]) -> str:
    if not iso_str:
        return "n/a"
    try:
        dt = datetime.fromisoformat(iso_str)
        delta = (dt - datetime.now(timezone.utc)).total_seconds()
        if delta <= 0:
            return "now"
        h, rem = divmod(int(delta), 3600)
        m, _ = divmod(rem, 60)
        return f"{h}h {m}m" if h else f"{m}m"
    except Exception:
        return "n/a"


async def _check_frontend(url: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=3.0, follow_redirects=True) as client:
            resp = await client.head(url)
            label = "OK" if resp.is_success else "ERROR"
            return f"{resp.status_code} {label}"
    except Exception as exc:
        return f"unreachable ({type(exc).__name__})"


async def _build_health_report() -> str:
    """Plain-text health snapshot for the Telegram /health command."""
    uptime_s = int(time.monotonic() - _started_at)
    h, rem = divmod(uptime_s, 3600)
    m, _ = divmod(rem, 60)

    sched = _scheduler.get_status()
    canary = _storage.get_last_canary_per_store()
    open_anomalies = _storage.get_open_anomalies()

    n_passed = sum(1 for c in canary.values() if c.get("passed"))
    n_total = len(canary)

    next_canary = "n/a"
    for j in sched.get("jobs", []) or []:
        if j.get("id") == "canary":
            next_canary = _format_until(j.get("next_run_utc"))
            break

    sched_state = "running" if sched.get("running") else (
        "disabled" if not sched.get("enabled") else "stopped"
    )
    cache_state = "disabled" if _cache.CACHE_DISABLED else "enabled"
    frontend_status = await _check_frontend(settings.frontend_url)

    stores_line = (
        f"Stores up: {n_passed}/{n_total}" if n_total else "Stores up: no canary data yet"
    )
    lines = [
        "<b>Health check</b>",
        f"Backend: OK · uptime {h}h {m}m",
        f"Scheduler: {sched_state} · next canary in {next_canary}",
        stores_line,
        f"Anomalies open: {len(open_anomalies)}",
        f"Cache: {cache_state}",
        f"Frontend: {frontend_status}",
    ]
    return "\n".join(lines)
