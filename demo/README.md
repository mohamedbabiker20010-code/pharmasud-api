# PharmaSUD Demo Pharmacy

## Overview

This directory contains the demo pharmacy seeding functionality.

## Files

| File | Purpose |
|------|---------|
| `demo_data.json` | Canonical demo dataset (NO passwords) |
| `seed_demo_pharmacy.py` | Seeder function (run at runtime) |
| `README.md` | This file |

## Demo Data Structure

- **15 medicines** across 10 categories
- **2-3 batches per medicine** with varied expiry (15 days to 2 years)
- **15 historical sales** over 9 days
- **2 employees** (admin + employee) - passwords generated at runtime
- **Default settings** (currency: SDG, locale: ar-SD, receipt footer: "DEMO - PharmaSUD")

## Usage

### Prerequisites

1. A demo pharmacy must exist in the database with `type = 'demo'`
2. The pharmacy must be activated (`is_active = true`)

### Create Demo Pharmacy

```bash
# Using the provisioning helper
python -c "
from database import SessionLocal
from auth import create_new_pharmacy

db = SessionLocal()
try:
    result = create_new_pharmacy(
        db,
        product_key='PHARM-XXXXXXXXXXXX',  # Valid unused key
        admin_username='demo_admin',
        admin_password='SecurePass123!',
        admin_full_name='Demo Administrator',
        pharmacy_name='PharmaSUD Demo Pharmacy',
        owner_name='Demo Owner',
        pharmacy_type='demo',
        phone='+249-91-000-0000',
        address='Khartoum, Sudan (Demo)'
    )
    print(result)
finally:
    db.close()
"
```

**Note**: The product key must be valid and unused. Generate keys with:
```bash
python scripts/generate_product_keys.py --count 1
```

### Seed Demo Data (Separate Step)

```bash
# After pharmacy is created, seed demo data
python -m demo.seed_demo_pharmacy <pharmacy_id>
```

Or from Python:
```python
from demo.seed_demo_pharmacy import seed_demo_pharmacy

result = seed_demo_pharmacy("<pharmacy_id>")
# Returns dict with credentials generated at runtime
```

The seeder will output credentials for the demo employees:
```json
{
  "success": true,
  "pharmacy_id": "...",
  "medicines_seeded": 15,
  "batches_seeded": 39,
  "employees_seeded": 2,
  "sales_seeded": 15,
  "credentials": {
    "demo_admin": "Xy7!mK9@pQ2#",
    "demo_user": "Ab3$cD5&eF8*"
  }
}
```

**Save these credentials** - they are generated once at seed time and not stored.

### Idempotent Seeding

The seeder is idempotent - running it multiple times will:
1. Clear existing demo data for that pharmacy
2. Re-seed fresh data
3. Generate NEW passwords each time

## Product Key Management

Keys are NOT typed:
```bash
# Generate keys for any purpose
python scripts/generate_product_keys.py --count 10 --label "Customer Batch #1"
```

Key format: `PHARM-XXXXXXXXXXXX` (12 hex chars from UUID4)

The pharmacy type is set during provisioning via `create_new_pharmacy(pharmacy_type=...)`, NOT derived from the key prefix.

## Demo Data Details

### Medicines (15)

| Category | Count | Examples |
|----------|-------|----------|
| مسكنات ومضادات الالتهاب | 3 | باراسيتامول، أندول فورت |
| مضادات حيوية | 2 | أمبيسيلين، أزيثرومايسين |
| أدوية القلب والضغط | 2 | لوسارتان، أسبيرين أطفال |
| أدوية السكري | 1 | ميتفورمين |
| أدوية الجهاز الهضمي | 2 | أوميبرازول، زوفران |
| أدوية الجهاز التنفسي | 1 | سالبوميترول |
| فيتامينات ومكملات | 1 | فيتامين د3 |
| أدوية الجلد | 1 | هيدروكورتيزون |
| قطرات وأدوية العيون | 1 | قطرات اصطناعية |
| أدوية الأعصاب | 2 | أميتربتيلين، سيرترالين |

### Batches (39 total)

Each medicine has 2-3 batches with:
- Varied expiry: 15 days (critical) to 730 days (long-term)
- Varied purchase prices
- Realistic batch numbers

### Sales (15)

- 9 days of history
- All 4 payment methods (cash, bankak, fory, transfer)
- FEFO allocation verified

## Security Notes

- **NO passwords in demo_data.json** - generated at runtime
- **Credentials printed once** during seeding - save immediately
- **Idempotent seeding** regenerates passwords each run
- **Type isolation** enforced: seeder validates `pharmacy.type == 'demo'`

## Extending Demo Data

To add/modify demo data:
1. Edit `demo_data.json`
2. Follow the same structure
3. Run seeder to test
4. No code changes needed for data-only updates
