# PHASE 2C — FUNCTIONAL COMPLETION AUDIT

**Date**: 2026-06-22
**Environment**: Production Render (`pharmasud-api.onrender.com`)
**Tester**: `recoveryadmin` / `RecoveryTestPass!`
**Scope**: Read-only investigation — NO code changes

---

## A. SETTINGS PAGE (`/settings`)

### Buttons Found
| Button | Ref | Alpine Binding |
|--------|-----|----------------|
| الموظفين (Employees) | e20 | `@click="activeTab='employees'"` |
| كلمة المرور (Password) | e21 | `@click="activeTab='password'"` |
| إعدادات الصيدلية (Pharmacy) | e22 | `@click="activeTab='pharmacy'; loadPharmacy()"` |

### What Happens on Click
**NOTHING.** All three buttons are non-functional.

### Root Cause
- **File**: `templates/settings.html`
- **Line 424**: `<main class="main-content">` — **NO `x-data` attribute**
- **Line 751**: `function settingsApp()` is defined with `activeTab`, `employees`, `passForm`, `pharmacyForm`, `loadPharmacy()`, `changePassword()`, `savePharmacy()`, etc.
- **Missing**: `x-data="settingsApp()"` wrapper on the content element
- **Impact**: Alpine.js never instantiates the component. All `@click`, `x-show`, `:class` bindings are silent no-ops.
- **Additional**: 42 Alpine bindings in this template are non-functional

### Additional Issues
- **Nested `<main>`**: Template has `<main class="main-content">` inside shared_layout's `<main>` — creates duplicate elements
- **No inline topbar**: Clean in this regard (no duplicate topbar)

---

## B. ALERTS PAGE (`/alerts`)

### Elements Found
| Element | Ref | Alpine Binding |
|---------|-----|----------------|
| تحديد الكل كمقروء (Mark all read) | e22 | `@click="markAllRead()"` |
| الكل (All) filter | e23 | `@click="activeFilter='all'"` |
| مخزون منخفض (Low stock) | e24 | `@click="activeFilter='low_stock'"` |
| انتهاء الصلاحية (Expiry) | e25 | `@click="activeFilter='expiry'"` |
| النظام (System) | e26 | `@click="activeFilter='system'"` |

### What Happens on Click
**NOTHING.** All filter buttons and "Mark all read" are non-functional.

### Root Cause
- **File**: `templates/alerts.html`
- **Line 72**: `<main class="main-content">` — **NO `x-data` attribute**
- **Line 258**: `function alertsApp()` is defined with `activeFilter`, `allAlerts`, `markAllRead()`, `loadAlerts()`, `toggleDark()`, etc.
- **Missing**: `x-data="alertsApp()"` wrapper
- **Impact**: Alpine.js never instantiates. All 32 Alpine bindings are silent no-ops.

### Additional Issues
- **Duplicate inline topbar** (line 49): `<header class="topbar">` — shared_layout already provides one
- **Nested `<main>`**: Template's `<main>` inside shared_layout's `<main>`
- **Duplicate dark mode button**: Inline topbar has `@click="toggleDark()"` (broken) + shared layout topbar has working `toggleDark()` from `pageApp()`
- **31 console errors**: All from `unpkg.com/lucide@latest` CDN — NOT from our code

### API Endpoint
- `/api/alerts/count` — called by `pageApp().loadNotifications()` (works)
- `/api/alerts/` — would be called by `alertsApp().loadAlerts()` (never called because Alpine not initialized)

---

## C. BATCH RECEIVE PAGE (`/batch-receive`)

### Current State
- **Title**: "اس�تلام شحنة" renders
- **Search input**: Present (textbox ref=e22)
- **Search button**: Present (button ref=e23)

### Root Cause
- **File**: `templates/batch_receive.html`
- **Line 64**: `<main class="main-content">` — **NO `x-data` attribute**
- **Line 249**: `function batchReceiveApp()` is defined with `searchQuery`, `searchResults`, `selectedMedicine`, `batches`, `receiveBatch()`, etc.
- **Missing**: `x-data="batchReceiveApp()"` wrapper
- **Impact**: 32 Alpine bindings non-functional. Search, batch selection, receive — all broken.

