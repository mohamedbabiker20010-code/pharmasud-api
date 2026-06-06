# PharmaSUD - Project Status
## Last Updated: 2026-06-06
## Current Stage: Stage 5 Complete (POS & Sales System)
## Version: 5.0.0
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

### Stage 5 — POS & Sales System (Complete) — **NEW** 🆕
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

---

## 📊 Current Database State

| Table | Count | Status |
|-------|-------|--------|
| pharmacies | 1 | ✅ Active |
| users | 1 | ✅ Admin (D. Abeer) |
| medicines | 3 | ✅ Test data loaded |
| units | 3+ | ✅ Per medicine |
| batches | 4 | ✅ Active (with data) |
| sales | 2 | ✅ Test sales completed |
| sale_items | 3 | ✅ Sale items logged |

---

## 💊 Test Data

### Medicines (3):
| Trade Name | Category | Sale Price | Stock |
|-----------|----------|-----------|-------|
| Milga | فيتامينات ومكملات | 450 ج | 140 strip |
| Fertilex Forte Women | فيتامينات ومكملات | 5,000 ج | 30 box |
| Genuphil | فيتامينات ومكملات | 850 ج | 200 box |

### Batches (4 active):
| Medicine | Batch | Qty | Expiry | Status |
|----------|-------|-----|--------|--------|
| Milga | BATCH-A | 45 | 2026-08-15 | 🟡 تحذير (70 يوم) |
| Milga | BATCH-B | 95 | 2027-03-20 | 🟢 سليم |
| Fertilex | BATCH-D | 30 | 2027-12-01 | 🟢 سليم |
| Genuphil | BATCH-C | 200 | 2027-06-15 | 🟢 سليم |

### Test Sales Completed:
| Invoice | Amount | Method | Customer |
|---------|--------|--------|----------|
| #1 | 27,000 ج | نقدي | أحمد محمد |
| #2 | 2,250 ج | بنكك | - |

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
├── main.py                    (1,380+ lines - routes, HTML templates)
├── database.py                (DB connection, engine)
├── models.py                  (SQLAlchemy models + Pydantic schemas)
├── auth.py                    (JWT, password hashing, auth middleware)
├── medicines.py               (Medicine CRUD, image upload, barcode)
├── batches.py                 (Batch receive, FEFO engine)
├── inventory.py               (Inventory display, expiry reports)
├── settings.py                (Employee management, pharmacy settings)
├── sales.py                   (Sales, FEFO transaction, public invoice)
├── requirements.txt           (Dependencies)
├── .env                       (Environment variables - not in repo)
├── STATUS.md                  (This file)
├── templates/
│   ├── activate.html          (Product key activation page)
│   ├── setup.html             (Admin setup page)
│   ├── login.html             (Login page)
│   ├── dashboard.html         (Admin dashboard)
│   ├── medicines_list.html    (Medicine grid)
│   ├── medicine_form.html     (Add/edit medicine form)
│   ├── batch_receive.html     (Batch receiving page)
│   ├── inventory.html         (Inventory management)
│   ├── settings.html          (System settings)
│   ├── pos.html               (🆕 POS interface with Alpine.js)
│   ├── invoice_view.html      (🆕 Public invoice view)
│   └── sales_history.html     (🆕 Sales history with filters)
└── static/
    └── medicines/             (Uploaded medicine images)
```

---

## 🔗 All API Endpoints

### Public (No Auth Required)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | API status |
| GET | `/ping` | 🔴 Keep Render alive |
| GET | `/health` | Database health check |
| GET | `/api/status` | System activation status |
| GET | `/api/public/invoice/{number}` | 🔴 View invoice (QR scan) |
| POST | `/api/auth/activate` | Activate product key |
| POST | `/api/auth/create-admin` | Create first admin |
| POST | `/api/auth/login` | Login to get JWT |

### Protected (JWT Required)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/auth/me` | Current user info |
| GET | `/api/medicines/` | List all medicines |
| GET | `/api/medicines/{id}` | Medicine details |
| POST | `/api/medicines/` | Add new medicine |
| POST | `/api/medicines/upload/{id}` | Upload medicine image |
| PUT | `/api/medicines/{id}` | Update medicine |
| DELETE | `/api/medicines/{id}` | Delete medicine |
| GET | `/api/medicines/search?q=` | Search by name/barcode |
| GET | `/api/medicines/barcode/{code}` | Search by barcode |
| POST | `/api/batches/receive` | Receive new batch |
| GET | `/api/batches/available/{id}` | Available batches (FEFO) |
| GET | `/api/inventory/` | Full inventory |
| GET | `/api/inventory/expired` | Expired items report |
| GET | `/api/inventory/{id}/batches` | Batch details per medicine |
| GET | `/api/sales/` | 🆕 Sales history (with filters) |
| GET | `/api/sales/{id}` | 🆕 Sale detail |
| POST | `/api/sales/create` | 🆕 Create sale (FEFO + Transaction) |
| GET | `/api/sales/pos/search?q=` | 🆕 POS search |
| GET | `/api/sales/pos/quick-medicines` | 🆕 Top 6 selling medicines |
| GET | `/api/sales/pos/barcode/{code}` | 🆕 POS barcode search |
| GET | `/api/settings/employees` | Employee list |
| POST | `/api/settings/employees` | Add employee |
| DELETE | `/api/settings/employees/{id}` | Delete employee |
| PATCH | `/api/settings/employees/{id}/toggle` | Enable/disable employee |
| POST | `/api/settings/change-password` | Change own password |
| GET | `/api/settings/pharmacy` | Pharmacy settings |
| PUT | `/api/settings/pharmacy` | Update pharmacy settings |

### HTML Pages
| Path | Auth | Description |
|------|------|-------------|
| `/activate` | No | Product key activation |
| `/setup` | No | Admin setup |
| `/login` | No | Login page |
| `/dashboard` | Admin | Admin dashboard |
| `/medicines` | JWT | Medicine list |
| `/medicine-form` | JWT | Add/edit medicine |
| `/batch-receive` | JWT | Receive batch |
| `/inventory` | JWT | Inventory view |
| `/pos` | JWT | 🆕 POS interface |
| `/sales-history` | JWT | 🆕 Sales history |
| `/settings` | JWT | System settings |
| `/invoice/{number}` | **No** | 🆕 Public invoice view |

---

## ⚠️ Known Issues & Notes

1. **Render Free Tier Sleep**: Server goes to sleep after 15 min inactivity.
   - **Fix**: `/ping` endpoint called every 10 min from POS frontend.
   - First request after sleep takes ~30 seconds to wake up.

2. **CORS Open**: Currently set to `*` for development.
   - **TODO**: Restrict to specific domains in production.

3. **No Reports Yet**: Stage 6 (Reports & Analytics) not started.

4. **Test Data**: Test medicines/batches should be cleaned for production launch.

---

## 🎯 Next Steps (Stage 6 — Reports & Analytics)

1. 📈 **Sales Reports** — Daily/weekly/monthly summaries
2. 💰 **Profit Calculation** — (sale_price - purchase_price) × quantity
3. 📊 **Charts with Chart.js** — Sales trends, top medicines
4. 📉 **Low Stock Alerts** — Dashboard notifications
5. 🏆 **Best Selling** — Products and categories
6. 👤 **Employee Performance** — Sales per cashier
7. 💳 **Payment Analysis** — Cash vs digital payments
8. 📥 **Export to Excel** — Downloadable reports

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

*تم التحديث: 6 يونيو 2026 — المرحلة الخامسة مكتملة 🚀*