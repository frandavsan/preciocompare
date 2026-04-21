import json

plans = [
  {"system": {"name": "American Express"}, "issuer": {"name": ""}, "installments": {"quantity": 3, "hasInterest": True}},
  {"system": {"name": "American Express"}, "issuer": {"name": ""}, "installments": {"quantity": 2, "hasInterest": True}},
  {"system": {"name": "American Express"}, "issuer": {"name": ""}, "installments": {"quantity": 6, "hasInterest": True}},
  {"system": {"name": "American Express"}, "issuer": {"name": ""}, "installments": {"quantity": 12, "hasInterest": True}},
  {"system": {"name": "American Express"}, "issuer": {"name": "Banco Macro"}, "installments": {"quantity": 3, "hasInterest": False}},
  {"system": {"name": "Mastercard"}, "issuer": {"name": "Banco de Santa Fe"}, "installments": {"quantity": 3, "hasInterest": False}},
  {"system": {"name": "Naranja"}, "issuer": None, "installments": {"quantity": 12, "hasInterest": True}},
  {"system": {"name": "Naranja"}, "issuer": None, "installments": {"quantity": 6, "hasInterest": True}},
  {"system": {"name": "Naranja"}, "issuer": None, "installments": {"quantity": 9, "hasInterest": True}},
  {"system": {"name": "Naranja"}, "issuer": None, "installments": {"quantity": 18, "hasInterest": True}},
  {"system": {"name": "American Express"}, "issuer": {"name": ""}, "installments": {"quantity": 3, "hasInterest": False}},
  {"system": {"name": "Mastercard"}, "issuer": None, "installments": {"quantity": 24, "hasInterest": True}},
  {"system": {"name": "Mastercard"}, "issuer": None, "installments": {"quantity": 6, "hasInterest": True}},
  {"system": {"name": "Mastercard"}, "issuer": None, "installments": {"quantity": 2, "hasInterest": True}},
  {"system": {"name": "Mastercard"}, "issuer": None, "installments": {"quantity": 3, "hasInterest": True}},
  {"system": {"name": "Mastercard"}, "issuer": None, "installments": {"quantity": 12, "hasInterest": True}},
  {"system": {"name": "Mastercard"}, "issuer": None, "installments": {"quantity": 18, "hasInterest": True}},
  {"system": {"name": "American Express"}, "issuer": {"name": ""}, "installments": {"quantity": 2, "hasInterest": True}},
  {"system": {"name": "American Express"}, "issuer": {"name": ""}, "installments": {"quantity": 6, "hasInterest": True}},
  {"system": {"name": "American Express"}, "issuer": {"name": ""}, "installments": {"quantity": 12, "hasInterest": True}},
  {"system": {"name": "American Express"}, "issuer": {"name": ""}, "installments": {"quantity": 3, "hasInterest": True}},
  {"system": {"name": "Visa"}, "issuer": {"name": "Banco de Córdoba"}, "installments": {"quantity": 3, "hasInterest": False}},
  {"system": {"name": "Visa"}, "issuer": {"name": "Banco de Santa Fe"}, "installments": {"quantity": 3, "hasInterest": False}},
  {"system": {"name": "Visa"}, "issuer": {"name": "Banco BBVA"}, "installments": {"quantity": 3, "hasInterest": False}},
  {"system": {"name": "Visa"}, "issuer": {"name": "Banco Entre Rios"}, "installments": {"quantity": 3, "hasInterest": False}},
  {"system": {"name": "American Express"}, "issuer": {"name": "Amex Propietarias"}, "installments": {"quantity": 3, "hasInterest": True}},
  {"system": {"name": "American Express"}, "issuer": {"name": "Amex Propietarias"}, "installments": {"quantity": 12, "hasInterest": True}},
  {"system": {"name": "American Express"}, "issuer": {"name": "Amex Propietarias"}, "installments": {"quantity": 2, "hasInterest": True}},
  {"system": {"name": "American Express"}, "issuer": {"name": "Amex Propietarias"}, "installments": {"quantity": 6, "hasInterest": True}},
  {"system": {"name": "Visa"}, "issuer": {"name": "Banco Macro"}, "installments": {"quantity": 3, "hasInterest": False}},
  {"system": {"name": "Cabal"}, "issuer": None, "installments": {"quantity": 3, "hasInterest": False}},
  {"system": {"name": "Mastercard"}, "issuer": {"name": "Banco ICBC"}, "installments": {"quantity": 3, "hasInterest": False}},
  {"system": {"name": "Visa"}, "issuer": None, "installments": {"quantity": 3, "hasInterest": False}},
  {"system": {"name": "American Express"}, "issuer": {"name": "Banco Galicia"}, "installments": {"quantity": 3, "hasInterest": False}},
  {"system": {"name": "Mastercard"}, "issuer": {"name": "Banco Nación"}, "installments": {"quantity": 3, "hasInterest": False}},
  {"system": {"name": "Mastercard"}, "issuer": {"name": "Banco Entre Rios"}, "installments": {"quantity": 3, "hasInterest": False}},
  {"system": {"name": "Visa"}, "issuer": {"name": "Banco Santa Cruz"}, "installments": {"quantity": 3, "hasInterest": False}},
  {"system": {"name": "Visa"}, "issuer": {"name": "Banco Nación"}, "installments": {"quantity": 3, "hasInterest": False}},
  {"system": {"name": "Naranja"}, "issuer": None, "installments": {"quantity": 3, "hasInterest": True}},
  {"system": {"name": "American Express"}, "issuer": {"name": ""}, "installments": {"quantity": 3, "hasInterest": False}},
  {"system": {"name": "American Express"}, "issuer": {"name": ""}, "installments": {"quantity": 2, "hasInterest": True}},
  {"system": {"name": "American Express"}, "issuer": {"name": ""}, "installments": {"quantity": 3, "hasInterest": True}},
  {"system": {"name": "American Express"}, "issuer": {"name": ""}, "installments": {"quantity": 12, "hasInterest": True}},
  {"system": {"name": "American Express"}, "issuer": {"name": ""}, "installments": {"quantity": 6, "hasInterest": True}},
  {"system": {"name": "Mastercard"}, "issuer": {"name": "Banco BBVA"}, "installments": {"quantity": 3, "hasInterest": False}},
  {"system": {"name": "Mastercard"}, "issuer": {"name": "Banco Santa Cruz"}, "installments": {"quantity": 3, "hasInterest": False}},
  {"system": {"name": "Visa"}, "issuer": None, "installments": {"quantity": 6, "hasInterest": True}},
  {"system": {"name": "Visa"}, "issuer": None, "installments": {"quantity": 12, "hasInterest": True}},
  {"system": {"name": "Visa"}, "issuer": None, "installments": {"quantity": 3, "hasInterest": True}},
  {"system": {"name": "Visa"}, "issuer": None, "installments": {"quantity": 24, "hasInterest": True}},
  {"system": {"name": "Visa"}, "issuer": None, "installments": {"quantity": 18, "hasInterest": True}},
  {"system": {"name": "Visa"}, "issuer": None, "installments": {"quantity": 2, "hasInterest": True}},
  {"system": {"name": "Visa"}, "issuer": {"name": "Banco San Juan"}, "installments": {"quantity": 3, "hasInterest": False}},
  {"system": {"name": "Visa"}, "issuer": {"name": "Banco ICBC"}, "installments": {"quantity": 3, "hasInterest": False}},
  {"system": {"name": "American Express"}, "issuer": {"name": ""}, "installments": {"quantity": 6, "hasInterest": True}},
  {"system": {"name": "American Express"}, "issuer": {"name": ""}, "installments": {"quantity": 12, "hasInterest": True}},
  {"system": {"name": "American Express"}, "issuer": {"name": ""}, "installments": {"quantity": 2, "hasInterest": True}},
  {"system": {"name": "American Express"}, "issuer": {"name": ""}, "installments": {"quantity": 3, "hasInterest": True}},
  {"system": {"name": "Cabal"}, "issuer": {"name": "Banco Credicoop"}, "installments": {"quantity": 3, "hasInterest": False}},
  {"system": {"name": "Mastercard"}, "issuer": None, "installments": {"quantity": 3, "hasInterest": False}},
  {"system": {"name": "American Express"}, "issuer": {"name": "Amex Propietarias"}, "installments": {"quantity": 3, "hasInterest": False}},
  {"system": {"name": "Mastercard"}, "issuer": {"name": "Banco de Córdoba"}, "installments": {"quantity": 3, "hasInterest": False}},
  {"system": {"name": "Mastercard"}, "issuer": {"name": "Banco San Juan"}, "installments": {"quantity": 3, "hasInterest": False}},
  {"system": {"name": "Mastercard"}, "issuer": {"name": "Banco Macro"}, "installments": {"quantity": 3, "hasInterest": False}},
  {"system": {"name": "American Express"}, "issuer": None, "installments": {"quantity": 3, "hasInterest": True}},
  {"system": {"name": "American Express"}, "issuer": None, "installments": {"quantity": 6, "hasInterest": True}},
  {"system": {"name": "American Express"}, "issuer": None, "installments": {"quantity": 2, "hasInterest": True}},
  {"system": {"name": "American Express"}, "issuer": None, "installments": {"quantity": 12, "hasInterest": True}},
  {"system": {"name": "American Express"}, "issuer": None, "installments": {"quantity": 24, "hasInterest": True}},
  {"system": {"name": "American Express"}, "issuer": None, "installments": {"quantity": 18, "hasInterest": True}},
  {"system": {"name": "American Express"}, "issuer": None, "installments": {"quantity": 9, "hasInterest": True}},
  {"system": {"name": "American Express"}, "issuer": {"name": ""}, "installments": {"quantity": 3, "hasInterest": False}},
  {"system": {"name": "Cabal"}, "issuer": None, "installments": {"quantity": 3, "hasInterest": True}},
  {"system": {"name": "Cabal"}, "issuer": None, "installments": {"quantity": 2, "hasInterest": True}},
  {"system": {"name": "Cabal"}, "issuer": None, "installments": {"quantity": 6, "hasInterest": True}},
  {"system": {"name": "Cabal"}, "issuer": None, "installments": {"quantity": 24, "hasInterest": True}},
  {"system": {"name": "Cabal"}, "issuer": None, "installments": {"quantity": 12, "hasInterest": True}},
  {"system": {"name": "Cabal"}, "issuer": None, "installments": {"quantity": 18, "hasInterest": True}},
]

