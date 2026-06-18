"""
PharmaSUD - Employees Module (Stage 7)
Version 7.0.0

يتولى:
- إدارة الموظفين (Admin فقط)
- إنشاء، تعطيل/تفعيل، إعادة كلمة المرور
- تسجيل العمليات في audit_log
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from models import User
from auth import get_current_user, require_admin, get_password_hash, verify_password, require_permission
from audit import log_action

router = APIRouter(prefix="/api/employees", tags=["employees"])


class EmployeeCreateSchema(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)
    phone: str = Field("", max_length=20)


class ResetPasswordSchema(BaseModel):
    new_password: str = Field(..., min_length=6, max_length=100)


@router.get("/", dependencies=[Depends(require_permission("employees.view"))])
async def list_employees(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """قائمة الموظفين (Admin فقط)."""
    ph_id = uuid.UUID(current_user["pharmacy_id"])

    employees = db.query(User).filter(
        User.pharmacy_id == ph_id
    ).order_by(User.created_at.desc()).all()

    result = []
    for emp in employees:
        result.append({
            "id": str(emp.id),
            "full_name": emp.full_name,
            "username": emp.username,
            "phone": emp.phone or "",
            "role": emp.role,
            "is_active": emp.is_active,
            "created_at": emp.created_at.isoformat() if emp.created_at else None
        })

    return {"employees": result}


@router.post("/", dependencies=[Depends(require_permission("employees.manage"))])
async def create_employee(
    data: EmployeeCreateSchema,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """إنشاء موظف جديد (Admin فقط - role='employee' دائماً)."""
    ph_id = uuid.UUID(current_user["pharmacy_id"])

    # التحقق من أن اسم المستخدم غير مكرر
    existing = db.query(User).filter(User.username == data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="اسم المستخدم موجود مسبقاً")

    # إنشاء المستخدم
    new_user = User(
        id=uuid.uuid4(),
        pharmacy_id=ph_id,
        username=data.username,
        full_name=data.full_name,
        password_hash=get_password_hash(data.password),
        phone=data.phone or "",
        role="employee",
        is_active=True
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # سجل في audit_log
    log_action(
        db=db,
        pharmacy_id=current_user["pharmacy_id"],
        user_id=current_user["user_id"],
        user_name=current_user.get("full_name", current_user["username"]),
        action_type="employee_create",
        description=f"إضافة موظف: {data.full_name}",
        new_value=data.username
    )

    return {
        "success": True,
        "employee_id": str(new_user.id),
        "message": "تم إنشاء حساب الموظف بنجاح"
    }


@router.put("/{employee_id}/toggle", dependencies=[Depends(require_permission("employees.manage"))])
async def toggle_employee(
    employee_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """تعطيل/تفعيل موظف (Admin فقط - لا يمكن تعطيل النفس)."""
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

    # بدّل الحالة
    employee.is_active = not employee.is_active
    db.commit()

    action_label = "تفعيل" if employee.is_active else "تعطيل"
    description = f"{action_label} حساب الموظف: {employee.full_name or employee.username}"

    # سجل في audit_log
    log_action(
        db=db,
        pharmacy_id=current_user["pharmacy_id"],
        user_id=current_user["user_id"],
        user_name=current_user.get("full_name", current_user["username"]),
        action_type="employee_toggle",
        description=description
    )

    return {
        "success": True,
        "message": description
    }


@router.put("/{employee_id}/reset-password", dependencies=[Depends(require_permission("employees.manage"))])
async def reset_employee_password(
    employee_id: str,
    data: ResetPasswordSchema,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """إعادة تعيين كلمة مرور موظف (Admin فقط)."""
    ph_id = uuid.UUID(current_user["pharmacy_id"])

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

    # تحديث كلمة المرور
    employee.password_hash = get_password_hash(data.new_password)
    db.commit()

    # سجل في audit_log
    log_action(
        db=db,
        pharmacy_id=current_user["pharmacy_id"],
        user_id=current_user["user_id"],
        user_name=current_user.get("full_name", current_user["username"]),
        action_type="employee_reset_password",
        description=f"إعادة تعيين كلمة مرور: {employee.full_name or employee.username}"
    )

    return {
        "success": True,
        "message": f"تم إعادة تعيين كلمة المرور للموظف {employee.full_name}"
    }


# ✅ انتهى - employees.py - المرحلة 7