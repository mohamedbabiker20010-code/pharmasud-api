"""
PharmaSUD - Batches Module (Stage 4)
Version 4.0.0

يتولى:
- استلام شحنات جديدة (Batch Receiving)
- منطق FEFO الكامل (First Expired First Out)
- تحويل الوحدات تلقائياً
- تنبيهات الصلاحية
- عرض الشحنات المتاحة للبيع

FEFO = First Expired First Out
الأقرب للانتهاء يُباع أولاً
"""

import uuid
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text, and_

from database import get_db
from models import (
    Medicine, Unit, Batch,
    BatchReceive, BatchReceiveConfirm, BatchReceiveResponse,
    BatchResponse, AvailableBatchResponse,
    FEFOAllocation, FEFOResult,
)
from auth import get_current_user, require_admin

# Create router
router = APIRouter(prefix="/api/batches", tags=["batches"])


# ═══════════════════════════════════════════════════════════
# دالة مساعدة: حساب أيام الصلاحية المتبقية
# ═══════════════════════════════════════════════════════════

def calculate_days_remaining(expiry_date: date) -> int:
    """
    تحسب عدد الأيام المتبقية حتى تاريخ انتهاء الصلاحية.
    """
    today = date.today()
    delta = expiry_date - today
    return delta.days


# ═══════════════════════════════════════════════════════════
# دالة مساعدة: تحديد حالة الصلاحية بناءً على الأيام المتبقية
# ═══════════════════════════════════════════════════════════

def get_expiry_status(days_remaining: int) -> str:
    """
    تعيد حالة الصلاحية:
    - منتهي: الأيام سالبة (انتهت صلاحيته)
    - ينتهي قريباً: أقل من 30 يوم
    - تحذير: بين 30 و 90 يوم
    - سليم: أكثر من 90 يوم
    """
    if days_remaining < 0:
        return "منتهي"  # 🔴
    elif days_remaining <= 30:
        return "ينتهي قريباً"  # 🟠
    elif days_remaining <= 90:
        return "تحذير"  # 🟡
    else:
        return "سليم"  # 🟢


# ═══════════════════════════════════════════════════════════
# دالة مساعدة: توليد رسالة تحذير الصلاحية
# ═══════════════════════════════════════════════════════════

def generate_expiry_warning(days_remaining: int) -> Optional[str]:
    """
    تولد رسالة تحذير مناسبة حسب الأيام المتبقية:
    - أقل من 30: رسالة خطر
    - بين 30 و 90: تحذير عادي
    - أكثر من 90: لا تحذير
    """
    if days_remaining < 0:
        return f"خطر: هذه الشحنة منتهية الصلاحية بالفعل ({abs(days_remaining)} يوم منذ انتهائها)"
    elif days_remaining <= 30:
        return f"خطر: هذه الشحنة تنتهي خلال {days_remaining} يوم. هل أنت متأكد من الاستلام؟"
    elif days_remaining <= 90:
        return f"تحذير: هذه الشحنة تنتهي خلال {days_remaining} يوم"
    else:
        return None  # لا تحذير


# ═══════════════════════════════════════════════════════════
# دالة مساعدة: تنسيق بيانات الشحنة للرد
# ═══════════════════════════════════════════════════════════

def format_batch_response(batch: Batch) -> dict:
    """
    تحويل كائن Batch إلى قاموس للرد.
    تحسب الأيام المتبقية وتحدد حالة الصلاحية.
    """
    days = calculate_days_remaining(batch.expiry_date)
    return {
        "batch_id": str(batch.id),
        "batch_number": batch.batch_number,
        "quantity": batch.quantity,
        "expiry_date": batch.expiry_date.isoformat(),
        "expiry_status": get_expiry_status(days),
        "days_remaining": days,
        "purchase_price": float(batch.purchase_price) if batch.purchase_price else None,
        "supplier_invoice": batch.supplier_invoice,
        "supplier_name": batch.supplier_name,
        "received_at": batch.received_at.isoformat() if batch.received_at else None
    }


# ═══════════════════════════════════════════════════════════
# المهمة 1: استلام شحنة جديدة
# POST /api/batches/receive
# ═══════════════════════════════════════════════════════════

