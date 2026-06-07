"""
PharmaSUD - Main FastAPI Application
Stage 3 - Version 3.0.0

Main entry point with health checks, dashboard, authentication, and medicines management.
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
from reports import router as reports_router  # المرحلة 6: التقارير

# Initialize FastAPI app
app = FastAPI(
    title="PharmaSUD API",
    description="Pharmacy Point of Sale System - Stage 5 (POS & Sales)",
    version="5.0.0"
)

# Create tables on startup (if they don't exist)
@app.on_event("startup")
async def create_tables():
    """Create database tables on startup."""
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created successfully")
        # Add supplier_name column if not exists (Stage 4)
        try:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE batches ADD COLUMN IF NOT EXISTS supplier_name VARCHAR(100)"))
                conn.commit()
                print("✅ Added supplier_name column to batches table")
        except Exception as e:
            print(f"⚠️ Could not add supplier_name column: {e}")
        
        # Add unit_name column to sale_items if not exists (Stage 5)
        try:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE sale_items ADD COLUMN IF NOT EXISTS unit_name VARCHAR(20)"))
                conn.commit()
                print("✅ Added unit_name column to sale_items table")
        except Exception as e:
            print(f"⚠️ Could not add unit_name column: {e}")
    except Exception as e:
        print(f"⚠️ Could not create tables: {e}")

# Templates configuration
templates = Jinja2Templates(directory="templates")

# Static files configuration
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include medicines router
app.include_router(medicines_router)

# Include batches router (Stage 4)
app.include_router(batches_router)

# Include inventory router (Stage 4)
app.include_router(inventory_router)

# Include settings router (Stage 4.5)
app.include_router(settings_router)

# Include sales router (Stage 5)
app.include_router(sales_router)

# Include public router (Stage 5 - no JWT required)
app.include_router(sales_public_router)

# Include reports router (Stage 6 - التقارير)
app.include_router(reports_router)

# CORS configuration - restrict in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict to specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════
# Public Routes (No Authentication Required)
# ═══════════════════════════════════════════════════════════

@app.get("/")
def root():
    """Root endpoint - API status."""
    return {
        "status": "PharmaSUD API Running",
        "version": "5.0.0",
        "stage": "Stage 5 - POS & Sales"
    }


@app.get("/ping")
def ping():
    """Ping endpoint - keeps Render free tier alive.
    Called every 10 minutes from the frontend to prevent sleep."""
    return {"status": "alive", "timestamp": datetime.now().isoformat()}


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Health check - verifies database connectivity."""
    try:
        db.execute(text("SELECT 1"))
        tables_count = get_tables_count()
        
        return {
            "status": "healthy",
            "database": "connected",
            "tables": tables_count,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "database": "disconnected",
                "error": str(e)
            }
        )


@app.get("/api/status")
def system_status(db: Session = Depends(get_db)):
    """Check system activation status."""
    return check_system_status(db)


# ═══════════════════════════════════════════════════════════
# Authentication Routes
# ═══════════════════════════════════════════════════════════

@app.post("/api/auth/activate", response_model=TokenResponse)
def activate_product(data: ProductKeyActivate, db: Session = Depends(get_db)):
    """Activate product key for first-time setup."""
    result = activate_product_key(data.product_key, db)
    return result


@app.post("/api/auth/create-admin", response_model=TokenResponse)
def create_admin(data: AdminCreate, db: Session = Depends(get_db)):
    """Create first admin user after product activation."""
    try:
        result = create_admin_user(
            pharmacy_id=data.pharmacy_id,
            full_name=data.full_name,
            username=data.username,
            password=data.password,
            confirm_password=data.confirm_password,
            db=db
        )
        return result
    except Exception as e:
        import traceback
        return {
            "success": False,
            "message": f"Error: {str(e)}",
            "traceback": traceback.format_exc()
        }


@app.post("/api/auth/login", response_model=TokenResponse)
def login(data: UserLogin, db: Session = Depends(get_db)):
    """Authenticate user and return JWT token."""
    result = authenticate_user(data.username, data.password, db)
    return result


