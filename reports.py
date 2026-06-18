"""
PharmaSUD - Reports & Dashboard Module (Stage 6)
Version 6.0.0

يتولى:
- المهمة 1: الداشبورد الرئيسي (إحصائيات اليوم، تنبيهات، رسم بياني)
- المهمة 2: تقرير المبيعات (فلاتر التاريخ/الدفع/الكاشير)
- المهمة 3: تقرير الأرباح (Admin only)
- المهمة 4: الأدوية الراكدة (لم تُبَع منذ 30+ يوم)
- المهمة 5: توقعات الشراء الذكية (معدل البيع اليومي)
"""

import uuid
from datetime import datetime, date, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from models import DashboardResponse, SalesReportResponse, ProfitReportResponse, SlowMovingResponse, PurchaseForecastResponse
from auth import get_current_user, require_admin, require_permission

# Create router for reports API
router = APIRouter(prefix="/api/reports", tags=["reports"])


# ═══════════════════════════════════════════════════════════
# دالة مساعدة: تحويل تاريخ لأنواع مختلفة
# ═══════════════════════════════════════════════════════════

def parse_date_range(period: str, start_date: str = None, end_date: str = None):
    """تحويل الفترة إلى تاريخ بداية ونهاية.
    
    Args:
        period: today|yesterday|week|month|custom
        start_date: تاريخ بداية مخصص (للفترة المخصصة)
        end_date: تاريخ نهاية مخصص
    
    Returns:
        tuple: (start_datetime, end_datetime)
    """
    today = date.today()
    
    if period == "today":
        return today, today
    elif period == "yesterday":
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday
    elif period == "week":
        week_ago = today - timedelta(days=7)
        return week_ago, today
    elif period == "month":
        month_ago = today - timedelta(days=30)
        return month_ago, today
    elif period == "custom" and start_date and end_date:
        try:
            sd = datetime.strptime(start_date, "%Y-%m-%d").date()
            ed = datetime.strptime(end_date, "%Y-%m-%d").date()
            return sd, ed
        except ValueError:
            raise HTTPException(status_code=400, detail="تاريخ غير صالح. استخدم YYYY-MM-DD")
    else:
        # Default to today
        return today, today


def format_currency(value) -> float:
    """تحويل القيمة إلى float."""
    return float(value) if value else 0.0


ARABIC_MONTHS = {
    1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل",
    5: "مايو", 6: "يونيو", 7: "يوليو", 8: "أغسطس",
    9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر"
}

ARABIC_DAYS = {
    0: "الأحد", 1: "الاثنين", 2: "الثلاثاء", 3: "الأربعاء",
    4: "الخميس", 5: "الجمعة", 6: "السبت"
}


# ═══════════════════════════════════════════════════════════
# المهمة 1: الداشبورد الرئيسي
# GET /api/reports/dashboard
# ═══════════════════════════════════════════════════════════

