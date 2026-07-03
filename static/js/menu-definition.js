/**
 * PharmaSUD - Menu Registry
 * Global declarative menu structure - NOT a sidebar implementation.
 * The sidebar is only ONE consumer. This registry is reusable by:
 * - Sidebar Navigation
 * - Mobile Navigation
 * - Dashboard Quick Actions
 * - Future Search/Command Palette
 * 
 * Version: 1.0.0 (Frozen Architecture v1)
 * No role checks - only permission and feature flags.
 */

const MENU_DEFINITION = [
  // ============================================================
  // Section: Main Operations (القائمة الرئيسية)
  // ============================================================
  {
    id: 'main',
    label: 'القائمة',
    permission: null,  // Section label - no permission needed
    feature: null,
    items: [
      {
        id: 'dashboard',
        label: 'لوحة التحكم',
        href: '/dashboard',
        icon: 'layout-dashboard',
        permission: Permissions.REPORTS_DASHBOARD,
        feature: Features.REPORTS,
        badge: null,
      },
      {
        id: 'pos',
        label: 'نقطة البيع',
        href: '/pos',
        icon: 'scan-barcode',
        permission: Permissions.SALES_POS,
        feature: Features.POS,
        badge: null,
      },
      {
        id: 'medicines',
        label: 'الأدوية',
        href: '/medicines',
        icon: 'pill',
        permission: Permissions.MEDICINES_VIEW,
        feature: null,  // Core module, always visible if permitted
        badge: null,
      },
      {
        id: 'inventory',
        label: 'المخزون',
        href: '/inventory',
        icon: 'package',
        permission: Permissions.INVENTORY_VIEW,
        feature: Features.INVENTORY,
        badge: null,
      },
      {
        id: 'batch-receive',
        label: 'استلام دفعة',
        href: '/batch-receive',
        icon: 'calendar-clock',
        permission: Permissions.INVENTORY_RECEIVE,
        feature: Features.INVENTORY,
        badge: null,
      },
      {
        id: 'sales-history',
        label: 'سجل المبيعات',
        href: '/sales-history',
        icon: 'receipt',
        permission: Permissions.SALES_VIEW_HISTORY,
        feature: Features.REPORTS,
        badge: null,
      },
    ],
  },

  // ============================================================
  // Section: Reports (التقارير)
  // ============================================================
  {
    id: 'reports',
    label: 'التقارير',
    permission: null,
    feature: Features.REPORTS,
    items: [
      {
        id: 'reports-sales',
        label: 'تقارير المبيعات',
        href: '/reports-sales',
        icon: 'chart-line',
        permission: Permissions.REPORTS_SALES,
        feature: Features.REPORTS,
        badge: null,
      },
      {
        id: 'reports-profits',
        label: 'تقرير الأرباح',
        href: '/reports-profits',
        icon: 'banknote',
        permission: Permissions.PROFIT_VIEW,
        feature: Features.PROFIT,
        badge: null,
      },
      {
        id: 'reports-slow-moving',
        label: 'بطيئة الحركة',
        href: '/reports-slow-moving',
        icon: 'turtle',
        permission: Permissions.REPORTS_SLOW_MOVING,
        feature: Features.REPORTS,
        badge: null,
      },
      {
        id: 'reports-purchase-forecast',
        label: 'توقعات الشراء',
        href: '/reports-purchase-forecast',
        icon: 'clipboard-list',
        permission: Permissions.REPORTS_FORECAST,
        feature: Features.PURCHASE_FORECAST,
        badge: null,
      },
    ],
  },

  // ============================================================
  // Section: Administration (إدارة)
  // ============================================================
  {
    id: 'admin',
    label: 'إدارة',
    permission: null,
    feature: null,
    items: [
      {
        id: 'employees',
        label: 'الموظفين',
        href: '/employees',
        icon: 'users',
        permission: Permissions.EMPLOYEES_VIEW,
        feature: Features.EMPLOYEES,
        badge: null,
      },
      {
        id: 'alerts',
        label: 'التنبيهات',
        href: '/alerts',
        icon: 'bell',
        permission: Permissions.ALERTS_VIEW,
        feature: null,
        badge: 'alertCount',  // Special: dynamic badge from alertCount
      },
      {
        id: 'settings',
        label: 'الإعدادات',
        href: '/settings',
        icon: 'settings',
        permission: Permissions.SETTINGS_VIEW,
        feature: Features.SETTINGS,
        badge: null,
      },
    ],
  },

  // ============================================================
  // Section: Specialized (ميزات متخصصة) - Future expansion
  // ============================================================
  {
    id: 'specialized',
    label: 'ميزات متخصصة',
    permission: null,
    feature: null,
    items: [
      {
        id: 'audit-log',
        label: 'سجل التدقيق',
        href: '/audit-log',
        icon: 'file-text',
        permission: Permissions.AUDIT_VIEW,
        feature: Features.AUDIT,
        badge: null,
      },
      {
        id: 'stocktake',
        label: 'الجرد',
        href: '/stocktake',
        icon: 'clipboard-check',
        permission: Permissions.INVENTORY_ADJUST,
        feature: Features.INVENTORY,
        badge: null,
      },
    ],
  },
];