### Additional Issues
- **Duplicate inline topbar** (line 41): `<header class="topbar">`
- **Nested `<main>`**: Template's `<main>` inside shared_layout's `<main>`
- **Duplicate dark mode button**: Same pattern as alerts

### Missing Upgrades Required
1. Add `x-data="batchReceiveApp()"` + `x-init="init()"` wrapper
2. Remove duplicate inline `<header class="topbar">`
3. Remove duplicate inline `<main class="main-content">` (or remove shared_layout's wrapper for this page)
4. Remove empty CSS remnants from Phase 1 migration (lines 8-40)
5. Remove duplicate dark mode toggle (use shared layout's)

---

## D. DARK MODE

### Working Pages
| Page | Toggle Exists | Click Works | `dark-mode` Class | Persists |
|------|--------------|-------------|-------------------|----------|
| Dashboard | ✅ (shared layout topbar) | ✅ | ✅ body.dark-mode | ✅ localStorage |
| Medicines | ✅ (shared layout topbar) | ✅ | ✅ | ✅ |
| Inventory | ✅ (shared layout topbar) | ✅ | ✅ | ✅ |

### Broken Pages
| Page | Shared Layout Toggle | Inline Toggle | Inline Works | Root Cause |
|------|---------------------|---------------|--------------|------------|
| Alerts | ✅ Works | ✅ Exists | ❌ No | `alertsApp` not initialized (`x-data` missing) |
| Batch Receive | ✅ Works | ✅ Exists | ❌ No | `batchReceiveApp` not initialized (`x-data` missing) |
| Settings | ✅ Works | ❌ N/A | N/A | No inline toggle; shared layout toggle works |

### Root Cause
- Dark mode is handled by `pageApp()` in `shared_layout.html` (line 225: `<body x-data="pageApp()">`)
- `pageApp()` has `isDark`, `toggleDark()`, persists to `localStorage`
- **The shared layout topbar dark mode toggle WORKS on ALL pages** (it's in the shared topbar)
- Pages with inline topbars (alerts, batch_receive, stocktake) have a SECOND dark mode button that uses the page's own `toggleDark()` from their own Alpine app — which is broken because `x-data` is missing
- **Net effect**: Dark mode works everywhere via the shared layout topbar. The inline toggles on alerts/batch_receive/stocktake are broken duplicates.

---

## E. MOBILE SIDEBAR

### Implementation
- **File**: `templates/shared_layout.html` + `templates/partials/sidebar.html`
- **State**: `sidebarOpen` in `pageApp()` (line 321)
- **Menu button**: Line 239-244: `@click="sidebarOpen = !sidebarOpen"`
- **Overlay**: Line 229-232: `x-show="sidebarOpen"` + `@click="sidebarOpen = false"`
- **Sidebar**: Line 12 in sidebar.html: `:class="{ 'mobile-open': sidebarOpen }"`
- **CSS**: `transform: translateX(100%)` (hidden) / `translateX(0)` (visible)

### Verification
| Behavior | Status | Notes |
|----------|--------|-------|
| Menu button exists | ✅ | In shared layout topbar |
| Menu opens | ✅ | `sidebarOpen = !sidebarOpen` |
| Overlay closes menu | ✅ | `@click="sidebarOpen = false"` |
| X/close button | ❌ **MISSING** | No close button in sidebar |
| Auto-close after navigation | ❌ **MISSING** | Sidebar stays open after clicking nav link |
| Touch scrolling | ✅ | `overflow-y: auto` on sidebar |

### Issues
1. **No X/close button**: User must click outside the sidebar to close it — no explicit close button
2. **No auto-close on navigation**: After clicking a nav link on mobile, the sidebar remains open, covering the new page content

---

## F. FILES REQUIRING MODIFICATION

### Critical (Broken Pages — Missing `x-data`)

| File | Issue | Alpine Bindings | Fix Required |
|------|-------|-----------------|--------------|
| `templates/settings.html` | No `x-data` on `<main>` (line 424) | 42 | Add `x-data="settingsApp()"` wrapper |
| `templates/alerts.html` | No `x-data` on `<main>` (line 72) | 32 | Add `x-data="alertsApp()"` wrapper |
| `templates/batch_receive.html` | No `x-data` on `<main>` (line 64) | 32 | Add `x-data="batchReceiveApp()"` wrapper |
| `templates/sales_history.html` | No `x-data` on `<main>` (line 397) | 22 | Add `x-data="salesApp()"` wrapper |
| `templates/stocktake.html` | No `x-data` on `<main>` (line 70) | 22 | Add `x-data="stocktakeApp()"` wrapper |

### Structural (Duplicate Elements)

| File | Issue | Lines | Fix Required |
|------|-------|-------|--------------|
| `templates/alerts.html` | Duplicate inline `<header class="topbar">` | 49-69 | Remove inline topbar |
| `templates/alerts.html` | Duplicate inline `<main class="main-content">` | 72 | Remove or replace with `<div>` |
| `templates/batch_receive.html` | Duplicate inline `<header class="topbar">` | 41-62 | Remove inline topbar |
| `templates/batch_receive.html` | Duplicate inline `<main class="main-content">` | 64 | Remove or replace with `<div>` |
| `templates/stocktake.html` | Duplicate inline `<header class="topbar">` | 43-68 | Remove inline topbar |
| `templates/stocktake.html` | Duplicate inline `<main class="main-content">` | 70 | Remove or replace with `<div>` |
| `templates/settings.html` | Duplicate inline `<main class="main-content">` | 424 | Remove or replace with `<div>` |
| `templates/sales_history.html` | Duplicate inline `<main class="main-content">` | 397 | Remove or replace with `<div>` |

### CSS Cleanup (Empty Remnants)

| File | Issue | Lines | Fix Required |
|------|-------|-------|--------------|
| `templates/alerts.html` | Empty sidebar/topbar CSS remnants | 8-42 | Remove |
| `templates/batch_receive.html` | Empty sidebar/topbar CSS remnants | 8-38 | Remove |
| `templates/sales_history.html` | Empty sidebar/topbar CSS remnants | 8-38 | Remove |
| `templates/settings.html` | Empty sidebar/topbar CSS remnants | 8-44 | Remove |
| `templates/stocktake.html` | Empty sidebar/topbar CSS remnants | 8-40 | Remove |

### Mobile Sidebar UX

| File | Issue | Fix Required |
|------|-------|--------------|
| `templates/partials/sidebar.html` | No X/close button | Add close button with `@click="sidebarOpen = false"` |
| `templates/partials/sidebar.html` | No auto-close on navigation | Add `@click="sidebarOpen = false"` to nav links |

---

## SUMMARY

### Pages by Status

| Page | URL | Alpine Init | Functional | Issues |
|------|-----|-------------|------------|--------|
| Dashboard | `/dashboard` | ✅ | ✅ | None |
| POS | `/pos` | ✅ (standalone) | ✅ | None |
| Medicines | `/medicines` | ✅ | ✅ | None |
| Inventory | `/inventory` | ✅ | ✅ | None |
| Batch Receive | `/batch-receive` | ❌ | ❌ | No x-data, duplicate topbar |
| Sales History | `/sales-history` | ❌ | ❌ | No x-data |
| Reports Sales | `/reports-sales` | ✅ | ✅ | None |
| Reports Profits | `/reports-profits` | ✅ | ✅ | None |
| Reports Slow Moving | `/reports-slow-moving` | ✅ | ✅ | Fixed in Phase 2B |
| Purchase Forecast | `/reports-purchase-forecast` | ✅ | ✅ | None |
| Employees | `/employees` | N/A (vanilla JS) | ✅ | None |
| Alerts | `/alerts` | ❌ | ❌ | No x-data, duplicate topbar |
| Settings | `/settings` | ❌ | ❌ | No x-data |

### Root Cause Pattern
**5 templates** (settings, alerts, batch_receive, sales_history, stocktake) were migrated to `shared_layout.html` during Phase 1 stabilization but **never received `x-data` wrappers**. The `function xxxApp()` is defined in each template's `extra_js` block, but Alpine.js never instantiates the component because the `x-data` attribute is missing on the content element.

### Fix Complexity
- **Simple fix**: Add `x-data="appName()"` to each template's content wrapper (5 files, 1 line each)
- **Full fix**: Also remove duplicate inline topbars (3 files), replace nested `<main>` with `<div>` (5 files), clean up empty CSS (5 files)
