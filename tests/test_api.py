"""Tier 2 — API integration tests.

Tests the FastAPI HTTP contract using TestClient with mocked adapters
and service layer. No real store requests are made.
"""

import time
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from electrodomestics_bot.api import limiter
from electrodomestics_bot.auth import ALGORITHM
from electrodomestics_bot.models import Installment, StoreSearchResult

from conftest import make_product, make_ssr

TEST_SECRET = "test-api-jwt-secret"

_PATCH_SEARCH = "electrodomestics_bot.api.search_products"
_PATCH_STORAGE = "electrodomestics_bot.api._storage"


def _token(sub: str = "user-1", exp_offset: int = 3600) -> str:
    return jwt.encode(
        {"sub": sub, "exp": int(time.time()) + exp_offset},
        TEST_SECRET,
        algorithm=ALGORITHM,
    )


def _auth_headers(token: str | None = None) -> dict:
    if token is None:
        token = _token()
    return {"Authorization": f"Bearer {token}"}


class _FakeAdapter:
    """Minimal stand-in for StoreAdapter — enough for ADAPTERS list."""
    def __init__(self, name: str):
        self.name = name
        self.base_url = f"https://{name}.com.ar"

_FAKE_ADAPTERS = [_FakeAdapter("store_a"), _FakeAdapter("store_b")]


@pytest.fixture()
def client():
    """TestClient with mocked scheduler, adapters, and JWT secret."""
    with (
        patch("electrodomestics_bot.api._scheduler") as mock_sched,
        patch("electrodomestics_bot.api.ADAPTERS", _FAKE_ADAPTERS),
        patch("electrodomestics_bot.auth.SUPABASE_JWT_SECRET", TEST_SECRET),
    ):
        mock_sched.start = lambda: None
        mock_sched.stop = lambda: None

        from electrodomestics_bot.api import app
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


class TestSearch:
    def test_returns_search_response_shape(self, client):
        p = make_product(name="Samsung S26 Ultra", price=500_000)
        mock_result = {
            "store_a": make_ssr([p], status="ok", duration_ms=120),
            "store_b": make_ssr([], status="ok", duration_ms=80),
        }
        with patch(_PATCH_SEARCH, new_callable=AsyncMock, return_value=mock_result):
            resp = client.get("/search", params={"q": "S26"}, headers=_auth_headers())

        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "S26"
        assert "store_a" in data["results"]
        assert "store_b" in data["results"]
        assert len(data["results"]["store_a"]) == 1
        assert data["results"]["store_a"][0]["name"] == "Samsung S26 Ultra"
        assert data["results"]["store_a"][0]["price"] == 500_000
        assert data["store_status"]["store_a"]["status"] == "ok"
        assert data["store_status"]["store_a"]["result_count"] == 1
        assert data["store_status"]["store_a"]["duration_ms"] == 120
        assert data["store_status"]["store_b"]["result_count"] == 0

    def test_no_results_returns_200_not_503(self, client):
        mock_result = {
            "store_a": make_ssr([], status="ok"),
            "store_b": make_ssr([], status="ok"),
        }
        with patch(_PATCH_SEARCH, new_callable=AsyncMock, return_value=mock_result):
            resp = client.get("/search", params={"q": "nonexistent"}, headers=_auth_headers())

        assert resp.status_code == 200
        data = resp.json()
        assert all(len(prods) == 0 for prods in data["results"].values())

    def test_all_stores_failure_returns_503(self, client):
        with patch(
            _PATCH_SEARCH,
            new_callable=AsyncMock,
            side_effect=Exception("all stores failed"),
        ):
            resp = client.get("/search", params={"q": "S26"}, headers=_auth_headers())

        assert resp.status_code == 503

    def test_search_requires_auth(self, client):
        resp = client.get("/search", params={"q": "S26"})
        assert resp.status_code == 401

    def test_search_rejects_bad_token(self, client):
        resp = client.get(
            "/search",
            params={"q": "S26"},
            headers={"Authorization": "Bearer garbage"},
        )
        assert resp.status_code == 401

    def test_product_fields_complete(self, client):
        """Every ProductResponse field from the Pydantic model is present."""
        p = make_product(
            name="Test TV", sku="TV001", price=100_000, url="https://store.com/tv",
            installments=[Installment(count=12, amount=8_333.33, cards=["Visa"])],
            free_shipping=True, international=True, available=True,
        )
        mock_result = {"store_a": make_ssr([p]), "store_b": make_ssr([])}
        with patch(_PATCH_SEARCH, new_callable=AsyncMock, return_value=mock_result):
            resp = client.get("/search", params={"q": "TV"}, headers=_auth_headers())

        product = resp.json()["results"]["store_a"][0]
        assert product["name"] == "Test TV"
        assert product["sku"] == "TV001"
        assert product["price"] == 100_000
        assert product["currency"] == "ARS"
        assert product["url"] == "https://store.com/tv"
        assert product["free_shipping"] is True
        assert product["international"] is True
        assert product["available"] is True
        assert len(product["installments"]) == 1
        assert product["installments"][0]["count"] == 12
        assert product["installments"][0]["amount"] == 8_333.33
        assert product["installments"][0]["cards"] == ["Visa"]


