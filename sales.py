"""
PharmaSUD - Sales & POS Module (Stage 5)
Version 5.0.0

يتولى:
- إنشاء مبيعة جديدة مع FEFO
- Transaction آمن (كل شيء ينجح أو كل شيء يُلغى)
- عرض سجل المبيعات مع الفلاتر
- البحث السريع في POS
- الأدوية الأكثر مبيعاً
- عرض الفاتورة العامة

FEFO = First Expired First Out
الأقرب للانتهاء يُباع أولاً
"""

import uuid
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text, and_, func, desc

from database import get_db
from models import (
    Medicine, Unit, Batch, Sale, SaleItem, Pharmacy, User,
    SaleCreate, SaleCreateItem, SaleResponse, SaleItemResponse,
    SaleListItem, SalesListResponse,
    POSSearchResult, POSSearchResponse,
    QuickMedicine, QuickMedicinesResponse,
)
from auth import get_current_user, require_admin
from batches import get_fefo_batches, format_batch_response

# Create router
router = APIRouter(prefix="/api/sales", tags=["sales"])


# ═══════════════════════════════════════════════════════════
# دالة مساعدة: توليد رقم فاتورة تلقائي
# ═══════════════════════════════════════════════════════════

def get_next_invoice_number(pharmacy_id: str, db: Session) -> int:
    """
    توليد رقم الفاتورة التالي للصيدلية.
    يبدأ من 1 ويزيد تلقائياً مع كل مبيعة.
    """
    result = db.execute(
        text("SELECT COALESCE(MAX(invoice_number), 0) + 1 FROM sales WHERE pharmacy_id = :pid"),
        {"pid": pharmacy_id}
    )
    return result.scalar()


# ═══════════════════════════════════════════════════════════
# دالة مساعدة: تنسيق اسم طريقة الدفع
# ═══════════════════════════════════════════════════════════

def format_payment_method(method: str) -> str:
    """تحويل طريقة الدفع الإنجليزية إلى عربية."""
    mapping = {
        "cash": "نقدي",
        "bankak": "بنكك",
        "fory": "فوري",
        "transfer": "تحويل بنكي"
    }
    return mapping.get(method, method)


# ═══════════════════════════════════════════════════════════
# المهمة 1: إنشاء مبيعة جديدة (مع Transaction)
# POST /api/sales/create
# ═══════════════════════════════════════════════════════════

