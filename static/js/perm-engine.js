/**
 * PharmaSUD - Permission Engine
 * Generic permission engine with zero knowledge of roles or permission sources.
 * Consumes a flat {permissionCode: boolean} object from /api/user/context.
 * Version: 1.0.0 (Frozen Architecture v1)
 */

const PharmaSUD = window.PharmaSUD || {};
PharmaSUD.perm = (function () {
  'use strict';

  let _cache = null;           // {permissionCode: boolean}
  let _features = {};          // {featureKey: {enabled, visible}}
  let _meta = {};              // {role, display_name, pharmacy_name, pharmacy_id, language, currency, system_version}
  let _initialized = false;

  // ============================================================
  // Initialization
  // ============================================================
  function init(context) {
    if (!context || !context.permissions) {
      console.warn('[PharmaSUD.perm] init() called with invalid context');
      return;
    }
    _cache = context.permissions || {};
    _features = context.feature_flags || {};
    _meta = context.meta || {};
    _initialized = true;
  }

  function isInitialized() {
    return _initialized;
  }

  // ============================================================
  // Generic Permission Checks
  // ============================================================
  function has(permissionCode) {
    return !!_cache?.[permissionCode];
  }

  function hasAny(permissionCodes) {
    if (!Array.isArray(permissionCodes) || permissionCodes.length === 0) return false;
    return permissionCodes.some(code => has(code));
  }

  function hasAll(permissionCodes) {
    if (!Array.isArray(permissionCodes) || permissionCodes.length === 0) return true;
    return permissionCodes.every(code => has(code));
  }

  // ============================================================
  // UI State Derivation (permission-centric)
  // Returns: 'visible' | 'hidden' | 'disabled' | 'readonly'
  // ============================================================
  function uiState(permissionCode) {
    if (!_initialized) return 'hidden';
    if (has(permissionCode)) return 'visible';
    return 'hidden';
  }

  // ============================================================
  // Feature Flag Checks
  // ============================================================
  function isFeatureEnabled(featureKey) {
    return !!_features?.[featureKey]?.enabled;
  }

  function isFeatureVisible(featureKey) {
    return !!_features?.[featureKey]?.visible;
  }

  // ============================================================
  // Combined Access Check (permission + feature)
  // ============================================================
  function canAccess(featureKey, permissionCode) {
    return isFeatureEnabled(featureKey) && has(permissionCode);
  }

  // ============================================================
  // Strategic Helpers (built from generic methods)
  // These are convenience methods for common UI patterns.
  // They MUST use the generic methods above, not duplicate logic.
  // ============================================================
  function canViewProfit() {
    return has(Permissions.PROFIT_VIEW) && isFeatureEnabled(Features.PROFIT);
  }

  function canUsePOS() {
    return has(Permissions.SALES_POS) && isFeatureEnabled(Features.POS);
  }

  function canManageEmployees() {
    return has(Permissions.EMPLOYEES_MANAGE) && isFeatureEnabled(Features.EMPLOYEES);
  }

  function canViewEmployees() {
    return has(Permissions.EMPLOYEES_VIEW) && isFeatureEnabled(Features.EMPLOYEES);
  }

  function canManageSettings() {
    return has(Permissions.SETTINGS_MANAGE) && isFeatureEnabled(Features.SETTINGS);
  }

  function canViewSettings() {
    return has(Permissions.SETTINGS_VIEW) && isFeatureEnabled(Features.SETTINGS);
  }

  function canViewAudit() {
    return has(Permissions.AUDIT_VIEW) && isFeatureEnabled(Features.AUDIT);
  }

  function canViewReports() {
    return has(Permissions.REPORTS_DASHBOARD) && isFeatureEnabled(Features.REPORTS);
  }

  function canUseBarcode() {
    return isFeatureEnabled(Features.BARCODE);
  }

  function canViewPurchaseForecast() {
    return has(Permissions.REPORTS_FORECAST) && isFeatureEnabled(Features.PURCHASE_FORECAST);
  }

  // ============================================================
  // Metadata Accessors
  // ============================================================
  function getRole() {
    return _meta?.role || '';
  }

  function getDisplayRole() {
    return _meta?.display_role_ar || _meta?.display_role_en || '';
  }

  function getPharmacyName() {
    return _meta?.pharmacy_name || '';
  }

  function getPharmacyId() {
    return _meta?.pharmacy_id || '';
  }

  function getLanguage() {
    return _meta?.language || 'ar';
  }

  function getCurrency() {
    return _meta?.currency || 'SDG';
  }

  function getSystemVersion() {
    return _meta?.system_version || '1.0.0';
  }

  function getFullName() {
    return _meta?.full_name || '';
  }

  function getUsername() {
    return _meta?.username || '';
  }

  // ============================================================
  // Cache Management
  // ============================================================
  function refresh(context) {
    init(context);
  }

  function clear() {
    _cache = null;
    _features = {};
    _meta = {};
    _initialized = false;
  }

  // ============================================================
  // Public API
  // ============================================================
  return {
    init,
    isInitialized,
    has,
    hasAny,
    hasAll,
    uiState,
    isFeatureEnabled,
    isFeatureVisible,
    canAccess,
    canViewProfit,
    canUsePOS,
    canManageEmployees,
    canViewEmployees,
    canManageSettings,
    canViewSettings,
    canViewAudit,
    canViewReports,
    canUseBarcode,
    canViewPurchaseForecast,
    getRole,
    getDisplayRole,
    getPharmacyName,
    getPharmacyId,
    getLanguage,
    getCurrency,
    getSystemVersion,
    getFullName,
    getUsername,
    refresh,
    clear,
  };
})();

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
  module.exports = PharmaSUD.perm;
}