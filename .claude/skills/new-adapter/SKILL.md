---
name: new-adapter
description: Step-by-step guide for adding a new store adapter to ElectrodomesticsBot. Use when the user asks to add a new store or when you need to create an adapter.
---

## Adding a New Store — Step by Step

### 1. Determine the Platform
Use the @store-researcher subagent or manually check:
- VTEX: look for /_v/api/ endpoints, vtex.js, __RUNTIME__
- Magento: look for /catalogsearch/, Magento meta tags, Summa installments

### 2. Create the Adapter File

For VTEX:
```python
# adapters/newstore.py
from ..platforms.vtex import VtexAdapter

class NewStoreAdapter(VtexAdapter):
    name = "newstore"
    base_url = "https://www.newstore.com.ar"
```

For Magento:
```python
# adapters/newstore.py
from ..platforms.magento import MagentoAdapter

class NewStoreAdapter(MagentoAdapter):
    name = "newstore"
    base_url = "https://www.newstore.com.ar"
```

### 3. Register the Adapter
Add to adapters/__init__.py:
```python
from .newstore import NewStoreAdapter
ADAPTERS = [..., NewStoreAdapter()]
```

### 4. Test
Run: python run.py
Query: "samsung tv 55" or similar broad query
Verify: results appear, prices are correct, installments parse

### 5. Overridable Attributes
- postal_code (VTEX, default "1425")
- verify_ssl (VTEX, default True)
- card_keywords (Magento, default Summa map)