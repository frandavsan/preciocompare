# STORE LAYER — base class for all store adapters.
# Store adapters should be minimal: just `name`, `base_url`, and any store-specific overrides.
# All platform logic belongs in platforms/magento.py or platforms/vtex.py.
# See CLAUDE.md for the full architecture guideline.
from abc import ABC, abstractmethod

from ..models import ProductResult


class StoreAdapter(ABC):
    name: str

    @abstractmethod
    async def search(self, query: str, detail: bool = False) -> list[ProductResult]:
        """Search the store and return all matching products for the given query.
        When detail=True, implementations may perform extra requests to return richer data
        (e.g. full card names per installment option) at the cost of extra latency."""
        ...
