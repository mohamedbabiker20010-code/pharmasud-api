"""
PharmaSUD - User Context Router
Provides /api/user/context endpoint for frontend permission engine bootstrap.
Returns effective permissions, feature flags, and metadata.
Version: 1.0.0 (Frozen Architecture v1)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Dict, Any, List

from database import get_db
from models import User, Role, Permission, Pharmacy
from auth import get_current_user

router = APIRouter(prefix="/api/user", tags=["user-context"])


def resolve_effective_permissions(user: Dict[str, Any], db: Session) -> Dict[str, bool]:
    """
    Single extension point for all future permission sources.
    
    Current implementation: Returns role-based permissions only.
    Future versions may merge:
    - User-level grants (user_permission_grants)
    - Temporary grants (with expires_at filtering)
    - Branch/region scoped grants
    - Corporate group permissions
    
    Frontend contract remains unchanged.
    """
    # 1. Base: Role permissions (current implementation)
    role_perms = get_role_permissions(user.get("role_id"), db)
    
    # 2. [FUTURE] User-level grants
    # user_grants = get_user_permission_grants(user["user_id"], db)
    
    # 3. [FUTURE] Temporary grants (filter by expires_at > now)
    # temp_grants = get_temporary_grants(user["user_id"], db)
    
    # 4. [FUTURE] Branch/region scoped grants
    # branch_grants = get_branch_grants(user["user_id"], user.get("pharmacy_id"), db)
    
    # 5. Merge: grants override role (additive)
    # effective = {**role_perms, **user_grants, **temp_grants, **branch_grants}
    
    effective = role_perms  # Current v1 implementation
    return effective


def get_role_permissions(role_id: str, db: Session) -> Dict[str, bool]:
    """Get all permission codes for a role as a flat dict {code: true}."""
    if not role_id:
        return {}
    
    perms = db.query(Permission.code).join(Role.permissions).filter(Role.id == role_id).all()
    return {p.code: True for p in perms}


def get_feature_flags(user: Dict[str, Any], db: Session) -> Dict[str, Dict[str, bool]]:
    """
    Feature flags - module-level toggles.
    Currently all enabled based on effective permissions.
    Future: Can be controlled per pharmacy, per branch, per user.
    """
    # Use effective permissions from RBAC, not legacy JWT permissions
    effective_perms = resolve_effective_permissions(user, db)
    
    return {
        "pos": {"enabled": effective_perms.get("sales.pos", False), "visible": effective_perms.get("sales.pos", False)},
        "inventory": {"enabled": effective_perms.get("inventory.view", False), "visible": effective_perms.get("inventory.view", False)},
        "reports": {"enabled": effective_perms.get("reports.dashboard", False), "visible": effective_perms.get("reports.dashboard", False)},
        "barcode": {"enabled": effective_perms.get("sales.pos", False), "visible": effective_perms.get("sales.pos", False)},
        "purchase_forecast": {"enabled": effective_perms.get("reports.forecast", False), "visible": effective_perms.get("reports.forecast", False)},
        "audit": {"enabled": effective_perms.get("audit.view", False), "visible": effective_perms.get("audit.view", False)},
        "profit": {"enabled": effective_perms.get("profit.view", False), "visible": effective_perms.get("profit.view", False)},
        "employees": {"enabled": effective_perms.get("employees.view", False), "visible": effective_perms.get("employees.view", False)},
        "settings": {"enabled": effective_perms.get("settings.view", False), "visible": effective_perms.get("settings.view", False)},
    }


def get_metadata(user: Dict[str, Any], db: Session) -> Dict[str, Any]:
    """Build stable metadata section for frontend bootstrap."""
    pharmacy = db.query(Pharmacy).filter(Pharmacy.id == user.get("pharmacy_id")).first()
    
    return {
        "role": user.get("role", ""),
        "display_role_ar": user.get("role_display_name", ""),
        "display_role_en": user.get("role_display_name", ""),
        "pharmacy_name": pharmacy.name if pharmacy else "",
        "pharmacy_id": str(user.get("pharmacy_id", "")),
        "language": "ar",
        "currency": "SDG",
        "system_version": "7.1.0",
        "full_name": user.get("full_name", ""),
        "username": user.get("username", ""),
    }


@router.get("/context")
async def get_user_context(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Frontend bootstrap endpoint.
    Returns complete context for permission engine initialization.
    
    Contract (Frozen Architecture v1):
    {
        "authentication": {...},
        "permissions": {...},      // flat {code: bool} - effective permissions
        "feature_flags": {...},    // {feature: {enabled, visible}}
        "pharmacy": {...},         // pharmacy info
        "meta": {...}              // role, display_name, pharmacy_name, etc.
    }
    """
    # Resolve effective permissions (single extension point)
    effective_permissions = resolve_effective_permissions(current_user, db)
    
    # Build feature flags
    feature_flags = get_feature_flags(current_user, db)
    
    # Build metadata
    meta = get_metadata(current_user, db)
    
    # Pharmacy info
    pharmacy = db.query(Pharmacy).filter(Pharmacy.id == current_user.get("pharmacy_id")).first()
    pharmacy_info = {
        "id": str(pharmacy.id) if pharmacy else "",
        "name": pharmacy.name if pharmacy else "",
        "branch_id": None,  # Future: multi-branch
        "owner_id": str(pharmacy.owner_id) if pharmacy and hasattr(pharmacy, 'owner_id') else None,
    }
    
    return {
        "authentication": {
            "user_id": current_user.get("user_id", ""),
            "full_name": current_user.get("full_name", ""),
            "username": current_user.get("username", ""),
            "display_role_ar": current_user.get("role_display_name", ""),
            "display_role_en": current_user.get("role_display_name", ""),
        },
        "permissions": effective_permissions,
        "feature_flags": feature_flags,
        "pharmacy": pharmacy_info,
        "meta": meta,
    }