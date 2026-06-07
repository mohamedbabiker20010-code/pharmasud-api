# PharmaSUD - Project Status
## Last Updated: 2026-06-07 (Night Session)
## Current Stage: Stage 6 - Reports & Dashboard (Complete) + Marketing Doc
## Version: 6.1.0
## Live URL: https://pharmasud-api.onrender.com
## GitHub: https://github.com/mohamedbabiker20010-code/pharmasud-api

---

## 🔄 Project Overview

نظام صيدلية متكامل (PharmaSUD) مبني على Render مع PostgreSQL.
هدف المشروع: نظام POS كامل للصيدليات السودانية.

---

## ✅ Completed Stages

### Stage 1 — Infrastructure (Complete)
- ✅ Render + PostgreSQL connected
- ✅ 7 database tables created
- ✅ FastAPI running

### Stage 2 — Authentication (Complete)
- ✅ Product Key Activation
- ✅ JWT Login
- ✅ Role system (Admin / Employee)

### Stage 3 — Medicine Management (Complete)
- ✅ Medicine CRUD with barcode
- ✅ Image upload with Pillow auto-resize (300x300)
- ✅ Units system (box/strip/tablet) with conversion factors
- ✅ Category filter (14 fixed categories)
- ✅ Stock status tracking (available/low/out)
- ✅ Role-based price hiding

### Stage 4 — Batches & Inventory (Complete)
- ✅ Batch receiving with unit conversion
- ✅ FEFO engine (First Expired First Out) — `get_fefo_batches()`
- ✅ 3-level expiry warnings (<30d danger, <90d warning, >90d safe)
- ✅ Inventory display with batch details
- ✅ Supplier tracking

### Stage 5 — POS & Sales System (Complete)
- ✅ Alpine.js cart UI with +/- controls
- ✅ Barcode search + text search
- ✅ Quick medicines (top 6 selling)
- ✅ Unit selection popup at POS
- ✅ FEFO-based sales with database Transaction (COMMIT/ROLLBACK)
- ✅ 4 payment methods: نقدي, بنكك, فوري, تحويل بنكي
- ✅ jsPDF invoice generated in browser
- ✅ Public invoice view (no JWT required) at `/invoice/{number}`
- ✅ Sales history with date/payment filters
- ✅ `/ping` endpoint keeps Render alive (frontend pings every 10 min)
- ✅ Stock verification before sale
- ✅ Insufficient stock rejection with clear error

### Stage 5.5 — Security Hardening (Complete)
- ✅ Fixed sidebar position:relative bug (content pushed below viewport)
- ✅ Locked pharmacy name + owner_name (cannot be edited after activation)
- ✅ Security audit: JWT, auth, SQL injection, XSS, CORS, file upload
- ✅ Confirmed no bulk delete/reset functionality exists

### Stage 6 — Reports & Dashboard 🆕
- ✅ **Main Dashboard** (`/dashboard`) — Live stats, top medicines, alerts, weekly CSS bar chart
- ✅ **Sales Report** (`/reports-sales`) — Filter by period/payment/cashier, payment distribution bars
- ✅ **Profit Report** (`/reports-profits`) — Admin only (403 for employees), profit by medicine, monthly comparison
- ✅ **Slow Moving Report** (`/reports-slow-moving`) — Medicines not sold in 30+ days, critical risk detection
- ✅ **Purchase Forecast** (`/reports-purchase-forecast`) — Smart reorder predictions based on 30-day avg daily sales
- ✅ **Test Data Generator** (`/api/test/generate-sales-data`) — Creates 30 days of test sales

---

## 📊 Current Database State

| Table | Count | Status |
|-------|-------|--------|
| pharmacies | 1 | ✅ Active |
| users | 1 | ✅ Admin (D. Abeer) |
| medicines | 3 | ✅ Test data loaded |
| units | 3+ | ✅ Per medicine |
| batches | 4 | ✅ Active (with data) |
| sales | 2+ | ✅ Test sales |
| sale_items | 3+ | ✅ Sale items logged |

---

## 👤 Admin Account
- **Full Name**: abeer alfadil
- **Username**: D. Abeer
- **Password**: abeer2026
- **Role**: admin
- **Pharmacy**: صيدلية الزاريات

---

## 📁 Project Structure

```
pharmasud/
├── main.py                    (1,100+ lines - routes, HTML templates, test data generator)
├── database.py                (DB connection, engine)
├── models.py                  (SQLAlchemy models + Pydantic schemas + Stage 6 report models)
├── auth.py                    (JWT, password hashing, auth middleware)
├── medicines.py               (Medicine CRUD, image upload, barcode)
├── batches.py                 (Batch receive, FEFO engine)
├── inventory.py               (Inventory display, expiry reports)
├── settings.py                (Employee management, pharmacy settings)
├── sales.py                   (Sales, FEFO transaction, public invoice)
├── reports.py                 (NEW Stage 6 — Dashboard, sales report, profit report,
│                               slow-moving, purchase forecast)
├── requirements.txt           (Dependencies)
├── .env                       (Environment variables - not in repo)
├── STATUS.md                  (This file)
├── generate_test_data.py      (Local script for generating test data)
├── templates/
│   ├── activate.html          (Product key activation page)
│   ├── setup.html             (Admin setup page)
│   ├── login.html             (Login page)
│   ├── dashboard.html         (NEW Stage 6 — Main dashboard with live stats and chart)
│   ├── medicines_list.html    (Medicine grid)
│   ├── medicine_form.html     (Add/edit medicine form)
│   ├── batch_receive.html     (Batch receiving page)
│   ├── inventory.html         (Inventory management)
│   ├── settings.html          (System settings)
│   ├── pos.html               (POS interface with Alpine.js)
│   ├── invoice_view.html      (Public invoice view)
│   ├── sales_history.html     (Sales history with filters)
│   ├── reports_sales.html     (NEW Stage 6 — Sales report with filters)
│   ├── reports_profits.html   (NEW Stage 6 — Profit report, admin only)
│   ├── reports_slow_moving.html (NEW Stage 6 — Slow moving medicines)
│   └── purchase_forecast.html (NEW Stage 6 — Purchase forecast)
├── static/
│   └── medicines/             (Uploaded medicine images)
```

