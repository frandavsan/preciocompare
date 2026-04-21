"""Tests for JWT authentication."""

import time
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from jose import jwt

from electrodomestics_bot.auth import ALGORITHM, require_auth

TEST_SECRET = "test-jwt-secret-for-unit-tests"


def _make_token(payload: dict, secret: str = TEST_SECRET) -> str:
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def _make_request(token: str | None = None) -> AsyncMock:
    request = AsyncMock()
    if token is not None:
        request.headers = {"Authorization": f"Bearer {token}"}
    else:
        request.headers = {}
    return request


@pytest.fixture(autouse=True)
def _patch_secret(monkeypatch):
    monkeypatch.setattr("electrodomestics_bot.auth.SUPABASE_JWT_SECRET", TEST_SECRET)


class TestRequireAuth:
    @pytest.mark.asyncio
    async def test_valid_token(self):
        token = _make_token({"sub": "user-123", "exp": int(time.time()) + 3600})
        request = _make_request(token)

        payload = await require_auth(request)
        assert payload["sub"] == "user-123"

    @pytest.mark.asyncio
    async def test_expired_token(self):
        token = _make_token({"sub": "user-123", "exp": int(time.time()) - 3600})
        request = _make_request(token)

        with pytest.raises(HTTPException) as exc_info:
            await require_auth(request)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_header(self):
        request = _make_request(None)

        with pytest.raises(HTTPException) as exc_info:
            await require_auth(request)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_malformed_token(self):
        request = _make_request("not-a-valid-jwt")

        with pytest.raises(HTTPException) as exc_info:
            await require_auth(request)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_wrong_secret(self):
        token = _make_token(
            {"sub": "user-123", "exp": int(time.time()) + 3600},
            secret="wrong-secret",
        )
        request = _make_request(token)

        with pytest.raises(HTTPException) as exc_info:
            await require_auth(request)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_exp_claim(self):
        token = _make_token({"sub": "user-123"})  # no exp
        request = _make_request(token)

        with pytest.raises(HTTPException) as exc_info:
            await require_auth(request)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_no_secret_configured(self, monkeypatch):
        monkeypatch.setattr("electrodomestics_bot.auth.SUPABASE_JWT_SECRET", "")
        token = _make_token({"sub": "user-123", "exp": int(time.time()) + 3600})
        request = _make_request(token)

        with pytest.raises(HTTPException) as exc_info:
            await require_auth(request)
        assert exc_info.value.status_code == 500
