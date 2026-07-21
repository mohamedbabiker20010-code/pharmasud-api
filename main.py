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
from contextlib import asynccontextmanager
import os
import logging

# Rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from database import get_db, test_connection, get_tables_count
from models import (
    ProductKeyActivate, AdminCreate, UserLogin, 
    TokenResponse, UserResponse, SystemStatus,
    RbacMeResponse,
)
from auth import (
    activate_product_key, create_admin_user, authenticate_user,
    get_current_user, require_admin, check_system_status,
    require_permission,
)
from medicines import router as medicines_router
from batches import router as batches_router
from inventory import router as inventory_router
from settings import router as settings_router
from sales import router as sales_router
from sales import public_router as sales_public_router
from reports import router as reports_router
from alerts import router as alerts_router
from employees import router as employees_router
from audit import router as audit_router
from routers.user_context import router as user_context_router
from startup import initialize_database


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize the production schema before accepting requests."""
    initialize_database()
    yield

app = FastAPI(
    title="PharmaSUD API",
    description="Pharmacy Point of Sale System - Stage 7.1 (New Visual Identity)",
    version="7.1.0",
    lifespan=lifespan,
)


# CORS - Production hardened
# Allow only specific production origins; credentials require explicit origins (no wildcard)
PRODUCTION_ORIGINS = os.getenv("ALLOWED_ORIGINS", "https://pharmasud-api.onrender.com").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=PRODUCTION_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
    expose_headers=["X-Request-ID"],
)

# Security Headers Middleware - Production hardened
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    
    # Prevent clickjacking
    response.headers["X-Frame-Options"] = "DENY"
    
    # Prevent MIME type sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"
    
    # Control referrer information
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    # Restrict browser features
    response.headers["Permissions-Policy"] = "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()"
    
    # Content Security Policy - REPORT ONLY
    # Note: Using reportOnly to monitor violations before enforcement
    csp_directives = [
        "default-src 'self'",
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
        "font-src 'self' https://fonts.gstatic.com data:",
        "img-src 'self' data: blob: https:",
        "connect-src 'self'",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self'",
    ]
    response.headers["Content-Security-Policy-Report-Only"] = "; ".join(csp_directives)
    
    return response

# Rate Limiter - Production hardened
# Key function uses client IP; apply strict limits to auth endpoints
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
app.include_router(alerts_router)
app.include_router(employees_router)
app.include_router(audit_router)
app.include_router(user_context_router)

logger = logging.getLogger(__name__)

# ================================================================
# BARCODE DECODE ENDPOINT (Server-side with ZBar)
# ================================================================
# PUBLIC ENDPOINTS
# ================================================================

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve splash screen (v7.2.0 Cloud Design)."""
    return templates.TemplateResponse("splash.html", {
        "request": request,
        "page_title": "PharmaSUD",
        "css_version": "7.3.0",
    })

@app.get("/api")
async def api_info():
    """API info endpoint."""
    return {
        "status": "PharmaSUD API Running",
        "version": "7.1.0",
        "stage": "Stage 7 - New Visual Identity (Light + Blue)"
    }

@app.get("/health")
async def health():
    """Health check endpoint."""
    try:
        db_ok = test_connection()
        tables = get_tables_count()
        payload = {
            "status": "healthy" if db_ok and tables > 0 else "unhealthy",
            "database": "connected" if db_ok else "disconnected",
            "environment": os.getenv("ENVIRONMENT", "development"),
            "schema_ready": bool(db_ok and tables > 0),
            "version": app.version,
            "timestamp": datetime.now().isoformat()
        }
        if not db_ok or tables <= 0:
            return JSONResponse(status_code=503, content=payload)
        return payload
    except Exception:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "environment": os.getenv("ENVIRONMENT", "development"),
                "schema_ready": False,
                "version": app.version,
            },
        )

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
    return templates.TemplateResponse("login.html", {
        "request": request,
        "page_title": "تسجيل الدخول",
        "css_version": "7.3.0",
    })

