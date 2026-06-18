"""
PharmaSUD - Authentication Module
Stage 2 - Version 2.0.0

Handles:
- Product Key Activation
- Admin Creation
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
import uuid
from dotenv import load_dotenv

from database import get_db
from models import Pharmacy, User

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
    
    # Verify user exists in database
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    
    return {
        "user_id": user_id,
        "pharmacy_id": pharmacy_id,
        "role": role,
        "username": user.username,
        "full_name": user.full_name
    }


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
# Product Key Activation Functions
# ═══════════════════════════════════════════════════════════

def activate_product_key(product_key: str, db: Session) -> Dict[str, Any]:
    """
    Activate a product key for first-time setup.
    
    Returns:
        Dict with success status, pharmacy info or error message
    """
    # Find pharmacy by product key
    pharmacy = db.query(Pharmacy).filter(Pharmacy.product_key == product_key).first()
    
    if not pharmacy:
        return {
            "success": False,
            "message": "المفتاح غير صحيح"
        }
    
    # Check if already activated
    if pharmacy.is_active:
        return {
            "success": False,
            "message": "المفتاح مُفعّل مسبقاً"
        }
    
    # Check if pharmacy already has an admin
    existing_admin = db.query(User).filter(
        User.pharmacy_id == pharmacy.id,
        User.role == "admin"
    ).first()
    
    if existing_admin:
        return {
            "success": False,
            "message": "الصيدلية لديها حساب مسؤول بالفعل"
        }
    
    # Activate the pharmacy
    pharmacy.is_active = True
    pharmacy.activated_at = datetime.utcnow()
    db.commit()
    
    return {
        "success": True,
        "pharmacy_id": str(pharmacy.id),
        "pharmacy_name": pharmacy.name
    }


# ═══════════════════════════════════════════════════════════
# Admin Creation Functions
# ═══════════════════════════════════════════════════════════

def create_admin_user(
    pharmacy_id: str,
    full_name: str,
    username: str,
    password: str,
    confirm_password: str,
    db: Session
) -> Dict[str, Any]:
    """
    Create the first admin user for a pharmacy.
    
    Returns:
        Dict with success status and message
    """
    # Validate passwords match
    if password != confirm_password:
        return {
            "success": False,
            "message": "كلمتا المرور غير متطابقتين"
        }
    
    # Validate password length
    if len(password) < 6:
        return {
            "success": False,
            "message": "كلمة المرور يجب أن تكون 6 أحرف على الأقل"
        }
    
    # Check if pharmacy exists and is activated
    from uuid import UUID as UUID_Class
    try:
        pharmacy_uuid = UUID_Class(pharmacy_id)
    except ValueError:
        return {
            "success": False,
            "message": "معرف الصيدلية غير صالح"
        }
    
    pharmacy = db.query(Pharmacy).filter(Pharmacy.id == pharmacy_uuid).first()
    if not pharmacy:
        return {
            "success": False,
            "message": "الصيدلية غير موجودة"
        }
    
    if not pharmacy.is_active:
        return {
            "success": False,
            "message": "يجب تفعيل مفتاح المنتج أولاً"
        }
    
    # Check if admin already exists
    existing_admin = db.query(User).filter(
        User.pharmacy_id == pharmacy_uuid,
        User.role == "admin"
    ).first()
    
    if existing_admin:
        return {
            "success": False,
            "message": "يوجد مسؤول بالفعل لهذه الصيدلية"
        }
    
    # Check if username is taken
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        return {
            "success": False,
            "message": "اسم المستخدم مستخدم مسبقاً"
        }
    
    # Create admin user
    from uuid import uuid4
    
    new_admin = User(
        id=uuid4(),
        pharmacy_id=pharmacy_uuid,
        username=username,
        full_name=full_name,
        password_hash=get_password_hash(password),
        role="admin",
        is_active=True
    )
    
    db.add(new_admin)
    db.commit()
    
    return {
        "success": True,
        "message": "تم إنشاء حساب المدير بنجاح"
    }


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
    pharmacy_name = pharmacy.name if pharmacy else "Unknown"
    
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
            "pharmacy_id": str(activated_pharmacy.id),
            "message": "يجب إنشاء حساب المدير"
        }
    
    # System ready - need login
    return {
        "status": "ready",
        "message": "النظام جاهز - تسجيل الدخول"
    }


# ════════════════════════════════════════════════════════════
# Pharmacy Provisioning Helpers
# ════════════════════════════════════════════════════════════

def apply_default_settings(db: Session, pharmacy_id: str) -> None:
    """
    Apply default settings to a newly created pharmacy.
    Lightweight defaults - no settings registry table.
    """
    pharmacy = db.query(Pharmacy).filter(
        Pharmacy.id == uuid.UUID(pharmacy_id)
    ).first()

    if not pharmacy:
        return

    # Default settings are handled via template defaults
    # No settings registry table - values provided by template context
    # This function exists for future extension
    pass


def create_new_pharmacy(
    db: Session,
    *,
    product_key: str,
    admin_username: str,
    admin_password: str,
    admin_full_name: str,
    pharmacy_name: str,
    owner_name: str,
    pharmacy_type: str = 'customer',
    phone: str = '',
    address: str = ''
) -> dict:
    """
    Single-call pharmacy provisioning.

    Responsibilities:
    1. Validate product_key format (no type derivation)
    2. Create pharmacy record (type from parameter)
    3. Create admin user
    4. Apply defaults
    5. Return pharmacy info + admin credentials

    Does NOT:
    - Seed demo data (use seed_demo_pharmacy separately)
    - Configure RBAC/permissions
    - Start cron jobs
    - Set up monitoring

    Args:
        product_key: Product activation key (must be valid and unused)
        admin_username: Admin username
        admin_password: Admin password (plaintext, will be hashed)
        admin_full_name: Admin full name
        pharmacy_name: Pharmacy name
        owner_name: Owner name
        pharmacy_type: 'development', 'demo', or 'customer' (default: 'customer')
        phone: Optional phone number
        address: Optional address

    Returns:
        Dict with pharmacy_id, admin credentials, type

    Raises:
        ValueError: If product key invalid, already used, or type invalid
    """
    # Validate pharmacy type
    if pharmacy_type not in ('development', 'demo', 'customer'):
        raise ValueError(f"Invalid pharmacy_type: {pharmacy_type}. Must be 'development', 'demo', or 'customer'")

    # Activate product key (validates key, checks not already used)
    activation_result = activate_product_key(product_key, db)
    if not activation_result.get('success'):
        raise ValueError(activation_result.get('message', 'Invalid product key'))

    pharmacy_id = activation_result['pharmacy_id']

    # Update pharmacy with provided details and type
    pharmacy = db.query(Pharmacy).filter(
        Pharmacy.id == uuid.UUID(pharmacy_id)
    ).first()

    if not pharmacy:
        raise ValueError("Pharmacy not found after activation")

    pharmacy.name = pharmacy_name
    pharmacy.owner_name = owner_name
    pharmacy.phone = phone
    pharmacy.address = address
    pharmacy.type = pharmacy_type  # Set type from parameter, NOT from key prefix

    db.commit()

    # Create admin user
    setup_result = create_admin_user(
        pharmacy_id=pharmacy_id,
        full_name=admin_full_name,
        username=admin_username,
        password=admin_password,
        confirm_password=admin_password,
        db=db
    )

    if not setup_result.get('success'):
        # Transaction will rollback on exception
        raise ValueError(setup_result.get('message', 'Failed to create admin user'))

    # Apply defaults
    apply_default_settings(db, pharmacy_id)

    # Audit log
    from audit import log_action
    log_action(
        db=db,
        pharmacy_id=pharmacy_id,
        user_id=db.query(User).filter(
            User.username == admin_username
        ).first().id,
        user_name=admin_full_name,
        action_type="pharmacy_provisioned",
        description=f"Pharmacy provisioned: {pharmacy_name} (type: {pharmacy_type})",
        new_value=f"type={pharmacy_type}, admin={admin_username}"
    )

    return {
        'success': True,
        'pharmacy_id': pharmacy_id,
        'pharmacy_name': pharmacy_name,
        'pharmacy_type': pharmacy_type,
        'admin_username': admin_username,
        'message': f"Pharmacy '{pharmacy_name}' provisioned successfully as {pharmacy_type}"
    }


# ✅ انتهى - auth.py - المرحلة 2
