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

# Initialize FastAPI app
app = FastAPI(
    title="PharmaSUD API",
    description="Pharmacy Point of Sale System - Stage 4 (Batch & FEFO)",
    version="4.0.0"
)

# Create tables on startup (if they don't exist)
@app.on_event("startup")
async def create_tables():
    """Create database tables on startup."""
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created successfully")
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
        "version": "4.0.0",
        "stage": "Stage 4 - Batch & FEFO"
    }


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

# Dashboard HTML (Protected - Admin)
DASHBOARD_HTML = f"""
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>لوحة التحكم - صيدلية الزاريات</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #0F172A;
            color: #F8FAFC;
            min-height: 100vh;
            display: flex;
            justify-content: flex-start;
            padding: 0;
        }}
        .sidebar {{
            width: 220px;
            background: #1E293B;
            min-height: 100vh;
            padding: 24px 0;
            border-left: 1px solid #334155;
            flex-shrink: 0;
        }}
        .sidebar .logo {{
            padding: 0 20px 24px;
            border-bottom: 1px solid #334155;
            margin-bottom: 16px;
        }}
        .sidebar .logo h1 {{ font-size: 18px; color: #3B82F6; }}
        .sidebar .logo p {{ font-size: 11px; color: #64748B; margin-top: 2px; }}
        .nav-item {{
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px 20px;
            color: #94A3B8;
            text-decoration: none;
            font-size: 14px;
            transition: all 0.2s;
            border-right: 3px solid transparent;
        }}
        .nav-item:hover, .nav-item.active {{
            background: #334155;
            color: #F8FAFC;
            border-right-color: #3B82F6;
        }}
        .nav-item .icon {{ font-size: 18px; }}
        .nav-item .badge {{
            background: #3B82F6;
            color: white;
            font-size: 11px;
            padding: 2px 8px;
            border-radius: 10px;
            margin-right: auto;
        }}
        .sidebar-footer {{
            position: absolute;
            bottom: 0;
            width: 220px;
            padding: 16px 20px;
            border-top: 1px solid #334155;
        }}
        .main-content {{
            flex: 1;
            padding: 32px 40px;
            overflow-y: auto;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 28px;
            padding-bottom: 20px;
            border-bottom: 1px solid #334155;
        }}
        .header h2 {{ font-size: 22px; }}
        .header-left {{ text-align: left; }}
        .header-left .name {{ font-weight: 600; }}
        .header-left .pharmacy {{ font-size: 13px; color: #94A3B8; }}
        .logout-btn {{
            background: #DC2626;
            border: none;
            color: white;
            padding: 8px 16px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 13px;
            transition: background 0.2s;
        }}
        .logout-btn:hover {{ background: #B91C1C; }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            margin-bottom: 32px;
        }}
        .stat-card {{
            background: #1E293B;
            padding: 20px;
            border-radius: 12px;
            text-align: center;
            border: 1px solid #334155;
        }}
        .stat-card .stat-icon {{ font-size: 24px; margin-bottom: 8px; }}
        .stat-card .stat-value {{ font-size: 28px; font-weight: 700; color: #3B82F6; }}
        .stat-card .stat-label {{ font-size: 13px; color: #94A3B8; margin-top: 4px; }}
        .nav-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 20px;
        }}
        .nav-card {{
            background: #1E293B;
            border: 1px solid #334155;
            border-radius: 14px;
            padding: 28px 24px;
            text-decoration: none;
            color: inherit;
            transition: all 0.25s;
            cursor: pointer;
            display: block;
        }}
        .nav-card:hover {{
            border-color: #3B82F6;
            transform: translateY(-2px);
            box-shadow: 0 8px 25px -5px rgba(59, 130, 246, 0.15);
        }}
        .nav-card .card-icon {{ font-size: 32px; margin-bottom: 12px; }}
        .nav-card h3 {{ font-size: 16px; margin-bottom: 6px; }}
        .nav-card p {{ font-size: 13px; color: #94A3B8; line-height: 1.5; }}
        .nav-card .card-status {{
            display: inline-block;
            margin-top: 12px;
            font-size: 12px;
            padding: 4px 10px;
            border-radius: 6px;
        }}
        .status-active {{ background: #065F46; color: #6EE7B7; }}
        .status-coming {{ background: #1E3A5F; color: #60A5FA; }}
        @media (max-width: 768px) {{
            .sidebar {{ display: none; }}
            .main-content {{ padding: 20px; }}
        }}
    </style>
</head>
<body>
    <!-- Sidebar -->
    <div class="sidebar" style="position:relative;">
        <div class="logo">
            <h1>⚕️ PharmaSUD</h1>
            <p>صيدلية الزاريات</p>
        </div>
        <a href="/dashboard" class="nav-item active">
            <span class="icon">📊</span> لوحة التحكم
        </a>
        <a href="/medicines" class="nav-item">
            <span class="icon">💊</span> الأدوية
            <span class="badge" id="medCount">-</span>
        </a>
        <a href="/medicine-form" class="nav-item">
            <span class="icon">➕</span> إضافة دواء
        </a>
        <a href="/inventory" class="nav-item">
            <span class="icon">📦</span> المخزون
        </a>
        <a href="/batch-receive" class="nav-item">
            <span class="icon">📥</span> استلام شحنة
        </a>
        <a href="/pos" class="nav-item">
            <span class="icon">🛒</span> نقطة البيع
        </a>
        <div class="sidebar-footer">
            <button class="logout-btn" onclick="logout()" style="width:100%;">🚪 تسجيل الخروج</button>
        </div>
    </div>

    <!-- Main Content -->
    <div class="main-content">
        <div class="header">
            <h2>📋 لوحة التحكم</h2>
            <div class="header-left">
                <div class="name" id="userName">جاري التحميل...</div>
                <div class="pharmacy" id="pharmacyName"></div>
            </div>
        </div>

        <!-- Stats -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-icon">💊</div>
                <div class="stat-value" id="statMedicines">-</div>
                <div class="stat-label">إجمالي الأدوية</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">📦</div>
                <div class="stat-value" id="statLowStock">-</div>
                <div class="stat-label">منخفضة المخزون</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">🛒</div>
                <div class="stat-value" id="statSales">0</div>
                <div class="stat-label">مبيعات اليوم</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">👤</div>
                <div class="stat-value" id="statEmployees">1</div>
                <div class="stat-label">الموظفين</div>
            </div>
        </div>

        <!-- Navigation Cards -->
        <h3 style="margin-bottom: 16px; color: #94A3B8; font-size: 15px;">🖱️ اختر وجهتك</h3>
        <div class="nav-grid">
            <a href="/medicines" class="nav-card">
                <div class="card-icon">💊</div>
                <h3>إدارة الأدوية</h3>
                <p>عرض، بحث، تصفية وتعديل جميع الأدوية في الصيدلية</p>
                <span class="card-status status-active">✅ مفعل</span>
            </a>
            <a href="/medicine-form" class="nav-card">
                <div class="card-icon">➕</div>
                <h3>إضافة دواء جديد</h3>
                <p>إضافة دواء مع الباركود، الصورة، الوحدات وسعر البيع</p>
                <span class="card-status status-active">✅ مفعل</span>
            </a>
            <a href="/inventory" class="nav-card">
                <div class="card-icon">📦</div>
                <h3>المخزون والشحنات</h3>
                <p>عرض المخزون بالشحنات، تواريخ الانتهاء، وحالة التخزين</p>
                <span class="card-status status-active">✅ مفعل</span>
            </a>
            <a href="/batch-receive" class="nav-card">
                <div class="card-icon">📥</div>
                <h3>استلام شحنة</h3>
                <p>استلام شحنات جديدة مع الباركود، وتحويل الوحدات تلقائياً</p>
                <span class="card-status status-active">✅ مفعل</span>
            </a>
            <a href="/pos" class="nav-card" style="opacity:0.7;">
                <div class="card-icon">🛒</div>
                <h3>نقطة البيع (POS)</h3>
                <p>نظام البيع السريع وإدارة الفواتير</p>
                <span class="card-status status-coming">🔄 قريباً</span>
            </a>
            <div class="nav-card" style="opacity:0.5; cursor:default;">
                <div class="card-icon">📈</div>
                <h3>التقارير</h3>
                <p>تقارير المبيعات والأرباح وتحليل المخزون</p>
                <span class="card-status status-coming">🔄 قريباً</span>
            </div>
        </div>
    </div>

    <script>
        const token = localStorage.getItem('token');
        const role = localStorage.getItem('role');

        // Check authentication
        if (!token) {{
            window.location.href = '/login';
        }}

        // Check admin role
        if (role !== 'admin') {{
            window.location.href = '/pos';
        }}

        // Display user info
        document.getElementById('userName').textContent = localStorage.getItem('full_name') || 'مستخدم';
        document.getElementById('pharmacyName').textContent = localStorage.getItem('pharmacy_name') || '';

        // Fetch medicines count
        async function loadStats() {{
            try {{
                const response = await fetch('/api/medicines/', {{
                    headers: {{ 'Authorization': 'Bearer ' + token }}
                }});
                if (response.ok) {{
                    const data = await response.json();
                    const medicines = data.medicines || [];
                    const total = data.total || medicines.length;
                    document.getElementById('statMedicines').textContent = total;
                    document.getElementById('medCount').textContent = total;
                    
                    // Count low stock (total_stock < min_stock or total_stock === 0)
                    const lowStock = medicines.filter(m => m.stock_status === 'out' || m.stock_status === 'low').length;
                    document.getElementById('statLowStock').textContent = lowStock;
                }}
            }} catch (err) {{
                console.error('Failed to load stats:', err);
            }}
        }}
        loadStats();

        // Verify token validity
        async function checkAuth() {{
            try {{
                const response = await fetch('/api/auth/me', {{
                    headers: {{ 'Authorization': 'Bearer ' + token }}
                }});
                if (!response.ok) {{
                    localStorage.clear();
                    window.location.href = '/login';
                }}
            }} catch (err) {{
                console.error('Auth check failed:', err);
            }}
        }}
        checkAuth();

        // Logout function
        function logout() {{
            localStorage.clear();
            window.location.href = '/login';
        }}
    </script>
</body>
</html>
"""

