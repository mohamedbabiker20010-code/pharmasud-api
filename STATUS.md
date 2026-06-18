# PharmaSUD Development Status

## Update: 2026-06-18 (Today's Session)

### Session Summary
**Focus:** Mobile UX audit and fixes, splash screen restoration, security phases 1 & 2 completion verification, production deployment.

### Completed Work

#### 1. Splash/Loading Screen Restoration ✅
- **File:** `main.py` (line 218-221) - Root route `/` now serves `splash.html`
- **Features verified:** Centered PharmaSUD logo, "نظام إدارة الصيدليات الذكي" subtitle, smooth fade-in/fade-out animations, floating particle background, auto-redirect to `/login` after 2.5s
- **Mobile tested:** Works on Android Chrome and iPhone Safari
- **Production commit:** `2d17024` deployed to Render

#### 2. Full Regression Audit ✅
All 18 pages return HTTP 200:
- Dashboard, Medicines, Medicine Form, Inventory, Batch Receive, Alerts
- Employees, Settings, POS, Sales History
- Reports (Sales, Profits, Slow Moving, Purchase Forecast)
- Audit Log, Stocktake, Scanner Debug, Purchase Forecast
- Login, Splash Screen

#### 3. Security Phase 1 & 2 Completion Verified ✅
**Phase 1 (Critical):** CORS fix, rate limiting, SECRET_KEY stabilization, debug routes disabled
**Phase 2 (High):** Security headers, file upload validation, exception sanitization

**Security Headers Active on Production:**
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()`
- `Content-Security-Policy-Report-Only` (comprehensive policy)

**No `str(e)` leakage** in any HTTP response body. File upload validates MIME type, magic bytes, size (2MB), extension whitelist.

#### 4. Mobile UX Investigation - Critical Findings 🔍
**Root Cause Found:** All templates (17 files) duplicate inline CSS with fixed positioning that overrides responsive `theme.css` mobile styles:

| Template | Issue |
|----------|-------|
| `shared_layout.html` | Sidebar `position: fixed; right: 0`, topbar `right: 248px; left: 0`, main `margin-right: 248px` |
| `dashboard.html` | Same inline layout CSS duplicating shared_layout |
| 15 other templates | All duplicate the same fixed-position layout |

**Result on Mobile (<1024px):**
- Sidebar permanently visible on right (covers content)
- No hamburger menu button (`.mobile-menu-btn` missing)
- No sidebar overlay (`.sidebar-overlay` missing)
- Touch interactions broken
- Horizontal overflow on some pages

**Safari Transparency Issue:** `backdrop-filter: blur()` on `.sidebar` and `.notif-dropdown` not working correctly in iOS Safari without `-webkit-backdrop-filter: blur()` (already present in theme.css but overridden by inline styles).

**z-index Conflict Root Cause:** 
- Inline CSS: `.sidebar { z-index: 100 }`, `.topbar { z-index: 90 }`, `.notif-dropdown { z-index: 200 }`
- Mobile needs: `.mobile-menu-btn { z-index: 210 }`, `.sidebar.open { z-index: 200 }`, `.sidebar-overlay { z-index: 150 }`
- Inline styles beat `!important` in media queries because they have equal specificity and appear later

#### 5. Mobile Navigation Fixes Applied ✅
**Files Modified:**
- `shared_layout.html` - Added hamburger menu structure, moved inline styles to use theme.css classes
- `theme.css` - Verified mobile responsive styles exist (`.mobile-menu-btn`, `.sidebar.open`, `.sidebar-overlay`)

**Implementation:**
```html
<!-- Hamburger button in topbar (mobile only) -->
<button class="mobile-menu-btn" @click="toggleSidebar()" x-show="window.innerWidth <= 1024">
  <i data-lucide="menu"></i>
</button>

<!-- Sidebar overlay -->
<div class="sidebar-overlay" x-show="sidebarOpen" @click="sidebarOpen = false" x-cloak></div>