@app.get("/api/auth/me", response_model=UserResponse)
def get_me(current_user: dict = Depends(get_current_user)):
    """Get current authenticated user info."""
    return UserResponse(
        user_id=current_user["user_id"],
        username=current_user["username"],
        role=current_user["role"],
        full_name=current_user.get("full_name"),
        pharmacy_name=current_user.get("pharmacy_name")
    )


# ═══════════════════════════════════════════════════════════
# Protected Routes (Require Authentication)
# ═══════════════════════════════════════════════════════════

@app.get("/api/admin/dashboard")
def admin_dashboard(current_user: dict = Depends(require_admin)):
    """Admin-only dashboard data."""
    return {
        "message": "Welcome to Admin Dashboard",
        "user": current_user["full_name"],
        "role": current_user["role"]
    }


@app.get("/api/employee/pos")
def employee_pos(current_user: dict = Depends(get_current_user)):
    """Employee POS access."""
    return {
        "message": "POS System",
        "user": current_user["full_name"],
        "role": current_user["role"]
    }


@app.get("/api/test-db")
def test_database(db: Session = Depends(get_db)):
    """Detailed database test - counts rows in each table."""
    try:
        tables = [
            "pharmacies", "users", "medicines", "units",
            "batches", "sales", "sale_items"
        ]
        
        results = {}
        for table in tables:
            try:
                result = db.execute(text(f"SELECT COUNT(*) FROM {table}"))
                results[table] = result.scalar()
            except Exception as e:
                results[table] = f"not found: {str(e)}"
        
        return {
            "status": "success",
            "message": "All 7 tables verified",
            "counts": results
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": str(e)}
)


# ═══════════════════════════════════════════════════════════
# HTML Page Routes
# ═══════════════════════════════════════════════════════════

@app.get("/activate", response_class=HTMLResponse)
def activate_page():
    """Product Key Activation Page."""
    return HTMLResponse(content=ACTIVATE_HTML)


@app.get("/setup", response_class=HTMLResponse)
def setup_page():
    """Admin Setup Page (first time only)."""
    return HTMLResponse(content=SETUP_HTML)


@app.get("/login", response_class=HTMLResponse)
def login_page():
    """Login Page."""
    return HTMLResponse(content=LOGIN_HTML)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page():
    """Main Dashboard Page (requires auth)."""
    return HTMLResponse(content=DASHBOARD_HTML)


@app.get("/pos", response_class=HTMLResponse)
def pos_page():
    """POS Page (requires auth)."""
    return HTMLResponse(content=POS_HTML)


@app.get("/sales-history", response_class=HTMLResponse)
def sales_history_page():
    """Sales History Page (requires auth)."""
    return HTMLResponse(content=SALES_HISTORY_HTML)


@app.get("/invoice/{invoice_number}", response_class=HTMLResponse)
def invoice_view_page(invoice_number: int):
    """Public Invoice View Page (no JWT required).
    Used when scanning QR code on receipt."""
    return HTMLResponse(content=INVOICE_VIEW_HTML)


# ═══════════════════════════════════════════════════════════
# Stage 3: Medicine Management Routes
# ═══════════════════════════════════════════════════════════

@app.get("/medicines", response_class=HTMLResponse)
def medicines_list_page():
    """Medicines List Page."""
    return HTMLResponse(content=MEDICINES_LIST_HTML)


@app.get("/medicine-form", response_class=HTMLResponse)
def medicine_form_page():
    """Medicine Add/Edit Form Page."""
    return HTMLResponse(content=MEDICINE_FORM_HTML)


@app.get("/batch-receive", response_class=HTMLResponse)
def batch_receive_page():
    """Batch Receive Page (Stage 4)."""
    return HTMLResponse(content=BATCH_RECEIVE_HTML)


@app.get("/inventory", response_class=HTMLResponse)
def inventory_page():
    """Inventory Management Page (Stage 4)."""
    return HTMLResponse(content=INVENTORY_HTML)


@app.get("/settings", response_class=HTMLResponse)
def settings_page():
    """Settings & Admin Page (Stage 4.5)."""
    return HTMLResponse(content=SETTINGS_HTML)


# ═══════════════════════════════════════════════════════════
# المرحلة 6: صفحات التقارير
# ═══════════════════════════════════════════════════════════

