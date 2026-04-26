"""
Supabase JWT authentication for FastAPI.

Verifies the Bearer token from the Authorization header. Supports both
asymmetric signing (ES256/RS256, the current Supabase default — verified
via the project's JWKS endpoint) and the legacy HS256 shared-secret mode.

Protected routes add ``user=Depends(require_auth)`` to receive the decoded
token payload (contains ``sub``, ``email``, ``role``, etc.).
"""

import time
from typing import Any

import httpx
from fastapi import HTTPException, Request
from jose import jwt, JWTError

from .config import settings

_JWKS_TTL_SECONDS = 3600
_jwks_cache: dict[str, Any] = {"keys": None, "fetched_at": 0.0}


async def _fetch_jwks(force: bool = False) -> list[dict]:
    now = time.monotonic()
    cached = _jwks_cache["keys"]
    if not force and cached is not None and now - _jwks_cache["fetched_at"] < _JWKS_TTL_SECONDS:
        return cached
    url = f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
    keys = resp.json().get("keys", [])
    _jwks_cache["keys"] = keys
    _jwks_cache["fetched_at"] = now
    return keys


def _find_jwk(keys: list[dict], kid: str) -> dict | None:
    for k in keys:
        if k.get("kid") == kid:
            return k
    return None


async def require_auth(request: Request) -> dict:
    """FastAPI dependency — rejects requests without a valid Supabase JWT."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(401, "Missing or malformed Authorization header")
    token = header.removeprefix("Bearer ")

    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError:
        raise HTTPException(401, "Malformed token header")

    alg = unverified_header.get("alg")

    if alg == "HS256":
        if not settings.supabase_jwt_secret:
            raise HTTPException(500, "SUPABASE_JWT_SECRET not configured for HS256 token")
        try:
            return jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                options={"require_exp": True, "verify_aud": False},
            )
        except JWTError:
            raise HTTPException(401, "Invalid or expired token")

    if alg not in ("ES256", "RS256"):
        raise HTTPException(401, f"Unsupported token algorithm: {alg}")

    if not settings.supabase_url:
        raise HTTPException(500, "SUPABASE_URL not configured for asymmetric token verification")

    kid = unverified_header.get("kid")
    if not kid:
        raise HTTPException(401, "Token header missing kid")

    keys = await _fetch_jwks()
    jwk = _find_jwk(keys, kid)
    if jwk is None:
        # Cache may be stale (key rotation); refresh once.
        keys = await _fetch_jwks(force=True)
        jwk = _find_jwk(keys, kid)
    if jwk is None:
        raise HTTPException(401, "Signing key not found")

    try:
        return jwt.decode(
            token,
            jwk,
            algorithms=[alg],
            options={"require_exp": True, "verify_aud": False},
        )
    except JWTError:
        raise HTTPException(401, "Invalid or expired token")
