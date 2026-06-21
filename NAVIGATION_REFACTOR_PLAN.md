# PharmaSUD — Sidebar Unification Migration Plan

> **Status**: PLAN ONLY — No implementation yet  
> **Created**: 2026-06-21  
> **Branch**: `navigation-refactor-backup` (rollback point, commit `a3497a8`)  
> **Target**: Unify 17 inline sidebars into a single shared component  

---

## 1. Templates Containing an Inline Sidebar

**17 templates** currently embed a full `<aside class="sidebar">` block with duplicated HTML and CSS:

| # | Template | Lines | Nav Items | Notes |
|---|---|---|---|---|
| 1 | `dashboard.html` | ~1191 | 11 | Complete set; most standard |
| 2 | `sales_history.html` | ~1073 | 10 | Missing Sales History (itself); hardcoded `class="nav-item active"` |
| 3 | `reports_profits.html` | ~1674 | 8 | Missing Alerts, Employees; links to `/reports-profits` instead of `/reports-sales` |
| 4 | `reports_sales.html` | ~1882 | 8 | Missing Alerts, Employees; has client-side report-type tabs (lines ~1181–1184) |
| 5 | `reports_slow_moving.html` | ~600 | 8 | Missing Alerts, Employees |
| 6 | `inventory.html` | ~1282 | 10 | Missing Sales History |
| 7 | `medicines_list.html` | ~749 | 10 | Missing Sales History |
| 8 | `employees.html` | ~630 | 11 | Complete set |
| 9 | `alerts.html` | ~924 | 11 | Complete set |
| 10 | `settings.html` | ~1182 | 10 | Missing Sales History |
| 11 | `batch_receive.html` | ~600 | 11 | Complete set |
| 12 | `stocktake.html` | ~600 | 11 | Complete set |
| 13 | `purchase_forecast.html` | ~1253 | 11 | **Two nav sections** ("القائمة" + "التقارير"); 4 report links; Alpine `:class` binding for mobile |
| 14 | `invoice_view.html` | ~600 | 10 | Missing Sales History; uses `x-text` i18n labels |
| 15 | `audit_log.html` | ~600 | 11 | Complete set |
| 16 | `medicine_form.html` | ~600 | 10 | Missing Sales History |
| 17 | `scanner_debug.html` | ~600 | 10 | Missing Sales History |

**3 templates without sidebar** (by design, NOT modified):
- `login.html` — login page
- `splash.html` — loading screen
- `pos.html` — standalone POS interface

**2 shared files** (exist but are NOT used by any template):
- `templates/shared_layout.html` — full layout shell with inline sidebar (11 items, missing Sales History)
- `templates/partials/sidebar.html` — sidebar HTML fragment (11 items, missing Sales History)

---

## 2. Complete Navigation Item Inventory

### All unique nav items found across the project

| Nav Item | Route | Arabic Label | Templates Present In | Status |
|---|---|---|---|---|
| Dashboard | `/dashboard` | لوحة التحكم | 17/17 | ✅ Universal |
| POS | `/pos` | نقطة البيع | 17/17 | ✅ Universal |
| Medicines | `/medicines` | الأدوية | 17/17 | ✅ Universal |
| Inventory | `/inventory` | المخزون | 17/17 | ✅ Universal |
| Batch Receive | `/batch-receive` | استلام دفعة | 17/17 | ✅ Universal |
| Sales History | `/sales-history` | سجل المبيعات | 10/17 | ❌ Missing from 7 templates |
| Reports (Sales) | `/reports-sales` | التقارير | 17/17 | ✅ Universal |
| Profit Report | `/reports-profits` | تقرير الأرباح | 2/17 | ❌ Missing from 15 templates |
| Slow Moving | `/reports-slow-moving` | بطيئة الحركة | 1/17 | ❌ Missing from 16 templates |
| Purchase Forecast | `/purchase-forecast` | توقعات الشراء | 1/17 | ❌ Missing from 16 templates |
| Employees | `/employees` | الموظفين | 10/17 | ❌ Missing from 7 templates |
| Alerts | `/alerts` | التنبيهات | 13/17 | ❌ Missing from 4 templates |
| Settings | `/settings` | الإعدادات | 17/17 | ✅ Universal |

