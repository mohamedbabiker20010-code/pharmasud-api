"""
PharmaSUD - Inventory Module (Stage 4 + Stage 7)
Version 7.0.0

يتولى:
- عرض المخزون الكامل مع إجمالي الشحنات
- تفاصيل شحنات كل دواء
- تقرير الأدوية المنتهية
- الجرد السريع بالباركود (Stage 7)
"""

import uuid
from datetime import datetime, date, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text, func

from database import get_db
from models import (
    Medicine, Unit, Batch,
    MedicineInventoryItem, InventoryListResponse,
    BatchDetailResponse, BatchResponse,
    ExpiredItem, ExpiredReportResponse,
)
from auth import get_current_user, require_admin
from batches import format_batch_response, calculate_days_remaining, get_expiry_status, get_fefo_batches
from audit import log_action

# Create router
router = APIRouter(prefix="/api/inventory", tags=["inventory"])


# ═══════════════════════════════════════════════════════════
# Pydantic models for Stocktake
# ═══════════════════════════════════════════════════════════

class StocktakeItemInput(BaseModel):
    medicine_id: str
    actual_quantity: int


class StocktakeSubmitRequest(BaseModel):
    notes: str = ""
    items: List[StocktakeItemInput]


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
# دالة مساعدة: آخر سعر شراء معروف لدواء
# ═══════════════════════════════════════════════════════════

def get_last_purchase_price(medicine_id, db: Session) -> float:
    """أحدث سعر شراء من أحدث شحنة."""
    result = db.execute(
        text("""
            SELECT purchase_price FROM batches
            WHERE medicine_id = :mid AND purchase_price IS NOT NULL
            ORDER BY created_at DESC LIMIT 1
        """),
        {"mid": medicine_id}
    ).scalar()
    return float(result) if result else 0.0


# ═══════════════════════════════════════════════════════════
# عرض المخزون الكامل
# ═══════════════════════════════════════════════════════════

