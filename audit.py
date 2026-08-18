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
    user_id: Optional[str],
    user_name: str,
    action_type: str,
    description: str,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None,
    target_entity: Optional[str] = None,
    target_id: Optional[str] = None,
    success: bool = True,
    request_ip: Optional[str] = None,
):
    """Legacy convenience wrapper that commits its own audit write."""
    try:
        add_audit_event(
            db, pharmacy_id=pharmacy_id, user_id=user_id, user_name=user_name,
            action_type=action_type, description=description, old_value=old_value,
            new_value=new_value, target_entity=target_entity, target_id=target_id,
            success=success, request_ip=request_ip,
        )
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Audit log error: {type(e).__name__}")
        return False


def add_audit_event(
    db: Session,
    *,
    pharmacy_id: Optional[str],
    user_id: Optional[str],
    user_name: str,
    action_type: str,
    description: str,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None,
    target_entity: Optional[str] = None,
    target_id: Optional[str] = None,
    success: bool = True,
    request_ip: Optional[str] = None,
) -> None:
    """Insert an audit event without committing or rolling back the caller."""
    db.execute(
        text("""
            INSERT INTO audit_log
                (pharmacy_id, user_id, user_name, action_type,
                 description, target_entity, target_id, old_value,
                 new_value, success, request_ip)
            VALUES
                (:pid, :uid, :uname, :atype,
                 :desc, :target_entity, :target_id, :old, :new,
                 :success, :request_ip)
        """),
        {
            "pid": uuid.UUID(str(pharmacy_id)) if pharmacy_id else None,
            "uid": uuid.UUID(str(user_id)) if user_id else None,
            "uname": user_name,
            "atype": action_type,
            "desc": description,
            "target_entity": target_entity,
            "target_id": target_id,
            "old": old_value,
            "new": new_value,
            "success": success,
            "request_ip": request_ip,
        },
    )
    db.flush()


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