### Report sub-section items (only in `purchase_forecast.html` sidebar)

These 4 report links exist only in `purchase_forecast.html`'s "التقارير" section:
- `/reports-sales` → تقارير المبيعات
- `/reports-profits` → تقارير الأرباح
- `/reports-slow-moving` → بطيئة الحركة
- `/purchase-forecast` → توقعات الشراء

### Client-side report tabs (only in `reports_sales.html`)

`reports_sales.html` has 4 `<button class="report-tab">` elements (lines ~1181–1184) that navigate to the same 4 report routes via Alpine.js `@click`. These are NOT sidebar nav items — they are page content tabs. They must be preserved during migration.

---

## 3. Final Unified Navigation Structure

### `templates/partials/sidebar.html` — Canonical Sidebar

```html
<aside class="sidebar" :class="{ 'mobile-open': sidebarOpen }">
  <!-- Brand -->
  <div class="brand">
    <div class="icon"></div>
    <div class="name">Pharma<span>SUD</span></div>
  </div>

  <!-- Section 1: Main Menu -->
  <div class="nav-section">القائمة</div>
  <a href="/dashboard"     class="nav-item {% if active_page == 'dashboard' %}active{% endif %}">...</a>
  <a href="/pos"          class="nav-item {% if active_page == 'pos' %}active{% endif %}">...</a>
  <a href="/medicines"    class="nav-item {% if active_page == 'medicines' %}active{% endif %}">...</a>
  <a href="/inventory"    class="nav-item {% if active_page == 'inventory' %}active{% endif %}">...</a>
  <a href="/batch-receive" class="nav-item {% if active_page == 'batch-receive' %}active{% endif %}">...</a>
  <a href="/sales-history" class="nav-item {% if active_page == 'sales-history' %}active{% endif %}">...</a>

  <!-- Section 2: Reports -->
  <div class="nav-section">التقارير</div>
  <a href="/reports-sales"          class="nav-item {% if active_page == 'reports-sales' %}active{% endif %}">...</a>
  <a href="/reports-profits"        class="nav-item {% if active_page == 'reports-profits' %}active{% endif %}">...</a>
  <a href="/reports-slow-moving"   class="nav-item {% if active_page == 'reports-slow-moving' %}active{% endif %}">...</a>
  <a href="/purchase-forecast"     class="nav-item {% if active_page == 'purchase-forecast' %}active{% endif %}">...</a>

  <!-- Admin-Only -->
  {% if is_admin | default(true) %}
  <a href="/employees" class="nav-item {% if active_page == 'employees' %}active{% endif %}" x-show="isAdmin">...</a>
  {% endif %}

  <!-- Common -->
  <a href="/alerts"   class="nav-item {% if active_page == 'alerts' %}active{% endif %}">...</a>
  <a href="/settings" class="nav-item {% if active_page == 'settings' %}active{% endif %}">...</a>

  <!-- User Card -->
  <div class="user-card" @click="logout()">...</div>
</aside>
```

**Total: 14 nav links across 2 sections + user card**

### `templates/shared_layout.html` — Base Layout

Provides for all page templates:
1. `<!DOCTYPE>` through `<body>` — all CSS (reset, layout, sidebar, topbar, notifications, dark mode)
2. `{% include 'partials/sidebar.html' %}` — canonical sidebar
3. Topbar (mobile hamburger, search, lang toggle, dark mode, notifications bell)
4. Notifications dropdown
5. `<main class="main-content">{% block content %}{% endblock %}</main>`
6. Shared `pageApp()` Alpine function
7. `{% block extra_css %}{% endblock}` and `{% block extra_js %}{% endblock}`

### Context Variables (passed from route handlers)

