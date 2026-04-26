# STORE LAYER — base class for all store adapters.
# Store adapters should be minimal: just `name`, `base_url`, and any store-specific overrides.
# All platform logic belongs in platforms/magento.py or platforms/vtex.py.
# See CLAUDE.md for the full architecture guideline.
from abc import ABC, abstractmethod
from typing import Optional

from ...models import ProductResult


class StoreAdapter(ABC):
    name: str

    @abstractmethod
    async def search(
        self,
        query: str,
        detail: bool = False,
        check_shipping: bool = True,
        postal_code: Optional[str] = None,
    ) -> list[ProductResult]:
        """Search the store and return all matching products for the given query.
        When detail=True, implementations may perform extra requests to return richer data
        (e.g. full card names per installment option) at the cost of extra latency.
        When check_shipping=False, shipping simulation is skipped and free_shipping=False
        for all products.
        When postal_code is provided, adapters that simulate shipping use it instead of
        their class-level default."""
        ...
