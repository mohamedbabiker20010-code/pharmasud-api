"""
PharmaSUD - Alerts Module (Stage 7)
Version 7.0.0

يتولى:
- تنبيهات الصلاحية (critical / warning)
- تنبيهات المخزون المنخفض
- عداد التنبيهات للجرس 🔔
"""

from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from auth import get_current_user

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("/")
async def get_alerts(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """نظام التنبيهات الموحد: صلاحية + مخزون."""
    pharmacy_id = current_user["pharmacy_id"]

    # ═══════════════════════════════════════════════════
    # تنبيهات الصلاحية
    # ═══════════════════════════════════════════════════
    expiry_rows = db.execute(text("""
        SELECT
            m.id as medicine_id,
            m.trade_name,
            b.batch_number,
            b.expiry_date,
            EXTRACT(DAY FROM b.expiry_date - NOW())::INTEGER as days_remaining,
            CASE
                WHEN b.expiry_date - NOW() < INTERVAL '30 days'
                    THEN 'critical'
                ELSE 'warning'
            END as severity
        FROM batches b
        JOIN medicines m ON b.medicine_id = m.id
        WHERE m.pharmacy_id = :pid
          AND b.is_active = true
          AND b.quantity > 0
          AND b.expiry_date BETWEEN NOW() AND NOW() + INTERVAL '90 days'
        ORDER BY b.expiry_date ASC
    """), {"pid": pharmacy_id}).fetchall()

    expiry_alerts = []
    for row in expiry_rows:
        expiry_alerts.append({
            "medicine_id": str(row[0]),
            "trade_name": row[1],
            "batch_number": row[2],
            "expiry_date": row[3].isoformat() if hasattr(row[3], 'isoformat') else str(row[3]),
            "days_remaining": row[4],
            "severity": row[5]
        })

    # ═══════════════════════════════════════════════════
    # تنبيهات المخزون المنخفض
    # ═══════════════════════════════════════════════════
    stock_rows = db.execute(text("""
        SELECT
            m.id as medicine_id,
            m.trade_name,
            m.base_unit,
            m.min_stock,
            COALESCE(SUM(b.quantity), 0)::INTEGER as current_stock
        FROM medicines m
        LEFT JOIN batches b ON m.id = b.medicine_id
            AND b.is_active = true
            AND b.expiry_date > NOW()
        WHERE m.pharmacy_id = :pid
        GROUP BY m.id, m.trade_name, m.base_unit, m.min_stock
        HAVING COALESCE(SUM(b.quantity), 0) < m.min_stock
    """), {"pid": pharmacy_id}).fetchall()

    low_stock_alerts = []
    for row in stock_rows:
        low_stock_alerts.append({
            "medicine_id": str(row[0]),
            "trade_name": row[1],
            "base_unit": row[2] or "شريط",
            "min_stock": row[3],
            "current_stock": row[4]
        })

    return {
        "expiry_alerts": expiry_alerts,
        "low_stock_alerts": low_stock_alerts,
        "total_count": len(expiry_alerts) + len(low_stock_alerts)
    }


@router.get("/count")
async def get_alerts_count(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """عداد التنبيهات الخفيف (للجرس 🔔)."""
    pharmacy_id = current_user["pharmacy_id"]

    # Count expiry alerts
    expiry_count = db.execute(text("""
        SELECT COUNT(*) FROM batches b
        JOIN medicines m ON b.medicine_id = m.id
        WHERE m.pharmacy_id = :pid
          AND b.is_active = true
          AND b.quantity > 0
          AND b.expiry_date BETWEEN NOW() AND NOW() + INTERVAL '90 days'
    """), {"pid": pharmacy_id}).scalar() or 0

    # Count low stock alerts
    stock_count = db.execute(text("""
        SELECT COUNT(*) FROM (
            SELECT m.id
            FROM medicines m
            LEFT JOIN batches b ON m.id = b.medicine_id
                AND b.is_active = true
                AND b.expiry_date > NOW()
            WHERE m.pharmacy_id = :pid
            GROUP BY m.id, m.min_stock
            HAVING COALESCE(SUM(b.quantity), 0) < m.min_stock
        ) sub
    """), {"pid": pharmacy_id}).scalar() or 0

    return {"count": expiry_count + stock_count}


# ✅ انتهى - alerts.py - المرحلة 7