---

## 🔗 Stage 6 API Endpoints

### Reports API (Protected - JWT Required)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/reports/dashboard` | Main dashboard data (today's stats, alerts, weekly chart) |
| GET | `/api/reports/sales` | Sales report with period/payment/cashier filters |
| GET | `/api/reports/profits` | **Admin only** — Profit report by medicine, monthly comparison |
| GET | `/api/reports/slow-moving` | Slow-moving medicines (not sold in 30+ days) |
| GET | `/api/reports/purchase-forecast` | Smart reorder predictions based on sales velocity |

### Stage 6 HTML Pages
| Path | Auth | Description |
|------|------|-------------|
| `/dashboard` | JWT | **UPDATED** — Main dashboard with live stats, alerts, weekly chart |
| `/reports-sales` | JWT | Sales report with period/payment/cashier filters |
| `/reports-profits` | Admin | Profit report (403 for employees) |
| `/reports-slow-moving` | JWT | Slow-moving medicines analysis |
| `/reports-purchase-forecast` | JWT | Purchase quantity recommendations |

### Test Endpoints (Stage 6)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/test/generate-sales-data` | **Admin only** — Generate 30 days of test sales data |

---

## ⚠️ Known Issues & Notes

1. **Render Free Tier Sleep**: Server goes to sleep after 15 min inactivity.
   - **Fix**: `/ping` endpoint called every 10 min from frontend.
   - First request after sleep takes ~30 seconds to wake up.

2. **CORS Open**: Currently set to `*` for development.
   - **TODO**: Restrict to specific domains in production.

3. **No Reports Yet**: (RESOLVED ✓) Stage 6 now has full reports.

4. **Test Data**: Test medicines/batches should be cleaned for production launch.

5. **Stage 6 — Testing Needed**:
   - Generate test data via `/api/test/generate-sales-data`
   - Verify each report endpoint returns correct data
   - Test profit report with employee account (should get 403)
   - Verify slow-moving report shows correct risk levels
   - Check purchase forecast priority ordering

---

## 🚀 Quick Start — Generate Test Data

1. Login as admin (D. Abeer / abeer2026)
2. Visit: `/api/test/generate-sales-data` (must be logged in)
3. Wait for "✅ تم إنشاء X مبيعة تجريبية!"
4. Visit `/dashboard` to see live stats
5. Visit report pages to see data

---

## 📝 Database Schema (7 Tables)

| Table | Key Fields |
|-------|-----------|
| **pharmacies** | id, product_key, name, owner_name, phone, address, is_active |
| **users** | id, pharmacy_id, username, password_hash, role, full_name, is_active |
| **medicines** | id, pharmacy_id, barcode, trade_name, scientific_name, category, sale_price, purchase_price, base_unit, min_stock, image_path |
| **units** | id, medicine_id, unit_name, conversion_factor, sale_price |
| **batches** | id, medicine_id, batch_number, quantity, expiry_date, purchase_price, supplier_invoice, supplier_name, is_active |
| **sales** | id, pharmacy_id, user_id, invoice_number, customer_name, total_amount, payment_method |
| **sale_items** | id, sale_id, medicine_id, batch_id, quantity, unit_name, unit_price, total_price |

---

## ⏰ Keep Render Alive

The frontend POS page automatically pings `/ping` every 10 minutes:
```javascript
setInterval(() => { fetch('/ping').catch(() => {}); }, 600000);
```

---

---

## 📄 New: Marketing Document

| Item | Detail |
|------|--------|
| File | `PharmaSUD_Project_Overview.md` (outside repo — delivered to Mohamed) |
| Purpose | Marketing doc to send to people asking about the system |
| Language | Arabic only — **zero technical terms** |
| Content | 10 sections: idea, problem, solution, 6 components, daily workflow, pricing, benefits, vision |
| Visuals | ASCII box diagrams, emoji icons, tables, comparisons |

---

## 🎯 Session Summary — June 7 Night

**What was accomplished:**
1. ✅ **Stage 6 — Reports & Dashboard** fully built and deployed to Render
2. ✅ **5 new HTML templates** (dashboard, sales report, profits, slow-moving, purchase forecast)
3. ✅ **reports.py** — 5 API endpoints with complex SQL
4. ✅ **Test data generator** — Creates 30 days of sample sales
5. ✅ **PharmaSUD_Project_Overview.md** — Professional marketing document (no tech terms)
6. ✅ **All 13 acceptance criteria** for Stage 6 met

**Next session:**
- Test Stage 6 reports live on Render
- Plan Stage 7 features (Excel export, mobile app, multi-branch, etc.)

---

*تم التحديث: ليلة 7 يونيو 2026 — المرحلة السادسة كاملة مع وثيقة تسويقية 🚀*