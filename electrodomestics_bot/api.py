import logging

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .auth import require_auth
from .fetching.adapters import ADAPTERS
from .models import ProductResponse, SearchResponse, StoreStatusResponse
from .fetching.service import search_products
from .monitoring import storage as _storage

logging.basicConfig(
    level=logging.INFO,
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
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"error": "Too many requests"})


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
    user: dict = Depends(require_auth),
):
    """Search all stores for a product model or SKU."""
    try:
        raw = await search_products(q, detail)
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


@app.get("/health", summary="Health check")
async def health():
    """Returns system health: store count, last canary probe results, last refresh summary, and monitoring DB size."""
    canary_status = _storage.get_last_canary_per_store()
    last_refresh = _storage.get_last_refresh()
    db_size_mb = _storage.get_db_size_mb()

    return {
        "status": "ok",
        "stores": len(ADAPTERS),
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


@app.get("/health/anomalies", summary="List open anomalies")
async def health_anomalies():
    """Returns all unacknowledged anomalies (null prices, zero results, installment drops) from the monitoring DB."""
    anomalies = _storage.get_open_anomalies()
    return {"count": len(anomalies), "anomalies": anomalies}


@app.post(
    "/health/anomalies/{anomaly_id}/acknowledge",
    summary="Acknowledge an anomaly",
    responses={404: {"description": "Anomaly ID not found"}},
)
async def acknowledge_anomaly(anomaly_id: int):
    """Marks a single anomaly as acknowledged so it no longer appears in /health/anomalies."""
    updated = _storage.acknowledge_anomaly(anomaly_id)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Anomaly {anomaly_id} not found")
    return {"acknowledged": True, "id": anomaly_id}
