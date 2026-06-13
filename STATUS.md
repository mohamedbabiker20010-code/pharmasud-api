# PharmaSUD - Project Status
## Last Updated: 2026-06-13 (Stage 7 Complete)
## Current Stage: Stage 7 - Alerts + Employees + Audit + Stocktake
## Version: 7.0.0
## Branch: master (Render watches this branch, NOT main!)
## Live URL: https://pharmasud-api.onrender.com
## GitHub: https://github.com/mohamedbabiker20010-code/pharmasud-api

---

## ⚠️ IMPORTANT: Render Environment Variables Required

After deploying, add these Environment Variables in Render Dashboard:
- `SECRET_KEY`: 9a3c8dd4d2178235674aea2828bfdd8019fd3e7bdb693aa80e800d9a8523b563
- `DATABASE_URL`: (already exists from PostgreSQL)

⚠️ `.env` file removed from Git tracking! Add secrets via Render Dashboard only.

---

## Recent Commits

### Stage 7 (2026-06-13)
**Complete implementation of Stage 7 features:**

#### New Files
- `alerts.py` - Unified alerts system (expiry + low stock + count endpoint)
- `audit.py` - Audit log helper function + admin-only log reader
- `employees.py` - Employee management (create, toggle, reset password)
- `inventory.py` - Stocktake endpoints added (start + submit)
- `templates/alerts.html` - Redesigned alerts page
- `templates/audit_log.html` - Audit log viewer with filters + pagination
- `templates/employees.html` - Employee management UI (modals for add/reset)
- `templates/stocktake.html` - QR/barcode stocktake page with standalone scanner

#### Modified Files
- `main.py` - Added 3 new tables, version 7.0.0, routes for alerts/employees/audit/stocktake
- `auth.py` - Added is_active check with message "هذا الحساب معطّل - تواصل مع المدير"
- `medicines.py` - Added log_action calls for price updates + deletions
- `models.py` - Added 3 new tables: audit_log, stocktake_sessions, stocktake_items
- `templates/dashboard.html` - Added sidebar links (Employees, Stocktake, Alerts, Audit Log) + bell count badge

#### Security Fixes
- Removed `.env` from Git tracking (critical) + added `.env.example` template
- `SECRET_KEY` now mandatory (no default) in auth.py
- `DATABASE_URL` now mandatory (no default) in database.py
- Fixed SQL injection in sales.py (parameterized LIMIT/OFFSET)
- Hidden pharmacy phone/address from public invoice endpoint
- Added authentication to `/scanner-debug` page

#### New Stage 7 Features
- **Alerts**: /api/alerts/ + /api/alerts/count (30-day critical, 90-day warning, low stock)
- **Employees**: /api/employees/ + /api/employees/{id}/toggle + /api/employees/{id}/reset-password
- **Audit Log**: async log_action() function + /api/audit-log/ endpoint with pagination
- **Stocktake**: /api/inventory/stocktake/start + /api/inventory/stocktake/submit with FEFO deduction and settlement batch creation
- **Barcode Scanner**: Stocktake page has standalone copy of pos.html scanner (no pos.html changes)

---

### Previous Commits

#### Security Hardening (2026-06-13)
- Remove `.env` from Git tracking
- Add `.env.example` template
- Enforce mandatory `SECRET_KEY` and `DATABASE_URL`
- Fix SQL injection in sales.py parameterized queries
- Hide sensitive data from public invoice

#### iOS Bug Fixes (2026-06-11)
- Fix `current_user` AttributeError in `/api/auth/me` (causing 500 → 403)
- Fix `generate_test_sales` dot notation
- Fix feminine→masculine voice in templates

#### Scanner + Auth Fixes (2026-06-12)
- Dual-engine barcode scanner (BarcodeDetector + zxing-wasm)
- Login endpoint arg mismatch fix
- Logout clearing `role` from localStorage in 5 templates
- Silent catch removal + proper error handling

#### Scanner Rebuild (2026-06-11)
- Surgical scanner replacement in pos.html
- Standalone scanner debug page

---

## Database Schema (Stage 7)

```sql
-- Audit Log
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pharmacy_id UUID REFERENCES pharmacies(id),
    user_id UUID REFERENCES users(id),
    user_name VARCHAR(100),
    action_type VARCHAR(50),
    description TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Stocktake Sessions
CREATE TABLE stocktake_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pharmacy_id UUID REFERENCES pharmacies(id),
    user_id UUID REFERENCES users(id),
    notes TEXT,
    items_adjusted INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Stocktake Items
CREATE TABLE stocktake_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES stocktake_sessions(id),
    medicine_id UUID REFERENCES medicines(id),
    medicine_name VARCHAR(100),
    system_quantity INTEGER,
    actual_quantity INTEGER,
    difference INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## Active Features by Stage

✅ **Stage 1**: Render + PostgreSQL + 7 tables  
✅ **Stage 2**: Product Key + JWT Login + Permissions  
✅ **Stage 3**: Medicines + Barcode + Images + Units  
✅ **Stage 4**: Batches + FEFO Auto-Deduction  
✅ **Stage 5**: POS + Cart + Sales + PDF Invoice + Dual Scanner  
✅ **Stage 6**: Dashboard + Reports (Sales, Profits, Slow-Moving, Purchase Forecast)  
✅ **Stage 7**: **NEW** Alerts + Employees + Audit Log + Quick Stocktake  

---

## Authentication Status
- JWT tokens via `/api/auth/login`
- is_active check on login → rejects disabled accounts
- Admin-only endpoints: /api/employees/, /api/audit-log/, /api/medicines (PUT/DELETE)
- Employee access: Sales + Inventory view only (403 on admin endpoints)

---

## Next Steps (Planned)
- Stage 8: Multi-pharmacy support + company admin
- Stage 9: WhatsApp integration + customer notifications

---

## Testing Checklist (Stage 7)
- [x] Expiry medicine < 30 days → critical alert
- [x] Dashboard bell shows real alert count
- [x] Admin creates employee → employee can login
- [x] Admin disables employee → login rejected with message
- [x] Price change → audit_log entry created
- [x] Medicine delete → audit_log entry created
- [x] Employee gets 403 on /api/employees/ and /api/audit-log/
- [x] Stocktake: actual < system → FEFO deduction
- [x] Stocktake: actual > system → settlement batch created
- [x] Barcode scan in stocktake page → scrolls to medicine + focuses input
- [x] All stocktake adjustments logged in audit_log

---

## Known Technical Debt
- CORS set to allow all origins (production should restrict to domain)
- No rate limiting on login (brute force risk)
- Typing indicator in POS interface (cosmetic only, no API cost)
- LSP diagnostics in inventory.py (type hints warnings, runtime OK)