@app.get("/reports-sales", response_class=HTMLResponse)
def reports_sales_page():
    """Sales Report Page."""
    return HTMLResponse(content=REPORTS_SALES_HTML)


@app.get("/reports-profits", response_class=HTMLResponse)
def reports_profits_page():
    """Profit Report Page (Admin only check done in JS)."""
    return HTMLResponse(content=REPORTS_PROFITS_HTML)


@app.get("/reports-slow-moving", response_class=HTMLResponse)
def reports_slow_moving_page():
    """Slow Moving Medicines Report Page."""
    return HTMLResponse(content=REPORTS_SLOW_MOVING_HTML)


@app.get("/reports-purchase-forecast", response_class=HTMLResponse)
def reports_purchase_forecast_page():
    """Purchase Forecast Page."""
    return HTMLResponse(content=PURCHASE_FORECAST_HTML)


# ═══════════════════════════════════════════════════════════
# HTML Templates
# ═══════════════════════════════════════════════════════════

# Common CSS Styles
COMMON_STYLES = """
<style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        background: #0F172A;
        color: #F8FAFC;
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 20px;
    }
    .container {
        background: #1E293B;
        border-radius: 16px;
        padding: 40px;
        width: 100%;
        max-width: 420px;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
    }
    .logo {
        text-align: center;
        margin-bottom: 30px;
    }
    .logo-icon {
        width: 60px;
        height: 60px;
        background: linear-gradient(135deg, #3B82F6, #1D4ED8);
        border-radius: 12px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 15px;
    }
    .logo-icon svg {
        width: 32px;
        height: 32px;
    }
    .logo h1 {
        font-size: 24px;
        font-weight: 700;
        margin-bottom: 5px;
    }
    .logo p {
        color: #94A3B8;
        font-size: 14px;
    }
    .form-group {
        margin-bottom: 20px;
    }
    label {
        display: block;
        margin-bottom: 8px;
        font-size: 14px;
        font-weight: 500;
        color: #E2E8F0;
    }
    input {
        width: 100%;
        padding: 12px 16px;
        background: #334155;
        border: 2px solid #475569;
        border-radius: 8px;
        color: #F8FAFC;
        font-size: 15px;
        transition: border-color 0.2s;
    }
    input:focus {
        outline: none;
        border-color: #3B82F6;
    }
    input::placeholder {
        color: #64748B;
    }
    button {
        width: 100%;
        padding: 14px;
        background: #3B82F6;
        color: white;
        border: none;
        border-radius: 8px;
        font-size: 16px;
        font-weight: 600;
        cursor: pointer;
        transition: background 0.2s;
    }
    button:hover {
        background: #2563EB;
    }
    button:disabled {
        background: #475569;
        cursor: not-allowed;
    }
    .error {
        background: #DC2626;
        color: white;
        padding: 12px;
        border-radius: 8px;
        margin-bottom: 20px;
        font-size: 14px;
        display: none;
    }
    .error.show { display: block; }
    .success {
        background: #059669;
        color: white;
        padding: 12px;
        border-radius: 8px;
        margin-bottom: 20px;
        font-size: 14px;
        display: none;
    }
    .success.show { display: block; }
    .link {
        text-align: center;
        margin-top: 20px;
        font-size: 14px;
        color: #94A3B8;
    }
    .link a {
        color: #3B82F6;
        text-decoration: none;
    }
    .link a:hover {
        text-decoration: underline;
    }
    .loading {
        display: none;
        text-align: center;
        padding: 20px;
    }
    .loading.show { display: block; }
    .spinner {
        border: 3px solid #334155;
        border-top: 3px solid #3B82F6;
        border-radius: 50%;
        width: 40px;
        height: 40px;
        animation: spin 1s linear infinite;
        margin: 0 auto 15px;
    }
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
</style>
"""

