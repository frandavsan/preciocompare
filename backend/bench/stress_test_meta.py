"""
Step 1: Fetch ~20 real Fravega listings per category to derive realistic queries.
"""
import asyncio
import sys

sys.path.insert(0, r'C:\Users\Frand\Documents\Bots\ElectrodomesticsBot')

from electrodomestics_bot.fetching.adapters.fravega import FravegaAdapter as _F


async def fetch_category(query: str, limit: int = 20) -> list:
    adapter = _F()
    results = await adapter.search(query, detail=False, check_shipping=False)
    return results[:limit]



async def main():
    categories = [
        ("heladeras", "heladera"),
        ("lavarropas", "lavarropas"),
        ("televisores", "televisor"),
        ("celulares", "celular samsung"),
        ("notebooks", "notebook"),
        ("aires acondicionados", "aire acondicionado"),
    ]
    for cat_name, query in categories:
        print(f"\n=== {cat_name.upper()} ===")
        try:
            products = await fetch_category(query)
            for p in products:
                print(f"  {p.name} | SKU:{p.sku} | ${p.price}")
        except Exception as e:
            print(f"  ERROR: {e}")


if __name__ == "__main__":
    asyncio.run(main())
