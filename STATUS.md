# PharmaSUD - Project Status
## Last Updated: 2026-06-10 (Session 5 - Deploy Fix)
## Current Stage: Stage 6.5 - Permissions & Storage
## Version: 6.3.3
## Branch: master (Render watches this branch, NOT main!)
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

## 🔴 Critical Fixes — June 8, 2026

### Bug #1: Sidebar Navigation Error ("Not Found")
- **Problem**: Clicking "الأدوية" in sidebar returned `{"detail":"Not Found"}`
- **Root Cause**: Sidebar link pointed to `/medicines-list` but actual route is `/medicines`
- **Fix**: Updated 3 templates (dashboard.html, reports_sales.html, reports_profits.html) — changed link from `/medicines-list` to `/medicines`
- **Status**: ✅ Fixed & Deployed

### Bug #2: Price Mismatch (Medicine vs Unit)
- **Problem**: Fertilex Forte Women showed price 1,200 in POS but 5,000 in medicines list
- **Root Cause**: Editing medicine price didn't sync to base unit price
- **Fix**: 
  1. Added auto-sync logic in `medicines.py` — updating medicine price now updates unit price automatically
  2. Ran DB fix to correct existing data (Fertilex unit price: 1,200 → 5,000)
- **Status**: ✅ Fixed & Deployed

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
├── medicines.py               (Medicine CRUD, image upload, barcode, PRICE SYNC FIX)
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
│   ├── dashboard.html         (NEW Stage 6 — Main dashboard, FIXED sidebar link)
│   ├── medicines_list.html    (Medicine grid)
│   ├── medicine_form.html     (Add/edit medicine form)
│   ├── batch_receive.html     (Batch receiving page)
│   ├── inventory.html         (Inventory management)
│   ├── settings.html          (System settings)
│   ├── pos.html               (POS interface with Alpine.js)
│   ├── invoice_view.html      (Public invoice view)
│   ├── sales_history.html     (Sales history with filters)
│   ├── reports_sales.html     (NEW Stage 6 — Sales report, FIXED sidebar link)
│   ├── reports_profits.html   (NEW Stage 6 — Profit report, FIXED sidebar link)
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

3. **Test Data**: Test medicines/batches should be cleaned for production launch.

4. **Stage 6 — Testing Needed**: 
   - ✅ Unit price sync bug fixed
   - ✅ Existing data fixed for Fertilex Forte Women
   - ✅ Sidebar navigation fixed
   
5. **Test Data Generator** (`/api/test/generate-sales-data`): Returns 500 error on Render (works locally). Needs batch processing to avoid memory limits.

6. **System Under Real-World Testing**: Handed to friend (pharmacy owner) for 5-day trial starting June 8, 2026.

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

## 📄 New: Marketing Document

| Item | Detail |
|------|--------|
| File | `PharmaSUD_Project_Overview.md` (outside repo — delivered to Mohamed) |
| Purpose | Marketing doc to send to people asking about the system |
| Language | Arabic only — **zero technical terms** |
| Content | 10 sections: idea, problem, solution, 6 components, daily workflow, pricing, benefits, vision |
| Visuals | ASCII box diagrams, emoji icons, tables, comparisons |

---

## 🎯 Session Summary — June 8, 2026

**What was accomplished:**
1. 🐛 **CRITICAL FIX**: Fixed sidebar navigation ("الأدوية" button was broken)
2. 🐛 **CRITICAL FIX**: Fixed price sync bug (medicine price now auto-syncs to unit price)
3. 🗄️ **DB Fix**: Corrected Fertilex Forte Women unit price (1,200 → 5,000)
4. 🚀 **Deployed**: All fixes pushed to GitHub & Render
5. 🧪 **Handover**: System delivered to friend for 5-day real-world testing

**Current Status:**
- ✅ All critical bugs fixed
- ✅ System stable and functional
- 🔄 Under real-world testing (5 days, ongoing)

---

## 🎯 Session Summary — June 10, 2026

**Changes based on friend's feedback:**

1. ✅ **Removed Units section** from Add Medicine form — simplified to just Base Unit selection
2. ✅ **Added visibility control** — "إضافة دواء جديد" button now only shows for Admins (`x-show="isAdmin"`)
3. ✅ **Fixed Settings sidebar** — الإعدادات link now hidden from employees in dashboard
4. ✅ **Protected Settings page** — non-admin users redirected to dashboard
5. ✅ **Protected Medicine Form** — non-admin users redirected to dashboard
6. ✅ **Improved price fields** — سعر البيع and سعر الشراء now stacked (not side-by-side) with clear labels and helper text
7. ✅ **Dashboard isAdmin** — added isAdmin tracking to dashboard Alpine.js app
8. ✅ **Delete button** — already had `x-show="isAdmin"` (confirmed working)

**Deployed:** All changes pushed to GitHub & Render

---

## 🎯 Session Summary — June 10, 2026 (Session 4 — Barcode Scanner Complete Rewrite)