@router.post("/create", response_model=SaleResponse)
async def create_sale(
    data: SaleCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    إنشاء مبيعة جديدة.
    
    العملية في Transaction واحد:
    1. التحقق من المخزون لكل دواء
    2. تطبيق FEFO (الأقرب للانتهاء أولاً)
    3. إنشاء سجل المبيعة
    4. إنشاء تفاصيل المبيعة
    5. خصم الكميات من الشحنات
    6. COMMIT (أو ROLLBACK عند أي خطأ)
    
    الـ payment_method:
    - cash = نقدي
    - bankak = بنكك
    - fory = فوري
    - transfer = تحويل بنكي
    """
    pharmacy_id = current_user["pharmacy_id"]
    user_id = current_user["user_id"]
    
    try:
        # ============================================================
        # 1. التحقق الأولي من المخزون لكل دواء
        # ============================================================
        insufficient = []
        today = date.today()
        
        for item in data.items:
            med_uuid = uuid.UUID(item.medicine_id)
            
            # إجمالي المخزون المتاح (غير منتهي)
            stock_result = db.execute(
                text("""
                    SELECT COALESCE(SUM(quantity), 0) 
                    FROM batches 
                    WHERE medicine_id = :mid 
                    AND is_active = true 
                    AND quantity > 0 
                    AND expiry_date > :today
                """),
                {"mid": med_uuid, "today": today}
            )
            available = stock_result.scalar()
            
            if available < item.quantity:
                # نجيب اسم الدواء
                med = db.query(Medicine).filter(Medicine.id == med_uuid).first()
                med_name = med.trade_name if med else "غير معروف"
                insufficient.append({
                    "medicine_name": med_name,
                    "requested": item.quantity,
                    "available": available
                })
        
        if insufficient:
            return SaleResponse(
                success=False,
                error_type="insufficient_stock",
                message="المخزون غير كافٍ لبعض الأدوية",
                details=insufficient
            )
        
        # ============================================================
        # 2. بدء Transaction
        # ============================================================
        
        # نجيب معلومات الصيدلية والموظف
        pharmacy = db.query(Pharmacy).filter(
            Pharmacy.id == uuid.UUID(pharmacy_id)
        ).first()
        
        user = db.query(User).filter(
            User.id == uuid.UUID(user_id)
        ).first()
        
        # رقم الفاتورة التالي
        invoice_number = get_next_invoice_number(pharmacy_id, db)
        
        # إنشاء سجل المبيعة
        sale = Sale(
            id=uuid.uuid4(),
            pharmacy_id=uuid.UUID(pharmacy_id),
            user_id=uuid.UUID(user_id),
            invoice_number=invoice_number,
            customer_name=data.customer_name,
            total_amount=data.total_amount,
            payment_method=data.payment_method,
        )
        db.add(sale)
        db.flush()  # نرسل لـ DB عشان نحصل على id
        
        # ============================================================
        # 3. معالجة كل صنف في المبيعة
        # ============================================================
        
        sale_items_response = []
        
        for item in data.items:
            med_uuid = uuid.UUID(item.medicine_id)
            medicine = db.query(Medicine).filter(Medicine.id == med_uuid).first()
            
            if not medicine:
                db.rollback()
                return SaleResponse(
                    success=False,
                    message=f"الدواء {item.medicine_id} غير موجود"
                )
            
            # الكمية المطلوبة بالوحدة الأساسية
            quantity_needed = item.quantity
            
            # تطبيق FEFO
            try:
                fefo_allocation = get_fefo_batches(
                    medicine_id=str(med_uuid),
                    quantity_needed=quantity_needed,
                    db=db
                )
            except Exception:
                db.rollback()
                return SaleResponse(
                    success=False,
                    error_type="fefo_error",
                    message="فشل في تخصيص المخزون (FEFO)"
                )
            
            # إنشاء سجلات sale_items وخصم الكميات
            for allocation in fefo_allocation:
                batch_id = uuid.UUID(allocation["batch_id"])
                batch_qty = allocation["quantity"]
                
                # نجيب تفاصيل الشحنة
                batch = db.query(Batch).filter(Batch.id == batch_id).first()
                
                # سعر البيع لهذا الصنف
                unit_price = item.unit_price
                total_price = unit_price * batch_qty
                
                # إنشاء sale_item
                sale_item = SaleItem(
                    id=uuid.uuid4(),
                    sale_id=sale.id,
                    medicine_id=med_uuid,
                    batch_id=batch_id,
                    quantity=batch_qty,
                    unit_name=item.unit_name,
                    unit_price=unit_price,
                    total_price=total_price,
                )
                db.add(sale_item)
                
                # خصم الكمية من الشحنة
                batch.quantity -= batch_qty
                
                # لو الشحنة خلصت، نعطّلها
                if batch.quantity <= 0:
                    batch.is_active = False
                
                sale_items_response.append({
                    "id": str(sale_item.id),
                    "medicine_id": str(med_uuid),
                    "medicine_name": medicine.trade_name,
                    "unit_name": item.unit_name,
                    "quantity": batch_qty,
                    "unit_price": float(unit_price),
                    "total_price": float(total_price),
                    "batch_id": str(batch.id),
                    "batch_number": batch.batch_number,
                    "expiry_date": batch.expiry_date.isoformat() if batch.expiry_date else None
                })
        
        # ============================================================
        # 4. تأكيد Transaction
        # ============================================================
        db.commit()
        
        return SaleResponse(
            success=True,
            sale_id=str(sale.id),
            invoice_number=sale.invoice_number,
            total_amount=float(sale.total_amount),
            payment_method=format_payment_method(sale.payment_method),
            customer_name=sale.customer_name,
            cashier_name=user.full_name if user else None,
            pharmacy_name=pharmacy.name if pharmacy else None,
            items=sale_items_response,
            created_at=sale.created_at.isoformat() if sale.created_at else datetime.now().isoformat(),
            message=f"تم إتمام البيع بنجاح - فاتورة رقم #{invoice_number}"
        )
        
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        import traceback
        traceback.print_exc()  # Log to server logs for debugging
        return SaleResponse(
            success=False,
            message="حدث خطأ أثناء معالجة البيع"
        )


# ═══════════════════════════════════════════════════════════
# المهمة 2: سجل المبيعات مع الفلاتر
# GET /api/sales/
# ═══════════════════════════════════════════════════════════

@router.get("/")
async def get_sales(
    date_filter: Optional[str] = Query(None, description="today, week, month, أو تاريخ YYYY-MM-DD"),
    payment: Optional[str] = Query(None, description="cash, bankak, fory, transfer"),
    user_id: Optional[str] = Query(None, description="معرف الموظف"),
    page: int = Query(1, ge=1, description="رقم الصفحة"),
    per_page: int = Query(50, ge=1, le=200, description="عدد النتائج في الصفحة"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """سجل المبيعات مع الفلاتر."""
    pharmacy_id = current_user["pharmacy_id"]
    
    # بناء الاستعلام الأساسي
    query = """
        SELECT s.id, s.invoice_number, s.total_amount, s.payment_method,
               s.customer_name, s.created_at,
               u.full_name as cashier_name,
               (SELECT COUNT(*) FROM sale_items si WHERE si.sale_id = s.id) as items_count
        FROM sales s
        LEFT JOIN users u ON s.user_id = u.id
        WHERE s.pharmacy_id = :pid
    """
    count_query = "SELECT COUNT(*) FROM sales s WHERE s.pharmacy_id = :pid"
    
    params = {"pid": pharmacy_id}
    
    # فلتر التاريخ
    today = date.today()
    if date_filter == "today":
        query += " AND s.created_at::date = :today"
        count_query += " AND s.created_at::date = :today"
        params["today"] = today
    elif date_filter == "week":
        week_ago = today - timedelta(days=7)
        query += " AND s.created_at::date >= :start_date"
        count_query += " AND s.created_at::date >= :start_date"
        params["start_date"] = week_ago
    elif date_filter == "month":
        month_ago = today - timedelta(days=30)
        query += " AND s.created_at::date >= :start_date"
        count_query += " AND s.created_at::date >= :start_date"
        params["start_date"] = month_ago
    elif date_filter:
        # تاريخ محدد
        query += " AND s.created_at::date = :custom_date"
        count_query += " AND s.created_at::date = :custom_date"
        params["custom_date"] = date_filter
    
    # فلتر طريقة الدفع
    if payment:
        query += " AND s.payment_method = :payment"
        count_query += " AND s.payment_method = :payment"
        params["payment"] = payment
    
    # فلتر الموظف
    if user_id:
        query += " AND s.user_id = :uid"
        count_query += " AND s.user_id = :uid"
        params["uid"] = user_id
    
    # الإجمالي
    total_result = db.execute(text(count_query), params)
    total_sales = total_result.scalar()
    
    # المجموع الكلي
    sum_query = count_query.replace("COUNT(*)", "COALESCE(SUM(s.total_amount), 0)")
    sum_result = db.execute(text(sum_query), params)
    total_amount = float(sum_result.scalar())
    
    # ترتيب وتقسيم الصفحات
    query += " ORDER BY s.created_at DESC"
    offset = (page - 1) * per_page
    query += " LIMIT :limit_val OFFSET :offset_val"
    params["limit_val"] = per_page
    params["offset_val"] = offset
    
    result = db.execute(text(query), params)
    rows = result.fetchall()
    
    sales_list = []
    for row in rows:
        sales_list.append({
            "sale_id": str(row[0]),
            "invoice_number": row[1],
            "total_amount": float(row[2]),
            "payment_method": format_payment_method(row[3]),
            "customer_name": row[4],
            "created_at": row[5].isoformat() if row[5] else "",
            "cashier_name": row[6] or "غير معروف",
            "items_count": row[7]
        })
    
    return {
        "sales": sales_list,
        "total_sales": total_sales,
        "total_amount": total_amount,
        "page": page,
        "per_page": per_page
    }


# ═══════════════════════════════════════════════════════════
# المهمة 3: تفاصيل مبيعة معينة
# GET /api/sales/{sale_id}
# ═══════════════════════════════════════════════════════════

@router.get("/{sale_id}")
async def get_sale_detail(
    sale_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """تفاصيل فاتورة كاملة."""
    pharmacy_id = current_user["pharmacy_id"]
    
    try:
        sale_uuid = uuid.UUID(sale_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="معرف المبيعة غير صالح")
    
    # نجيب المبيعة
    sale = db.query(Sale).filter(
        Sale.id == sale_uuid,
        Sale.pharmacy_id == uuid.UUID(pharmacy_id)
    ).first()
    
    if not sale:
        raise HTTPException(status_code=404, detail="الفاتورة غير موجودة")
    
    # نجيب الموظف
    user = db.query(User).filter(User.id == sale.user_id).first()
    
    # نجيب الصيدلية
    pharmacy = db.query(Pharmacy).filter(Pharmacy.id == sale.pharmacy_id).first()
    
    # نجيب أصناف المبيعة
    items_result = db.execute(
        text("""
            SELECT si.id, si.medicine_id, si.quantity, si.unit_name, 
                   si.unit_price, si.total_price,
                   si.batch_id,
                   m.trade_name as medicine_name,
                   b.batch_number, b.expiry_date
            FROM sale_items si
            LEFT JOIN medicines m ON si.medicine_id = m.id
            LEFT JOIN batches b ON si.batch_id = b.id
            WHERE si.sale_id = :sid
            ORDER BY m.trade_name
        """),
        {"sid": sale_uuid}
    )
    
    items = []
    for row in items_result.fetchall():
        items.append({
            "id": str(row[0]),
            "medicine_id": str(row[1]),
            "quantity": row[2],
            "unit_name": row[3],
            "unit_price": float(row[4]),
            "total_price": float(row[5]),
            "batch_id": str(row[6]) if row[6] else None,
            "medicine_name": row[7] or "غير معروف",
            "batch_number": row[8],
            "expiry_date": row[9].isoformat() if row[9] else None
        })
    
    return {
        "success": True,
        "sale_id": str(sale.id),
        "invoice_number": sale.invoice_number,
        "total_amount": float(sale.total_amount),
        "payment_method": format_payment_method(sale.payment_method),
        "customer_name": sale.customer_name,
        "cashier_name": user.full_name if user else None,
        "pharmacy_name": pharmacy.name if pharmacy else None,
        "items": items,
        "created_at": sale.created_at.isoformat() if sale.created_at else None
    }


# ═══════════════════════════════════════════════════════════
# المهمة 4: بحث سريع لـ POS
# GET /api/pos/search?q=بانادول
# ═══════════════════════════════════════════════════════════

@router.get("/pos/search", tags=["pos"])
async def pos_search(
    q: str = Query("", min_length=1, description="نص البحث"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """بحث سريع في POS بالاسم أو الباركود."""
    pharmacy_id = current_user["pharmacy_id"]
    search_term = f"%{q}%"
    
    # البحث في الاسم التجاري والعلمي والباركود
    medicines = db.query(Medicine).filter(
        Medicine.pharmacy_id == uuid.UUID(pharmacy_id),
        (
            Medicine.trade_name.ilike(search_term) |
            Medicine.scientific_name.ilike(search_term) |
            Medicine.barcode.ilike(search_term)
        )
    ).limit(20).all()
    
    results = []
    today = date.today()
    
    for med in medicines:
        # حساب المخزون المتاح
        stock_result = db.execute(
            text("""
                SELECT COALESCE(SUM(quantity), 0) 
                FROM batches 
                WHERE medicine_id = :mid 
                AND is_active = true 
                AND quantity > 0 
                AND expiry_date > :today
            """),
            {"mid": med.id, "today": today}
        )
        available = stock_result.scalar()
        
        # نجيب الوحدات
        units_result = db.execute(
            text("""
                SELECT unit_name, sale_price, conversion_factor
                FROM units 
                WHERE medicine_id = :mid
                ORDER BY conversion_factor DESC
            """),
            {"mid": med.id}
        )
        
        units = []
        for u in units_result.fetchall():
            units.append({
                "unit_name": u[0],
                "sale_price": float(u[1]) if u[1] else float(med.sale_price),
                "conversion_factor": float(u[2])
            })
        
        # إذا ما في وحدات، نضيف الوحدة الأساسية
        if not units:
            units.append({
                "unit_name": med.base_unit or "شريط",
                "sale_price": float(med.sale_price),
                "conversion_factor": 1.0
            })
        
        image_url = f"/static/medicines/{med.id}.jpg" if med.image_path else None
        
        results.append({
            "medicine_id": str(med.id),
            "trade_name": med.trade_name,
            "scientific_name": med.scientific_name,
            "sale_price": float(med.sale_price),
            "available_stock": available,
            "image_url": image_url,
            "units": units
        })
    
    return {"results": results}


# ═══════════════════════════════════════════════════════════
# المهمة 5: الأدوية الأكثر مبيعاً
# GET /api/pos/quick-medicines
# ═══════════════════════════════════════════════════════════

@router.get("/pos/quick-medicines", tags=["pos"])
async def quick_medicines(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """أعلى 6 أدوية مبيعاً في آخر 30 يوم."""
    pharmacy_id = current_user["pharmacy_id"]
    thirty_days_ago = date.today() - timedelta(days=30)
    
    # الأدوية الأكثر تكراراً في المبيعات (آخر 30 يوم)
    result = db.execute(
        text("""
            SELECT m.id, m.trade_name, m.sale_price, m.image_path,
                   COUNT(si.id) as sale_count
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            JOIN medicines m ON si.medicine_id = m.id
            WHERE s.pharmacy_id = :pid
            AND s.created_at::date >= :start_date
            GROUP BY m.id, m.trade_name, m.sale_price, m.image_path
            ORDER BY sale_count DESC
            LIMIT 6
        """),
        {"pid": pharmacy_id, "start_date": thirty_days_ago}
    )
    
    top_medicines = result.fetchall()
    
    # لو ما في مبيعات سابقة، نجيب أي 6 أدوية عندها مخزون
    if not top_medicines:
        today = date.today()
        result = db.execute(
            text("""
                SELECT m.id, m.trade_name, m.sale_price, m.image_path
                FROM medicines m
                WHERE m.pharmacy_id = :pid
                AND EXISTS (
                    SELECT 1 FROM batches b 
                    WHERE b.medicine_id = m.id 
                    AND b.is_active = true 
                    AND b.quantity > 0 
                    AND b.expiry_date > :today
                )
                LIMIT 6
            """),
            {"pid": pharmacy_id, "today": today}
        )
        top_medicines = result.fetchall()
    
    medicines = []
    for row in top_medicines:
        image_url = f"/static/medicines/{row[0]}.jpg" if row[3] else None
        medicines.append({
            "medicine_id": str(row[0]),
            "trade_name": row[1],
            "sale_price": float(row[2]),
            "image_url": image_url
        })
    
    return {"medicines": medicines}


# ═══════════════════════════════════════════════════════════
# المهمة 6: مسح الباركود (لـ POS)
# GET /api/pos/barcode/{barcode}
# ═══════════════════════════════════════════════════════════

@router.get("/pos/barcode/{barcode}", tags=["pos"])
async def pos_barcode_search(
    barcode: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """بحث بالباركود لـ POS."""
    pharmacy_id = current_user["pharmacy_id"]
    
    medicine = db.query(Medicine).filter(
        Medicine.pharmacy_id == uuid.UUID(pharmacy_id),
        Medicine.barcode == barcode
    ).first()
    
    if not medicine:
        return {"found": False, "medicine": None, "barcode": barcode}
    
    today = date.today()
    stock_result = db.execute(
        text("""
            SELECT COALESCE(SUM(quantity), 0) 
            FROM batches 
            WHERE medicine_id = :mid 
            AND is_active = true 
            AND quantity > 0 
            AND expiry_date > :today
        """),
        {"mid": medicine.id, "today": today}
    )
    available = stock_result.scalar()
    
    # نجيب الوحدات
    units_result = db.execute(
        text("""
            SELECT unit_name, sale_price, conversion_factor
            FROM units 
            WHERE medicine_id = :mid
            ORDER BY conversion_factor DESC
        """),
        {"mid": medicine.id}
    )
    
    units = []
    for u in units_result.fetchall():
        units.append({
            "unit_name": u[0],
            "sale_price": float(u[1]) if u[1] else float(medicine.sale_price),
            "conversion_factor": float(u[2])
        })
    
    if not units:
        units.append({
            "unit_name": medicine.base_unit or "شريط",
            "sale_price": float(medicine.sale_price),
            "conversion_factor": 1.0
        })
    
    image_url = f"/static/medicines/{medicine.id}.jpg" if medicine.image_path else None
    
    return {
        "found": True,
        "medicine": {
            "medicine_id": str(medicine.id),
            "trade_name": medicine.trade_name,
            "scientific_name": medicine.scientific_name,
            "sale_price": float(medicine.sale_price),
            "available_stock": available,
            "image_url": image_url,
            "units": units
        },
        "barcode": barcode
    }


# ═══════════════════════════════════════════════════════════
# المهمة 7: عرض الفاتورة العامة (بدون JWT)
# GET /api/public/invoice/{invoice_number}
# ═══════════════════════════════════════════════════════════

# This endpoint is mounted in main.py under /api/public prefix
# No JWT required - anyone with the link can view

public_router = APIRouter(prefix="/api/public", tags=["public"])


@public_router.get("/invoice/{invoice_number}")
async def get_public_invoice(
    invoice_number: int,
    db: Session = Depends(get_db)
):
    """
    عرض الفاتورة للعميل (بدون تسجيل دخول).
    تُستخدم عند مسح QR Code من الفاتورة.
    """
    # نجيب المبيعة برقم الفاتورة
    sale = db.query(Sale).filter(
        Sale.invoice_number == invoice_number
    ).first()
    
    if not sale:
        raise HTTPException(status_code=404, detail="الفاتورة غير موجودة")
    
    # نجيب الموظف
    user = db.query(User).filter(User.id == sale.user_id).first()
    
    # نجيب الصيدلية
    pharmacy = db.query(Pharmacy).filter(Pharmacy.id == sale.pharmacy_id).first()
    
    # نجيب أصناف المبيعة
    items_result = db.execute(
        text("""
            SELECT si.id, si.medicine_id, si.quantity, si.unit_name, 
                   si.unit_price, si.total_price,
                   si.batch_id,
                   m.trade_name as medicine_name,
                   b.batch_number, b.expiry_date
            FROM sale_items si
            LEFT JOIN medicines m ON si.medicine_id = m.id
            LEFT JOIN batches b ON si.batch_id = b.id
            WHERE si.sale_id = :sid
            ORDER BY m.trade_name
        """),
        {"sid": sale.id}
    )
    
    items = []
    for row in items_result.fetchall():
        items.append({
            "id": str(row[0]),
            "medicine_id": str(row[1]),
            "quantity": row[2],
            "unit_name": row[3],
            "unit_price": float(row[4]),
            "total_price": float(row[5]),
            "batch_id": str(row[6]) if row[6] else None,
            "medicine_name": row[7] or "غير معروف",
            "batch_number": row[8],
            "expiry_date": row[9].isoformat() if row[9] else None
        })
    
    return {
        "success": True,
        "sale_id": str(sale.id),
        "invoice_number": sale.invoice_number,
        "total_amount": float(sale.total_amount),
        "payment_method": format_payment_method(sale.payment_method),
        "customer_name": sale.customer_name,
        "cashier_name": user.full_name if user else None,
        "pharmacy_name": pharmacy.name if pharmacy else None,
        "items": items,
        "created_at": sale.created_at.isoformat() if sale.created_at else None
    }


# ✅ انتهى - sales.py - المرحلة 5
