"""
Script to insert test batch data for Stage 4 testing.
Run locally before pushing to Render.
"""
import requests
import json
from datetime import date, timedelta

BASE_URL = "https://pharmasud-api.onrender.com"
LOGIN_URL = f"{BASE_URL}/api/auth/login"
BATCH_URL = f"{BASE_URL}/api/batches/receive"
CONFIRM_URL = f"{BASE_URL}/api/batches/receive/confirm-short-expiry"

# Step 1: Login
print("1. Logging in...")
r = requests.post(LOGIN_URL, json={"username": "D. Abeer", "password": "abeer2026"}, timeout=15)
data = r.json()
TOKEN = data["token"]
print(f"   ✅ Token: {TOKEN[:20]}...")

HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

# Medicine IDs
MILGA_ID = "d56fe32b-8a91-4781-9a8e-049770a3d85d"
GENUPHIL_ID = "d6247b3c-0290-48d0-a62e-e926955869d4"
FERTILEX_ID = "ce97161a-684c-4e3f-8921-3172ee3556db"

today = date.today()

# Test scenarios:
# 1. BATCH-A: Milga 50 strips, 70 days → Yellow warning (تحذير)
# 2. BATCH-B: Milga 95 strips, 287 days → Green (سليم)
# 3. BATCH-C: Genuphil 200 boxes, 400 days → Green (سليم)
# 4. BATCH-D: Fertilex 30 boxes, 180 days → Green (سليم)
# 5. BATCH-SHORT: Milga 30 strips, 20 days → RED danger (خطر)

batches = [
    {
        "name": "BATCH-A (Milga 50, 70d)",
        "data": {
            "medicine_id": MILGA_ID,
            "batch_number": "BATCH-A",
            "quantity": 50,
            "unit_name": "strip",
            "expiry_date": (today + timedelta(days=70)).isoformat(),
            "purchase_price": 380.00,
            "supplier_invoice": "INV-001",
            "supplier_name": "مورد 1 - شركة الأدوية السودانية"
        }
    },
    {
        "name": "BATCH-B (Milga 95, 287d)",
        "data": {
            "medicine_id": MILGA_ID,
            "batch_number": "BATCH-B",
            "quantity": 95,
            "unit_name": "strip",
            "expiry_date": (today + timedelta(days=287)).isoformat(),
            "purchase_price": 375.00,
            "supplier_invoice": "INV-001",
            "supplier_name": "مورد 1 - شركة الأدوية السودانية"
        }
    },
    {
        "name": "BATCH-C (Genuphil 200, 400d)",
        "data": {
            "medicine_id": GENUPHIL_ID,
            "batch_number": "BATCH-C",
            "quantity": 200,
            "unit_name": "box",
            "expiry_date": (today + timedelta(days=400)).isoformat(),
            "purchase_price": 720.00,
            "supplier_invoice": "INV-002",
            "supplier_name": "مورد 2 - مستودع الخرطوم"
        }
    },
    {
        "name": "BATCH-D (Fertilex 30, 180d)",
        "data": {
            "medicine_id": FERTILEX_ID,
            "batch_number": "BATCH-D",
            "quantity": 30,
            "unit_name": "box",
            "expiry_date": (today + timedelta(days=180)).isoformat(),
            "purchase_price": 950.00,
            "supplier_invoice": "INV-003",
            "supplier_name": "مورد 3 - شركة فيتامينات"
        }
    },
]

print("\n2. Creating test batches...")
for b in batches:
    r = requests.post(BATCH_URL, json=b["data"], headers=HEADERS, timeout=15)
    result = r.json()
    status = "✅" if result.get("success") else "❌"
    warning = result.get("expiry_warning", "")
    print(f"   {status} {b['name']}: {result.get('message', result.get('detail', 'ERROR'))}")
    if warning:
        print(f"      ⚠️  Warning: {warning}")

# Short expiry batch (20 days - needs confirmation)
print("\n3. Testing short expiry batch (20 days - danger)...")
short_data = {
    "medicine_id": MILGA_ID,
    "batch_number": "BATCH-SHORT",
    "quantity": 30,
    "unit_name": "strip",
    "expiry_date": (today + timedelta(days=20)).isoformat(),
    "purchase_price": 350.00,
    "supplier_invoice": "INV-004",
    "supplier_name": "مورد 3 - تخفيضات"
}

r = requests.post(BATCH_URL, json=short_data, headers=HEADERS, timeout=15)
result = r.json()
print(f"   {'✅' if result.get('success') else '❌'} Short batch: warning={result.get('expiry_warning')}")

if result.get("expiry_warning") and "خطر" in result.get("expiry_warning", ""):
    print("   ⚠️  Danger warning detected! Confirming receipt...")
    confirm_data = {
        "batch_data": short_data,
        "confirmed": True
    }
    r2 = requests.post(CONFIRM_URL, json=confirm_data, headers=HEADERS, timeout=15)
    result2 = r2.json()
    print(f"   {'✅' if result2.get('success') else '❌'} Confirmed: {result2.get('message')}")

# Now test FEFO
print("\n4. Testing FEFO allocation for Milga (quantity=60)...")
FEFO_URL = f"{BASE_URL}/api/batches/fefo-test/{MILGA_ID}?quantity=60"
r = requests.get(FEFO_URL, headers=HEADERS, timeout=15)
result = r.json()
if result.get("success"):
    print(f"   ✅ FEFO Result:")
    for a in result["allocated"]:
        print(f"      - Batch {a['batch_id'][:8]}... : {a['quantity']} units, expires {a['expiry_date']}")
    print(f"   Total allocated: {result['total_allocated']}")
else:
    print(f"   ❌ FEFO failed: {result.get('message')}")

# Test FEFO with insufficient quantity
print("\n5. Testing FEFO with insufficient quantity (500)...")
r = requests.get(f"{BASE_URL}/api/batches/fefo-test/{MILGA_ID}?quantity=500", headers=HEADERS, timeout=15)
result = r.json()
print(f"   {'✅' if not result.get('success') else '❌'} Expected failure: {result.get('message')}")

# Test inventory
print("\n6. Testing inventory API...")
INV_URL = f"{BASE_URL}/api/inventory/"
r = requests.get(INV_URL, headers=HEADERS, timeout=15)
inv = r.json()
for m in inv.get("medicines", []):
    print(f"   {m['trade_name']}: {m['total_stock']} {m['base_unit']} - Exp: {m['nearest_expiry']} ({m['nearest_expiry_status']}) - {m['batches_count']} batches")

print("\n✅ Test data insertion complete!")