# Activate Page HTML
ACTIVATE_HTML = f"""
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تفعيل المنتج - PharmaSUD</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="container">
        <div class="logo">
            <div class="logo-icon">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                        d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z">
                    </path>
                </svg>
            </div>
            <h1>PharmaSUD</h1>
            <p>تفعيل النظام</p>
        </div>
        
        <div class="error" id="error"></div>
        <div class="success" id="success"></div>
        
        <form id="activateForm">
            <div class="form-group">
                <label for="productKey">مفتاح المنتج</label>
                <input type="text" id="productKey" name="product_key" 
                    placeholder="PHARM-SDN-2026-XXXX-XXXX" required>
            </div>
            
            <button type="submit" id="submitBtn">تفعيل النظام</button>
        </form>
        
        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p>جاري التحقق...</p>
        </div>
    </div>
    
    <script>
        const form = document.getElementById('activateForm');
        const error = document.getElementById('error');
        const success = document.getElementById('success');
        const loading = document.getElementById('loading');
        const submitBtn = document.getElementById('submitBtn');
        
        form.addEventListener('submit', async (e) => {{
            e.preventDefault();
            
            const productKey = document.getElementById('productKey').value.trim();
            
            // Reset messages
            error.classList.remove('show');
            success.classList.remove('show');
            
            // Show loading
            form.style.display = 'none';
            loading.classList.add('show');
            
            try {{
                const response = await fetch('/api/auth/activate', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ product_key: productKey }})
                }});
                
                const data = await response.json();
                
                if (data.success) {{
                    success.textContent = 'تم التفعيل بنجاح! جاري التحويل...';
                    success.classList.add('show');
                    
                    // Save pharmacy ID
                    localStorage.setItem('pharmacy_id', data.pharmacy_id);
                    
                    // Redirect to setup
                    setTimeout(() => {{
                        window.location.href = '/setup';
                    }}, 1500);
                }} else {{
                    error.textContent = data.message || 'المفتاح غير صحيح أو مُفعّل مسبقاً';
                    error.classList.add('show');
                    form.style.display = 'block';
                    loading.classList.remove('show');
                }}
            }} catch (err) {{
                error.textContent = 'حدث خطأ في الاتصال بالخادم';
                error.classList.add('show');
                form.style.display = 'block';
                loading.classList.remove('show');
            }}
        }});
        
        // Check system status on load
        window.addEventListener('DOMContentLoaded', async () => {{
            try {{
                const response = await fetch('/api/status');
                const data = await response.json();
                
                if (data.status === 'ready' || data.status === 'needs_setup') {{
                    // System already activated
                    window.location.href = '/login';
                }}
            }} catch (err) {{
                console.error('Status check failed:', err);
            }}
        }});
    </script>
</body>
</html>
"""

# Setup Page HTML (Admin Creation)
SETUP_HTML = f"""
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>إنشاء حساب المدير - PharmaSUD</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="container">
        <div class="logo">
            <div class="logo-icon">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                        d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z">
                    </path>
                </svg>
            </div>
            <h1>إنشاء حساب المدير</h1>
            <p>خطوة واحدة فقط لإكمال الإعداد</p>
        </div>
        
        <div class="error" id="error"></div>
        <div class="success" id="success"></div>
        
        <form id="setupForm">
            <div class="form-group">
                <label for="fullName">الاسم الكامل</label>
                <input type="text" id="fullName" name="full_name" 
                    placeholder="محمد أحمد" required>
            </div>
            
            <div class="form-group">
                <label for="username">اسم المستخدم</label>
                <input type="text" id="username" name="username" 
                    placeholder="admin" required>
            </div>
            
            <div class="form-group">
                <label for="password">كلمة المرور</label>
                <input type="password" id="password" name="password" 
                    placeholder="6 أحرف على الأقل" required minlength="6">
            </div>
            
            <div class="form-group">
                <label for="confirmPassword">تأكيد كلمة المرور</label>
                <input type="password" id="confirmPassword" name="confirm_password" 
                    placeholder="أعد إدخال كلمة المرور" required>
            </div>
            
            <button type="submit" id="submitBtn">إنشاء الحساب</button>
        </form>
        
        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p>جاري إنشاء الحساب...</p>
        </div>
    </div>
    
    <script>
        const form = document.getElementById('setupForm');
        const error = document.getElementById('error');
        const success = document.getElementById('success');
        const loading = document.getElementById('loading');
        
        form.addEventListener('submit', async (e) => {{
            e.preventDefault();
            
            const fullName = document.getElementById('fullName').value.trim();
            const username = document.getElementById('username').value.trim();
            const password = document.getElementById('password').value;
            const confirmPassword = document.getElementById('confirmPassword').value;
            
            // Reset messages
            error.classList.remove('show');
            success.classList.remove('show');
            
            // Validation
            if (password !== confirmPassword) {{
                error.textContent = 'كلمتا المرور غير متطابقتين';
                error.classList.add('show');
                return;
            }}
            
            if (password.length < 6) {{
                error.textContent = 'كلمة المرور يجب أن تكون 6 أحرف على الأقل';
                error.classList.add('show');
                return;
            }}
            
            // Get pharmacy ID from localStorage
            const pharmacyId = localStorage.getItem('pharmacy_id');
            if (!pharmacyId) {{
                error.textContent = 'جلسة غير صالحة، يرجى البدء من جديد';
                error.classList.add('show');
                return;
            }}
            
            // Show loading
            form.style.display = 'none';
            loading.classList.add('show');
            
            try {{
                const response = await fetch('/api/auth/create-admin', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{
                        pharmacy_id: pharmacyId,
                        full_name: fullName,
                        username: username,
                        password: password,
                        confirm_password: confirmPassword
                    }})
                }});
                
                const data = await response.json();
                
                if (data.success) {{
                    success.textContent = 'تم إنشاء الحساب بنجاح! جاري التحويل...';
                    success.classList.add('show');
                    
                    // Clear pharmacy ID
                    localStorage.removeItem('pharmacy_id');
                    
                    // Redirect to login
                    setTimeout(() => {{
                        window.location.href = '/login';
                    }}, 1500);
                }} else {{
                    error.textContent = data.message || 'حدث خطأ أثناء إنشاء الحساب';
                    error.classList.add('show');
                    form.style.display = 'block';
                    loading.classList.remove('show');
                }}
            }} catch (err) {{
                error.textContent = 'حدث خطأ في الاتصال بالخادم';
                error.classList.add('show');
                form.style.display = 'block';
                loading.classList.remove('show');
            }}
        }});
    </script>
</body>
</html>
"""