@router.post("/receive", response_model=BatchReceiveResponse)
async def receive_batch(
    data: BatchReceive,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    استلام شحنة جديدة من المورد.

    السيناريو:
    1. الصيدلاني يمسح باركود الدواء أو يبحث عنه
    2. يدخل رقم الشحنة، الكمية، الوحدة، تاريخ الانتهاء، السعر
    3. النظام يحول الكمية للوحدة الأساسية ويحفظ الشحنة
    4. النظام يرجع تحذير إذا الصلاحية قريبة

    تحويل الوحدات:
    - إذا الوحدة المدخلة غير الوحدة الأساسية، النظام يحول تلقائياً
    - مثال: 5 علب × 10 (معامل التحويل) = 50 شريط
    """
    try:
        # Parse medicine_id to UUID
        try:
            med_uuid = uuid.UUID(data.medicine_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="معرف الدواء غير صالح")

        # التحقق من وجود الدواء
        medicine = db.query(Medicine).filter(
            Medicine.id == med_uuid,
            Medicine.pharmacy_id == uuid.UUID(current_user["pharmacy_id"])
        ).first()

        if not medicine:
            raise HTTPException(status_code=404, detail="الدواء غير موجود")

        # التحقق من أن رقم الشحنة غير مكرر
        existing = db.query(Batch).filter(
            Batch.batch_number == data.batch_number,
            Batch.is_active == True
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"رقم الشحنة {data.batch_number} موجود مسبقاً")

        # Parse expiry date
        try:
            expiry_date = datetime.strptime(data.expiry_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="تاريخ الانتهاء غير صالح. استخدم الصيغة YYYY-MM-DD")

        # ═══════════════════════════════════════════════════
        # تحويل الوحدات
        # ═══════════════════════════════════════════════════
        # نبحث عن معامل التحويل للوحدة المدخلة
        unit = db.query(Unit).filter(
            Unit.medicine_id == med_uuid,
            Unit.unit_name == data.unit_name
        ).first()

        if unit:
            # يوجد معامل تحويل: نحول الكمية للوحدة الأساسية
            conversion_factor = float(unit.conversion_factor)
            quantity_in_base_units = int(data.quantity * conversion_factor)
            unit_converted = medicine.base_unit
        else:
            # لا يوجد معامل تحويل: نستخدم الكمية كما هي
            # (الوحدة المدخلة هي نفسها الوحدة الأساسية)
            quantity_in_base_units = int(data.quantity)
            unit_converted = data.unit_name

        # التأكد أن الكمية المحولة أكبر من صفر
        if quantity_in_base_units <= 0:
            raise HTTPException(
                status_code=400,
                detail="الكمية المحولة غير صالحة. تأكد من معامل التحويل"
            )

        # ═══════════════════════════════════════════════════
        # إنشاء الشحنة
        # ═══════════════════════════════════════════════════
        new_batch = Batch(
            id=uuid.uuid4(),
            medicine_id=med_uuid,
            batch_number=data.batch_number,
            quantity=quantity_in_base_units,
            expiry_date=expiry_date,
            purchase_price=data.purchase_price,
            supplier_invoice=data.supplier_invoice,
            supplier_name=data.supplier_name,
            is_active=True
        )

        db.add(new_batch)
        db.commit()
        db.refresh(new_batch)

        # ═══════════════════════════════════════════════════
        # تنبيهات الصلاحية (المهمة 4)
        # ═══════════════════════════════════════════════════
        days_remaining = calculate_days_remaining(expiry_date)
        expiry_warning = generate_expiry_warning(days_remaining)

        # بناء رسالة النجاح
        success_message = f"تم استلام {quantity_in_base_units} {unit_converted} {medicine.trade_name} بنجاح"

        return {
            "success": True,
            "batch_id": str(new_batch.id),
            "quantity_stored": quantity_in_base_units,
            "unit_converted": unit_converted,
            "expiry_warning": expiry_warning,
            "message": success_message
        }

    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="فشل في استلام الشحنة"
        )


# ═══════════════════════════════════════════════════════════
# تأكيد استلام شحنة ذات صلاحية قصيرة (أقل من 30 يوم)
# POST /api/batches/receive/confirm-short-expiry
# ═══════════════════════════════════════════════════════════

@router.post("/receive/confirm-short-expiry", response_model=BatchReceiveResponse)
async def confirm_short_expiry_batch(
    data: BatchReceiveConfirm,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    تأكيد استلام شحنة ذات صلاحية قصيرة جداً (أقل من 30 يوم).
    يُستخدم بعد أن يؤكد المستخدم أنه يريد استلامها رغم التحذير.
    """
    if not data.confirmed:
        return {
            "success": False,
            "message": "تم إلغاء استلام الشحنة"
        }

    # نفس منطق receive_batch لكن بدون تحذير
    try:
        med_uuid = uuid.UUID(data.batch_data.medicine_id)
        medicine = db.query(Medicine).filter(
            Medicine.id == med_uuid,
            Medicine.pharmacy_id == uuid.UUID(current_user["pharmacy_id"])
        ).first()

        if not medicine:
            raise HTTPException(status_code=404, detail="الدواء غير موجود")

        # Parse expiry and convert units
        expiry_date = datetime.strptime(data.batch_data.expiry_date, "%Y-%m-%d").date()

        unit = db.query(Unit).filter(
            Unit.medicine_id == med_uuid,
            Unit.unit_name == data.batch_data.unit_name
        ).first()

        if unit:
            conversion_factor = float(unit.conversion_factor)
            quantity_in_base_units = int(data.batch_data.quantity * conversion_factor)
            unit_converted = medicine.base_unit
        else:
            quantity_in_base_units = int(data.batch_data.quantity)
            unit_converted = data.batch_data.unit_name

        new_batch = Batch(
            id=uuid.uuid4(),
            medicine_id=med_uuid,
            batch_number=data.batch_data.batch_number,
            quantity=quantity_in_base_units,
            expiry_date=expiry_date,
            purchase_price=data.batch_data.purchase_price,
            supplier_invoice=data.batch_data.supplier_invoice,
            supplier_name=data.batch_data.supplier_name,
            is_active=True
        )

        db.add(new_batch)
        db.commit()
        db.refresh(new_batch)

        days_remaining = calculate_days_remaining(expiry_date)
        warning = generate_expiry_warning(days_remaining)

        return {
            "success": True,
            "batch_id": str(new_batch.id),
            "quantity_stored": quantity_in_base_units,
            "unit_converted": unit_converted,
            "expiry_warning": warning,
            "message": f"تم استلام {quantity_in_base_units} {unit_converted} {medicine.trade_name} بنجاح"
        }

    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="فشل في استلام الشحنة"
        )