// ============================================================
// Menu Registry API
// ============================================================
const MenuRegistry = {
  /**
   * Get all menu sections
   */
  getAll() {
    return MENU_DEFINITION;
  },

  /**
   * Get flat list of all menu items (for search, keyboard nav, etc.)
   */
  getAllItems() {
    return MENU_DEFINITION.flatMap(section => 
      section.items.map(item => ({ ...item, sectionId: section.id, sectionLabel: section.label }))
    );
  },

  /**
   * Get items by section ID
   */
  getSection(sectionId) {
    return MENU_DEFINITION.find(s => s.id === sectionId) || null;
  },

  /**
   * Get item by ID (across all sections)
   */
  getItem(itemId) {
    for (const section of MENU_DEFINITION) {
      const item = section.items.find(i => i.id === itemId);
      if (item) return { ...item, sectionId: section.id, sectionLabel: section.label };
    }
    return null;
  },

  /**
   * Get items for a specific consumer (sidebar, mobile, quick actions, etc.)
   * Consumer can filter by feature, permission, or section.
   */
  getForConsumer(consumer) {
    const { allowedSections, allowedFeatures, requiredPermission } = consumer || {};
    
    return MENU_DEFINITION
      .filter(section => {
        if (allowedSections && !allowedSections.includes(section.id)) return false;
        if (section.feature && allowedFeatures && !allowedFeatures.includes(section.feature)) return false;
        return true;
      })
      .map(section => ({
        ...section,
        items: section.items.filter(item => {
          if (requiredPermission && !PharmaSUD.perm.has(item.permission)) return false;
          if (item.feature && allowedFeatures && !allowedFeatures.includes(item.feature)) return false;
          return true;
        }),
      }))
      .filter(section => section.items.length > 0);
  },

  /**
   * Check if a menu item should be visible (permission + feature)
   * Uses PharmaSUD.perm engine - MUST be called after perm.init()
   */
  isItemVisible(item) {
    if (!window.PharmaSUD || !window.PharmaSUD.perm || !window.PharmaSUD.perm.isInitialized()) {
      return false;
    }
    
    // Check permission
    if (item.permission && !PharmaSUD.perm.has(item.permission)) {
      return false;
    }
    
    // Check feature flag
    if (item.feature && !PharmaSUD.perm.isFeatureEnabled(item.feature)) {
      return false;
    }
    
    return true;
  },

  /**
   * Get visible items for current user (permission-aware)
   * Returns filtered menu structure ready for rendering
   */
  getVisibleMenu() {
    if (!window.PharmaSUD || !window.PharmaSUD.perm || !window.PharmaSUD.perm.isInitialized()) {
      return [];
    }
    
    return MENU_DEFINITION
      .map(section => {
        const visibleItems = section.items.filter(item => this.isItemVisible(item));
        if (visibleItems.length === 0) return null;
        return { ...section, items: visibleItems };
      })
      .filter(Boolean);
  },

  /**
   * Quick Actions - for dashboard shortcuts
   * Returns high-priority items for quick access
   */
  getQuickActions(limit = 6) {
    const visible = this.getVisibleMenu().flatMap(s => s.items);
    // Priority order for quick actions
    const priority = ['pos', 'dashboard', 'medicines', 'inventory', 'batch-receive', 'sales-history', 'alerts'];
    return visible
      .sort((a, b) => (priority.indexOf(a.id) - priority.indexOf(b.id)))
      .slice(0, limit);
  },
};

// Export for module systems and global namespace
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { MENU_DEFINITION, MenuRegistry };
} else {
  window.MENU_DEFINITION = MENU_DEFINITION;
  window.MenuRegistry = MenuRegistry;
}