**Barcode Scanner — Changed from continuous scan to snapshot-based (v6.3.2):**

1. 🐛 **Root Cause**: `html5-qrcode@2.3.8` continuous video scanning doesn't work reliably on mobile browsers. The library's `start()` method relies on native `BarcodeDetector` API which has inconsistent support.
2. 🔄 **New Approach: Snapshot (تصوير لحظي)**:
   - Camera opens in a `<video>` element (raw `getUserMedia()`)
   - User sees live preview with a green alignment frame
   - User taps **"📷 تصوير الباركود"** button to capture
   - Frame drawn to `<canvas>`, then decoded using:
     - **Primary**: Native `BarcodeDetector` API (Chrome, Safari 16.4+) — supports 13 formats
     - **Fallback**: `Html5Qrcode.decodeFromImage()` as backup
     - **2nd attempt**: Inverted colors (white bars on dark background)
   - Also: **Manual entry field** at the bottom of the scanner modal
3. ✅ **Better UX**: White flash effect on capture, clear error messages, manual barcode input always available
4. ✅ **Works on**: iPhone Safari, Android Chrome, all modern browsers

**Deployed:** GitHub + Render (v6.3.2)

---

## 🎯 Session Summary — June 10, 2026 (Session 5 — Deploy Fix v6.3.3)

**CRITICAL BUILD FIX — Render was failing to start:**

1. 🐛 **Root Cause**: `models.py` line 574 used `Column(Text)` but `Text` was **not imported** from SQLAlchemy. The import line only had `text` (lowercase — SQL function), not `Text` (uppercase — type class).
2. ✅ **Fix**: Added `Text` to the SQLAlchemy import statement in `models.py` line 10.
3. 🚀 **Pushed**: Both `main` and `master` branches updated on GitHub.
4. 🔄 **Deploy**: Deploy hook triggered on Render — waiting for build to complete.

---

## 🎯 Next Steps

**Barcode Scanner Real-World Fix:**

1. 🐛 **CRITICAL: Library didn't scan barcodes at all** — `html5-qrcode@2.3.8` defaults to QR codes only. Added `formatsToSupport` with 11 barcode formats: EAN-13, EAN-8, UPC-A, UPC-E, CODE-128, CODE-39, CODE-93, ITF, CODABAR, RSS-14, RSS-EXPANDED.
2. 🐛 **CRITICAL: Alpine.js x-show hiding the scanner** — `x-show="showScanner"` sets `display: none` on the modal. When `startScanner()` ran immediately, the `#reader` div had zero dimensions. Fixed with `setTimeout(300ms)` to let Alpine render first.
3. ✅ **Better error messages** — Clear instructions for iPhone (Safari only, Chrome doesn't support camera on iOS) vs Android (Chrome works).
4. ✅ **Added hint text** — "وجّهي الكاميرا نحو الباركود ليتم قراءته تلقائياً" under the scanner.

**Deployed:** All changes pushed to GitHub & Render (v6.3.1)

---

## 🎯 Next Steps

**Changes based on friend's feedback:**

1. ✅ **Fixed Admin check bug** — was using `localStorage.getItem('user')` which doesn't exist (login stores role in `localStorage.getItem('role')`). Fixed in 4 templates.
2. ✅ **Fixed template corruption** — line number prefixes (`1| 2| 3|...`) were rendering on the page due to corrupted file. Full cleanup.
3. ✅ **Permission System (Admin vs Employee)** — defined clear permission model:

| Feature | Employee | Admin | 
|---------|----------|-------|
| POS (بيع) | ✅ | ✅ |
| Medicines list | ✅ (no purchase price) | ✅ |
| Inventory | ✅ | ✅ |
| Sales history | ✅ | ✅ |
| Sales report | ✅ | ✅ |
| Dashboard (today revenue/profit) | ✅ | ✅ |
| Slow moving report | ✅ | ✅ |
| Add/Edit medicine | 🔒 | ✅ |
| Batch receive (استلام دفعة) | 🔒 | ✅ |
| Settings (الموظفين) | 🔒 | ✅ |
| Profit report | 🔒 | ✅ |
| Purchase forecast | 🔒 | ✅ |

4. ✅ **Base64 Image Storage** — images now stored in database as Base64 (persists across deploys). `image_path` column changed from VARCHAR(255) to TEXT.
5. ✅ **Sidebar updated** — batch-receive, reports-profits, purchase-forecast hidden from employees
6. ✅ **Page redirects** — batch-receive, purchase-forecast, settings redirect non-admin to dashboard

**Deployed:** All changes pushed to GitHub & Render (v6.3.0)

---

**Next Steps:**
- Wait for friend's testing feedback  
- Plan Stage 7: Excel export, mobile app, multi-branch, or offline mode
- Security hardening for production

*تم التحديث: 10 يونيو 2026 — نظام الصلاحيات + تخزين الصور 🚀*
