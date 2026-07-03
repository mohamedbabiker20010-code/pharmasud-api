# PharmaSUD RBAC Frontend Architecture Documentation
**Version**: 1.0.0 (Frozen Architecture v1)
**Date**: 2026-07-03
**Status**: FINAL - No redesigns permitted

---

## 1. Overview

This document describes the frontend authorization architecture for PharmaSUD v1. It is **frozen** — all future work must build on this foundation without redesigning it.

### Core Principles
- **Backend is sole authorization authority** — Frontend never makes access decisions
- **Single permission source** — `/api/user/context` returns effective permissions
- **Permission-centric, not role-centric** — Frontend only knows permission codes
- **Feature flags independent from permissions** — Module toggles separate from RBAC
- **Extensible by design** — Internal backend changes never break frontend contract

---

## 2. Permission Engine (`PharmaSUD.perm`)

**Location**: `static/js/perm-engine.js`

### API Surface (Frozen)

```javascript
// Initialization (called once on app bootstrap)
PharmaSUD.perm.init(context)           // context from /api/user/context

// Generic Permission Checks
PharmaSUD.perm.has(code)               // boolean
PharmaSUD.perm.hasAny(codes[])         // boolean (OR)
PharmaSUD.perm.hasAll(codes[])         // boolean (AND)

// UI State Derivation
PharmaSUD.perm.uiState(code)           // 'visible' | 'hidden' | 'disabled' | 'readonly'

// Feature Flags
PharmaSUD.perm.isFeatureEnabled(key)   // boolean
PharmaSUD.perm.isFeatureVisible(key)   // boolean

// Combined Access
PharmaSUD.perm.canAccess(feature, permission)  // feature enabled AND has permission

// Strategic Helpers (built from generic methods above)
PharmaSUD.perm.canViewProfit()
PharmaSUD.perm.canUsePOS()
PharmaSUD.perm.canManageEmployees()
PharmaSUD.perm.canViewEmployees()
PharmaSUD.perm.canManageSettings()
PharmaSUD.perm.canViewSettings()
PharmaSUD.perm.canViewAudit()
PharmaSUD.perm.canViewReports()
PharmaSUD.perm.canUseBarcode()
PharmaSUD.perm.canViewPurchaseForecast()

// Metadata (from context.meta)
PharmaSUD.perm.getRole()
PharmaSUD.perm.getDisplayRole()
PharmaSUD.perm.getPharmacyName()
PharmaSUD.perm.getPharmacyId()
PharmaSUD.perm.getLanguage()
PharmaSUD.perm.getCurrency()
PharmaSUD.perm.getSystemVersion()
PharmaSUD.perm.getFullName()
PharmaSUD.perm.getUsername()

// Cache Management
PharmaSUD.perm.refresh(context)
PharmaSUD.perm.clear()
PharmaSUD.perm.isInitialized()
```

### Design Invariants
- **Zero role awareness** — No `role` checks, no `isAdmin` logic
- **Zero permission string literals** — All codes from `Permissions` constants
- **Pure functions** — No DOM manipulation, no side effects
- **Single source** — Only `PharmaSUD.perm` exposes permission logic

---

## 3. Permission Constants (`Permissions`)

**Location**: `static/js/permissions.js`

### Catalog (26 Permissions - Frozen)

```javascript
// Authentication
Permissions.AUTH_LOGIN              // 'auth.login'

// Medicines
Permissions.MEDICINES_VIEW          // 'medicines.view'
Permissions.MEDICINES_CREATE        // 'medicines.create'
Permissions.MEDICINES_EDIT          // 'medicines.edit'
Permissions.MEDICINES_DELETE        // 'medicines.delete'

// Inventory
Permissions.INVENTORY_VIEW          // 'inventory.view'
Permissions.INVENTORY_RECEIVE       // 'inventory.receive'
Permissions.INVENTORY_ADJUST        // 'inventory.adjust'
Permissions.INVENTORY_VIEW_EXPIRED  // 'inventory.view_expired'

// Sales
Permissions.SALES_POS               // 'sales.pos'
Permissions.SALES_VIEW_HISTORY      // 'sales.view_history'
Permissions.SALES_VOID              // 'sales.void'

// Reports
Permissions.REPORTS_DASHBOARD       // 'reports.dashboard'
Permissions.REPORTS_SALES           // 'reports.sales'
Permissions.REPORTS_FORECAST        // 'reports.forecast'
Permissions.REPORTS_SLOW_MOVING     // 'reports.slow_moving'
Permissions.REPORTS_FINANCIAL       // 'reports.financial'

// Profit (Financial - Owner Only)
Permissions.PROFIT_VIEW             // 'profit.view'

// Alerts
Permissions.ALERTS_VIEW             // 'alerts.view'
Permissions.ALERTS_RESOLVE          // 'alerts.resolve'

// Employees
Permissions.EMPLOYEES_VIEW          // 'employees.view'
Permissions.EMPLOYEES_MANAGE        // 'employees.manage'

// Settings
Permissions.SETTINGS_VIEW           // 'settings.view'
Permissions.SETTINGS_MANAGE         // 'settings.manage'

// Audit (Financial - Owner Only)
Permissions.AUDIT_VIEW              // 'audit.view'

// Purchase
Permissions.PURCHASE_VIEW           // 'purchase.view'
```