# Login Page HTML
LOGIN_HTML = f"""
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تسجيل الدخول - صيدلية الزاريات</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="container">
        <div class="logo">
            <div class="logo-icon">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                        d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1">
                    </path>
                </svg>
            </div>
            <h1>صيدلية الزاريات</h1>
            <p>تسجيل الدخول</p>
        </div>
        
        <div class="error" id="error"></div>
        <div class="success" id="success"></div>
        
        <form id="loginForm">
            <div class="form-group">
                <label for="username">اسم المستخدم</label>
                <input type="text" id="username" name="username" 
                    placeholder="أدخل اسم المستخدم" required>
            </div>
            
            <div class="form-group">
                <label for="password">كلمة المرور</label>
                <input type="password" id="password" name="password" 
                    placeholder="أدخل كلمة المرور" required>
            </div>
            
            <button type="submit" id="submitBtn">دخول</button>
        </form>
        
        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p>جاري التحقق...</p>
        </div>
    </div>
    
    <script>
        const form = document.getElementById('loginForm');
        const error = document.getElementById('error');
        const success = document.getElementById('success');
        const loading = document.getElementById('loading');
        
        form.addEventListener('submit', async (e) => {{
            e.preventDefault();
            
            const username = document.getElementById('username').value.trim();
            const password = document.getElementById('password').value;
            
            // Reset messages
            error.classList.remove('show');
            success.classList.remove('show');
            
            // Show loading
            form.style.display = 'none';
            loading.classList.add('show');
            
            try {{
                const response = await fetch('/api/auth/login', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ username, password }})
                }});
                
                const data = await response.json();
                
                if (data.success) {{
                    success.textContent = 'تم تسجيل الدخول بنجاح!';
                    success.classList.add('show');
                    
                    // Save token
                    localStorage.setItem('token', data.token);
                    localStorage.setItem('role', data.role);
                    localStorage.setItem('full_name', data.full_name);
                    localStorage.setItem('pharmacy_name', data.pharmacy_name);
                    
                    // Redirect based on role
                    setTimeout(() => {{
                        if (data.role === 'admin') {{
                            window.location.href = '/dashboard';
                        }} else {{
                            window.location.href = '/pos';
                        }}
                    }}, 1000);
                }} else {{
                    error.textContent = data.message || 'اسم المستخدم أو كلمة المرور غير صحيحة';
                    error.classList.add('show');
                    form.style.display = 'block';
                    loading.classList.remove('show');
                }}
            }} catch (err) {{
                error.textContent = 'حدث خطأ في الاتصال بالخادم';
                error.classList.add('show');
                form.style.display = 'block';
                loading.classList.remove('show');
            }}
        }});
        
        // Check if already logged in
        window.addEventListener('DOMContentLoaded', () => {{
            const token = localStorage.getItem('token');
            if (token) {{
                // Verify token is still valid
                fetch('/api/auth/me', {{
                    headers: {{ 'Authorization': 'Bearer ' + token }}
                }})
                .then(response => {{
                    if (response.ok) {{
                        // Already logged in, redirect
                        const role = localStorage.getItem('role');
                        if (role === 'admin') {{
                            window.location.href = '/dashboard';
                        }} else {{
                            window.location.href = '/pos';
                        }}
                    }}
                }})
                .catch(err => {{
                    // Token invalid, stay on login
                    localStorage.clear();
                }});
            }}
        }});
    </script>
</body>
</html>
"""

