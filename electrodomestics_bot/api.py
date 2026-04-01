import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .fetching.adapters import ADAPTERS
from .models import ProductResponse, SearchResponse
from .fetching.service import search_products
from .monitoring import storage as _storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="ElectrodomesticsBot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled error on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(status_code=500, content={"error": "Internal server error"})


@app.get("/search", response_model=SearchResponse)
async def search(q: str, detail: bool = False):
    """Search all stores for a product model or SKU."""
    try:
        results = await search_products(q, detail)
        return SearchResponse(
            query=q,
            results={
                store: [ProductResponse.from_dataclass(p) for p in products]
                for store, products in results.items()
            },
        )
    except Exception as e:
        logger.error("Search failed for query '%s': %s", q, e)
        raise HTTPException(status_code=503, detail="Search failed")


@app.get("/stores")
async def stores():
    """List all configured stores with their platform."""
    return [
        {
            "name": a.name,
            "base_url": a.base_url,
            "platform": type(a).__bases__[0].__name__,
        }
        for a in ADAPTERS
    ]


@app.get("/health")
async def health():
    """Health check — includes last canary status per store and last refresh summary."""
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


@app.get("/health/anomalies")
async def health_anomalies():
    """Returns all unacknowledged anomalies from the monitoring DB."""
    anomalies = _storage.get_open_anomalies()
    return {"count": len(anomalies), "anomalies": anomalies}


@app.post("/health/anomalies/{anomaly_id}/acknowledge")
async def acknowledge_anomaly(anomaly_id: int):
    """Marks a single anomaly as acknowledged so it no longer appears in /health/anomalies."""
    updated = _storage.acknowledge_anomaly(anomaly_id)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Anomaly {anomaly_id} not found")
    return {"acknowledged": True, "id": anomaly_id}