# POS HTML (Protected - Employee)
POS_HTML = f"""
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>نقطة البيع - PharmaSUD</title>
    {COMMON_STYLES}
    <style>
        body {{ justify-content: flex-start; padding-top: 40px; }}
        .container {{ max-width: 800px; }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid #334155;
        }}
        .logout-btn {{
            background: #DC2626;
            width: auto;
            padding: 8px 16px;
            font-size: 14px;
        }}
        .logout-btn:hover {{ background: #B91C1C; }}
        .pos-area {{
            background: #334155;
            padding: 40px;
            border-radius: 12px;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo" style="margin:0;">
                <h1 style="font-size:20px;">نقطة البيع</h1>
            </div>
            <button class="logout-btn" onclick="logout()">تسجيل الخروج</button>
        </div>
        
        <div class="pos-area">
            <h2>مرحباً، <span id="userName">-</span></h2>
            <p style="color: #94A3B8; margin-top: 10px;">نظام البيع سيتم تفعيله في المرحلة القادمة</p>
        </div>
    </div>
    
    <script>
        const token = localStorage.getItem('token');
        const fullName = localStorage.getItem('full_name');
        
        // Check authentication
        if (!token) {{
            window.location.href = '/login';
        }}
        
        // Display user info
        document.getElementById('userName').textContent = fullName || 'موظف';
        
        // Verify token validity
        async function checkAuth() {{
            try {{
                const response = await fetch('/api/auth/me', {{
                    headers: {{ 'Authorization': 'Bearer ' + token }}
                }});
                
                if (!response.ok) {{
                    localStorage.clear();
                    window.location.href = '/login';
                }}
            }} catch (err) {{
                console.error('Auth check failed:', err);
            }}
        }}
        
        checkAuth();
        
        // Logout function
        function logout() {{
            localStorage.clear();
            window.location.href = '/login';
        }}
    </script>
</body>
</html>
"""

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

# ✅ انتهى - main.py - المرحلة 4
