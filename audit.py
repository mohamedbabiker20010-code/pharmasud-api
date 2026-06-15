"""
PharmaSUD - Audit Log Module (Stage 7)
Version 7.0.0

يتولى:
- تسجيل العمليات الحساسة في audit_log
- قراءة سجل التدقيق مع الفلاتر والصفحات
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from auth import get_current_user, require_admin

# Create router
router = APIRouter(prefix="/api/audit-log", tags=["audit"])


def log_action(
    db: Session,
    pharmacy_id: str,
    user_id: str,
    user_name: str,
    action_type: str,
    description: str,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None
):
    """تسجيل أي عملية حساسة في audit_log."""
    try:
        db.execute(
            text("""
                INSERT INTO audit_log
                    (pharmacy_id, user_id, user_name, action_type,
                     description, old_value, new_value)
                VALUES
                    (:pid, :uid, :uname, :atype,
                     :desc, :old, :new)
            """),
            {
                "pid": uuid.UUID(pharmacy_id),
                "uid": uuid.UUID(user_id),
                "uname": user_name,
                "atype": action_type,
                "desc": description,
                "old": old_value,
                "new": new_value
            }
        )
    except Exception as e:
        print(f"⚠️ Audit log error: {e}")


@router.get("/")
async def get_audit_log(
    action_type: str = Query("all", description="all|price_update|medicine_delete|employee_create|employee_toggle|employee_reset_password|stocktake_adjustment"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """قراءة سجل التدقيق (Admin فقط)."""
    pharmacy_id = current_user["pharmacy_id"]

    conditions = "WHERE a.pharmacy_id = :pid"
    params = {"pid": uuid.UUID(current_user["pharmacy_id"])}

    if action_type != "all":
        conditions += " AND a.action_type = :atype"
        params["atype"] = action_type

    # Total count
    count_result = db.execute(
        text(f"SELECT COUNT(*) FROM audit_log a {conditions}"),
        params
    )
    total = count_result.scalar()

    # Fetch page
    offset = (page - 1) * limit
    rows = db.execute(
        text(f"""
            SELECT a.id, a.user_name, a.action_type, a.description,
                   a.old_value, a.new_value, a.created_at
            FROM audit_log a
            {conditions}
            ORDER BY a.created_at DESC
            LIMIT :lim OFFSET :off
        """),
        {**params, "lim": limit, "off": offset}
    ).fetchall()

    logs = []
    for row in rows:
        logs.append({
            "id": str(row[0]),
            "user_name": row[1],
            "action_type": row[2],
            "description": row[3],
            "old_value": row[4],
            "new_value": row[5],
            "created_at": row[6].isoformat() if hasattr(row[6], 'isoformat') else str(row[6])
        })

    return {
        "logs": logs,
        "total": total,
        "page": page
    }


# ✅ انتهى - audit.py - المرحلة 7