# ═══════════════════════════════════════════════════════════
# المهمة 2: الشحنات المتاحة للبيع (حسب FEFO)
# GET /api/batches/available/{medicine_id}
# ═══════════════════════════════════════════════════════════

@router.get("/available/{medicine_id}", response_model=AvailableBatchResponse)
async def get_available_batches(
    medicine_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    تعيد كل الشحنات المتاحة للبيع لدواء معين.
    ترتب حسب FEFO (الأقرب للانتهاء أولاً).
    تتجاهل الشحنات المنتهية.
    """
    try:
        med_uuid = uuid.UUID(medicine_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="معرف الدواء غير صالح")

    medicine = db.query(Medicine).filter(
        Medicine.id == med_uuid,
        Medicine.pharmacy_id == uuid.UUID(current_user["pharmacy_id"])
    ).first()

    if not medicine:
        raise HTTPException(status_code=404, detail="الدواء غير موجود")

    # استعلام FEFO: الشحنات النشطة غير المنتهية مرتبة تصاعدياً حسب تاريخ الانتهاء
    today = date.today()
    batches = db.query(Batch).filter(
        Batch.medicine_id == med_uuid,
        Batch.quantity > 0,
        Batch.is_active == True,
        Batch.expiry_date > today
    ).order_by(Batch.expiry_date.asc()).all()

    total_available = sum(b.quantity for b in batches)

    return {
        "medicine_id": str(medicine.id),
        "trade_name": medicine.trade_name,
        "total_available": total_available,
        "batches": [format_batch_response(b) for b in batches]
    }


# ═══════════════════════════════════════════════════════════
# المهمة 2 (قلب النظام): دالة FEFO لتخصيص الشحنات للبيع
# تُستخدم من مرحلة البيع (Stage 5)
# ═══════════════════════════════════════════════════════════

def get_fefo_batches(medicine_id: str, quantity_needed: int, db: Session) -> list[dict]:
    """
    دالة FEFO الأساسية.
    تأخذ معرف الدواء والكمية المطلوبة.
    ترجع قائمة الشحنات المخصصة بالترتيب الصحيح (الأقرب للانتهاء أولاً).

    مثال:
    المطلوب: 60 شريط
    الشحنة A: 50 شريط (تنتهي 2026) ← تأخذ كلها
    الشحنة B: 95 شريط (تنتهي 2027) ← تأخذ 10 منها
    النتيجة: [{batch_id: A, quantity: 50}, {batch_id: B, quantity: 10}]

    Parameters:
        medicine_id: معرف الدواء (نص)
        quantity_needed: الكمية المطلوبة بالوحدة الأساسية
        db: جلسة قاعدة البيانات

    Returns:
        قائمة مخصصات الشحنات

    Raises:
        Exception: إذا المخزون غير كافٍ
    """
    today = date.today()

    # نجيب الشحنات المتاحة مرتبة: الأقرب للانتهاء أولاً
    batches = db.query(Batch).filter(
        Batch.medicine_id == medicine_id,
        Batch.quantity > 0,
        Batch.is_active == True,
        Batch.expiry_date > today
    ).order_by(Batch.expiry_date.asc()).all()

    result = []
    remaining = quantity_needed

    for batch in batches:
        if remaining <= 0:
            break

        # نأخذ الكمية المطلوبة أو المتاحة (الأقل)
        take = min(batch.quantity, remaining)

        result.append({
            "batch_id": str(batch.id),
            "quantity": take,
            "expiry_date": batch.expiry_date.isoformat()
        })

        remaining -= take

    # إذا باقي كمية = المخزون غير كافٍ
    if remaining > 0:
        total_available = sum(b.quantity for b in batches)
        raise Exception(
            f"المخزون غير كافٍ - المطلوب {quantity_needed} وحدة، "
            f"المتوفر {total_available} وحدة، ناقص {remaining} وحدة"
        )

    return result


# ═══════════════════════════════════════════════════════════
# Endpoint اختبار: تجربة FEFO على دواء معين
# GET /api/batches/fefo-test/{medicine_id}?quantity=60
# ═══════════════════════════════════════════════════════════

@router.get("/fefo-test/{medicine_id}")
async def test_fefo(
    medicine_id: str,
    quantity: int = Query(..., gt=0, description="الكمية المطلوبة"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    اختبار دالة FEFO: تجرب توزيع كمية معينة على الشحنات المتاحة.
    تُستخدم للتحقق قبل تفعيل البيع الفعلي.
    """
    try:
        med_uuid = uuid.UUID(medicine_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="معرف الدواء غير صالح")

    medicine = db.query(Medicine).filter(
        Medicine.id == med_uuid,
        Medicine.pharmacy_id == uuid.UUID(current_user["pharmacy_id"])
    ).first()

    if not medicine:
        raise HTTPException(status_code=404, detail="الدواء غير موجود")

    try:
        # نجرب دالة FEFO
        allocation = get_fefo_batches(str(med_uuid), quantity, db)

        total_allocated = sum(a["quantity"] for a in allocation)

        return {
            "success": True,
            "medicine_id": str(medicine.id),
            "trade_name": medicine.trade_name,
            "quantity_needed": quantity,
            "allocated": allocation,
            "total_allocated": total_allocated,
            "remaining": 0,
            "message": f"تم تخصيص {total_allocated} من {quantity} بنجاح"
        }

    except Exception:
        # المخزون غير كافٍ
        total_available = sum(
            b.quantity for b in db.query(Batch).filter(
                Batch.medicine_id == med_uuid,
                Batch.quantity > 0,
                Batch.is_active == True,
                Batch.expiry_date > date.today()
            ).all()
        )
        return {
            "success": False,
            "medicine_id": str(medicine.id),
            "trade_name": medicine.trade_name,
            "quantity_needed": quantity,
            "total_available": total_available,
            "message": "المخزون غير كافٍ"
        }


# ✅ انتهى - batches.py - المرحلة 4