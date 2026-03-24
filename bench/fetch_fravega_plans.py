import asyncio
from curl_cffi.requests import AsyncSession

QUERY = '{ plans(sku: "782619") { system { name } issuer { name } installments { quantity hasInterest } } }'

async def main():
    url = "https://www.fravega.com/api/v1/rest/search"
    payload = {"query": QUERY}

    async with AsyncSession(impersonate="chrome120") as session:
        resp = await session.post(url, json=payload)
        data = resp.json()

    # Navigate to plans list
    plans = data.get("data", {}).get("plans", [])

    all_rows = []
    for plan in plans:
        system_name = (plan.get("system") or {}).get("name", "")
        issuer_name = (plan.get("issuer") or {}).get("name", "")
        inst = plan.get("installments") or {}
        qty = inst.get("quantity")
        has_interest = inst.get("hasInterest")
        all_rows.append({
            "system": system_name,
            "issuer": issuer_name,
            "qty": qty,
            "hasInterest": has_interest,
        })

    sin_interes = [r for r in all_rows if r["hasInterest"] is False and r["qty"] > 1]
    sin_interes_sorted = sorted(sin_interes, key=lambda r: (-r["qty"], r["system"], r["issuer"]))

    print("=== Sin-interés rows ===")
    for r in sin_interes_sorted:
        print(f"system={r['system']}  issuer={r['issuer']}  qty={r['qty']}")

    print()
    print("=== Summary ===")
    print(f"Total rows         : {len(all_rows)}")
    print(f"Sin-interés rows   : {len(sin_interes)}")
    distinct_qty = sorted({r['qty'] for r in sin_interes}, reverse=True)
    print(f"Distinct quantities: {distinct_qty}")

asyncio.run(main())
