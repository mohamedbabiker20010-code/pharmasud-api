# PharmaSUD Development Status

## Current State: UI Standardization Phase Complete ✅

**Version:** 7.2.0 "Light + Blue Theme"  
**Branch:** `master` (Render watches `master`)  
**Production:** https://pharmasud-api.onrender.com ✅ Live  
**Demo:** recoveryadmin / RecoveryTestPass!

---

## Milestone: UI Standardization Phase (2026-07-01)

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

## Production Status

| Page | Route | Status |
|------|-------|--------|
| Dashboard | /dashboard | ✅ 200 |
| Medicines | /medicines | ✅ 200 |
| Inventory | /inventory | ✅ 200 |
| Batch Receive | /batch-receive | ✅ 200 |
| Alerts | /alerts | ✅ 200 |
| Employees | /employees | ✅ 200 |
| Settings | /settings | ✅ 200 |
| POS | /pos | ✅ 200 |
| Sales History | /sales-history | ✅ 200 |
| Stocktake | /stocktake | ✅ 200 |
| Reports (Sales) | /reports-sales | ✅ 200 |
| Reports (Profits) | /reports-profits | ✅ 200 |
| Reports (Slow) | /reports-slow-moving | ✅ 200 |
| Purchase Forecast | /reports-purchase-forecast | ✅ 200 (restored) |
| Audit Log | /audit-log | ✅ 200 |
| Login | /login | ✅ 200 |
| Splash | / | ✅ 200 |

---

## Current Outstanding Issues

### P0 (Must Fix Before Real Pharmacy Use)
1. ❌ Mobile sidebar on 2 pages — sales_history.html (empty CSS placeholders), stocktake.html (unclosed CSS braces)
2. ❌ No void sale — Customer changes mind = manual workaround
3. ❌ Profit shows inconsistent values — Still investigating data capture

### P1 (High Priority)
4. ❌ RBAC over-permissive — Employees can call admin APIs
5. ❌ No JWT revocation — Stolen token valid 24h
6. ❌ CSP report-only — No XSS protection enforcement

### MEDIUM Priority
7. ❌ Date picker broken on batch_receive
8. ❌ POS shows out-of-stock items
9. ❌ Camera barcode scanner fails silently
10. ❌ Quick medicines hardcoded
11. ❌ No multi-item cart qty editing
12. ❌ FEFO uses `expiry_date > today`
13. ❌ No audit log for login events

---

## Security Status

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1 (Critical) | ✅ Complete | CORS fix, rate limiting, SECRET_KEY validation |
| Phase 2 (High) | ✅ Complete | Security headers, file upload validation |
| Phase 3 (Medium) | ❌ Not Started | CSRF, MFA/TOTP, Redis JWT denylist, CSP enforcement |

---

## RBAC Status

| Aspect | Status | Notes |
|--------|--------|-------|
| Phase 1 Tables | ✅ Seeded | roles, permissions, user_roles tables exist |
| Permission System | ✅ Implemented | `require_permission()` factory in auth.py |
| Enforcement Coverage | ~15% | Most endpoints still use implicit role checks |

---

## Last Updated
**2026-07-01** — UI Standardization Phase complete. Ready for final polish phase.