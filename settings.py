"""
PharmaSUD - Settings & Admin Module (Stage 4.5)
Version 4.5.0

يتولى:
- إدارة الموظفين (إضافة، حذف، تعطيل)
- تغيير كلمة السر
- إعدادات الصيدلية (تعديل الاسم، العنوان، الهاتف)
"""

import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from models import (
    Pharmacy, User,
    EmployeeCreate, EmployeeResponse, EmployeeListResponse,
    PasswordChange, PharmacyUpdate, PharmacySettingsResponse,
    EmployeeStatusToggle,
)
from auth import get_current_user, require_admin, get_password_hash, verify_password

# Create router
router = APIRouter(prefix="/api/settings", tags=["settings"])


# ═══════════════════════════════════════════════════════════
# Helper: Format employee for response
# ═══════════════════════════════════════════════════════════

def format_employee(user: User) -> dict:
    """تنسيق بيانات الموظف للرد."""
    return {
        "id": str(user.id),
        "full_name": user.full_name,
        "username": user.username,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None
    }


# ═══════════════════════════════════════════════════════════
# 1. قائمة الموظفين
# GET /api/settings/employees
# ═══════════════════════════════════════════════════════════

@router.get("/employees")
async def list_employees(
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """عرض كل الموظفين في الصيدلية."""
    ph_id = uuid.UUID(current_user["pharmacy_id"])

    employees = db.query(User).filter(
        User.pharmacy_id == ph_id
    ).order_by(User.created_at.desc()).all()

    return {
        "employees": [format_employee(e) for e in employees],
        "total": len(employees)
    }


# ═══════════════════════════════════════════════════════════
# 2. إضافة موظف جديد
# POST /api/settings/employees
# ═══════════════════════════════════════════════════════════

@router.post("/employees")
async def create_employee(
    data: EmployeeCreate,
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """إضافة موظف جديد (أدمن فقط)."""
    ph_id = uuid.UUID(current_user["pharmacy_id"])

    # التحقق من أن اسم المستخدم غير مكرر
    existing = db.query(User).filter(User.username == data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="اسم المستخدم موجود مسبقاً")

    # التحقق من أن الدور صحيح
    if data.role not in ("admin", "employee"):
        raise HTTPException(status_code=400, detail="الدور يجب أن يكون admin أو employee")

    # إنشاء المستخدم
    new_user = User(
        id=uuid.uuid4(),
        pharmacy_id=ph_id,
        username=data.username,
        full_name=data.full_name,
        password_hash=get_password_hash(data.password),
        role=data.role,
        is_active=True
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "success": True,
        "message": f"تم إضافة {data.full_name} بنجاح",
        "employee": format_employee(new_user)
    }


# ═══════════════════════════════════════════════════════════
# 3. حذف موظف
# DELETE /api/settings/employees/{employee_id}
# ═══════════════════════════════════════════════════════════

@router.delete("/employees/{employee_id}")
async def delete_employee(
    employee_id: str,
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """حذف موظف (أدمن فقط - لا يمكن حذف نفسك)."""
    ph_id = uuid.UUID(current_user["pharmacy_id"])
    current_user_id = current_user["user_id"]

    try:
        emp_uuid = uuid.UUID(employee_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="معرف الموظف غير صالح")

    # منع حذف النفس
    if employee_id == current_user_id:
        raise HTTPException(status_code=400, detail="لا يمكنك حذف حسابك بنفسك")

    employee = db.query(User).filter(
        User.id == emp_uuid,
        User.pharmacy_id == ph_id
    ).first()

    if not employee:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")

    name = employee.full_name or employee.username
    db.delete(employee)
    db.commit()

    return {
        "success": True,
        "message": f"تم حذف {name} بنجاح"
    }


# ═══════════════════════════════════════════════════════════
# 4. تعطيل/تفعيل موظف
# PATCH /api/settings/employees/{employee_id}/toggle
# ═══════════════════════════════════════════════════════════

@router.patch("/employees/{employee_id}/toggle")
async def toggle_employee_status(
    employee_id: str,
    data: EmployeeStatusToggle,
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """تعطيل أو تفعيل موظف (أدمن فقط - لا يمكن تعطيل نفسك)."""
    ph_id = uuid.UUID(current_user["pharmacy_id"])
    current_user_id = current_user["user_id"]

    if employee_id == current_user_id:
        raise HTTPException(status_code=400, detail="لا يمكنك تعطيل حسابك بنفسك")

    try:
        emp_uuid = uuid.UUID(employee_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="معرف الموظف غير صالح")

    employee = db.query(User).filter(
        User.id == emp_uuid,
        User.pharmacy_id == ph_id
    ).first()

    if not employee:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")

    employee.is_active = data.is_active
    db.commit()

    status_text = "تفعيل" if data.is_active else "تعطيل"
    name = employee.full_name or employee.username

    return {
        "success": True,
        "message": f"تم {status_text} حساب {name} بنجاح",
        "employee": format_employee(employee)
    }


# ═══════════════════════════════════════════════════════════
# 5. تغيير كلمة السر
# POST /api/settings/change-password
# ═══════════════════════════════════════════════════════════

@router.post("/change-password")
async def change_password(
    data: PasswordChange,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """تغيير كلمة السر للمستخدم الحالي."""
    user_id = current_user["user_id"]

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    # التحقق من كلمة السر الحالية
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="كلمة السر الحالية غير صحيحة")

    # تحديث كلمة السر
    user.password_hash = get_password_hash(data.new_password)
    db.commit()

    return {
        "success": True,
        "message": "تم تغيير كلمة السر بنجاح"
    }


# ═══════════════════════════════════════════════════════════
# 6. عرض إعدادات الصيدلية
# GET /api/settings/pharmacy
# ═══════════════════════════════════════════════════════════

@router.get("/pharmacy")
async def get_pharmacy_settings(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """عرض إعدادات الصيدلية."""
    ph_id = uuid.UUID(current_user["pharmacy_id"])

    pharmacy = db.query(Pharmacy).filter(Pharmacy.id == ph_id).first()
    if not pharmacy:
        raise HTTPException(status_code=404, detail="الصيدلية غير موجودة")

    return {
        "id": str(pharmacy.id),
        "name": pharmacy.name,
        "owner_name": pharmacy.owner_name,
        "phone": pharmacy.phone,
        "address": pharmacy.address,
        "is_active": pharmacy.is_active,
        "created_at": pharmacy.created_at.isoformat() if pharmacy.created_at else None
    }


# ═══════════════════════════════════════════════════════════
# 7. تعديل إعدادات الصيدلية
# PUT /api/settings/pharmacy
# ═══════════════════════════════════════════════════════════

@router.put("/pharmacy")
async def update_pharmacy_settings(
    data: PharmacyUpdate,
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """تعديل إعدادات الصيدلية (أدمن فقط)."""
    ph_id = uuid.UUID(current_user["pharmacy_id"])

    pharmacy = db.query(Pharmacy).filter(Pharmacy.id == ph_id).first()
    if not pharmacy:
        raise HTTPException(status_code=404, detail="الصيدلية غير موجودة")

    # ⚠️ اسم الصيدلية واسم المالك مقفولان — لا يمكن تغييرهما بعد التفعيل
    # المحافظة على الأمان ومنع إعادة البيع
    if data.phone is not None:
        pharmacy.phone = data.phone
    if data.address is not None:
        pharmacy.address = data.address

    db.commit()

    return {
        "success": True,
        "message": "تم تحديث إعدادات الصيدلية بنجاح",
        "pharmacy": {
            "id": str(pharmacy.id),
            "name": pharmacy.name,
            "owner_name": pharmacy.owner_name,
            "phone": pharmacy.phone,
            "address": pharmacy.address
        }
    }


# ✅ انتهى - settings.py - المرحلة 4.5