class TestHealth:
    def test_returns_ok_without_auth(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["stores"] == len(_FAKE_ADAPTERS)

    def test_health_ignores_jwt(self, client):
        """Even an invalid token should not block /health."""
        resp = client.get("/health", headers={"Authorization": "Bearer garbage"})
        assert resp.status_code == 200


class TestHealthDetail:
    def test_requires_auth(self, client):
        resp = client.get("/health/detail")
        assert resp.status_code == 401

    def test_returns_detail_with_auth(self, client):
        with (
            patch(_PATCH_STORAGE) as mock_storage,
            patch("electrodomestics_bot.api._scheduler") as mock_sched,
        ):
            mock_storage.get_last_canary_per_store.return_value = {}
            mock_storage.get_last_refresh.return_value = None
            mock_storage.get_db_size_mb.return_value = 0.01
            mock_sched.get_status.return_value = {"enabled": False}

            resp = client.get("/health/detail", headers=_auth_headers())

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "canary" in data
        assert "last_refresh" in data
        assert "monitoring_db_size_mb" in data


class TestHealthAnomalies:
    def test_requires_auth(self, client):
        resp = client.get("/health/anomalies")
        assert resp.status_code == 401

    def test_returns_anomalies_with_auth(self, client):
        with patch(_PATCH_STORAGE) as mock_storage:
            mock_storage.get_open_anomalies.return_value = [
                {"id": 1, "store": "store_a", "anomaly_type": "null_prices"},
            ]
            resp = client.get("/health/anomalies", headers=_auth_headers())

        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["anomalies"][0]["id"] == 1


class TestAcknowledgeAnomaly:
    def test_requires_auth(self, client):
        resp = client.post("/health/anomalies/1/acknowledge")
        assert resp.status_code == 401

    def test_acknowledge_existing(self, client):
        with patch(_PATCH_STORAGE) as mock_storage:
            mock_storage.acknowledge_anomaly.return_value = True
            resp = client.post("/health/anomalies/42/acknowledge", headers=_auth_headers())

        assert resp.status_code == 200
        assert resp.json()["acknowledged"] is True
        assert resp.json()["id"] == 42

    def test_acknowledge_nonexistent_returns_404(self, client):
        with patch(_PATCH_STORAGE) as mock_storage:
            mock_storage.acknowledge_anomaly.return_value = False
            resp = client.post("/health/anomalies/999/acknowledge", headers=_auth_headers())

        assert resp.status_code == 404


class TestRateLimiting:
    @pytest.fixture(autouse=True)
    def reset_limiter(self):
        limiter.reset()

    def test_rate_limit_returns_429(self, client):
        mock_result = {"store_a": make_ssr([]), "store_b": make_ssr([])}

        with patch(_PATCH_SEARCH, new_callable=AsyncMock, return_value=mock_result):
            for _ in range(10):
                resp = client.get("/search", params={"q": "test"}, headers=_auth_headers())
                assert resp.status_code == 200

            resp = client.get("/search", params={"q": "test"}, headers=_auth_headers())
            assert resp.status_code == 429