### Feature Flags (9 Features - Frozen)

```javascript
Features.POS                        // 'pos'
Features.INVENTORY                  // 'inventory'
Features.REPORTS                    // 'reports'
Features.BARCODE                    // 'barcode'
Features.PURCHASE_FORECAST          // 'purchase_forecast'
Features.AUDIT                      // 'audit'
Features.PROFIT                     // 'profit'
Features.EMPLOYEES                  // 'employees'
Features.SETTINGS                   // 'settings'
```

---

## 4. Context Contract (`/api/user/context`)

**Endpoint**: `GET /api/user/context`
**Router**: `routers/user_context.py`

### Response Structure (Frozen)

```json
{
  "authentication": {
    "user_id": "uuid",
    "full_name": "string",
    "username": "string",
    "display_role_ar": "string",
    "display_role_en": "string"
  },
  "permissions": {
    "permission.code": true|false,
    ...
  },
  "feature_flags": {
    "feature_key": { "enabled": true|false, "visible": true|false },
    ...
  },
  "pharmacy": {
    "id": "uuid",
    "name": "string",
    "branch_id": null,
    "owner_id": "uuid|null"
  },
  "meta": {
    "role": "string",
    "display_role_ar": "string",
    "display_role_en": "string",
    "pharmacy_name": "string",
    "pharmacy_id": "uuid",
    "language": "ar",
    "currency": "SDG",
    "system_version": "7.1.0",
    "full_name": "string",
    "username": "string"
  }
}
```

### Contract Guarantees
- **Flat permissions object** — `{code: boolean}` for O(1) lookup
- **Feature flags always present** — All 9 keys returned, never null
- **Meta includes stable identifiers** — `pharmacy_id`, `currency`, `language` for i18n
- **Extensible** — New keys added, never removed or renamed

---

## 5. Bootstrap Flow

**Location**: `templates/shared_layout.html` (inline script)

```javascript
// 1. On DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
  if (window.lucide) lucide.createIcons();
  initializePermissionEngine();  // ← Critical: runs before any page logic
});

// 2. initializePermissionEngine()
async function initializePermissionEngine() {
  const token = localStorage.getItem('token');
  if (!token) return;
  
  try {
    const response = await fetch('/api/user/context', {
      headers: { 'Authorization': 'Bearer ' + token }
    });
    
    if (response.ok) {
      const context = await response.json();
      
      // Initialize engine (single source of truth)
      if (window.PharmaSUD && window.PharmaSUD.perm) {
        window.PharmaSUD.perm.init(context);
      }
      
      // Cache for offline/refresh resilience
      localStorage.setItem('pharmasud.perm.cache', JSON.stringify(context));
      
      // Notify other components
      window.dispatchEvent(new CustomEvent('pharmasud:perm:ready', { detail: context }));
    }
  } catch (e) {
    // Fallback to cached context
    const cached = localStorage.getItem('pharmasud.perm.cache');
    if (cached && window.PharmaSUD?.perm) {
      window.PharmaSUD.perm.init(JSON.parse(cached));
    }
  }
}
```

### Load Order (Critical)
1. `permissions.js` — Constants first
2. `perm-engine.js` — Engine second
3. `menu-definition.js` — Registry third
4. Alpine `pageApp()` — Page logic last (consumes engine)

---

## 6. Menu Registry (`MenuRegistry`)

**Location**: `static/js/menu-definition.js`

### Purpose
Global declarative menu structure — **NOT a sidebar implementation**.  
Consumers: Sidebar, Mobile Nav, Dashboard Quick Actions, Future Search.

### Structure (Frozen)

```javascript
const MENU_DEFINITION = [
  {
    id: 'main',
    label: 'القائمة',
    permission: null,
    feature: null,
    items: [
      { id: 'dashboard', label: 'لوحة التحكم', href: '/dashboard', icon: 'layout-dashboard',
        permission: Permissions.REPORTS_DASHBOARD, feature: Features.REPORTS },
      { id: 'pos', label: 'نقطة البيع', href: '/pos', icon: 'scan-barcode',
        permission: Permissions.SALES_POS, feature: Features.POS },
      { id: 'medicines', label: 'الأدوية', href: '/medicines', icon: 'pill',
        permission: Permissions.MEDICINES_VIEW, feature: null },
      // ... more items
    ]
  },
  // sections: reports, admin, specialized
];
```