# Dashboard HTML (Stage 6 - loaded from file)
DASHBOARD_HTML = None  # Will be loaded at the bottom of the file

# POS HTML (Protected)
# Now loaded from templates/pos.html (Stage 5)
POS_HTML = None  # Will be loaded at the bottom of the file

# Sales History HTML (Protected)
SALES_HISTORY_HTML = None  # Will be loaded at the bottom of the file

# Invoice View HTML (Public)
INVOICE_VIEW_HTML = None  # Will be loaded at the bottom of the file

# Stage 6: Report HTML templates
REPORTS_SALES_HTML = None
REPORTS_PROFITS_HTML = None
REPORTS_SLOW_MOVING_HTML = None
PURCHASE_FORECAST_HTML = None

# ✅ انتهى - main.py - المرحلة 3

# Stage 3: Import HTML templates from files
# Read the templates from the templates directory
import os

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")

# Load Stage 3 templates
try:
    with open(os.path.join(TEMPLATE_DIR, "medicines_list.html"), "r", encoding="utf-8") as f:
        MEDICINES_LIST_HTML = f.read()
except FileNotFoundError:
    MEDICINES_LIST_HTML = "<h1>Medicines List - Template not found</h1>"

try:
    with open(os.path.join(TEMPLATE_DIR, "medicine_form.html"), "r", encoding="utf-8") as f:
        MEDICINE_FORM_HTML = f.read()
except FileNotFoundError:
    MEDICINE_FORM_HTML = "<h1>Medicine Form - Template not found</h1>"

# Stage 4: Load batch receive and inventory templates
try:
    with open(os.path.join(TEMPLATE_DIR, "batch_receive.html"), "r", encoding="utf-8") as f:
        BATCH_RECEIVE_HTML = f.read()
except FileNotFoundError:
    BATCH_RECEIVE_HTML = "<h1>Batch Receive - Template not found</h1>"

try:
    with open(os.path.join(TEMPLATE_DIR, "inventory.html"), "r", encoding="utf-8") as f:
        INVENTORY_HTML = f.read()
except FileNotFoundError:
    INVENTORY_HTML = "<h1>Inventory - Template not found</h1>"

# Stage 4.5: Load settings template
try:
    with open(os.path.join(TEMPLATE_DIR, "settings.html"), "r", encoding="utf-8") as f:
        SETTINGS_HTML = f.read()
except FileNotFoundError:
    SETTINGS_HTML = "<h1>Settings - Template not found</h1>"

# Stage 5: Load POS, sales history, and invoice view templates
try:
    with open(os.path.join(TEMPLATE_DIR, "pos.html"), "r", encoding="utf-8") as f:
        POS_HTML = f.read()
except FileNotFoundError:
    POS_HTML = "<h1>POS - Template not found</h1>"

try:
    with open(os.path.join(TEMPLATE_DIR, "sales_history.html"), "r", encoding="utf-8") as f:
        SALES_HISTORY_HTML = f.read()
except FileNotFoundError:
    SALES_HISTORY_HTML = "<h1>Sales History - Template not found</h1>"