```python
{
    "request": request,
    "active_page": "dashboard",       # string — active nav highlight
    "is_admin": True,                 # boolean — Employees link visibility
    "user_name": "محمد",              # string — user card
    "user_role": "مدير",              # string — user card
    "user_initials": "م ب",           # string — avatar
    "alert_count": 7,                 # int — notification badge
    "page_title": "لوحة التحكم",      # string — <title>
}
```

### Example Child Template After Refactor

```html
{% extends 'shared_layout.html' %}
{% set active_page = 'dashboard' %}

{% block extra_css %}
<style>
  /* Page-specific CSS only — NO sidebar/topbar CSS */
</style>
{% endblock %}

{% block content %}
<!-- Page HTML content only — NO <aside>, NO <header>, NO <main> wrapper -->
{% endblock %}

{% block extra_js %}
<script>/* Page-specific JS */</script>
{% endblock %}
```

---

## 4. Migration Order

### Phase 0: Foundation (no template changes)

| Step | Action | File |
|---|---|---|
| 0.1 | Rewrite `shared_layout.html` to final canonical form | `templates/shared_layout.html` |
| 0.2 | Rewrite `partials/sidebar.html` to final canonical form | `templates/partials/sidebar.html` |
| 0.3 | Update route handlers in `main.py` to pass context variables | `main.py` |

### Phase 1: Low-risk templates (standard structure, complete or near-complete nav)

| Order | Template | `active_page` Value | Special Handling |
|---|---|---|---|
| 1.1 | `dashboard.html` | `'dashboard'` | None — baseline template |
| 1.2 | `employees.html` | `'employees'` | None |
| 1.3 | `alerts.html` | `'alerts'` | None |
| 1.4 | `batch_receive.html` | `'batch-receive'` | None |
| 1.5 | `stocktake.html` | `'inventory'` | Stocktake is inventory sub-page |

### Phase 2: Medium-risk templates (missing nav items that will be added)

| Order | Template | `active_page` Value | Missing Items Now Added |
|---|---|---|---|
| 2.1 | `sales_history.html` | `'sales-history'` | Sales History link |
| 2.2 | `inventory.html` | `'inventory'` | Sales History link |
| 2.3 | `medicines_list.html` | `'medicines'` | Sales History link |
| 2.4 | `settings.html` | `'settings'` | Sales History link |
| 2.5 | `invoice_view.html` | `'pos'` (or new `'invoice'`) | Sales History; remove `x-text` i18n |
| 2.6 | `medicine_form.html` | `'medicines'` | Sales History link |
| 2.7 | `scanner_debug.html` | `'pos'` | Sales History link |

### Phase 3: High-risk templates (unique structures)

| Order | Template | `active_page` Value | Special Handling |
|---|---|---|---|
| 3.1 | `reports_profits.html` | `'reports-profits'` | Add Alerts + Employees links; change from `/reports-profits` to `/reports-sales` in main nav |
| 3.2 | `reports_sales.html` | `'reports-sales'` | Add Alerts + Employees links; **preserve client-side report tabs** in content area |
| 3.3 | `reports_slow_moving.html` | `'reports-slow-moving'` | Add Alerts + Employees links |
| 3.4 | `audit_log.html` | `'settings'` (or new `'audit-log'`) | Add Alerts link; consider adding Audit Log to nav |
| 3.5 | `purchase_forecast.html` | `'purchase-forecast'` | **Merge two nav sections** into one; move mobile toggle to `shared_layout.html`; remove `sidebarOpen` from page app |

### Phase 4: Cleanup

| Step | Action |
|---|---|
| 4.1 | Remove all inline `.sidebar` CSS from every template's `<style>` block |
| 4.2 | Remove duplicate dark-mode `.sidebar` CSS from every template |
| 4.3 | Verify no template contains literal `<aside` (all use include) |
| 4.4 | Update `css_version` in `shared_layout.html` to `7.3.0` |

---

## 5. Rollback Procedure

### Rollback Point

Branch: `navigation-refactor-backup` at commit `a3497a8`

### Full Rollback (all templates)

```bash
git checkout navigation-refactor-backup -- templates/
```