@router.get("/dashboard")
async def get_dashboard(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """الداشبورد الرئيسي: إحصائيات اليوم، تنبيهات، رسم بياني لآخر 7 أيام."""
    pharmacy_id = current_user["pharmacy_id"]
    
    # ── إيرادات وعدد فواتير اليوم ──
    today_result = db.execute(text("""
        SELECT
            COALESCE(SUM(s.total_amount), 0) as revenue,
            COUNT(s.id) as invoices_count
        FROM sales s
        WHERE s.pharmacy_id = :pid
          AND DATE(s.created_at) = CURRENT_DATE
    """), {"pid": pharmacy_id}).first()
    
    today_revenue = format_currency(today_result[0])
    today_invoices = today_result[1]
    
    # ── ربح اليوم ──
    profit_result = db.execute(text("""
        SELECT COALESCE(
            SUM(si.quantity * si.unit_price) -
            SUM(si.quantity * COALESCE(b.purchase_price, 0))
        , 0) as profit
        FROM sale_items si
        JOIN batches b ON si.batch_id = b.id
        JOIN sales s ON si.sale_id = s.id
        WHERE s.pharmacy_id = :pid
          AND DATE(s.created_at) = CURRENT_DATE
    """), {"pid": pharmacy_id}).first()
    
    today_profit = format_currency(profit_result[0])
    
    # ── أكثر الأدوية مبيعاً اليوم ──
    top_meds = db.execute(text("""
        SELECT
            m.trade_name,
            SUM(si.quantity)::INTEGER as quantity_sold,
            SUM(si.total_price) as revenue
        FROM sale_items si
        JOIN medicines m ON si.medicine_id = m.id
        JOIN sales s ON si.sale_id = s.id
        WHERE s.pharmacy_id = :pid
          AND DATE(s.created_at) = CURRENT_DATE
        GROUP BY m.id, m.trade_name
        ORDER BY quantity_sold DESC
        LIMIT 5
    """), {"pid": pharmacy_id}).fetchall()
    
    top_medicines = []
    for m in top_meds:
        top_medicines.append({
            "trade_name": m[0],
            "quantity_sold": m[1],
            "revenue": format_currency(m[2])
        })
    
    # ── ملخص المخزون ──
    inv_result = db.execute(text("""
        SELECT
            COUNT(DISTINCT m.id)::INTEGER as total_medicines,
            COUNT(DISTINCT CASE WHEN COALESCE(cs.total_stock, 0) < m.min_stock THEN m.id END)::INTEGER as low_stock_count
        FROM medicines m
        LEFT JOIN (
            SELECT medicine_id, SUM(quantity) as total_stock
            FROM batches
            WHERE is_active = true AND quantity > 0 AND expiry_date > NOW()
            GROUP BY medicine_id
        ) cs ON m.id = cs.medicine_id
        WHERE m.pharmacy_id = :pid
    """), {"pid": pharmacy_id}).first()
    
    total_medicines = inv_result[0] if inv_result else 0
    low_stock_count = inv_result[1] if inv_result else 0
    
    # ── الأدوية القريبة من الانتهاء (خلال 90 يوم) ──
    expiring_count = db.execute(text("""
        SELECT COUNT(DISTINCT b.medicine_id)::INTEGER
        FROM batches b
        JOIN medicines m ON b.medicine_id = m.id
        WHERE m.pharmacy_id = :pid
          AND b.is_active = true
          AND b.quantity > 0
          AND b.expiry_date BETWEEN NOW() AND NOW() + INTERVAL '90 days'
    """), {"pid": pharmacy_id}).scalar() or 0
    
    # ── التنبيهات ──
    # 1. إنذارات الصلاحية (أقرب 5)
    expiry_alerts = db.execute(text("""
        SELECT
            m.trade_name,
            b.batch_number,
            EXTRACT(DAY FROM b.expiry_date - NOW())::INTEGER as days_remaining
        FROM batches b
        JOIN medicines m ON b.medicine_id = m.id
        WHERE m.pharmacy_id = :pid
          AND b.is_active = true
          AND b.quantity > 0
          AND b.expiry_date BETWEEN NOW() AND NOW() + INTERVAL '90 days'
        ORDER BY b.expiry_date ASC
        LIMIT 5
    """), {"pid": pharmacy_id}).fetchall()
    
    # 2. إنذارات المخزون المنخفض (أقرب 5)
    low_stock_alerts = db.execute(text("""
        SELECT
            m.trade_name,
            COALESCE(cs.total_stock, 0)::INTEGER as current_stock,
            m.min_stock
        FROM medicines m
        LEFT JOIN (
            SELECT medicine_id, SUM(quantity) as total_stock
            FROM batches
            WHERE is_active = true AND quantity > 0 AND expiry_date > NOW()
            GROUP BY medicine_id
        ) cs ON m.id = cs.medicine_id
        WHERE m.pharmacy_id = :pid
          AND COALESCE(cs.total_stock, 0) < m.min_stock
        ORDER BY (COALESCE(cs.total_stock, 0)::FLOAT / NULLIF(m.min_stock, 0)) ASC
        LIMIT 5
    """), {"pid": pharmacy_id}).fetchall()
    
    alerts = []
    for a in expiry_alerts:
        days = a[2]
        if days is not None and days <= 30:
            severity = "high"
        elif days is not None and days <= 90:
            severity = "medium"
        else:
            severity = "low"
        alerts.append({
            "type": "expiry_warning",
            "medicine_name": a[0],
            "batch": a[1],
            "days_remaining": days,
            "severity": severity
        })
    
    for a in low_stock_alerts:
        current = a[1] or 0
        min_stock = a[2] or 10
        ratio = current / max(min_stock, 1)
        severity = "high" if ratio < 0.3 else ("medium" if ratio < 0.6 else "low")
        alerts.append({
            "type": "low_stock",
            "medicine_name": a[0],
            "current_stock": current,
            "min_stock": min_stock,
            "severity": severity
        })
    
    # ترتيب التنبيهات: الأخطر أولاً
    severity_order = {"high": 0, "medium": 1, "low": 2}
    alerts.sort(key=lambda x: severity_order.get(x.get("severity", "low"), 3))
    
    # ── مبيعات آخر 7 أيام (رسم بياني) ──
    weekly = db.execute(text("""
        SELECT
            DATE(s.created_at) as sale_date,
            COALESCE(SUM(s.total_amount), 0) as revenue
        FROM sales s
        WHERE s.pharmacy_id = :pid
          AND s.created_at >= NOW() - INTERVAL '7 days'
        GROUP BY DATE(s.created_at)
        ORDER BY sale_date ASC
    """), {"pid": pharmacy_id}).fetchall()
    
    weekly_chart = []
    seen_dates = set()
    for w in weekly:
        d = w[0]
        seen_dates.add(str(d))
        day_of_week = d.weekday()
        day_name = ARABIC_DAYS.get(day_of_week, "")
        weekly_chart.append({
            "date": str(d),
            "day_name": day_name,
            "revenue": format_currency(w[1])
        })
    
    # Fill in missing days with 0
    today = date.today()
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        d_str = str(d)
        if d_str not in seen_dates:
            day_of_week = d.weekday()
            day_name = ARABIC_DAYS.get(day_of_week, "")
            weekly_chart.append({
                "date": d_str,
                "day_name": day_name,
                "revenue": 0.0
            })
    weekly_chart.sort(key=lambda x: x["date"])
    
    return {
        "today": {
            "revenue": today_revenue,
            "invoices_count": today_invoices,
            "profit": today_profit,
            "top_medicines": top_medicines
        },
        "inventory_summary": {
            "total_medicines": total_medicines,
            "low_stock_count": low_stock_count,
            "expiring_soon_count": expiring_count
        },
        "alerts": alerts,
        "weekly_chart": weekly_chart
    }


# ═══════════════════════════════════════════════════════════
# المهمة 2: تقرير المبيعات
# GET /api/reports/sales
# ═══════════════════════════════════════════════════════════

@router.get("/sales")
async def get_sales_report(
    period: str = Query("today", description="today|yesterday|week|month|custom"),
    start_date: Optional[str] = Query(None, description="تاريخ البداية (لـ custom) YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="تاريخ النهاية (لـ custom) YYYY-MM-DD"),
    payment_method: str = Query("all", description="all|cash|bankak|fory|transfer"),
    user_id: str = Query("all", description="all|uuid"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """تقرير المبيعات مع فلاتر التاريخ وطريقة الدفع والكاشير."""
    pharmacy_id = current_user["pharmacy_id"]
    
    # تحديد نطاق التاريخ
    start_date_obj, end_date_obj = parse_date_range(period, start_date, end_date)
    
    # ── بناء الاستعلام الأساسي ──
    query = """
        SELECT
            s.invoice_number,
            s.created_at,
            s.total_amount,
            s.payment_method,
            s.customer_name,
            u.full_name as cashier_name,
            COUNT(si.id)::INTEGER as items_count
        FROM sales s
        JOIN users u ON s.user_id = u.id
        LEFT JOIN sale_items si ON s.id = si.sale_id
        WHERE s.pharmacy_id = :pid
          AND DATE(s.created_at) BETWEEN :start_date AND :end_date
    """
    params = {"pid": pharmacy_id, "start_date": start_date_obj, "end_date": end_date_obj}
    
    # فلتر طريقة الدفع
    if payment_method != "all":
        pm_map = {"cash": "cash", "bankak": "bankak", "fory": "fory", "transfer": "transfer"}
        mapped = pm_map.get(payment_method)
        if mapped:
            query += " AND s.payment_method = :payment_method"
            params["payment_method"] = mapped
    
    # فلتر الكاشير
    if user_id != "all":
        try:
            uid = uuid.UUID(user_id)
            query += " AND s.user_id = :uid"
            params["uid"] = str(uid)
        except ValueError:
            pass  # تجاهل UUID غير صالح
    
    query += " GROUP BY s.id, u.full_name ORDER BY s.created_at DESC"
    
    sales_result = db.execute(text(query), params).fetchall()
    
    # ── حساب ملخص الفترة ──
    total_revenue = sum(float(r[2]) for r in sales_result) if sales_result else 0
    invoices_count = len(sales_result)
    avg_invoice = total_revenue / invoices_count if invoices_count > 0 else 0
    
    # ── توزيع طرق الدفع ──
    payment_totals = {"cash": {"amount": 0, "count": 0},
                      "bankak": {"amount": 0, "count": 0},
                      "fory": {"amount": 0, "count": 0},
                      "transfer": {"amount": 0, "count": 0}}
    for r in sales_result:
        pm = r[3] or "cash"
        amt = float(r[2])
        if pm in payment_totals:
            payment_totals[pm]["amount"] += amt
            payment_totals[pm]["count"] += 1
    
    payment_breakdown = {}
    for pm, data in payment_totals.items():
        pct = round((data["amount"] / total_revenue * 100), 1) if total_revenue > 0 else 0
        payment_breakdown[pm] = {
            "amount": round(data["amount"], 2),
            "count": data["count"],
            "percentage": pct
        }
    
    # ── أعلى الأيام ──
    daily_totals = {}
    for r in sales_result:
        day_str = str(r[1].date()) if hasattr(r[1], 'date') else str(r[1])[:10]
        if day_str not in daily_totals:
            daily_totals[day_str] = {"revenue": 0, "count": 0}
        daily_totals[day_str]["revenue"] += float(r[2])
        daily_totals[day_str]["count"] += 1
    
    top_days = sorted(daily_totals.items(), key=lambda x: x[1]["revenue"], reverse=True)[:5]
    
    # ── قائمة المبيعات ──
    sales_list = []
    for r in sales_result:
        sales_list.append({
            "invoice_number": r[0],
            "created_at": r[1].isoformat() if hasattr(r[1], 'isoformat') else str(r[1]),
            "cashier_name": r[5] or "غير معروف",
            "payment_method": r[3] or "cash",
            "customer_name": r[4],
            "total_amount": float(r[2]),
            "items_count": r[6]
        })
    
    return {
        "summary": {
            "total_revenue": round(total_revenue, 2),
            "invoices_count": invoices_count,
            "average_invoice": round(avg_invoice, 2),
            "payment_breakdown": payment_breakdown,
            "top_days": [
                {"date": d, "revenue": round(t["revenue"], 2), "invoices": t["count"]}
                for d, t in top_days
            ]
        },
        "sales": sales_list,
        "total_records": invoices_count
    }


# ═══════════════════════════════════════════════════════════
# المهمة 3: تقرير الأرباح (Admin Only)
# GET /api/reports/profits
# ═══════════════════════════════════════════════════════════

@router.get("/profits", dependencies=[Depends(require_permission("profit.view"))])
async def get_profit_report(
    period: str = Query("month", description="today|yesterday|week|month|custom"),
    start_date: Optional[str] = Query(None, description="تاريخ البداية YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="تاريخ النهاية YYYY-MM-DD"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """تقرير الأرباح — يتطلب صلاحية profit.view."""

    pharmacy_id = current_user["pharmacy_id"]
    start_date_obj, end_date_obj = parse_date_range(period, start_date, end_date)
    params = {"pid": pharmacy_id, "start_date": start_date_obj, "end_date": end_date_obj}
    
    # ── الأرباح حسب الدواء ──
    profit_rows = db.execute(text("""
        SELECT
            m.trade_name,
            SUM(si.quantity)::INTEGER as quantity_sold,
            SUM(si.quantity * si.unit_price) as revenue,
            SUM(si.quantity * COALESCE(b.purchase_price, 0)) as cost,
            SUM(si.quantity * si.unit_price) -
            SUM(si.quantity * COALESCE(b.purchase_price, 0)) as profit,
            ROUND(
                (SUM(si.quantity * si.unit_price) -
                 SUM(si.quantity * COALESCE(b.purchase_price, 0))) /
                NULLIF(SUM(si.quantity * si.unit_price), 0) * 100
            , 2) as margin_percentage
        FROM sale_items si
        JOIN medicines m ON si.medicine_id = m.id
        JOIN batches b ON si.batch_id = b.id
        JOIN sales s ON si.sale_id = s.id
        WHERE s.pharmacy_id = :pid
          AND DATE(s.created_at) BETWEEN :start_date AND :end_date
        GROUP BY m.id, m.trade_name
        ORDER BY profit DESC
    """), params).fetchall()
    
    # ── إجمالي الملخص ──
    total_revenue = sum(float(r[2]) for r in profit_rows) if profit_rows else 0
    total_cost = sum(float(r[3]) for r in profit_rows) if profit_rows else 0
    net_profit = total_revenue - total_cost
    profit_margin = round((net_profit / total_revenue * 100), 2) if total_revenue > 0 else 0
    
    by_medicine = []
    for r in profit_rows:
        by_medicine.append({
            "trade_name": r[0],
            "quantity_sold": r[1],
            "revenue": float(r[2]),
            "cost": float(r[3]),
            "profit": float(r[4]),
            "margin_percentage": r[5] if r[5] else 0.0
        })
    
    # ── مقارنة الأشهر (آخر 6 أشهر) ──
    monthly = db.execute(text("""
        SELECT
            TO_CHAR(s.created_at, 'YYYY-MM') as month,
            SUM(si.quantity * si.unit_price) -
            SUM(si.quantity * COALESCE(b.purchase_price, 0)) as profit
        FROM sale_items si
        JOIN batches b ON si.batch_id = b.id
        JOIN sales s ON si.sale_id = s.id
        WHERE s.pharmacy_id = :pid
          AND s.created_at >= NOW() - INTERVAL '6 months'
        GROUP BY TO_CHAR(s.created_at, 'YYYY-MM')
        ORDER BY month ASC
    """), {"pid": pharmacy_id}).fetchall()
    
    monthly_comparison = []
    for m in monthly:
        month_parts = m[0].split("-")
        month_num = int(month_parts[1])
        month_name = ARABIC_MONTHS.get(month_num, m[0])
        monthly_comparison.append({
            "month": m[0],
            "month_name": month_name,
            "profit": float(m[1]) if m[1] else 0.0
        })
    
    return {
        "summary": {
            "total_revenue": round(total_revenue, 2),
            "total_cost": round(total_cost, 2),
            "net_profit": round(net_profit, 2),
            "profit_margin": profit_margin
        },
        "by_medicine": by_medicine,
        "monthly_comparison": monthly_comparison
    }


# ═══════════════════════════════════════════════════════════
# المهمة 4: الأدوية الراكدة
# GET /api/reports/slow-moving
# ═══════════════════════════════════════════════════════════

@router.get("/slow-moving")
async def get_slow_moving(
    days: int = Query(30, ge=1, le=365, description="عدد الأيام بدون بيع"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """الأدوية الراكدة — لم تُبَع منذ X يوم."""
    pharmacy_id = current_user["pharmacy_id"]
    
    rows = db.execute(text("""
        WITH last_sales AS (
            SELECT
                si.medicine_id,
                MAX(s.created_at) as last_sale_date,
                EXTRACT(DAY FROM NOW() - MAX(s.created_at))::INTEGER as days_since_last_sale
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            WHERE s.pharmacy_id = :pid
            GROUP BY si.medicine_id
        ),
        current_stock AS (
            SELECT
                b.medicine_id,
                SUM(b.quantity)::INTEGER as total_stock,
                MIN(b.expiry_date) as nearest_expiry,
                SUM(b.quantity * COALESCE(b.purchase_price, 0)) as stock_value
            FROM batches b
            WHERE b.is_active = true
              AND b.quantity > 0
              AND b.expiry_date > NOW()
            GROUP BY b.medicine_id
            HAVING SUM(b.quantity) > 0
        )
        SELECT
            m.id as medicine_id,
            m.trade_name,
            m.base_unit,
            COALESCE(cs.total_stock, 0)::INTEGER as total_stock,
            cs.nearest_expiry,
            COALESCE(cs.stock_value, 0) as stock_value,
            ls.last_sale_date,
            COALESCE(ls.days_since_last_sale, 999)::INTEGER as days_since_last_sale,
            EXTRACT(DAY FROM cs.nearest_expiry - NOW())::INTEGER as days_to_expiry
        FROM medicines m
        JOIN current_stock cs ON m.id = cs.medicine_id
        LEFT JOIN last_sales ls ON m.id = ls.medicine_id
        WHERE m.pharmacy_id = :pid
          AND (ls.last_sale_date < NOW() - (:days || ' days')::INTERVAL OR ls.last_sale_date IS NULL)
        ORDER BY days_since_last_sale DESC
    """), {"pid": pharmacy_id, "days": days}).fetchall()
    
    total_value = 0
    medicines_list = []
    
    for r in rows:
        med_id = str(r[0])
        trade_name = r[1]
        base_unit = r[2] or "شريط"
        total_stock = r[3] if r[3] else 0
        nearest_expiry = r[4]
        stock_value = float(r[5]) if r[5] else 0
        last_sale_date = r[6]
        days_since_last_sale = r[7] if r[7] else 999
        days_to_expiry = r[8] if r[8] else None
        
        # منطق تحديد الخطر
        if days_to_expiry is not None and days_to_expiry < 90 and days_since_last_sale > 30:
            risk_level = "critical"  # خطر مزدوج: راكد + قريب الانتهاء
        elif days_since_last_sale > 60:
            risk_level = "high"
        elif days_since_last_sale > 30:
            risk_level = "medium"
        else:
            risk_level = "low"
        
        total_value += stock_value
        
        medicines_list.append({
            "medicine_id": med_id,
            "trade_name": trade_name,
            "total_stock": total_stock,
            "base_unit": base_unit,
            "last_sale_date": last_sale_date.isoformat() if hasattr(last_sale_date, 'isoformat') else (str(last_sale_date) if last_sale_date else None),
            "days_since_last_sale": days_since_last_sale,
            "nearest_expiry": nearest_expiry.isoformat() if hasattr(nearest_expiry, 'isoformat') else (str(nearest_expiry) if nearest_expiry else None),
            "days_to_expiry": days_to_expiry,
            "stock_value": stock_value,
            "risk_level": risk_level
        })
    
    return {
        "total_slow_moving_value": round(total_value, 2),
        "medicines": medicines_list
    }


# ═══════════════════════════════════════════════════════════
# المهمة 5: توقعات الشراء الذكية
# GET /api/reports/purchase-forecast
# ═══════════════════════════════════════════════════════════

@router.get("/purchase-forecast")
async def get_purchase_forecast(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """توقعات الشراء بناءً على معدل البيع اليومي لآخر 30 يوم."""
    pharmacy_id = current_user["pharmacy_id"]
    
    rows = db.execute(text("""
        WITH daily_avg AS (
            SELECT
                si.medicine_id,
                CASE
                    WHEN EXTRACT(DAY FROM NOW() - MIN(s.created_at)) = 0
                    THEN COALESCE(SUM(si.quantity), 0)::FLOAT
                    ELSE COALESCE(SUM(si.quantity), 0)::FLOAT /
                         NULLIF(EXTRACT(DAY FROM NOW() - MIN(s.created_at)), 0)
                END as avg_daily_sales
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            WHERE s.pharmacy_id = :pid
              AND s.created_at >= NOW() - INTERVAL '30 days'
            GROUP BY si.medicine_id
        ),
        current_stock AS (
            SELECT
                medicine_id,
                SUM(quantity)::INTEGER as total_stock
            FROM batches
            WHERE is_active = true
              AND quantity > 0
              AND expiry_date > NOW()
            GROUP BY medicine_id
        )
        SELECT
            m.id as medicine_id,
            m.trade_name,
            m.base_unit,
            COALESCE(cs.total_stock, 0)::INTEGER as current_stock,
            COALESCE(da.avg_daily_sales, 0)::FLOAT as avg_daily_sales,
            CASE
                WHEN COALESCE(da.avg_daily_sales, 0) = 0 THEN 999
                ELSE GREATEST(ROUND(COALESCE(cs.total_stock, 0)::FLOAT / da.avg_daily_sales), 0)::INTEGER
            END as days_remaining,
            CASE
                WHEN COALESCE(da.avg_daily_sales, 0) = 0 THEN NULL
                ELSE (CURRENT_DATE + (COALESCE(cs.total_stock, 0)::FLOAT / da.avg_daily_sales) * INTERVAL '1 day')::DATE
            END as expected_runout_date,
            GREATEST(CEIL(COALESCE(da.avg_daily_sales, 0) * 30), 0)::INTEGER as suggested_order_quantity
        FROM medicines m
        LEFT JOIN current_stock cs ON m.id = cs.medicine_id
        LEFT JOIN daily_avg da ON m.id = da.medicine_id
        WHERE m.pharmacy_id = :pid
          AND COALESCE(cs.total_stock, 0) > 0
        ORDER BY days_remaining ASC
    """), {"pid": pharmacy_id}).fetchall()
    
    forecast_list = []
    priority_counts = {"critical": 0, "high": 0, "medium": 0, "ok": 0}
    
    for r in rows:
        med_id = str(r[0])
        trade_name = r[1]
        base_unit = r[2] or "شريط"
        current_stock = r[3] if r[3] else 0
        avg_daily_sales = float(r[4]) if r[4] else 0.0
        days_remaining = r[5] if r[5] else 999
        expected_runout = r[6]
        suggested_order = r[7] if r[7] else 0
        
        # تحديد الأولوية
        if days_remaining <= 7:
            priority = "critical"
            priority_label = "اشترِ الآن فوراً"
        elif days_remaining <= 14:
            priority = "high"
            priority_label = "اشترِ هذا الأسبوع"
        elif days_remaining <= 30:
            priority = "medium"
            priority_label = "خطط للشراء"
        else:
            priority = "ok"
            priority_label = "لا حاجة الآن"
        
        priority_counts[priority] = priority_counts.get(priority, 0) + 1
        
        forecast_list.append({
            "medicine_id": med_id,
            "trade_name": trade_name,
            "base_unit": base_unit,
            "current_stock": current_stock,
            "avg_daily_sales": round(avg_daily_sales, 1),
            "days_remaining": days_remaining,
            "expected_runout_date": expected_runout.isoformat() if hasattr(expected_runout, 'isoformat') else (str(expected_runout) if expected_runout else None),
            "suggested_order_quantity": suggested_order,
            "priority": priority,
            "priority_label": priority_label
        })
    
    return {
        "forecast": forecast_list,
        "summary": {
            "critical_count": priority_counts.get("critical", 0),
            "high_count": priority_counts.get("high", 0),
            "medium_count": priority_counts.get("medium", 0),
            "ok_count": priority_counts.get("ok", 0)
        }
    }


# ✅ انتهى - reports.py - المرحلة 6