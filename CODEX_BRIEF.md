# PharmaSUD — Full Project Brief for AI Analysis

## 1. PROJECT OVERVIEW

### What is PharmaSUD?
PharmaSUD is a **Pharmacy Point of Sale (POS) and Inventory Management System** built specifically for the Sudanese market. It is a web-based application (FastAPI backend + HTML/JS/Alpine.js frontend) designed to replace manual/physical pharmacy management with a digital system.

### Target Market
- Sudan pharmacy market (primary)
- Currency: Sudanese Pound (SDG)
- Market characteristics: fragmented, low-quality Egypt/Gulf repackages, offline-first is critical trust factor

### Business Model
- One-time license pricing (NOT subscription)
- Current pricing:
  - Pilot: 200,000 SDG (first 10 pharmacies, 3 months free support)
  - Standard: 250,000 SDG
  - Multi-branch: 500,000 SDG
- License includes: full code ownership transfer to client
- Support: 3 months free, then paid
- Payment methods: Sudan/Turkey bank transfer + crypto

### Unique Value Proposition
"أرخص نظام إدارة صيدليات متكامل في السوق السوداني مع ميزات تفوق المنافسين"

---

## 2. TECH STACK

### Backend
- **Framework:** FastAPI (Python 3.11)
- **Database:** PostgreSQL (hosted on Render)
- **ORM:** SQLAlchemy
- **Authentication:** JWT tokens (HS256)
- **File uploads:** python-multipart
- **Server:** Uvicorn

### Frontend
- **Templating:** Jinja2
- **Framework:** Alpine.js (CDN-loaded, no build step)
- **Styling:** CSS with custom properties (CSS Variables) — Light Mode + Blue theme
- **Font:** Cairo (Google Fonts) + system fallbacks
- **Barcode scanning:** Dual-engine
  - Android: BarcodeDetector API (native)
  - iOS/non-Android: zxing-wasm (loaded dynamically via esm.sh)
- **Icons:** SVG inline

### Infrastructure
- **Hosting:** Render.com (pharmasud-api.onrender.com)
- **Database:** PostgreSQL on Render (dpg-d8hcm6l...oregon-postgres.render.com)
- **Repo:** github.com/mohamedbabiker20010-code/pharmasud-api (PUBLIC)
- **CI/CD:** Automatic deploy on push to master (Render builds from GitHub)

---

## 3. SYSTEM ARCHITECTURE