### Registry API (Frozen)

```javascript
MenuRegistry.getAll()                    // Full structure
MenuRegistry.getAllItems()               // Flat array with section info
MenuRegistry.getSection(sectionId)       // Section by ID
MenuRegistry.getItem(itemId)             // Item by ID (with section context)
MenuRegistry.getForConsumer(config)      // Filtered for specific consumer
MenuRegistry.isItemVisible(item)         // Permission + feature check
MenuRegistry.getVisibleMenu()            // Fully filtered structure
MenuRegistry.getQuickActions(limit)      // Priority items for dashboard
```

### Consumer Config Example
```javascript
// Sidebar consumer
MenuRegistry.getForConsumer({
  allowedSections: ['main', 'reports', 'admin'],
  allowedFeatures: null,  // all
  requiredPermission: null
});

// Dashboard quick actions consumer
MenuRegistry.getQuickActions(6);  // Top 6 priority items
```

---

## 7. Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        BACKEND                                   │
│  ┌─────────────────┐    ┌──────────────────┐    ┌────────────┐ │
│  │ User + Role     │───►│ resolve_effective│───►│ /api/user/ │ │
│  │ role_permissions│    │ _permissions()   │    │ context    │ │
│  └─────────────────┘    └──────────────────┘    └────────────┘ │
│         │                        │                    │         │
│         │                        │                    │         │
│         ▼                        ▼                    ▼         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Extension Points (Future, No Frontend Impact)           │  │
│  │  • user_permission_grants  (delegation)                  │  │
│  │  • temporary_grants        (expiring)                    │  │
│  │  • branch_grants           (multi-branch)                │  │
│  │  • corporate_grants        (multi-pharmacy)              │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ JSON over HTTPS
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │ permissions.js│───►│ perm-engine.js│◄──│ shared_layout.html│  │
│  │ (constants)   │    │ (PharmaSUD.  │    │ (bootstrap)      │  │
│  └──────────────┘    │  perm)       │    └────────┬─────────┘  │
│                      └──────┬───────┘             │            │
│                             │                      │            │
│              ┌──────────────┼──────────────┐      │            │
│              ▼              ▼              ▼      ▼            │
│       menu-definition.js  pageApp()    dashboard.html   etc.  │
│       (MenuRegistry)      (Alpine)     (consumes perm)       │
│                                                                 │
│  ALL consumers use: PharmaSUD.perm.has(Permissions.X)        │
│  NO consumer uses: role, isAdmin, raw strings                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8. Extension Points (Backend Only)

The following backend changes **require zero frontend modifications**:

| Extension | Backend Change | Frontend Impact |
|-----------|---------------|-----------------|
| User-level grants | Add `user_permission_grants` table, merge in `resolve_effective_permissions()` | None — permissions object expands |
| Temporary permissions | Add `expires_at` to grants, filter in resolver | None — same permission codes |
| Branch-scoped permissions | Add `branch_id` to grants, scope in resolver | None — same permission codes |
| Corporate groups | Add `corporate_group_id`, merge grants | None — same permission codes |
| New feature flag | Add key to `get_feature_flags()` return | None — new `Features.KEY` constant only |
| New permission | Add to seeder, appears in context | Add `Permissions.NEW_PERM` constant |

---

## 9. Compliance Checklist (Frozen Architecture v1)

| Requirement | Implementation | Status |
|-------------|---------------|--------|
| Backend sole auth authority | `/api/user/context` single source | ✅ |
| No role checks in frontend | `PharmaSUD.perm` has zero role logic | ✅ |
| No raw permission strings | All via `Permissions.CONSTANT` | ✅ |
| Feature flags independent | Separate `feature_flags` in context | ✅ |
| Single permission engine | `PharmaSUD.perm` only | ✅ |
| Menu registry decoupled | `MenuRegistry` no sidebar logic | ✅ |
| Context returns effective perms | `resolve_effective_permissions()` | ✅ |
| Metadata section present | `meta` in context contract | ✅ |
| Cache resilience | localStorage fallback | ✅ |
| Extension-ready resolver | Commented merge points documented | ✅ |

---

## 10. Version History

| Version | Date | Change |
|---------|------|--------|
| 1.0.0 | 2026-07-03 | Initial freeze — Wave 1 complete |

**No further versions without explicit architecture review.**