### Partial Rollback (specific templates)

```bash
git checkout navigation-refactor-backup -- templates/dashboard.html
git checkout navigation-refactor-backup -- templates/reports_profits.html
```

### Route Handler Rollback

```bash
git checkout navigation-refactor-backup -- main.py
```

### Rollback Triggers

| Trigger | Severity | Action |
|---|---|---|
| Blank sidebar on any page | CRITICAL | Full rollback |
| Active menu wrong on >2 pages | HIGH | Revert specific templates |
| Mobile sidebar broken | HIGH | Revert `shared_layout.html` + `purchase_forecast.html` |
| Employees link visible to non-admin | CRITICAL | Full rollback; fix `is_admin` logic |
| Dark mode sidebar broken | MEDIUM | Revert `shared_layout.html` CSS |
| Report tabs on `reports_sales.html` broken | MEDIUM | Revert `reports_sales.html` only |

### Post-Rollback Verification

1. Hard refresh (Ctrl+Shift+R) on 3 different pages
2. Sidebar renders correctly
3. Active menu highlighting works
4. Mobile sidebar toggle works

---

## 6. Validation Checklist

### Per-Template (repeat for all 17)

- [ ] Sidebar visible on page load (not blank)
- [ ] Brand "PharmaSUD" with cross icon renders
- [ ] All 14 nav items present (6 main + 4 reports + employees + alerts + settings)
- [ ] Current page's nav item has active state (blue bg, white text)
- [ ] Hover on nav items shows highlight effect
- [ ] User card shows name, initials, role
- [ ] Clicking user card logs out (redirects to /login)
- [ ] Mobile: sidebar hidden at <1024px; hamburger menu visible
- [ ] Mobile: tapping hamburger opens sidebar with overlay
- [ ] Dark mode: sidebar colors invert correctly
- [ ] No JavaScript errors in browser console
- [ ] No 404 errors for CSS/JS resources
- [ ] Page content layout unchanged (no margin/padding shifts)

### Global

- [ ] All 17 templates pass per-template checklist
- [ ] No template contains literal `<aside class="sidebar">` (all use include)
- [ ] No template contains `.sidebar .nav-item` CSS (all in `shared_layout.html`)
- [ ] `shared_layout.html` is the only file with sidebar CSS
- [ ] `partials/sidebar.html` is the only file with sidebar HTML
- [ ] `pos.html`, `login.html`, `splash.html` are untouched
- [ ] Employees link hidden for non-admin users
- [ ] Alert badge shows dynamic count (not hardcoded "7")
- [ ] Report sub-section with 4 items visible on all pages
- [ ] `reports_sales.html` client-side report tabs still functional
- [ ] `purchase_forecast.html` mobile toggle still works
- [ ] No layout shift when navigating between pages
- [ ] Cache-busting `?v7.3.0` applied to CSS link

---

## 7. Affected Files Summary

### Modified (19 files)

**Shared components (2):**
- `templates/shared_layout.html` — rewritten as base layout
- `templates/partials/sidebar.html` — rewritten as canonical sidebar

**Page templates (17):**
- `templates/dashboard.html`
- `templates/sales_history.html`
- `templates/reports_profits.html`
- `templates/reports_sales.html`
- `templates/reports_slow_moving.html`
- `templates/inventory.html`
- `templates/medicines_list.html`
- `templates/employees.html`
- `templates/alerts.html`
- `templates/settings.html`
- `templates/batch_receive.html`
- `templates/stocktake.html`
- `templates/purchase_forecast.html`
- `templates/invoice_view.html`
- `templates/audit_log.html`
- `templates/medicine_form.html`
- `templates/scanner_debug.html`

**Route handlers (1):**
- `main.py` — update context variables passed to templates

### NOT Modified (3 files)
- `templates/login.html` — no sidebar by design
- `templates/splash.html` — no sidebar by design
- `templates/pos.html` — standalone POS, no sidebar by design

---

*End of plan. Awaiting approval before implementation.*
