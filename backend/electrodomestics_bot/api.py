import logging
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .auth import require_auth
from .config import settings
from .fetching.adapters import ADAPTERS
from .models import ProductResponse, SearchResponse, StoreStatusResponse
from .fetching.service import search_products
from .pricing import generate_pricing_excel
from .monitoring import storage as _storage
from . import scheduler as _scheduler

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
    _scheduler.start()


@app.on_event("shutdown")
async def _shutdown():
    _scheduler.stop()


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
    user: dict = Depends(require_auth),
):
    """Run the pricing pipeline and stream the filled Excel as a download."""
    try:
        output_path = await generate_pricing_excel(q)
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
