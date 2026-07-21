"""Idempotent RBAC foundation seeding."""

from sqlalchemy.orm import Session

from database import SessionLocal
from models import Permission, Role, RolePermission, User


ROLE_DEFINITIONS = {
    "owner": ("Owner", "Pharmacy owner with full access"),
    "manager": ("Manager", "Operations manager"),
    "pharmacist": ("Pharmacist", "Licensed pharmacist"),
    "cashier": ("Cashier", "Point-of-sale operator"),
    "store_keeper": ("Store keeper", "Inventory operator"),
}

PERMISSION_DEFINITIONS = {
    "medicines.view": "medicines", "medicines.create": "medicines",
    "medicines.edit": "medicines", "medicines.delete": "medicines",
    "inventory.view": "inventory", "inventory.receive": "inventory",
    "inventory.adjust": "inventory", "inventory.view_expired": "inventory",
    "sales.pos": "sales", "sales.view_history": "sales", "sales.void": "sales",
    "reports.sales": "reports", "reports.slow_moving": "reports",
    "reports.forecast": "reports", "profit.view": "profit",
    "employees.view": "employees", "employees.manage": "employees",
    "settings.view": "settings", "settings.manage": "settings",
    "purchase.view": "purchase",
}

ROLE_PERMISSIONS = {
    "owner": set(PERMISSION_DEFINITIONS),
    "manager": set(PERMISSION_DEFINITIONS) - {"medicines.delete", "settings.manage"},
    "pharmacist": {
        "medicines.view", "medicines.create", "medicines.edit",
        "inventory.view", "inventory.receive", "inventory.adjust", "inventory.view_expired",
        "sales.pos", "sales.view_history", "sales.void",
        "reports.sales", "reports.slow_moving", "reports.forecast", "purchase.view",
    },
    "cashier": {"medicines.view", "inventory.view", "inventory.view_expired", "sales.pos"},
    "store_keeper": {
        "medicines.view", "inventory.view", "inventory.receive", "inventory.adjust",
        "inventory.view_expired", "reports.forecast", "purchase.view",
    },
}


def seed_rbac_foundation(db: Session | None = None) -> dict:
    """Create missing RBAC rows and backfill only users without a role_id."""
    owns_session = db is None
    session = db or SessionLocal()
    inserted = {"roles": 0, "permissions": 0, "role_permissions": 0}

    try:
        roles = {role.name: role for role in session.query(Role).all()}
        for name, (display_name, description) in ROLE_DEFINITIONS.items():
            if name not in roles:
                role = Role(name=name, display_name=display_name, description=description)
                session.add(role)
                session.flush()
                roles[name] = role
                inserted["roles"] += 1

        permissions = {permission.code: permission for permission in session.query(Permission).all()}
        for code, category in PERMISSION_DEFINITIONS.items():
            if code not in permissions:
                permission = Permission(code=code, category=category, description=code)
                session.add(permission)
                session.flush()
                permissions[code] = permission
                inserted["permissions"] += 1

        existing_mappings = {
            (mapping.role_id, mapping.permission_id)
            for mapping in session.query(RolePermission).all()
        }
        for role_name, codes in ROLE_PERMISSIONS.items():
            role = roles[role_name]
            for code in codes:
                key = (role.id, permissions[code].id)
                if key not in existing_mappings:
                    session.add(RolePermission(role_id=key[0], permission_id=key[1]))
                    existing_mappings.add(key)
                    inserted["role_permissions"] += 1

        migrated = 0
        for user in session.query(User).filter(User.role_id.is_(None)).all():
            user.role_id = roles["owner"].id if user.role == "admin" else roles["cashier"].id
            migrated += 1

        if owns_session:
            session.commit()
        else:
            session.flush()
        return {**inserted, "migration": {"updated": migrated}}
    except Exception:
        if owns_session:
            session.rollback()
        raise
    finally:
        if owns_session:
            session.close()
