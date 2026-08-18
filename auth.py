"""
PharmaSUD - Authentication Module
Stage 2 - Version 2.0.0

Handles:
- JWT Authentication
- User Authorization
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError, jwt
import bcrypt
import os
from dotenv import load_dotenv

from database import get_db
from models import Pharmacy, User, Role, Permission

# Load environment variables
load_dotenv()

# Security Configuration
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("⚠️ SECRET_KEY غير موجود! حدده في متغيرات البيئة (Environment Variables) على Render")

# Validate SECRET_KEY strength (production hardening)
if SECRET_KEY in ("change-this-to-a-random-secret-key", "your-secret-key-here", "secret", "test"):
    raise ValueError("⚠️ SECRET_KEY ضعيف أو افتراضي! غيّره إلى مفتاح عشوائي قوي (openssl rand -hex 32)")

if len(SECRET_KEY) < 32:
    raise ValueError("⚠️ SECRET_KEY قصير جداً! يجب أن يكون 32 حرفاً على الأقل (openssl rand -hex 32)")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

# HTTP Bearer for token authentication
security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against its hash."""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    # bcrypt has a 72-byte limit
    password_bytes = password.encode('utf-8')[:72]
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode('utf-8')


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get current authenticated user from JWT token.
    Used as dependency for protected endpoints.
    """
    token = credentials.credentials
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="الرمز غير صالح أو منتهي الصلاحية",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = decode_token(token)
    if payload is None:
        raise credentials_exception
    
    user_id: str = payload.get("user_id")
    pharmacy_id: str = payload.get("pharmacy_id")
    role: str = payload.get("role")
    
    if user_id is None or pharmacy_id is None:
        raise credentials_exception
    
    # Verify user and authoritative tenant linkage in the database.
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is disabled",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if str(user.pharmacy_id) != str(pharmacy_id):
        raise credentials_exception
    pharmacy = db.query(Pharmacy).filter(Pharmacy.id == user.pharmacy_id).first()
    if pharmacy is None or not pharmacy.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is disabled",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get effective permissions from role
    permissions = []
    role_display_name = ""
    role_id_str = ""
    
    if user.role_id:
        role_obj = db.query(Role).filter(Role.id == user.role_id).first()
        if role_obj:
            role_display_name = role_obj.display_name
            role_id_str = str(role_obj.id)
            # Get permissions from role
            perms = db.query(Permission).join(Role.permissions).filter(Role.id == role_obj.id).all()
            permissions = [p.code for p in perms]
    
    # Fallback for legacy users without role_id (map admin/employee to basic permissions)
    if not permissions:
        if user.role == "admin":
            permissions = [
                "medicines.view", "medicines.create", "medicines.edit", "medicines.delete",
                "inventory.view", "inventory.receive", "inventory.adjust", "inventory.view_expired",
                "sales.pos", "sales.view_history", "sales.void",
                "reports.sales", "reports.slow_moving", "reports.forecast",
                "profit.view",
                "employees.view", "employees.manage",
                "settings.view", "settings.manage",
                "purchase.view",
            ]
            role_display_name = "المدير"
        elif user.role == "employee":
            permissions = [
                "medicines.view",
                "inventory.view", "inventory.view_expired",
                "sales.pos",
            ]
            role_display_name = "صيدلي"
        role_id_str = str(user.role_id) if user.role_id else ""
    
    return {
        "user_id": str(user.id),
        "pharmacy_id": str(user.pharmacy_id),
        "role": user.role,  # Authoritative legacy role string
        "role_id": role_id_str,  # New RBAC role UUID
        "role_display_name": role_display_name,
        "permissions": permissions,
        "username": user.username,
        "full_name": user.full_name,
    }


def require_permission(permission_code: str):
    """
    FastAPI dependency factory for permission-based access control.
    
    Usage:
        @app.post("/api/medicines/", dependencies=[Depends(require_permission("medicines.create"))])
        def create_medicine(...):
            ...
    """
    async def checker(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        user_permissions = current_user.get("permissions", [])
        if permission_code not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"ليس لديك صلاحية لهذا الإجراء: {permission_code}"
            )
        return current_user
    return checker


async def require_admin(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Require admin role for protected endpoints.
    Raises 403 if user is not admin.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="هذه الصفحة مخصصة للمدير فقط"
        )
    return current_user


# ═══════════════════════════════════════════════════════════
# Login Functions
# ═══════════════════════════════════════════════════════════

def authenticate_user(username: str, password: str, db: Session) -> Dict[str, Any]:
    """
    Authenticate user with username and password.
    
    Returns:
        Dict with success status, token and user info or error message
    """
    # Find user by username
    user = db.query(User).filter(User.username == username).first()
    
    if not user:
        return {
            "success": False,
            "message": "اسم المستخدم أو كلمة المرور غير صحيحة"
        }
    
    # Check if user is active
    if not user.is_active:
        return {
            "success": False,
            "message": "هذا الحساب معطّل - تواصل مع المدير"
        }
    
    # Verify password
    if not verify_password(password, user.password_hash):
        return {
            "success": False,
            "message": "اسم المستخدم أو كلمة المرور غير صحيحة"
        }
    
    # Get pharmacy info
    pharmacy = db.query(Pharmacy).filter(Pharmacy.id == user.pharmacy_id).first()
    if pharmacy is None or not pharmacy.is_active:
        return {
            "success": False,
            "message": "اسم المستخدم أو كلمة المرور غير صحيحة"
        }
    pharmacy_name = pharmacy.name
    
    # Create JWT token
    token_data = {
        "user_id": str(user.id),
        "pharmacy_id": str(user.pharmacy_id),
        "role": user.role,
        "username": user.username
    }
    
    access_token = create_access_token(token_data)
    
    return {
        "success": True,
        "token": access_token,
        "role": user.role,
        "full_name": user.full_name,
        "pharmacy_name": pharmacy_name
    }


# ═══════════════════════════════════════════════════════════
# Check System Status Functions
# ═══════════════════════════════════════════════════════════

def check_system_status(db: Session) -> Dict[str, Any]:
    """
    Check if system needs activation, setup, or login.
    
    Returns:
        Dict with current system state
    """
    # Check if any pharmacy is activated
    activated_pharmacy = db.query(Pharmacy).filter(Pharmacy.is_active == True).first()
    
    if not activated_pharmacy:
        # No activated pharmacy - need activation
        return {
            "status": "needs_activation",
            "message": "النظام يحتاج لتفعيل مفتاح المنتج"
        }
    
    # Check if activated pharmacy has admin
    admin_exists = db.query(User).filter(
        User.pharmacy_id == activated_pharmacy.id,
        User.role == "admin"
    ).first()
    
    if not admin_exists:
        # Activated but no admin - need setup
        return {
            "status": "needs_setup",
            "message": "يجب إنشاء حساب المدير"
        }
    
    # System ready - need login
    return {
        "status": "ready",
        "message": "النظام جاهز - تسجيل الدخول"
    }


# ✅ انتهى - auth.py - المرحلة 2
