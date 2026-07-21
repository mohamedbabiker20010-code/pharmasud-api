#!/usr/bin/env python3
"""One-time, repeatable marketing demo bootstrap with fail-closed safeguards."""

import argparse
import json
import os
import sys
import uuid

from sqlalchemy import text

from auth import get_password_hash
from database import SessionLocal
from demo.seed_demo_pharmacy import seed_demo_pharmacy
from models import Pharmacy, Role, User
from rbac_seeder import seed_rbac_foundation
from startup import initialize_database


PASSWORD_ENV = "PHARMASUD_DEMO_ADMIN_PASSWORD"


def parse_args():
    parser = argparse.ArgumentParser(description="Bootstrap the PharmaSUD marketing demo")
    parser.add_argument("--confirm-demo-bootstrap", action="store_true")
    parser.add_argument("--username", required=True)
    parser.add_argument("--demo-key", required=True, help="Stable non-customer key used to identify this demo")
    parser.add_argument("--pharmacy-name", required=True)
    parser.add_argument("--owner-name", default="PharmaSUD Marketing")
    return parser.parse_args()


def bootstrap(args, password: str) -> dict:
    if not args.confirm_demo_bootstrap:
        raise ValueError("--confirm-demo-bootstrap is required")
    if len(password) < 12:
        raise ValueError(f"{PASSWORD_ENV} must contain at least 12 characters")

    initialize_database()
    created = {"pharmacies": 0, "administrators": 0}
    skipped = {"pharmacies": 0, "administrators": 0}

    with SessionLocal.begin() as db:
        seed_rbac_foundation(db)
        pharmacy = db.query(Pharmacy).filter(Pharmacy.product_key == args.demo_key).first()
        if pharmacy and pharmacy.type != "demo":
            raise ValueError("Refusing to target a non-demo pharmacy")
        if pharmacy and not pharmacy.is_active:
            raise ValueError("Refusing to modify an inactive demo pharmacy")
        if pharmacy:
            skipped["pharmacies"] += 1
        else:
            pharmacy = Pharmacy(
                id=uuid.uuid4(), product_key=args.demo_key, name=args.pharmacy_name,
                owner_name=args.owner_name, is_active=True, type="demo",
            )
            db.add(pharmacy)
            db.flush()
            created["pharmacies"] += 1

        user = db.query(User).filter(User.username == args.username).first()
        if user and user.pharmacy_id != pharmacy.id:
            raise ValueError("Username belongs to another pharmacy")
        if user and user.role != "admin":
            raise ValueError("Existing demo username is not an administrator")
        if user and not user.is_active:
            raise ValueError("Existing demo administrator is disabled")
        if user:
            skipped["administrators"] += 1
        else:
            owner_role = db.query(Role).filter(Role.name == "owner").one()
            user = User(
                id=uuid.uuid4(), pharmacy_id=pharmacy.id, username=args.username,
                full_name=args.owner_name, password_hash=get_password_hash(password),
                role="admin", role_id=owner_role.id, is_active=True,
            )
            db.add(user)
            db.flush()
            created["administrators"] += 1

        seed_result = seed_demo_pharmacy(
            str(pharmacy.id), db=db, seed_users=False, allow_production_cli=True
        )
        db.execute(text("""
            INSERT INTO audit_log
                (pharmacy_id, user_id, user_name, action_type, description,
                 target_entity, target_id, success)
            VALUES
                (:pid, :uid, :username, 'demo_bootstrap', :description,
                 'pharmacy', :target_id, TRUE)
        """), {
            "pid": str(pharmacy.id), "uid": str(user.id), "username": user.username,
            "description": "Marketing demo bootstrap completed",
            "target_id": str(pharmacy.id),
        })
        pharmacy_id = str(pharmacy.id)

    return {
        "success": True,
        "pharmacy_id": pharmacy_id,
        "created": created,
        "skipped": skipped,
        "medicines_seeded": seed_result["medicines_seeded"],
        "sales_seeded": seed_result["sales_seeded"],
    }


def main() -> int:
    args = parse_args()
    password = os.getenv(PASSWORD_ENV, "")
    if not password:
        print(f"error: set {PASSWORD_ENV} in the environment", file=sys.stderr)
        return 2
    try:
        print(json.dumps(bootstrap(args, password), indent=2))
        return 0
    except Exception as exc:
        print(f"bootstrap_failed: {type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
