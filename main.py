"""
PharmaSUD - Main FastAPI Application
Stage 3 - Version 6.5.0
"""
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
import os
import base64
import io
import logging

from database import engine, get_db, test_connection, get_tables_count, Base
from models import (
    ProductKeyActivate, AdminCreate, UserLogin, 
    TokenResponse, UserResponse, SystemStatus,
)
from auth import (
    activate_product_key, create_admin_user, authenticate_user,
    get_current_user, require_admin, check_system_status
)
from medicines import router as medicines_router
from batches import router as batches_router
from inventory import router as inventory_router
from settings import router as settings_router
from sales import router as sales_router
from sales import public_router as sales_public_router
from reports import router as reports_router

app = FastAPI(
    title="PharmaSUD API",
    description="Pharmacy Point of Sale System - Stage 6.5 (Server Barcode Decoder)",
    version="6.5.0"
)

# Create tables on startup (if they don't exist)
@app.on_event("startup")
async def create_tables():
    """Create database tables on startup."""
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created successfully")
        try:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE batches ADD COLUMN IF NOT EXISTS supplier_name VARCHAR(100)"))
                conn.commit()
                print("✅ Added supplier_name column to batches table")
        except Exception as e:
            print(f"⚠️ Could not add supplier_name column: {e}")
        
        try:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE sale_items ADD COLUMN IF NOT EXISTS unit_name VARCHAR(20)"))
                conn.commit()
                print("✅ Added unit_name column to sale_items table")
        except Exception as e:
            print(f"⚠️ Could not add unit_name column: {e}")
        
        try:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE medicines ALTER COLUMN image_path TYPE TEXT"))
                conn.commit()
                print("✅ Changed image_path column to TEXT for Base64 storage")
        except Exception as e:
            print(f"⚠️ Could not change image_path column: {e}")
    except Exception as e:
        print(f"⚠️ Could not create tables: {e}")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Templates
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Routers
app.include_router(medicines_router)
app.include_router(batches_router)
app.include_router(inventory_router)
app.include_router(settings_router)
app.include_router(sales_router)
app.include_router(sales_public_router)
app.include_router(reports_router)

logger = logging.getLogger(__name__)

# ================================================================
# BARCODE DECODE ENDPOINT (Server-side with ZBar)
# ================================================================
# PUBLIC ENDPOINTS
# ================================================================

@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "status": "PharmaSUD API Running",
        "version": "6.5.0",
        "stage": "Stage 6.5 - Permissions & Storage"
    }