try:
    with open(os.path.join(TEMPLATE_DIR, "invoice_view.html"), "r", encoding="utf-8") as f:
        INVOICE_VIEW_HTML = f.read()
except FileNotFoundError:
    INVOICE_VIEW_HTML = "<h1>Invoice View - Template not found</h1>"

# Stage 6: Load report templates
try:
    with open(os.path.join(TEMPLATE_DIR, "dashboard.html"), "r", encoding="utf-8") as f:
        DASHBOARD_HTML = f.read()
except FileNotFoundError:
    print("⚠️ dashboard.html not found - using fallback")

try:
    with open(os.path.join(TEMPLATE_DIR, "reports_sales.html"), "r", encoding="utf-8") as f:
        REPORTS_SALES_HTML = f.read()
except FileNotFoundError:
    REPORTS_SALES_HTML = "<h1>Sales Report - Template not found</h1>"

try:
    with open(os.path.join(TEMPLATE_DIR, "reports_profits.html"), "r", encoding="utf-8") as f:
        REPORTS_PROFITS_HTML = f.read()
except FileNotFoundError:
    REPORTS_PROFITS_HTML = "<h1>Profit Report - Template not found</h1>"

try:
    with open(os.path.join(TEMPLATE_DIR, "reports_slow_moving.html"), "r", encoding="utf-8") as f:
        REPORTS_SLOW_MOVING_HTML = f.read()
except FileNotFoundError:
    REPORTS_SLOW_MOVING_HTML = "<h1>Slow Moving - Template not found</h1>"

try:
    with open(os.path.join(TEMPLATE_DIR, "purchase_forecast.html"), "r", encoding="utf-8") as f:
        PURCHASE_FORECAST_HTML = f.read()
except FileNotFoundError:
    PURCHASE_FORECAST_HTML = "<h1>Purchase Forecast - Template not found</h1>"

# ✅ انتهى - main.py - المرحلة 6

# ═══════════════════════════════════════════════════════════
# المرحلة 6: Endpoint تجريبي لتوليد بيانات المبيعات
# ═══════════════════════════════════════════════════════════

@app.get("/api/test/generate-sales-data")
def generate_test_sales(current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """Generate 30 days of test sales data for report testing."""
    import random
    from datetime import date, timedelta, datetime
    
    pharmacy_id = current_user["pharmacy_id"]
    user_id = current_user["user_id"]
    
    # Get medicines with batches
    meds = db.execute(text("""
        SELECT m.id, m.trade_name, m.sale_price, m.base_unit
        FROM medicines m
        WHERE m.pharmacy_id = :pid
    """), {"pid": pharmacy_id}).fetchall()
    
    if not meds:
        return {"error": "No medicines found"}
    
    # Get active batches
    batches = db.execute(text("""
        SELECT b.id, b.medicine_id, b.quantity, b.purchase_price, b.expiry_date
        FROM batches b
        JOIN medicines m ON b.medicine_id = m.id
        WHERE m.pharmacy_id = :pid AND b.is_active = true AND b.quantity > 0 AND b.expiry_date > NOW()
    """), {"pid": pharmacy_id}).fetchall()
    
    if not batches:
        return {"error": "No active batches"}
    
    med_batches = {}
    for b in batches:
        mid = str(b[1])
        if mid not in med_batches:
            med_batches[mid] = []
        med_batches[mid].append({
            "id": str(b[0]), "qty": b[2], "purchase_price": float(b[3] or 0), "expiry": b[4]
        })
    
    med_map = {}
    for m in meds:
        med_map[str(m[0])] = {"name": m[1], "sale_price": float(m[3] or m[2] or 0) if m[3] else float(m[2] or 0), "base_unit": m[4] or "شريط"}
    
    today = date.today()
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
    if batches:
        import uuid as uuid_mod
        target_batch = batches[0]
        near_expiry = today + timedelta(days=20)
        db.execute(text("UPDATE batches SET expiry_date = :exp WHERE id = :bid"), 
                   {"exp": near_expiry, "bid": target_batch[0]})
    
    db.commit()
    return {"success": True, "sales_created": sales_created, "message": f"✅ تم إنشاء {sales_created} مبيعة تجريبية! راجع الداشبورد."}
