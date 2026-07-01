# PharmaSUD — Current State Snapshot
*Authoritative recovery snapshot — max 100 lines. Updated after every major change.*

---

## Version & Branch
- **Version**: 7.2.0 "Light + Blue Theme"
- **Branch**: `master` (Render watches `master`)
- **Last Commit**: `6d0e1a7` — Purchase Forecast restored + UI standardization verified
- **Production**: https://pharmasud-api.onrender.com ✅ Live

---

## Current Task
**No active task** — UI Standardization Phase complete. Purchase Forecast verified on production.

---

## Production Blockers (Must Fix Before Real Pharmacy Use)
1. ❌ **Mobile sidebar on 2 pages** — sales_history.html, stocktake.html have CSS issues
2. ❌ **No void sale** — Customer changes mind = manual workaround
3. ❌ **Profit shows inconsistent values** — Still investigating data capture
4. ❌ **RBAC over-permissive** — Employees can call admin APIs
5. ❌ **No JWT revocation** — Stolen token valid 24h
6. ❌ **CSP report-only** — No XSS protection enforcement

---

## Milestone: UI Standardization Phase Complete (2026-07-01)

The following pages now share one unified design system:

| Page | Template Type | Status |
|------|---------------|--------|
| Dashboard | shared_layout | ✅ Standardized |
| Medicines | shared_layout | ✅ Standardized |
| Inventory | shared_layout | ✅ Standardized |
| Sales History | shared_layout | ✅ Standardized |
| Sales Report | shared_layout | ✅ Standardized |
| Profit Report | shared_layout | ✅ Standardized |
| Purchase Forecast | standalone | ✅ Restored to v7.2.0 |

All standardized pages share:
- identical page spacing (`.page-content` padding: 24px 28px)
- identical page header layout (`display:flex; align-items:flex-end; justify-content:space-between`)
- identical content container (`.main-content` margin-right: 248px on desktop)
- identical responsive behavior (sidebar transforms on mobile, hamburger menu)
- identical KPI card style (`.metric-card` with `.metric-header`, `.metric-icon`, `.metric-label`, `.metric-value`)
- identical typography (IBM Plex Sans Arabic, 26px h1, 14.5px subtitle)
- identical Design System (CSS variables in `static/css/theme.css`)

---

## Today's Completed Work (2026-07-01)

| Time | Task | Result |
|------|------|--------|
| Forensic analysis | Identified commit 754b861 as regression source | ✅ |
| Template comparison | Original vs broken v7.2.0 Purchase Forecast | ✅ |
| Restoration | Reverted to 1187-line standalone template | ✅ |
| Verification | Production HTTP 200, Alpine app functional | ✅ |

---

## Recently Fixed Items

| Commit | Date | Fix |
|--------|------|-----|
| `6d0e1a7` | 2026-07-01 | Purchase Forecast restored, UI standardization verified |
| `29fc483` | 2026-06-22 | Restore CSS styles in alerts.html |
| `1eec0cd` | 2026-06-22 | Fix JS syntax in alerts/batch_receive |
| `f4383f0` | 2026-06-22 | Phase 2D - x-data wrappers + sidebar close button |
| `acce5f7` | 2026-06-22 | Fix reports_slow_moving.html Alpine errors |

---

## Do Not Touch List
- `main.py` startup DDL — `create_all()` + ALTER TABLE runs on boot
- `auth.py` JWT config — 24h expiry, localStorage (Phase 3 will change)
- `batches.py` FEFO logic — `expiry_date > today` excludes today-expiring batches
- Template inline CSS in shared_layout templates — Working correctly
- `pos.html` barcode scanner — Dual engine (BarcodeDetector + zxing-wasm)
- `demo/` auto-seed — Creates demo pharmacy if DB empty

---

## Key Metrics
- **Feature Complete**: ~80%
- **Production Hardened**: ~48%
- **RBAC Enforced**: 15% (only 3 endpoints)
- **Mobile UX Fixed**: 85% (shared_layout templates work, 2 pages have CSS issues)

---

## Last Updated
**2026-07-01** — UI Standardization Phase complete. Ready for final polish phase.