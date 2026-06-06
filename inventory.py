"""
PharmaSUD - Inventory Module (Stage 4)
Version 4.0.0

يتولى:
- عرض المخزون الكامل مع إجمالي الشحنات
- تفاصيل شحنات كل دواء
- تقرير الأدوية المنتهية
- حساب أقرب تاريخ انتهاء لكل دواء
"""

import uuid
from datetime import datetime, date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text, func

from database import get_db
from models import (
    Medicine, Unit, Batch,
    MedicineInventoryItem, InventoryListResponse,
    BatchDetailResponse, BatchResponse,
    ExpiredItem, ExpiredReportResponse,
)
from auth import get_current_user
from batches import format_batch_response, calculate_days_remaining, get_expiry_status

# Create router
router = APIRouter(prefix="/api/inventory", tags=["inventory"])


# ═══════════════════════════════════════════════════════════
# دالة مساعدة: جمع المخزون من الشحنات
# ═══════════════════════════════════════════════════════════

def get_medicine_total_stock(medicine_id, db: Session) -> int:
    """حساب إجمالي المخزون لدواء من كل الشحنات النشطة."""
    result = db.query(func.coalesce(func.sum(Batch.quantity), 0)).filter(
        Batch.medicine_id == medicine_id,
        Batch.is_active == True
    ).scalar()
    return int(result)


def get_stock_status(total_stock: int, min_stock: int) -> str:
    """تحديد حالة المخزون."""
    if total_stock <= 0:
        return "out"
    elif total_stock <= min_stock:
        return "low"
    else:
        return "available"


# ═══════════════════════════════════════════════════════════
# دالة مساعدة: أقرب تاريخ انتهاء لدواء
# ═══════════════════════════════════════════════════════════

def get_nearest_expiry(medicine_id, db: Session):
    """
    تجيب أقرب تاريخ انتهاء للشحنات النشطة غير المنتهية.
    ترجع (التاريخ, حالة_الصلاحية) أو (None, None) إذا ما في شحنات.
    """
    today = date.today()
    batch = db.query(Batch).filter(
        Batch.medicine_id == medicine_id,
        Batch.quantity > 0,
        Batch.is_active == True,
        Batch.expiry_date > today
    ).order_by(Batch.expiry_date.asc()).first()

    if batch:
        days = calculate_days_remaining(batch.expiry_date)
        return batch.expiry_date.isoformat(), get_expiry_status(days)

    return None, None


# ═══════════════════════════════════════════════════════════
# المهمة 3: عرض المخزون الكامل
# GET /api/inventory/
# ═══════════════════════════════════════════════════════════

@router.get("/")
async def get_inventory(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    عرض المخزون الكامل.
    لكل دواء يعرض:
    - إجمالي الكمية من كل الشحنات
    - أقرب تاريخ انتهاء
    - عدد الشحنات المتاحة
    - حالة المخزون (متوفر/منخفض/نفد)
    """
    ph_id = uuid.UUID(current_user["pharmacy_id"])

    # نجيب كل الأدوية النشطة في الصيدلية
    medicines = db.query(Medicine).filter(
        Medicine.pharmacy_id == ph_id
    ).order_by(Medicine.trade_name).all()

    inventory_items = []

    for med in medicines:
        med_id = med.id
        total_stock = get_medicine_total_stock(med_id, db)
        stock_status = get_stock_status(total_stock, med.min_stock)

        # عدد الشحنات النشطة
        batches_count = db.query(func.count(Batch.id)).filter(
            Batch.medicine_id == med_id,
            Batch.quantity > 0,
            Batch.is_active == True
        ).scalar() or 0

        # أقرب تاريخ انتهاء
        nearest_expiry, nearest_expiry_status = get_nearest_expiry(med_id, db)

        inventory_items.append({
            "medicine_id": str(med_id),
            "trade_name": med.trade_name,
            "scientific_name": med.scientific_name,
            "category": med.category,
            "image_url": med.image_path or "/static/images/default-medicine.svg",
            "total_stock": total_stock,
            "base_unit": med.base_unit,
            "stock_status": stock_status,
            "nearest_expiry": nearest_expiry,
            "nearest_expiry_status": nearest_expiry_status,
            "batches_count": batches_count
        })

    return {
        "medicines": inventory_items,
        "total": len(inventory_items)
    }


# ═══════════════════════════════════════════════════════════
# تفاصيل شحنات دواء معين
# GET /api/inventory/{medicine_id}/batches
# ═══════════════════════════════════════════════════════════

@router.get("/{medicine_id}/batches")
async def get_medicine_batches(
    medicine_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    عرض كل الشحنات لدواء معين.
    تشمل الشحنات النشطة والمنتهية.
    مرتبة حسب تاريخ الانتهاء (الأقرب أولاً).
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

    # نجيب كل الشحنات (حتى المنتهية) مرتبة حسب تاريخ الانتهاء
    batches = db.query(Batch).filter(
        Batch.medicine_id == med_uuid
    ).order_by(Batch.expiry_date.asc()).all()

    total_stock = get_medicine_total_stock(med_uuid, db)

    return {
        "medicine_id": str(medicine.id),
        "trade_name": medicine.trade_name,
        "scientific_name": medicine.scientific_name,
        "image_url": medicine.image_path or "/static/images/default-medicine.svg",
        "base_unit": medicine.base_unit,
        "total_stock": total_stock,
        "batches": [format_batch_response(b) for b in batches]
    }


# ═══════════════════════════════════════════════════════════
# المهمة 4: تقرير الأدوية المنتهية
# GET /api/inventory/expired
# ═══════════════════════════════════════════════════════════

@router.get("/expired")
async def get_expired_report(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    تقرير بكل الشحنات المنتهية الصلاحية.
    تُظهر فقط الشحنات التي انتهى تاريخها.
    """
    ph_id = uuid.UUID(current_user["pharmacy_id"])
    today = date.today()

    # نجيب كل الشحنات المنتهية مع اسم الدواء
    results = db.execute(text("""
        SELECT
            m.trade_name,
            b.batch_number,
            b.quantity,
            b.expiry_date,
            m.id as medicine_id
        FROM batches b
        JOIN medicines m ON m.id = b.medicine_id
        WHERE m.pharmacy_id = :pharmacy_id
          AND b.expiry_date < :today
          AND b.quantity > 0
        ORDER BY b.expiry_date DESC
    """), {
        "pharmacy_id": ph_id,
        "today": today
    }).fetchall()

    expired_items = []
    for row in results:
        expiry = row[3] if isinstance(row[3], date) else row[3]
        days_expired = (today - expiry).days

        expired_items.append({
            "medicine_name": row[0],
            "batch_number": row[1],
            "quantity": row[2],
            "expiry_date": expiry.isoformat() if hasattr(expiry, 'isoformat') else str(expiry),
            "days_expired": days_expired
        })

    return {
        "expired": expired_items,
        "total_expired_items": len(expired_items)
    }


# ✅ انتهى - inventory.py - المرحلة 4