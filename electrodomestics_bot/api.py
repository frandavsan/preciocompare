import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .fetching.adapters import ADAPTERS
from .models import ProductResponse, SearchResponse
from .fetching.service import search_products

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
    """Health check."""
    return {"status": "ok", "stores": len(ADAPTERS)}
