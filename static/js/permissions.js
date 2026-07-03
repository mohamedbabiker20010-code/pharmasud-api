/**
 * PharmaSUD - Permission Constants
 * Single source of truth for all permission codes.
 * Frontend must NEVER use raw string literals for permissions.
 * Version: 1.0.0 (Frozen Architecture v1)
 */

const Permissions = {
  // Authentication
  AUTH_LOGIN: 'auth.login',

  // Medicines
  MEDICINES_VIEW: 'medicines.view',
  MEDICINES_CREATE: 'medicines.create',
  MEDICINES_EDIT: 'medicines.edit',
  MEDICINES_DELETE: 'medicines.delete',

  // Inventory
  INVENTORY_VIEW: 'inventory.view',
  INVENTORY_RECEIVE: 'inventory.receive',
  INVENTORY_ADJUST: 'inventory.adjust',
  INVENTORY_VIEW_EXPIRED: 'inventory.view_expired',

  // Sales
  SALES_POS: 'sales.pos',
  SALES_VIEW_HISTORY: 'sales.view_history',
  SALES_VOID: 'sales.void',

  // Reports
  REPORTS_DASHBOARD: 'reports.dashboard',
  REPORTS_SALES: 'reports.sales',
  REPORTS_FORECAST: 'reports.forecast',
  REPORTS_SLOW_MOVING: 'reports.slow_moving',
  REPORTS_FINANCIAL: 'reports.financial',

  // Profit (Financial - Owner only)
  PROFIT_VIEW: 'profit.view',

  // Alerts
  ALERTS_VIEW: 'alerts.view',
  ALERTS_RESOLVE: 'alerts.resolve',

  // Employees
  EMPLOYEES_VIEW: 'employees.view',
  EMPLOYEES_MANAGE: 'employees.manage',

  // Settings
  SETTINGS_VIEW: 'settings.view',
  SETTINGS_MANAGE: 'settings.manage',

  // Audit (Financial - Owner only)
  AUDIT_VIEW: 'audit.view',

  // Purchase
  PURCHASE_VIEW: 'purchase.view',
};

// Feature Flags - Module-level feature toggles
const Features = {
  POS: 'pos',
  INVENTORY: 'inventory',
  REPORTS: 'reports',
  BARCODE: 'barcode',
  PURCHASE_FORECAST: 'purchase_forecast',
  AUDIT: 'audit',
  PROFIT: 'profit',
  EMPLOYEES: 'employees',
  SETTINGS: 'settings',
};

// Export for module systems and global namespace
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { Permissions, Features };
} else {
  window.Permissions = Permissions;
  window.Features = Features;
}