@router.get("/")
async def get_inventory(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """عرض المخزون الكامل."""
    ph_id = uuid.UUID(current_user["pharmacy_id"])

    medicines = db.query(Medicine).filter(
        Medicine.pharmacy_id == ph_id
    ).order_by(Medicine.trade_name).all()

    inventory_items = []

    for med in medicines:
        med_id = med.id
        total_stock = get_medicine_total_stock(med_id, db)
        stock_status = get_stock_status(total_stock, med.min_stock)

        batches_count = db.query(func.count(Batch.id)).filter(
            Batch.medicine_id == med_id,
            Batch.quantity > 0,
            Batch.is_active == True
        ).scalar() or 0

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
# ═══════════════════════════════════════════════════════════

@router.get("/{medicine_id}/batches")
async def get_medicine_batches(
    medicine_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
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
# تقرير الأدوية المنتهية
# ═══════════════════════════════════════════════════════════

@router.get("/expired")
async def get_expired_report(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ph_id = uuid.UUID(current_user["pharmacy_id"])
    today = date.today()

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


# ═══════════════════════════════════════════════════════════
# المهمة 4 (Stage 7): الجرد السريع - بدء الجرد
# GET /api/inventory/stocktake/start
# ═══════════════════════════════════════════════════════════

@router.get("/stocktake/start")
async def start_stocktake(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """بدء الجرد: قائمة كل الأدوية مع كمية النظام الحالية."""
    ph_id = uuid.UUID(current_user["pharmacy_id"])

    medicines = db.query(Medicine).filter(
        Medicine.pharmacy_id == ph_id
    ).order_by(Medicine.trade_name).all()

    result = []
    for med in medicines:
        total_stock = get_medicine_total_stock(str(med.id), db)
        result.append({
            "medicine_id": str(med.id),
            "trade_name": med.trade_name,
            "barcode": med.barcode or "",
            "base_unit": med.base_unit or "شريط",
            "system_quantity": total_stock,
            "image_url": med.image_path or "/static/images/default-medicine.svg"
        })

    return {"medicines": result}


# ═══════════════════════════════════════════════════════════
# الجرد السريع - حفظ نتائج الجرد
# POST /api/inventory/stocktake/submit
# ═══════════════════════════════════════════════════════════

@router.post("/stocktake/submit")
async def submit_stocktake(
    data: StocktakeSubmitRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """حفظ نتائج الجرد مع تطبيق الفروقات."""
    pharmacy_id = current_user["pharmacy_id"]
    user_id = current_user["user_id"]
    user_name = current_user.get("full_name", current_user["username"])

    ph_uuid = uuid.UUID(pharmacy_id)
    user_uuid = uuid.UUID(user_id)

    # إنشاء جلسة الجرد
    session_id = uuid.uuid4()
    db.execute(
        text("""
            INSERT INTO stocktake_sessions (id, pharmacy_id, user_id, notes)
            VALUES (:sid, :pid, :uid, :notes)
        """),
        {"sid": session_id, "pid": ph_uuid, "uid": user_uuid, "notes": data.notes}
    )

    adjustments = []
    unchanged_count = 0
    today = date.today()

    for item in data.items:
        med_id_str = item.medicine_id
        try:
            med_uuid = uuid.UUID(med_id_str)
        except ValueError:
            continue

        # 1. أعد حساب system_quantity الحالي من قاعدة البيانات
        system_qty = get_medicine_total_stock(str(med_uuid), db)

        actual_qty = item.actual_quantity
        difference = actual_qty - system_qty

        # 2. لو الفرق = 0 → تجاهل
        if difference == 0:
            unchanged_count += 1
            continue

        # نجيب اسم الدواء
        medicine = db.query(Medicine).filter(Medicine.id == med_uuid).first()
        med_name = medicine.trade_name if medicine else "غير معروف"

        # سجّل في stocktake_items
        db.execute(
            text("""
                INSERT INTO stocktake_items
                    (session_id, medicine_id, medicine_name,
                     system_quantity, actual_quantity, difference)
                VALUES
                    (:sid, :mid, :mname, :sys, :act, :diff)
            """),
            {
                "sid": session_id,
                "mid": med_uuid,
                "mname": med_name,
                "sys": system_qty,
                "act": actual_qty,
                "diff": difference
            }
        )

        action_desc = ""

        if difference < 0:
            # 3. الفرق سالب (نقصان): اخصم |الفرق| باستخدام FEFO
            qty_to_remove = abs(difference)

            # استخدم FEFO لتحديد الشحنات المطلوب خصمها
            try:
                # نجيب الشحنات المتاحة مرتبة FEFO
                fefo_batches = db.query(Batch).filter(
                    Batch.medicine_id == med_uuid,
                    Batch.quantity > 0,
                    Batch.is_active == True,
                    Batch.expiry_date > today
                ).order_by(Batch.expiry_date.asc()).all()

                remaining = qty_to_remove
                for batch in fefo_batches:
                    if remaining <= 0:
                        break
                    take = min(batch.quantity, remaining)
                    batch.quantity -= take
                    remaining -= take
                    if batch.quantity <= 0:
                        batch.is_active = False

                action_desc = "تم خصم من المخزون"
            except Exception:
                action_desc = "فشل الخصم"

        elif difference > 0:
            # 4. الفرق موجب (زيادة): أضف شحنة تسوية
            last_price = get_last_purchase_price(str(med_uuid), db)
            next_year = today + timedelta(days=365)

            db.execute(
                text("""
                    INSERT INTO batches
                        (id, medicine_id, batch_number, quantity,
                         expiry_date, purchase_price, supplier_name, is_active)
                    VALUES
                        (:bid, :mid, :bnum, :qty, :exp, :price, :supplier, true)
                """),
                {
                    "bid": uuid.uuid4(),
                    "mid": med_uuid,
                    "bnum": f"تسوية-جرد-{today.isoformat()}",
                    "qty": difference,
                    "exp": next_year,
                    "price": last_price,
                    "supplier": "تسوية جرد"
                }
            )

            action_desc = f"تم إضافة {difference} كشحنة تسوية"

        adjustments.append({
            "medicine_name": med_name,
            "system_quantity": system_qty,
            "actual_quantity": actual_qty,
            "difference": difference,
            "action": action_desc
        })

        # 7. سجّل في audit_log
        log_action(
            db=db,
            pharmacy_id=pharmacy_id,
            user_id=user_id,
            user_name=user_name,
            action_type="stocktake_adjustment",
            description=f"جرد: {med_name} - النظام: {system_qty} - الفعلي: {actual_qty} - الفرق: {difference}",
            old_value=str(system_qty),
            new_value=str(actual_qty)
        )

    # تحديث عدد العناصر المعدّلة في الجلسة
    db.execute(
        text("UPDATE stocktake_sessions SET items_adjusted = :adj WHERE id = :sid"),
        {"adj": len(adjustments), "sid": session_id}
    )

    db.commit()

    return {
        "success": True,
        "session_id": str(session_id),
        "adjustments": adjustments,
        "unchanged_count": unchanged_count
    }


# ✅ انتهى - inventory.py - المرحلة 7