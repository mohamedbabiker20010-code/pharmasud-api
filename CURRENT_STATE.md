# PharmaSUD — Current State Snapshot
*Authoritative recovery snapshot — max 100 lines. Updated after every major change.*

---

## Version & Branch
- **Version**: 7.2.0 "Light + Blue Theme"
- **Branch**: `master` (Render watches `master`)
- **Last Commit**: `5a0c1aa` — "feat: Add permanent project memory system"

---

## Current Task
**No active task** — Project memory system created and committed. Ready for next sprint.

---

## Next Task (Priority Order)
1. **Initialize Production DB** — Activate product key + create admin (15 min)
2. **Fix Mobile Sidebar** — Remove inline CSS from 15 templates (4 hrs)
3. **Implement Void Sale** — `sales.void` endpoint + POS undo (1 day)
4. **Full RBAC Enforcement** — Replace `require_admin` with `require_permission()` on all endpoints (1 day)
5. **Fix Profit Report** — Capture `purchase_price` on all batches (4 hrs)

---

## Production Blockers (Must Fix Before Real Pharmacy Use)
1. ❌ **Production DB not initialized** — No activated pharmacy, no admin user
2. ❌ **Mobile sidebar broken** — 15/17 pages unusable on phone
3. ❌ **No void sale** — Customer changes mind = manual workaround
4. ❌ **Profit shows 0.00** — Misleading owner dashboard
5. ❌ **RBAC over-permissive** — Employees can call admin APIs
6. ❌ **No JWT revocation** — Stolen token valid 24h
7. ❌ **CSP report-only only** — No XSS protection enforcement

---

## Recently Fixed Items (Last 5 Commits)
| Commit | Date | Fix |
|--------|------|-----|
| `5a0c1aa` | 2026-06-19 | Project memory system (PROJECT_MEMORY.md + backup) |
| `c6b89f7` | 2026-06-19 | RBAC tables + role_id in startup |
| `230071e` | 2026-06-18 | RBAC Phase 1: roles, permissions, audit logging |
| `2d17024` | 2026-06-18 | Splash screen at root (v7.2.0) |
| `e2b3dc2` | 2026-06-17 | Exception sanitization (Phase 2.3) |

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
- **Feature Complete**: ~78%
- **Production Hardened**: ~45%
- **RBAC Enforced**: 15% (only 3 endpoints)
- **Mobile UX Fixed**: 12% (2/17 templates)

---

## Last Updated
**2026-06-19** — Project memory system created, committed at `5a0c1aa`