# ================================================================
# DASHBOARD PAGES (Stage 6)
# ================================================================

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Main dashboard page."""
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "page_title": "لوحة التحكم",
        "active_page": "dashboard",
        "is_admin": True,
        "css_version": "7.3.0",
    })

@app.get("/medicines", response_class=HTMLResponse)
async def medicines_page(request: Request):
    """Medicines list page."""
    return templates.TemplateResponse("medicines_list.html", {
        "request": request,
        "page_title": "الأدوية",
        "active_page": "medicines",
        "is_admin": True,
        "css_version": "7.3.0",
    })

@app.get("/medicine-form", response_class=HTMLResponse)
async def medicine_form_page(request: Request):
    """Add/Edit medicine form."""
    return templates.TemplateResponse("medicine_form.html", {
        "request": request,
        "page_title": "إضافة دواء",
        "active_page": "medicines",
        "is_admin": True,
        "css_version": "7.3.0",
    })

@app.get("/batch-receive", response_class=HTMLResponse)
async def batch_receive_page(request: Request):
    """Batch receiving page."""
    return templates.TemplateResponse("batch_receive.html", {
        "request": request,
        "page_title": "استلام دفعة",
        "active_page": "batch-receive",
        "is_admin": True,
        "css_version": "7.3.0",
    })

@app.get("/inventory", response_class=HTMLResponse)
async def inventory_page(request: Request):
    """Inventory page."""
    return templates.TemplateResponse("inventory.html", {
        "request": request,
        "page_title": "المخزون",
        "active_page": "inventory",
        "is_admin": True,
        "css_version": "7.3.0",
    })

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Settings page."""
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "page_title": "الإعدادات",
        "active_page": "settings",
        "is_admin": True,
        "css_version": "7.3.0",
    })

@app.get("/pos", response_class=HTMLResponse)
async def pos_page(request: Request):
    """POS page."""
    return templates.TemplateResponse("pos.html", {
        "request": request,
        "page_title": "نقطة البيع",
        "active_page": "pos",
        "is_admin": True,
        "css_version": "7.3.0",
    })

# ═══════════════════════════════════════════════════════════════
# BARCODE DIAGNOSTIC (disabled in production)
# ═══════════════════════════════════════════════════════════════

if os.getenv("ENVIRONMENT", "development") != "production":

    @app.get("/scanner-debug", response_class=HTMLResponse)
    async def scanner_debug_page(request: Request, current_user: dict = Depends(get_current_user)):
        """Barcode scanner diagnostic page (dev only)."""
        return templates.TemplateResponse("scanner_debug.html", {
            "request": request,
            "page_title": "تشفير الباركود",
            "active_page": "pos",
            "is_admin": True,
            "css_version": "7.3.0",
        })

# ═══════════════════════════════════════════════════════════════
# STAGE 7 PAGES
# ═══════════════════════════════════════════════════════════════

@app.get("/alerts", response_class=HTMLResponse)
async def alerts_page(request: Request):
    """Alerts page."""
    return templates.TemplateResponse("alerts.html", {
        "request": request,
        "page_title": "التنبيهات",
        "active_page": "alerts",
        "is_admin": True,
        "css_version": "7.3.0",
    })

@app.get("/employees", response_class=HTMLResponse)
async def employees_page(request: Request):
    """Employees management page."""
    return templates.TemplateResponse("employees.html", {
        "request": request,
        "page_title": "الموظفين",
        "active_page": "employees",
        "is_admin": True,
        "css_version": "7.3.0",
    })

@app.get("/audit-log", response_class=HTMLResponse)
async def audit_log_page(request: Request):
    """Audit log page."""
    return templates.TemplateResponse("audit_log.html", {
        "request": request,
        "page_title": "سجل التدقيق",
        "active_page": "settings",
        "is_admin": True,
        "css_version": "7.3.0",
    })

@app.get("/stocktake", response_class=HTMLResponse)
async def stocktake_page(request: Request):
    """Stocktake / inventory count page."""
    return templates.TemplateResponse("stocktake.html", {
        "request": request,
        "page_title": "الجرد",
        "active_page": "inventory",
        "is_admin": True,
        "css_version": "7.3.0",
    })

# ═══════════════════════════════════════════════════════════════
# REPORTS PAGES (Stage 6)
# ═══════════════════════════════════════════════════════════════

@app.get("/sales-history", response_class=HTMLResponse)
async def sales_history_page(request: Request):
    """Sales history page."""
    return templates.TemplateResponse("sales_history.html", {
        "request": request,
        "page_title": "سجل المبيعات",
        "active_page": "sales-history",
        "is_admin": True,
        "css_version": "7.3.0",
    })

# ================================================================
# REPORTS PAGES (Stage 6)
# ================================================================

@app.get("/reports-sales", response_class=HTMLResponse)
async def reports_sales_page(request: Request):
    """Sales report page."""
    return templates.TemplateResponse("reports_sales.html", {
        "request": request,
        "page_title": "تقارير المبيعات",
        "active_page": "reports-sales",
        "is_admin": True,
        "css_version": "7.3.0",
    })

@app.get("/reports-profits", response_class=HTMLResponse)
async def reports_profits_page(request: Request):
    """Profit report page."""
    return templates.TemplateResponse("reports_profits.html", {
        "request": request,
        "page_title": "تقرير الأرباح",
        "active_page": "reports-profits",
        "is_admin": True,
        "css_version": "7.3.0",
    })

