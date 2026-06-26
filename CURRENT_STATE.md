# PharmaSUD — Current State Snapshot
*Authoritative recovery snapshot — max 100 lines. Updated after every major change.*

---

## Version & Branch
- **Version**: 7.2.0 "Light + Blue Theme"
- **Branch**: `master` (Render watches `master`)
- **Last Commit**: `5a0c1aa` — "feat: Add permanent project memory system"

---

## Current Task
**No active task** — Phase 2D/2F deployed. Mobile sidebar fixed for settings/alerts/batch_receive. Sidebar has close button + auto-close. Ready for next sprint.

---

## Next Task (Priority Order)
1. **Fix mobile sidebar x-data on 2 pages** — sales_history.html and stocktake.html (2 hours)
2. **Implement Void Sale** — `sales.void` endpoint + POS undo (1 day)
3. **Full RBAC Enforcement** — Replace `require_admin` with `require_permission()` on all endpoints (1 day)
4. **Fix Profit Report** — Capture `purchase_price` on all batches (4 hours)
5. **Security Phase 3** — CSRF, MFA, JWT denylist, CSP enforcement (5 days)

---

## Production Blockers (Must Fix Before Real Pharmacy Use)
1. ❌ **Mobile sidebar on 2 pages** — sales_history.html and stocktake.html still lack x-data wrapper
2. ❌ **No void sale** — Customer changes mind = manual workaround
3. ❌ **Profit shows 0.00** — Misleading owner dashboard
4. ❌ **RBAC over-permissive** — Employees can call admin APIs
5. ❌ **No JWT revocation** — Stolen token valid 24h
6. ❌ **CSP report-only** — No XSS protection enforcement

---

## Recently Fixed Items (Last 5 Commits)
|| Commit | Date | Fix |
||--------|------|-----|
|| `29fc483` | 2026-06-22 | Restore CSS styles in alerts.html - complete design migration |
|| `1eec0cd` | 2026-06-22 | Fix JS syntax — close loadNotifications with comma not brace |
|| `f4383f0` | 2026-06-22 | Phase 2D — Complete x-data wrappers for settings/alerts/batch_receive + sidebar X/close button |
|| `acce5f7` | 2026-06-22 | Fix reports_slow_moving.html — replace nested <main> with <div> |
|| `c6b89f7` | 2026-06-19 | Add RBAC tables and role_id column creation to startup event handler |

---

## Do Not Touch List
- **`main.py` startup DDL** — `create_all()` + ALTER TABLE runs on every boot (Alembic not used in deploy)
- **`auth.py` JWT config** — 24h expiry, HS256, localStorage (Phase 3 will change)
- **`batches.py` FEFO logic** — `expiry_date > today` excludes today-expiring batches
- **`models.py` Base64 images** — Migration to S3 planned, not yet
- **Template inline CSS** — 15 templates still duplicate layout; fix via `shared_layout.html` pattern
- **`pos.html` barcode scanner** — Dual engine (BarcodeDetector + zxing-wasm) — tested, working
- **`demo/` auto-seed** — Creates demo pharmacy if DB empty; masks real DB issues

---

## Key Metrics
- **Feature Complete**: ~80%
- **Production Hardened**: ~48%
- **RBAC Enforced**: 15% (only 3 endpoints)
- **Mobile UX Fixed**: 90% (2/21 pages remaining)

---

## Last Updated
**2026-06-23** — Phase 2D/2F deployed. Mobile sidebar fixed for settings/alerts/batch_receive. Sidebar has close button + auto-close. Production verified with recoveryadmin.