@app.get("/health")
async def health():
    """Health check endpoint."""
    try:
        db_ok = test_connection()
        tables = get_tables_count()
        return {
            "status": "healthy",
            "database": "connected" if db_ok else "disconnected",
            "tables": tables,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

@app.get("/ping")
async def ping():
    """Keep Render alive (no DB call)."""
    return {"pong": True, "time": datetime.now().isoformat()}

# ================================================================
# AUTH PAGES
# ================================================================

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page."""
    return templates.TemplateResponse("login.html", {"request": request})

# ================================================================
# DASHBOARD PAGES (Stage 6)
# ================================================================

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Main dashboard page."""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/medicines", response_class=HTMLResponse)
async def medicines_page(request: Request):
    """Medicines list page."""
    return templates.TemplateResponse("medicines_list.html", {"request": request})

@app.get("/medicine-form", response_class=HTMLResponse)
async def medicine_form_page(request: Request):
    """Add/Edit medicine form."""
    return templates.TemplateResponse("medicine_form.html", {"request": request})

@app.get("/batch-receive", response_class=HTMLResponse)
async def batch_receive_page(request: Request):
    """Batch receiving page."""
    return templates.TemplateResponse("batch_receive.html", {"request": request})

@app.get("/inventory", response_class=HTMLResponse)
async def inventory_page(request: Request):
    """Inventory page."""
    return templates.TemplateResponse("inventory.html", {"request": request})

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Settings page."""
    return templates.TemplateResponse("settings.html", {"request": request})

@app.get("/pos", response_class=HTMLResponse)
async def pos_page(request: Request):
    """POS page."""
    return templates.TemplateResponse("pos.html", {"request": request})

# ═══════════════════════════════════════════════════════════════
# BARCODE DIAGNOSTIC (no JWT — temporary test page)
# ═══════════════════════════════════════════════════════════════

@app.get("/scanner-debug", response_class=HTMLResponse)
async def scanner_debug_page(request: Request):
    """Barcode scanner diagnostic page (no auth required)."""
    return templates.TemplateResponse("scanner_debug.html", {"request": request})

# ═══════════════════════════════════════════════════════════════
# REPORTS PAGES (Stage 6)
# ═══════════════════════════════════════════════════════════════

@app.get("/sales-history", response_class=HTMLResponse)
async def sales_history_page(request: Request):
    """Sales history page."""
    return templates.TemplateResponse("sales_history.html", {"request": request})

# ================================================================
# REPORTS PAGES (Stage 6)
# ================================================================

@app.get("/reports-sales", response_class=HTMLResponse)
async def reports_sales_page(request: Request):
    """Sales report page."""
    return templates.TemplateResponse("reports_sales.html", {"request": request})

@app.get("/reports-profits", response_class=HTMLResponse)
async def reports_profits_page(request: Request):
    """Profit report page."""
    return templates.TemplateResponse("reports_profits.html", {"request": request})

@app.get("/reports-slow-moving", response_class=HTMLResponse)
async def reports_slow_moving_page(request: Request):
    """Slow moving medicines report."""
    return templates.TemplateResponse("reports_slow_moving.html", {"request": request})

@app.get("/reports-purchase-forecast", response_class=HTMLResponse)
async def purchase_forecast_page(request: Request):
    """Purchase forecast report."""
    return templates.TemplateResponse("purchase_forecast.html", {"request": request})

# ================================================================
# AUTH API
# ================================================================

@app.post("/api/auth/activate", response_model=dict)
def api_activate(data: ProductKeyActivate, db: Session = Depends(get_db)):
    """Activate product key (Stage 2)."""
    return activate_product_key(db, data)

@app.post("/api/auth/setup", response_model=dict)
def api_setup(data: AdminCreate, db: Session = Depends(get_db)):
    """Create admin user (Stage 2)."""
    return create_admin_user(db, data)

@app.post("/api/auth/login", response_model=TokenResponse)
def api_login(data: UserLogin, db: Session = Depends(get_db)):
    """User login (Stage 2)."""
    return authenticate_user(data.username, data.password, db)

@app.get("/api/auth/me", response_model=dict)
def api_me(current_user: UserResponse = Depends(get_current_user)):
    """Get current user info."""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "role": current_user.role,
        "full_name": current_user.full_name,
        "pharmacy_id": current_user.pharmacy_id,
        "pharmacy_name": current_user.pharmacy_name,
        "owner_name": current_user.owner_name
    }

@app.get("/api/system/status", response_model=SystemStatus)
def api_status(db: Session = Depends(get_db)):
    """Get system status."""
    return check_system_status(db)

# ================================================================
# TEST DATA GENERATOR (Stage 6)
# ================================================================

@app.get("/api/test/generate-sales-data")
def generate_test_sales(current_user: UserResponse = Depends(require_admin), db: Session = Depends(get_db)):
    """Generate 30 days of test sales data (Admin only)."""
    from datetime import datetime, timedelta
    import random
    
    today = datetime.now().date()
    pharmacy_id = str(current_user.pharmacy_id)
    user_id = str(current_user.id)
    
    # Get all medicines with their batches
    meds = db.execute(text("""
        SELECT m.id, m.trade_name, m.sale_price, m.base_unit, m.min_stock,
               m.purchase_price, m.scientific_name
        FROM medicines m WHERE m.pharmacy_id = :pid
    """), {"pid": pharmacy_id}).fetchall()
    
    if not meds:
        return {"success": False, "message": "لا توجد أدوية. أضف أدوية أولاً."}
    
    med_map = {}
    for m in meds:
        med_map[str(m[0])] = {
            "sale_price": float(m[2]),
            "base_unit": m[3],
            "min_stock": float(m[4]) if m[4] else 0,
            "purchase_price": float(m[5]) if m[5] else 0,
            "scientific_name": m[6]
        }
    
    # Get batches
    all_batches = db.execute(text("""
        SELECT b.id, b.medicine_id, b.quantity, b.expiry_date
        FROM batches b
        JOIN medicines m ON m.id = b.medicine_id
        WHERE m.pharmacy_id = :pid AND b.is_active = true
    """), {"pid": pharmacy_id}).fetchall()
    
    # Group batches by medicine
    med_batches = {}
    for b in all_batches:
        mid = str(b[1])
        if mid not in med_batches:
            med_batches[mid] = []
        med_batches[mid].append({"id": str(b[0]), "qty": float(b[2]), "exp": b[3]})
    
    sales_created = 0
    
    for day_offset in range(30, 0, -1):
        sale_date = today - timedelta(days=day_offset)
        daily_count = random.randint(3, 8)
        
        for _ in range(daily_count):
            available = [m for m in med_map if m in med_batches]
            if not available:
                continue
            med_id = random.choice(available)
            mdata = med_map[med_id]
            batch_list = med_batches[med_id]
            if not batch_list:
                continue
            batch = random.choice(batch_list)
            
            pm = random.choices(["cash", "bankak", "fory", "transfer"], weights=[60, 25, 10, 5], k=1)[0]
            qty = random.randint(1, 5)
            unit_price = mdata["sale_price"]
            total_price = round(qty * unit_price, 2)
            
            sale_time = datetime.combine(sale_date, datetime.min.time()) + timedelta(
                hours=random.randint(8, 20), minutes=random.randint(0, 59))
            
            customer = random.choice(["أحمد", "محمد", "خالد", "فاطمة", "مريم", None, None])
            
            result = db.execute(text("""
                INSERT INTO sales (pharmacy_id, user_id, customer_name, total_amount, payment_method, created_at)
                VALUES (:pid, :uid, :customer, :amount, :pm, :created)
                RETURNING id, invoice_number
            """), {"pid": pharmacy_id, "uid": user_id, "customer": customer, "amount": total_price, "pm": pm, "created": sale_time}).first()
            
            sale_id = str(result[0])
            
            db.execute(text("""
                INSERT INTO sale_items (sale_id, medicine_id, batch_id, quantity, unit_price, total_price, unit_name)
                VALUES (:sid, :mid, :bid, :qty, :price, :total, :unit)
            """), {"sid": sale_id, "mid": med_id, "bid": batch["id"], "qty": qty, "price": unit_price, "total": total_price, "unit": mdata["base_unit"]})
            
            sales_created += 1
    
    # Set one batch to expire soon
    if all_batches:
        import uuid as uuid_mod
        target_batch = all_batches[0]
        near_expiry = today + timedelta(days=20)
        db.execute(text("UPDATE batches SET expiry_date = :exp WHERE id = :bid"), 
                   {"exp": near_expiry, "bid": target_batch[0]})
    
    db.commit()
    return {"success": True, "sales_created": sales_created, "message": f"✅ تم إنشاء {sales_created} مبيعة تجريبية! راجع الداشبورد."}