### Directory Structure
```
pharmasud/
├── main.py                 # FastAPI app, all routes, DB init
├── alembic/                # Database migrations
├── templates/              # Jinja2 HTML templates (16 files)
│   ├── login.html
│   ├── splash.html
│   ├── dashboard.html
│   ├── pos.html            # POS page with barcode scanner (CRITICAL)
│   ├── medicines_list.html
│   ├── medicine_form.html
│   ├── batch_receive.html
│   ├── inventory.html
│   ├── sales_history.html
│   ├── invoice_view.html
│   ├── reports_sales.html
│   ├── reports_profits.html
│   ├── reports_slow_moving.html
│   ├── purchase_forecast.html
│   ├── scanner_debug.html
│   └── settings.html
├── static/
│   └── css/
│       └── theme.css       # NEW v7.1.0 — CSS Variables (Light + Blue theme)
├── .env                    # NOT in git (Render env vars only)
├── .env.example            # Template with placeholders
├── .gitignore              # Excludes .env, venv, __pycache__
└── employees.py            # Employees module
    audit.py                # Audit log module

### Database Schema (Core Tables)
- pharmacies (multi-tenant)
- users (with roles: admin, manager, cashier)
- medicines (inventory items)
- batches (FEFO tracking — expiry dates, purchase price, sale price)
- sales / sale_items
- purchases / purchase_items
- expenses
- customers (CRM)
- suppliers
- invoices
- audit_log (Stage 7)
- alerts (Stage 7)
- stocktake_sessions (Stage 7)
- employees (Stage 7)

### API Routes
- POST /api/auth/login — JWT login
- GET  /api/auth/me — current user
- POST /api/auth/logout
- POST /api/sales — create sale
- GET  /api/inventory — inventory list
- POST /api/medicines — add medicine
- POST /api/batch/receive — batch receive
- GET  /api/reports/sales
- GET  /api/reports/profits
- GET  /api/reports/slow_moving
- GET  /api/alerts
- GET  /api/employees
- POST /api/audit/log
- GET  /api/stocktake

---

## 4. DEVELOPMENT STAGES (Version History)

### v6.0 — Core POS
- Basic sales, inventory, medicines CRUD
- Dark mode UI

### v6.4 — Fixes
- Bug fixes, feminine→masculine voice in UI
- Security hardening

### v6.5 — Permissions & Storage
- Role-based access control
- Server barcode decoder

### v7.0 — Stage 7 (Current before v7.1.0)
- Alerts system (expiry, low stock, financial)
- Employees management module
- Audit Log (full tracking)
- Stocktake module (inventory counting)
- Dual-engine barcode scanner (BarcodeDetector + zxing-wasm)
- Scanner debug page
- Logout fix

### v7.1.0 — New Visual Identity (CURRENT — deployed)
- Light Mode (white backgrounds)
- Blue theme (replaced dark green/blue)
- Animated Splash Screen (once per day)
- Split-screen Login (desktop) / Form-only (mobile)
- Cairo font
- CSS Variables centralized in theme.css
- All 16 templates color-swapped (Dark → Light)

---

## 5. CODING RULES & CONVENTIONS (GOLDEN RULES)

### A. Surgical Patches ONLY
**Rule:** Never rewrite a whole file. Edit only the exact line/function needed.
- If error appears → STOP at offending file, diagnose, patch exact line
- Full rewrite = LAST RESORT after 2-3 failed patch attempts + explicit user approval
- Reason: tested barcode engine (pos.html) must never be accidentally overwritten

### B. Semantic Versioning (SemVer)
- **PATCH** (x.x.+1): bug fixes, CSS colors, text fixes
- **MINOR** (x.+1.0): new feature/page (e.g., v7.1.0 = new visual identity)
- **MAJOR** (+.0.0): breaking changes (database schema, auth system) — RARE
- Example: current is 7.1.0
  - CSS fix → 7.1.1
  - New report page → 7.2.0
  - Migrate DB schema → 8.0.0

### C. Arabic Language Rules
- All UI text: Arabic-first, masculine/general masculine (مذكر عام)
- NEVER feminine forms (تأكدي→تأكد، ادخلي→أدخل، اضغطي→اضغط)
- English only for: code, commands, filenames, SQL queries

### D. Error Protocol
1. STOP at offending file
2. Report: file/line/function/error message/fix suggestion
3. WAIT for user approval before any additional edits
4. Keep version at 7.0.x until issue resolved

---

## 6. COMPETITOR ANALYSIS

### Competitor 1: Saydalati / صيدليتي (SEIDLETI)
- **Type:** Web app (SaaS), hosted on Vercel
- **URL:** saydali.app (Flutter project on GitHub), my-pharmacy-version-2.vercel.app
- **Developer:** Individual named "حازم" (Hazem)
- **Pricing:** 600,000 SDG (offline) / 800,000 SDG (online)
- **UI:** Professional (teal/blue-white), similar to modern SaaS
- **Critical Weaknesses (verified by live testing with admin@example.com / Admin@12345):**
  - 96% of inventory shows as "low stock" (542/562 items) — broken algorithm or fake data
  - ALL product quantities = 0 (data zeroed out or never tracked)
  - NO batch/FEFO tracking (no expiry date column in medicine table)
  - NO CRM/Customers module
  - NO advanced reports
  - NO employee/permissions management
  - NO audit log
  - NO stocktake
  - Data is unrealistic (expected profit 130M SDG vs actual sales 20K SDG — 6500x discrepancy)
  - "version-2" in URL suggests still in development
  - Free hosting on Vercel (not production-grade)
- **Verdict:** NOT a real threat. Beautiful UI, empty inside.

### Competitor 2: pyharmacy
- **Type:** Desktop application (Windows .exe)
- **Pricing:** 300,000 / 500,000 / 800,000 SDG tiers
- **Platform:** Windows desktop only (not web)
- **Known features:** Basic POS, inventory, reports (not verified)
- **Weaknesses:** No web access, no mobile, no AI, no real-time multi-user
- **Verdict:** Moderate threat only due to price (300k vs our 250k). We beat them on features + price.

### Competitive Position
PharmaSUD is currently the **strongest** system in the Sudanese pharmacy market:
- Only system with FEFO/batch tracking
- Only system with AI vision capabilities
- Only system with full audit trail + stocktake
- Lowest price (250k vs 300k-800k)
- Web-based (accessible anywhere, any device)
- Arabic-first design

---

## 7. CURRENT SYSTEM STATUS

- **Version:** 7.1.0
- **Status:** Deployed on Render (automatic rebuild on git push)
- **Live URL:** https://pharmasud-api.onrender.com
- **Repo:** https://github.com/mohamedbabiker20010-code/pharmasud-api (PUBLIC)
- **Database:** PostgreSQL on Render (connection via DATABASE_URL env var)
- **Auth:** JWT with SECRET_KEY (both mandatory env vars)
- **Barcode engine:** Dual (BarcodeDetector for Android, zxing-wasm for iOS) — TESTED on real devices
- **Design system:** Light Mode + Blue theme (rolled out in v7.1.0 across all 16 templates)

---

## 8. IMMEDIATE PLANNED WORK

### Next Feature: Debt Management (إدارة مديونات)
- Track customer debts
- Payment reminders
- Credit limits
- Aging reports

This will be **v7.2.0** (MINOR bump — new feature).

### Future Ideas
- WhatsApp integration (360dialog) for notifications
- Claude Vision for medicine recognition
- Multi-language support (Arabic + English)
- Advanced analytics dashboard

---

## 9. TECHNICAL DEBT & KNOWN ISSUES

1. **FastAPI/Jinja2 version conflict:** jinja2 3.0.3 is required for compatibility with starlette 1.0.1 (hermes-agent requires jinja2 3.1.6, creating a conflict for local development)
2. **Local dev requires Render DB:** The app auto-connects to Render PostgreSQL on startup, so local offline development fails without internet
3. **No test suite:** No automated tests (manual testing only)
4. **Single developer:** David builds, Mohamed sells

---

## 10. DEPLOYMENT WORKFLOW

```
1. Edit files locally (/home/lenovo/pharmasud/)
2. git add -A && git commit -m "feat: ..."
3. git push origin master
4. Render auto-detects push → rebuilds → deploys (2-5 min)
5. Verify at https://pharmasud-api.onrender.com
```

---

## 11. SECURITY NOTES

- `.env` is gitignored (contains DATABASE_URL, SECRET_KEY)
- `.env.example` contains only placeholders (safe to commit)
- JWT tokens expire after 480 minutes (8 hours)
- CORS allows all origins (`*`) — should be tightened in production
- scanner-debug route requires authentication (added in v6.4)
- Sensitive invoice data hidden from public view

---

## 12. WHAT TO TELL CODEX

If you paste this into Codex, say something like:

> "This is the full technical brief for PharmaSUD, a pharmacy POS system for Sudan. Please analyze the project structure, identify architectural strengths/weaknesses, suggest improvements, and compare our system against competitors (Saydalati/صيدليتي and pyharmacy). Our core differentiators are FEFO tracking, AI vision, audit log, and lowest price. We need to maintain surgical patch discipline and semantic versioning. The project is deployed at pharmasud-api.onrender.com, repo is public."

---

File version: 1.0
Generated: June 2026
For: Codex / OpenAI CLI analysis
