#!/usr/bin/env python3
"""Idempotently classify known legacy/QA records using explicit stable UUIDs.

Dry-run is the default. Pass --apply only during a separately authorized,
controlled operation. This script never creates pharmacies or users and never
sends email.
"""
import argparse
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from audit import add_audit_event
from database import SessionLocal
from models import CustomerHandover, Pharmacy, Role, User


def _uuid(value: str) -> uuid.UUID:
    return uuid.UUID(value)


def _owner(db, pharmacy: Pharmacy, owner_role: Role) -> User:
    owners = db.query(User).filter(
        User.pharmacy_id == pharmacy.id,
        User.role_id == owner_role.id,
    ).all()
    if len(owners) != 1:
        raise RuntimeError(f"pharmacy {pharmacy.id} must have exactly one canonical Owner")
    return owners[0]


def _legacy_row(db, pharmacy: Pharmacy, owner: User, classification: str):
    row = db.query(CustomerHandover).filter(CustomerHandover.pharmacy_id == pharmacy.id).one_or_none()
    created = row is None
    if row is None:
        row = CustomerHandover(
            id=uuid.uuid4(),
            customer_reference=pharmacy.customer_reference or f"LEGACY-{pharmacy.id}",
            pharmacy_name=pharmacy.name,
            owner_name=owner.full_name or pharmacy.owner_name or owner.username,
            owner_email=owner.email,
            owner_phone=owner.phone or pharmacy.phone,
            city=None,
            status="ACTIVE",
            classification=classification,
            origin="LEGACY_BACKFILL",
            pharmacy_id=pharmacy.id,
            owner_user_id=owner.id,
            # Intentionally no payment or activation delivery timestamps.
            payment_confirmed_at=None,
            payment_confirmed_by=None,
            activation_email_sent_at=None,
        )
        db.add(row)
    else:
        if row.owner_user_id not in (None, owner.id):
            raise RuntimeError(f"handover {row.id} is linked to a different Owner")
        row.owner_user_id = owner.id
        row.classification = classification
        row.origin = "LEGACY_BACKFILL"
        row.status = "ACTIVE"
    return row, created


def apply_semantics(db, *, commercial_pharmacy_id, demo_pharmacy_id,
                    qa_pharmacy_id, abandoned_handover_id, actor, apply=False):
    owner_role = db.query(Role).filter(Role.name == "owner").one()
    commercial = db.get(Pharmacy, _uuid(commercial_pharmacy_id))
    demo = db.get(Pharmacy, _uuid(demo_pharmacy_id))
    qa = db.get(Pharmacy, _uuid(qa_pharmacy_id))
    abandoned = db.get(CustomerHandover, _uuid(abandoned_handover_id))
    if not all((commercial, demo, qa, abandoned)):
        raise RuntimeError("one or more explicit target UUIDs do not exist")
    if commercial.type != "customer" or qa.type != "customer" or demo.type != "demo":
        raise RuntimeError("target pharmacy classifications do not match existing pharmacy types")
    if abandoned.pharmacy_id is not None:
        raise RuntimeError("abandoned handover unexpectedly has a pharmacy link")
    if abandoned.status not in {"READY_TO_PROVISION", "ABANDONED"}:
        raise RuntimeError("abandoned handover is not in the expected lifecycle state")

    commercial_owner = _owner(db, commercial, owner_role)
    demo_owner = _owner(db, demo, owner_role)
    qa_owner = _owner(db, qa, owner_role)
    commercial_row, commercial_created = _legacy_row(db, commercial, commercial_owner, "COMMERCIAL")
    demo_row, demo_created = _legacy_row(db, demo, demo_owner, "DEMO")
    qa_row = db.query(CustomerHandover).filter(CustomerHandover.pharmacy_id == qa.id).one()
    if qa_row.owner_user_id not in (None, qa_owner.id):
        raise RuntimeError("QA handover is linked to a different Owner")
    qa_row.owner_user_id = qa_owner.id
    qa_row.classification = "QA"
    abandoned.classification = "QA"
    abandoned.status = "ABANDONED"

    targets = (commercial_row, demo_row, qa_row, abandoned)
    changed = any(db.is_modified(row, include_collections=False) for row in targets) or commercial_created or demo_created
    result = {
        "mode": "APPLY" if apply else "DRY_RUN",
        "changed": changed,
        "commercial_representation": "CREATE" if commercial_created else "PRESENT",
        "demo_representation": "CREATE" if demo_created else "PRESENT",
        "duplicate_pharmacies": 0,
        "duplicate_owners": 0,
        "email_sent": False,
    }
    if apply:
        if changed:
            for row in targets:
                add_audit_event(
                    db, pharmacy_id=str(row.pharmacy_id) if row.pharmacy_id else None,
                    user_id=None, user_name=actor,
                    action_type="customer_semantics_backfill",
                    description="Customer representation classified without tenant recreation",
                    target_entity="customer_handover", target_id=str(row.id),
                    new_value=f"{row.classification}:{row.status}:{row.origin}",
                )
        db.commit()
    else:
        db.rollback()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--commercial-pharmacy-id", required=True)
    parser.add_argument("--demo-pharmacy-id", required=True)
    parser.add_argument("--qa-pharmacy-id", required=True)
    parser.add_argument("--abandoned-handover-id", required=True)
    parser.add_argument("--actor", default="operator@daryonix.com")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as db:
        result = apply_semantics(
            db,
            commercial_pharmacy_id=args.commercial_pharmacy_id,
            demo_pharmacy_id=args.demo_pharmacy_id,
            qa_pharmacy_id=args.qa_pharmacy_id,
            abandoned_handover_id=args.abandoned_handover_id,
            actor=args.actor,
            apply=args.apply,
        )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
