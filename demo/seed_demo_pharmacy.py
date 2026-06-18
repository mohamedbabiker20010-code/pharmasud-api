#!/usr/bin/env python3
"""
Demo Pharmacy Seeder

Seeds a demo pharmacy with realistic test data.
NO passwords stored in data files - generated at runtime.

Usage:
    python -m demo.seed_demo_pharmacy <pharmacy_id>

Requirements:
    - Pharmacy must exist and have type='demo'
    - Admin/employee passwords generated securely at runtime
"""

import json
import uuid
import secrets
import string
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import engine
from models import (
    Pharmacy, User, Medicine, Unit, Batch, Sale, SaleItem
)
from auth import get_password_hash


def generate_secure_password(length: int = 12) -> str:
    """Generate a cryptographically secure random password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def load_demo_data() -> dict:
    """Load demo data from JSON file."""
    import os
    demo_path = os.path.join(os.path.dirname(__file__), 'demo_data.json')
    with open(demo_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def verify_demo_pharmacy(db: Session, pharmacy_id: str) -> Pharmacy:
    """Verify pharmacy exists and is type='demo'."""
    pharmacy = db.query(Pharmacy).filter(
        Pharmacy.id == uuid.UUID(pharmacy_id)
    ).first()

    if not pharmacy:
        raise ValueError(f"Pharmacy {pharmacy_id} not found")

    if pharmacy.type != 'demo':
        raise ValueError(f"Pharmacy {pharmacy_id} is not a demo pharmacy (type={pharmacy.type})")

    return pharmacy


def seed_pharmacy_info(db: Session, pharmacy: Pharmacy, demo_data: dict) -> None:
    """Update pharmacy with demo info."""
    demo_pharmacy = demo_data['pharmacy']
    pharmacy.name = demo_pharmacy['name']
    pharmacy.owner_name = demo_pharmacy['owner_name']
    pharmacy.phone = demo_pharmacy['phone']
    pharmacy.address = demo_pharmacy['address']
    db.commit()


def seed_medicines_and_batches(
    db: Session,
    pharmacy_id: uuid.UUID,
    demo_data: dict
) -> Dict[str, uuid.UUID]:
    """
    Create medicines, units, and batches.
    Returns medicine trade_name -> medicine_id mapping.
    """
    pharmacy_uuid = pharmacy_id
    medicine_id_map = {}

    for med_data in demo_data['medicines']:
        med_id = uuid.uuid4()

        # Create medicine
        medicine = Medicine(
            id=med_id,
            pharmacy_id=pharmacy_uuid,
            barcode=med_data['barcode'],
            trade_name=med_data['trade_name'],
            scientific_name=med_data['scientific_name'],
            category=med_data['category'],
            sale_price=med_data['sale_price'],
            purchase_price=med_data['purchase_price'],
            base_unit=med_data['base_unit'],
            min_stock=med_data['min_stock'],
            image_path=None
        )
        db.add(medicine)

        # Create default unit
        unit = Unit(
            id=uuid.uuid4(),
            medicine_id=med_id,
            unit_name=med_data['base_unit'],
            conversion_factor=1.0,
            sale_price=med_data['sale_price']
        )
        db.add(unit)

        # Create batches
        for batch_data in med_data['batches']:
            expiry_date = date.today() + timedelta(days=batch_data['expiry_days'])
            batch = Batch(
                id=uuid.uuid4(),
                medicine_id=med_id,
                batch_number=f"BATCH-{med_data['barcode'][-4:]}-{uuid.uuid4().hex[:6].upper()}",
                quantity=batch_data['quantity'],
                expiry_date=expiry_date,
                purchase_price=batch_data['purchase_price'],
                supplier_invoice=f"INV-{uuid.uuid4().hex[:8].upper()}",
                supplier_name="مورد تجريبي",
                is_active=True
            )
            db.add(batch)

        medicine_id_map[med_data['trade_name']] = med_id

    db.commit()
    return medicine_id_map


def seed_employees(
    db: Session,
    pharmacy_id: uuid.UUID,
    demo_data: dict
) -> Dict[str, str]:
    """
    Create demo employees (admin + employee).
    Passwords generated at runtime and returned.
    Returns username -> password mapping.
    """
    credentials = {}

    for emp_data in demo_data['employees']:
        password = generate_secure_password()
        credentials[emp_data['username']] = password

        user = User(
            id=uuid.uuid4(),
            pharmacy_id=pharmacy_id,
            username=emp_data['username'],
            full_name=emp_data['full_name'],
            password_hash=get_password_hash(password),
            role=emp_data['role'],
            is_active=True
        )
        db.add(user)

    db.commit()
    return credentials


def seed_sales(
    db: Session,
    pharmacy_id: uuid.UUID,
    medicine_id_map: Dict[str, uuid.UUID],
    demo_data: dict
) -> None:
    """Create historical sales for demo pharmacy."""
    from batches import get_fefo_batches

    for sale_data in demo_data['sales']:
        med_trade_name = demo_data['medicines'][sale_data['medicine_idx']]['trade_name']
        med_id = medicine_id_map[med_trade_name]
        qty = sale_data['quantity']

        # Get FEFO allocation
        try:
            allocation = get_fefo_batches(str(med_id), qty, str(pharmacy_id), db)
        except Exception:
            continue  # Skip if insufficient stock

        # Create sale
        sale_date = datetime.now() - timedelta(days=sale_data['days_ago'])
        sale = Sale(
            id=uuid.uuid4(),
            pharmacy_id=pharmacy_id,
            user_id=db.query(User).filter(
                User.pharmacy_id == pharmacy_id,
                User.role == 'admin'
            ).first().id,
            invoice_number=db.query(Sale).filter(
                Sale.pharmacy_id == pharmacy_id
            ).count() + 1 + len(sale_data),
            customer_name=None,
            total_amount=0,
            payment_method=sale_data['payment'],
            created_at=sale_date
        )
        db.add(sale)
        db.flush()

        total_amount = 0
        for alloc in allocation:
            batch_id = uuid.UUID(alloc['batch_id'])
            batch_qty = alloc['quantity']

            batch = db.query(Batch).filter(Batch.id == batch_id).first()
            med = db.query(Medicine).filter(Medicine.id == med_id).first()
            unit_price = med.sale_price
            total_price = unit_price * batch_qty

            sale_item = SaleItem(
                id=uuid.uuid4(),
                sale_id=sale.id,
                medicine_id=med_id,
                batch_id=batch_id,
                quantity=batch_qty,
                unit_name=med.base_unit,
                unit_price=unit_price,
                total_price=total_price
            )
            db.add(sale_item)

            batch.quantity -= batch_qty
            if batch.quantity <= 0:
                batch.is_active = False

            total_amount += total_price

        sale.total_amount = total_amount
        sale.created_at = sale_date

    db.commit()


def apply_demo_settings(db: Session, pharmacy_id: uuid.UUID, demo_data: dict) -> None:
    """Apply demo-specific settings."""
    # The settings are applied via receipt footer in the template
    # Demo pharmacy gets "DEMO - PharmaSUD" footer
    pass


def seed_demo_pharmacy(pharmacy_id: str) -> dict:
    """
    Main entry point to seed a demo pharmacy.
    
    Args:
        pharmacy_id: UUID string of the demo pharmacy
        
    Returns:
        dict with seeded counts and generated credentials
        
    Raises:
        ValueError: If pharmacy not found or not type='demo'
    """
    demo_data = load_demo_data()

    with Session(engine) as db:
        # Verify pharmacy
        pharmacy = verify_demo_pharmacy(db, pharmacy_id)
        pharmacy_uuid = uuid.UUID(pharmacy_id)

        # Clear existing demo data (idempotent)
        clear_demo_data(db, pharmacy_id)

        # Seed in order
        seed_pharmacy_info(db, pharmacy, demo_data)
        medicine_id_map = seed_medicines_and_batches(db, uuid.UUID(pharmacy_id), demo_data)
        credentials = seed_employees(db, uuid.UUID(pharmacy_id), demo_data)
        seed_sales(db, uuid.UUID(pharmacy_id), medicine_id_map, demo_data)
        apply_demo_settings(db, uuid.UUID(pharmacy_id), demo_data)

        return {
            'success': True,
            'pharmacy_id': pharmacy_id,
            'pharmacy_name': pharmacy.name,
            'medicines_seeded': len(medicine_id_map),
            'batches_seeded': sum(
                len(m['batches']) for m in demo_data['medicines']
            ),
            'employees_seeded': len(demo_data['employees']),
            'sales_seeded': len(demo_data['sales']),
            'credentials': credentials,
            'message': 'Demo pharmacy seeded successfully'
        }


def clear_demo_data(db: Session, pharmacy_id: str) -> None:
    """Clear existing demo data for idempotent seeding."""
    pid = uuid.UUID(pharmacy_id)

    # Delete in reverse FK order
    db.query(SaleItem).filter(
        SaleItem.medicine_id.in_(
            db.query(Medicine.id).filter(Medicine.pharmacy_id == pid)
        )
    ).delete(synchronize_session=False)

    db.query(Sale).filter(Sale.pharmacy_id == pid).delete(synchronize_session=False)
    db.query(Batch).filter(
        Batch.medicine_id.in_(
            db.query(Medicine.id).filter(Medicine.pharmacy_id == pid)
        )
    ).delete(synchronize_session=False)

    db.query(Unit).filter(
        Unit.medicine_id.in_(
            db.query(Medicine.id).filter(Medicine.pharmacy_id == pid)
        )
    ).delete(synchronize_session=False)

    db.query(Medicine).filter(Medicine.pharmacy_id == pid).delete(synchronize_session=False)
    db.query(User).filter(User.pharmacy_id == pid).delete(synchronize_session=False)

    db.commit()


if __name__ == '__main__':
    import sys

    if len(sys.argv) != 2:
        print("Usage: python -m demo.seed_demo_pharmacy <pharmacy_id>")
        sys.exit(1)

    pharmacy_id = sys.argv[1]

    try:
        result = seed_demo_pharmacy(pharmacy_id)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
