"""
Supabase JWT authentication for FastAPI.

Validates the Bearer token from the Authorization header against the
Supabase project's JWT secret. Protected routes add ``user=Depends(require_auth)``
to receive the decoded token payload (contains ``sub``, ``email``, ``role``, etc.).
"""

from fastapi import HTTPException, Request
from jose import jwt, JWTError

from .config import settings

SUPABASE_JWT_SECRET = settings.supabase_jwt_secret
ALGORITHM = "HS256"


async def require_auth(request: Request) -> dict:
    """FastAPI dependency — rejects requests without a valid Supabase JWT."""
    if not SUPABASE_JWT_SECRET:
        raise HTTPException(500, "SUPABASE_JWT_SECRET not configured")

    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(401, "Missing or malformed Authorization header")

    token = header.removeprefix("Bearer ")
    try:
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=[ALGORITHM],
            options={"require_exp": True},
        )
    except JWTError:
        raise HTTPException(401, "Invalid or expired token")

    return payload
