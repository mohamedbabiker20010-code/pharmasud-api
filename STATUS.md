# PharmaSUD - Project Status
## Last Updated: 2026-06-12 (Session 6 — Scanner Rebuild + Auth Fixes)
## Current Stage: Stage 6.5 - Permissions & Storage / Mobile Scanner Hardening
## Version: 6.5.0
## Branch: master (Render watches this branch, NOT main!)
## Live URL: https://pharmasud-api.onrender.com
## GitHub: https://github.com/mohamedbabiker20010-code/pharmasud-api

---

## what changed today (best-effort — later turns may differ)

- Replace old scanner code with tested dual-engine scanner in `templates/pos.html`
- keep existing `searchByBarcode()` and all POS features unchanged
- fixes basis: `startScanner`, `stopScanner`, scan loop, `scannerStream`, `scannerRunning`, `scannerEngine`, `scannerEngineType`

### barcode engine selection
- primary: `BarcodeDetector` + `getSupportedFormats()` check
- fallback: `https://esm.sh/zxing-wasm@2/reader`

### recent fixes
- removed duplicate `#scanner-status` div
- restored `#scan-torch-btn`
- kept manual barcode fallback and `searchManualBarcode()`
- removed silent `.catch(() => {})`; errors shown via `updateScannerStatus`

### auth / logout fix
- fixed logout clearing `role` from `localStorage` in:
  - `templates/dashboard.html`
  - `templates/purchase_forecast.html`
  - `templates/reports_slow_moving.html`
  - `templates/reports_profits.html`
  - `templates/reports_sales.html`

### independence
only `templates/pos.html`, `templates/scanner_debug.html`, and the 5 templates above were changed. no server-side changes.
