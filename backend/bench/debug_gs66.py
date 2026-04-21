import asyncio
import sys
sys.path.insert(0, "C:/Users/Frand/Documents/Bots/ElectrodomesticsBot")

from electrodomestics_bot.fetching.service import search_products
from electrodomestics_bot.processing.matching import extract_keys, _keys_match

async def main():
    raw = await search_products("GS66SXSC", detail=False)
    for store, ssr in raw.items():
        print(f"\n=== {store} ({len(ssr.products)} products) ===")
        for p in ssr.products[:3]:
            keys = extract_keys(p.name)
            print(f"  Name: {p.name}")
            print(f"  Keys: {keys}")
            print(f"  Key count: {len(keys)}")
            print()

    all_keys = {}
    for store, ssr in raw.items():
        if ssr.products:
            name = ssr.products[0].name
            keys = extract_keys(name)
            all_keys[store] = (name, keys)

    print("\n=== Pairwise _keys_match results ===")
    stores = list(all_keys.keys())
    for i, s1 in enumerate(stores):
        for s2 in stores[i+1:]:
            k1 = all_keys[s1][1]
            k2 = all_keys[s2][1]
            shorter, longer = (k1, k2) if len(k1) <= len(k2) else (k2, k1)
            overlap = len(shorter & longer)
            ratio = overlap / len(shorter) if shorter else 0
            match = _keys_match(k1, k2)
            print(f"  {s1} vs {s2}: match={match}, overlap={overlap}/{len(shorter)} = {ratio:.2%}")
            print(f"    {s1} keys: {all_keys[s1][1]}")
            print(f"    {s2} keys: {all_keys[s2][1]}")
            print(f"    intersection: {k1 & k2}")
            print(f"    only in {s1}: {k1 - k2}")
            print(f"    only in {s2}: {k2 - k1}")
            print()

asyncio.run(main())
