# INFRASTRUCTURE LAYER — Megatone / Doofinder v6 platform.
# New features that apply to any Doofinder-backed store belong here, not in individual adapters.
# See CLAUDE.md for the full architecture guideline.
import asyncio
import functools
import secrets
from math import ceil
from typing import Optional
from urllib.parse import quote

from ..core import get_client, http_post, matches_query
from ...models import Installment, ProductResult
from ..adapters.base import StoreAdapter


class MegatoneAdapter(StoreAdapter):
    """
    Base adapter for stores using the Doofinder v6 search API.
    Subclasses must set `name`, `base_url`, and `_doofinder_hashid`.

    Installments are fetched via individual `retornarplanes` calls per card network
    (not the comprehensive IdTarjeta=0 call, which understates counts). All calls fire
    in parallel via asyncio.gather:
      - 5 card networks: Visa(5), Mastercard(3), AmEx(2), Cabal(6), NaranjaX(7)
      - 1 Directo/debit(18) — only lowest tier used
      - 1 comprehensive(0) — fallback for Mercado Pago (no dedicated IdTarjeta found)
      - N bank promos: IdTarjeta=5 + each bank in _BANK_PROMOS

    The API accepts multiple SKUs in `Productos`, so one call covers all products.
    Each card appears only at its highest sin-interes count (mirrors website display).
    Bank promos only add a row when they exceed the base Visa count.
    Installment amounts are calculated as price/count (exact for 0% interest).
    """

    # --- subclasses must override ---
    name: str
    base_url: str
    _doofinder_hashid: str

    # --- subclasses may override ---
    verify_ssl: bool = True
    _SUCURSAL = 104  # 104 = web store (434 = MX)

    # Banks that offer Visa-exclusive sin-interes promotions exceeding the base Visa tier.
    # IDs are BCRA (Argentine Central Bank) codes.
    _BANK_PROMOS: dict[int, str] = {
        11:  "BNA",
        7:   "Banco Galicia",
        17:  "BBVA",
        72:  "Banco Santander",
        330: "Banco Santa Fe",
        386: "Banco Entre Rios",
        45:  "Banco San Juan",
        86:  "Banco Santa Cruz",
    }

    # Individual card network calls (IdTarjeta → display name).
    # These return correct counts; the comprehensive call (IdTarjeta=0) understates them.
    _CARD_CALLS: list[tuple[int, str]] = [
        (5,  "Visa"),
        (3,  "Mastercard"),
        (2,  "American Express"),
        (6,  "Cabal"),
        (7,  "NaranjaX"),
    ]

    # Keyword map for parsing the `tarjeta` field in the comprehensive call response.
    # Only used as fallback for cards without a dedicated IdTarjeta (e.g. Mercado Pago).
    _CARD_KEYWORDS: list[tuple[str, str]] = [
        ("MERCADO PAGO",   "Mercado Pago"),
        ("NARANJA VISA",   "Naranja Visa"),
        ("NARANJA",        "NaranjaX"),
        ("CABAL",          "Cabal"),
        ("VISA",           "Visa"),
        ("MASTER",         "Mastercard"),
        ("AMEX",           "American Express"),
        ("AMERICAN",       "American Express"),
    ]

    # Labels that appear in the API but are NOT shown on the website — filter these out.
    _CARD_BLACKLIST: frozenset[str] = frozenset({"NATIVA"})

    _DOOFINDER_HOST = "https://us1-search.doofinder.com/6"
    _RPP = 100
    _MAX_PAGES = 10

    @property
    def _endpoint(self) -> str:
        return f"{self._DOOFINDER_HOST}/{self._doofinder_hashid}/_search"

    @property
    def _plans_endpoint(self) -> str:
        return f"{self.base_url}/apirecursosweb/api/planes/retornarplanes"

    @functools.cached_property
    def _origin_headers(self) -> dict:
        return {"Origin": self.base_url, "Referer": self.base_url + "/"}

    async def search(self, query: str, detail: bool = False) -> list[ProductResult]:
        raw = await self._fetch_all_products(query)
        matching = [p for p in raw if matches_query(p.get("title", ""), query)]

        results = []
        eligible = []
        for p in matching:
            result = self._parse_product(p)
            results.append(result)
            if result.price and result.sku and self._has_sin_interes(p):
                eligible.append(result)

        if eligible:
            # Use a single representative SKU — the API returns the intersection of plans
            # valid for ALL SKUs, which collapses to nothing with 3+ mixed products.
            # Installment tiers are store-wide promotions; any eligible product reveals them.
            rep = max(eligible, key=lambda r: r.price)
            card_counts = await self._fetch_card_counts([rep.sku], rep.price)
            sorted_tiers = self._sorted_tiers(card_counts)
            for result in eligible:
                result.installments = [
                    Installment(count=count, amount=round(result.price / count, 2), cards=cards)
                    for count, cards in sorted_tiers
                ]

        return results

    def _search_url(self, query: str, page: int) -> str:
        return f"{self._endpoint}?page={page}&rpp={self._RPP}&query={quote(query)}"

    async def _fetch_all_products(self, query: str) -> list[dict]:
        # Doofinder enforces domain whitelisting via Origin header; without it the API returns 403.
        data = (await get_client(self.verify_ssl).get(self._search_url(query, 1), headers=self._origin_headers)).json()
        results = data.get("results", [])
        total = data.get("total", len(results))
        total_pages = min(ceil(total / self._RPP), self._MAX_PAGES)

        if total_pages > 1:
            extra = await asyncio.gather(*[
                self._fetch_page(query, page)
                for page in range(2, total_pages + 1)
            ])
            for page_results in extra:
                results.extend(page_results)

        return results

    async def _fetch_page(self, query: str, page: int) -> list[dict]:
        try:
            return (await get_client(self.verify_ssl).get(self._search_url(query, page), headers=self._origin_headers)).json().get("results", [])
        except Exception:
            return []

    def _parse_product(self, p: dict) -> ProductResult:
        return ProductResult(
            name=p.get("title"),
            sku=p.get("id"),
            price=self._extract_price(p),
            currency="ARS",
            url=p.get("link", ""),
            installments=[],
            available=p.get("availability", "").lower() == "in stock",
            free_shipping=p.get("free_shipping") == "true",
            international=p.get("productointernacional") == "true",
        )

    @staticmethod
    def _has_sin_interes(p: dict) -> bool:
        """Doofinder marks products with sin-interes via highlight_installments; marketplace products show 'Rebajas' instead."""
        return "Sin Inter" in (p.get("highlight_installments") or "")

    def _extract_price(self, p: dict) -> Optional[float]:
        val = p.get("sale_price")
        try:
            return float(val) if val is not None else None
        except (ValueError, TypeError):
            return None

    def _card_name_from_tarjeta(self, tarjeta: str) -> Optional[str]:
        """Map a raw `tarjeta` string from retornarplanes to a display name.
        Returns None for blacklisted cards (e.g. Nativa) that appear in the API but not on the website."""
        upper = tarjeta.upper()
        if any(bl in upper for bl in self._CARD_BLACKLIST):
            return None
        for keyword, display_name in self._CARD_KEYWORDS:
            if keyword in upper:
                return display_name
        return None

    @staticmethod
    def _is_sin_interes(plan: dict) -> bool:
        return plan.get("tasaDirecta", 1) == 0 and int(plan.get("cuotas", 1)) > 1

    async def _fetch_card_counts(self, skus: list[str], capital: float) -> dict[str, int]:
        """
        Batch-fetch installment plans for all SKUs via parallel retornarplanes calls.
        Uses individual card calls (not the comprehensive IdTarjeta=0, which understates counts).
        Returns {card_name: max_sin_interes_count}.
        """
        bank_ids = list(self._BANK_PROMOS.keys())

        # All calls fire in parallel across three logical groups.
        card_results, (directo, comprehensive), bank_results = await asyncio.gather(
            asyncio.gather(*[
                self._fetch_plans_batch(skus, capital, card_id=cid)
                for cid, _ in self._CARD_CALLS
            ]),
            asyncio.gather(
                self._fetch_plans_batch(skus, capital, card_id=18),
                self._fetch_plans_batch(skus, capital, card_id=0),  # Mercado Pago fallback only
            ),
            asyncio.gather(*[
                self._fetch_plans_batch(skus, capital, card_id=5, bank_id=bid)
                for bid in bank_ids
            ]),
        )

        max_count_by_card: dict[str, int] = {}

        for (_, card_name), plans in zip(self._CARD_CALLS, card_results):
            for plan in plans:
                if not self._is_sin_interes(plan):
                    continue
                count = int(plan["cuotas"])
                if count > max_count_by_card.get(card_name, 0):
                    max_count_by_card[card_name] = count

        # Directo (IdTarjeta=18): website shows only the lowest sin-interés tier.
        directo_counts = [int(p["cuotas"]) for p in directo if self._is_sin_interes(p)]
        if directo_counts:
            max_count_by_card["Directo"] = min(directo_counts)

        # Comprehensive (IdTarjeta=0): fallback for cards without a dedicated call (e.g. Mercado Pago).
        # Cards already populated by individual calls are skipped — comprehensive understates their counts.
        known_cards = set(max_count_by_card.keys())
        for plan in comprehensive:
            if not self._is_sin_interes(plan):
                continue
            card_name = self._card_name_from_tarjeta(plan.get("tarjeta", ""))
            if not card_name or card_name in known_cards:
                continue
            count = int(plan["cuotas"])
            if count > max_count_by_card.get(card_name, 0):
                max_count_by_card[card_name] = count

        visa_max = max_count_by_card.get("Visa", 0)

        # Bank promos only add a row when they beat base Visa (e.g. 12x vs 9x).
        for bank_id, plans in zip(bank_ids, bank_results):
            bank_name = self._BANK_PROMOS[bank_id]
            for plan in plans:
                if not self._is_sin_interes(plan):
                    continue
                count = int(plan["cuotas"])
                if count <= visa_max:
                    continue
                if count > max_count_by_card.get(bank_name, 0):
                    max_count_by_card[bank_name] = count

        return max_count_by_card

    @staticmethod
    def _sorted_tiers(card_counts: dict[str, int]) -> list[tuple[int, list[str]]]:
        """Group card_counts into sorted (count, sorted_cards) tiers — computed once, reused per product."""
        cards_by_count: dict[int, list[str]] = {}
        for card_name, count in card_counts.items():
            cards_by_count.setdefault(count, []).append(card_name)
        return [(count, sorted(cards)) for count, cards in sorted(cards_by_count.items(), reverse=True)]

    async def _fetch_plans_batch(self, skus: list[str], capital: float, card_id: int, bank_id: int = 0) -> list[dict]:
        payload = {
            "IdTarjeta": card_id,
            "IdBanco": bank_id,
            "Productos": skus,
            "Sucursal": self._SUCURSAL,
            "Capital": int(round(capital)),
            "Token": secrets.token_hex(32),
        }
        try:
            resp = await http_post(
                self._plans_endpoint,
                verify_ssl=self.verify_ssl,
                json=payload,
                headers={"Content-Type": "application/json; charset=utf-8", **self._origin_headers},
            )
            return resp.json().get("resumen", [])
        except Exception:
            return []