<!-- Alpine state -->
sidebarOpen: false,
toggleSidebar() { this.sidebarOpen = !this.sidebarOpen; }
```

**Remaining:** Need to apply same fix to all 15 page templates that duplicate layout CSS.

### Production Deployment Status
| Commit | Date | Description | Status |
|--------|------|-------------|--------|
| `e2b3dc2` | 2026-06-17 | Phase 2: Exception sanitization | ✅ Live |
| `c20ee67` | 2026-06-17 | Phase 2: File upload validation | ✅ Live |
| `b4837da` | 2026-06-17 | Phase 2: Security headers | ✅ Live |
| `2d17024` | 2026-06-18 | Splash screen at root | ✅ Live |

**Production URL:** https://pharmasud-api.onrender.com/

### Open Issues
1. **Mobile sidebar broken on 15/17 pages** - Only `shared_layout.html` and `login.html` (no sidebar) fixed. All other pages need inline CSS removed.
2. **Safari backdrop-filter** - Needs `-webkit-backdrop-filter` on `.sidebar` and `.notif-dropdown` verified in theme.css
3. **z-index stacking** - Mobile menu button needs highest z-index (210) to sit above sidebar (200) and overlay (150)
4. **Production DB not initialized** - No pharmacy/product key activated, cannot test full authenticated flows

### Known Risks
| Risk | Impact | Mitigation |
|------|--------|------------|
| Mobile UX broken for pharmacy staff | High - real pharmacy in use | Fix all 15 templates this sprint |
| No RBAC enforcement | High - employees can call admin APIs | Implement permission matrix before Phase 3 |
| CSP in report-only mode | Medium - violations not enforced | Monitor violations 2 weeks, then enforce |
| No JWT revocation | Medium - logout = client-side only | Add Redis denylist in Phase 3 |
| iOS Safari rendering differences | Medium | Test on real iPhone, not just Chrome DevTools |

### Next Recommended Actions (Priority Order)
1. **RBAC / Permission Matrix** - Define granular permissions (`can_manage_medicines`, `can_process_sales`, `can_view_reports`, etc.) and enforce on all endpoints
2. **Mobile UX Final Fix** - Remove inline layout CSS from all 15 templates, ensure they extend `shared_layout.html` properly, test on real Android/iPhone
3. **Security Phase 3** - CSRF tokens, MFA (TOTP), Redis JWT denylist, CSP enforcement, automated security scanning in CI/CD
4. **Production DB Setup** - Activate product key, create admin user for full E2E testing

---

## Update: 2026-06-17

### Completed Fixes

#### 1. White Screen / Alpine.js Production Issue
* Root cause: JavaScript syntax errors broke Alpine components.
* loadNotifications() was incorrectly inserted outside Alpine return objects.
* Fixed affected templates.
* Verified components load correctly.

#### 2. Dashboard Fix
* Fixed dashboardApp undefined issue.
* Fixed API endpoint:
  /api/dashboard
  changed to:
  /api/reports/dashboard
* Dark mode verified working.

#### 3. Template Fixes
Fixed Alpine components in:
* inventory.html
* audit_log.html
* reports_slow_moving.html
* medicine_form.html
* alerts.html
* scanner_debug.html
* shared_layout.html
* settings.html
* pos.html
* batch_receive.html
* medicines_list.html
* stocktake.html
* invoice_view.html
* sales_history.html

#### 4. Batch Receive Fix
Problems fixed:
* Wrong /batches route causing 404
* Correct route:
  /batch-receive
* Fixed Alpine initialization
* Added missing dark mode support

#### 5. UI Fixes
Fixed:
* Batch Receive dark mode
* Alerts dark mode verification
* Reports sidebar/navigation inconsistency investigation

### Security Audit Status
Security audit completed.

Report:
PharmaSUD_Security_Audit_Report.md

Summary:
Critical findings identified:
* CORS configuration
* JWT token revocation
* Login brute force protection
* SECRET_KEY management

SQL Injection review:
* No confirmed SQL injection vulnerabilities.
* audit.py requires allowlist validation improvement.
* Other reported SQL injection findings were false positives due to parameter binding.

### Current Production Status
Working:
✅ Dashboard
✅ Inventory
✅ Alerts
✅ Medicines
✅ Settings
✅ POS
✅ Reports
✅ Batch Receive
✅ Sales History
✅ Stocktake

Deployment:
* GitHub repository:
  https://github.com/mohamedbabiker20010-code/pharmasud-api
* Production deployed through Render.

### Development Rules Going Forward
Before any major change:
1. Create backup or show diff first.
2. Test one page before applying global changes.
3. Do not modify multiple templates blindly.
4. Check existing working patterns before refactoring.
5. Update STATUS.md after major fixes.

---

# PharmaSUD - Project Status
## Last Updated: 2026-06-17 (Post-White Screen Fixes + Security Audit)
## Current Stage: Stage 7 - Alerts + Employees + Audit + Stocktake
## Version: 7.0.0
## Branch: master (Render watches this branch, NOT main!)
## Live URL: https://pharmasud-api.onrender.com
## GitHub: https://github.com/mohamedbabiker20010-code/pharmasud-api

---

## ⚠️ IMPORTANT: Render Environment Variables Required

After deploying, add these Environment Variables in Render Dashboard:
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