@app.get("/reports-slow-moving", response_class=HTMLResponse)
async def reports_slow_moving_page(request: Request):
    """Slow moving medicines report."""
    return templates.TemplateResponse("reports_slow_moving.html", {
        "request": request,
        "page_title": "الأدوية الراكدة",
        "active_page": "reports-slow-moving",
        "is_admin": True,
        "css_version": "7.3.0",
    })

@app.get("/reports-purchase-forecast", response_class=HTMLResponse)
async def purchase_forecast_page(request: Request):
    """Purchase forecast report."""
    return templates.TemplateResponse("purchase_forecast.html", {
        "request": request,
        "page_title": "توقعات الشراء",
        "active_page": "purchase-forecast",
        "is_admin": True,
        "css_version": "7.3.0",
    })

# ================================================================
# AUTH API
# ================================================================

@app.post("/api/auth/activate", response_model=dict)
@limiter.limit("10/minute")
def api_activate(request: Request, data: ProductKeyActivate, db: Session = Depends(get_db)):
    """Activate product key (Stage 2)."""
    return activate_product_key(data.product_key, db)

@app.post("/api/auth/setup", response_model=dict)
@limiter.limit("5/minute")
def api_setup(request: Request, data: AdminCreate, db: Session = Depends(get_db)):
    """Create admin user (Stage 2)."""
    return create_admin_user(
        pharmacy_id=data.pharmacy_id,
        product_key=data.product_key,
        full_name=data.full_name,
        username=data.username,
        password=data.password,
        confirm_password=data.confirm_password,
        db=db
    )

# Temporary endpoint for validation - creates pharmacy with product key
@app.post("/api/auth/create-pharmacy", response_model=dict)
@limiter.limit("5/minute")
def api_create_pharmacy(request: Request, data: dict, db: Session = Depends(get_db)):
    """Retired validation route; pharmacy provisioning is never public."""
    raise HTTPException(status_code=404, detail="Not found")

# Temporary endpoint for validation - seed demo pharmacy
@app.post("/api/auth/seed-demo", response_model=dict)
@limiter.limit("2/minute")
def api_seed_demo(request: Request, data: dict, db: Session = Depends(get_db)):
    """Retired HTTP demo route; use the confirmed one-time CLI bootstrap."""
    logging.getLogger("pharmasud.audit").warning(
        "rejected_demo_seed_http ip=%s environment=%s",
        request.client.host if request.client else "unknown",
        os.getenv("ENVIRONMENT", "development"),
    )
    raise HTTPException(status_code=404, detail="Not found")

@app.post("/api/auth/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def api_login(request: Request, data: UserLogin, db: Session = Depends(get_db)):
    """User login (Stage 2)."""
    return authenticate_user(data.username, data.password, db)

@app.get("/api/auth/me", response_model=dict)
def api_me(current_user: UserResponse = Depends(get_current_user)):
    """Get current user info."""
    return {
        "id": current_user["user_id"],
        "username": current_user["username"],
        "role": current_user["role"],
        "full_name": current_user.get("full_name", ""),
        "pharmacy_id": current_user["pharmacy_id"],
        "pharmacy_name": current_user.get("pharmacy_name", ""),
        "owner_name": current_user.get("owner_name", "")
    }


@app.get("/api/rbac/me", response_model=RbacMeResponse)
def api_rbac_me(current_user: UserResponse = Depends(get_current_user)):
    """Get current user's RBAC info: role, permissions, etc."""
    return {
        "user_id": current_user["user_id"],
        "username": current_user["username"],
        "role": current_user["role"],
        "role_id": current_user.get("role_id", ""),
        "role_display_name": current_user.get("role_display_name", ""),
        "permissions": current_user.get("permissions", []),
    }

@app.get("/api/system/status", response_model=SystemStatus)
def api_status(db: Session = Depends(get_db)):
    """Get system status."""
    return check_system_status(db)

# ================================================================
# TEST DATA GENERATOR (disabled in production)
# ================================================================

if os.getenv("ENVIRONMENT", "development") != "production":

    @app.get("/api/test/generate-sales-data")
    @limiter.limit("2/minute")
    def generate_test_sales(request: Request, current_user: UserResponse = Depends(require_admin), db: Session = Depends(get_db)):
        """Generate 30 days of test sales data (Admin only, dev only)."""
        from datetime import datetime, timedelta
        import random
        
        today = datetime.now().date()
        pharmacy_id = str(current_user["pharmacy_id"])
        user_id = str(current_user["user_id"])
        
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