print(f"Total plans: {len(plans)}")
print()

# Filter sin-interés, quantity >= 3
sin_interes = [p for p in plans if not p["installments"]["hasInterest"] and p["installments"]["quantity"] >= 3]
print(f"Sin-interés plans (hasInterest=False, quantity>=3): {len(sin_interes)}")
print()

print("=== UNIQUE (system, issuer, quantity) SIN-INTERÉS COMBINATIONS ===")
seen = set()
rows = []
for p in sin_interes:
    sys_name = p["system"]["name"]
    iss = p["issuer"]
    iss_name = iss.get("name") if iss else None
    qty = p["installments"]["quantity"]
    key = (sys_name, iss_name, qty)
    if key not in seen:
        seen.add(key)
        rows.append((sys_name, iss_name, qty))

for sys_name, iss_name, qty in sorted(rows, key=lambda x: (x[0], x[1] or "", x[2])):
    print(f"  system={sys_name!r:22} issuer={str(iss_name)!r:25} qty={qty}")

print()
unique_issuers = set()
unique_systems = set()
for p in sin_interes:
    sys_name = p["system"]["name"]
    iss = p["issuer"]
    iss_name = iss.get("name") if iss else None
    unique_systems.add(sys_name)
    unique_issuers.add(iss_name)

print(f"Unique system.names in sin-interés plans: {len(unique_systems)}")
for s in sorted(s for s in unique_systems if s):
    print(f"  - {s}")

print()
print(f"Unique issuer.names in sin-interés plans: {len(unique_issuers)}")
for i in sorted(str(i) for i in unique_issuers):
    print(f"  - {i!r}")

print()
print("=== EXPLANATION: why website shows 4, API returns many ===")
print("The website groups by system.name (Visa, Mastercard, Cabal, American Express).")
print("The API returns one row per (system, issuer, quantity) combo.")
print(f"There are {len(unique_systems)} unique system names, but {len(seen)} unique (system+issuer+qty) rows.")
print("Each system has multiple issuer variants (Banco Macro, Banco BBVA, null, etc.),")
print("each appearing as a separate plan entry in the API response.")
