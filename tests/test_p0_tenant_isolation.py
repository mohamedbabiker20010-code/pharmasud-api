import asyncio
import os
import uuid
from datetime import date, timedelta

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from auth import create_access_token, get_password_hash
from database import get_db
from inventory import router as inventory_router
from models import Base, Batch, Medicine, Pharmacy, Sale, SaleItem, User
from sales import public_router, router as sales_router


DATABASE_URL = os.environ.get("P0_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="P0_TEST_DATABASE_URL must point to a dedicated disposable PostgreSQL database",
)


@pytest.fixture(scope="module")
def postgres():
    engine = create_engine(DATABASE_URL)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    Base.metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE sales DROP COLUMN public_invoice_token"))
        connection.execute(text("""
            CREATE TABLE audit_log (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                pharmacy_id UUID REFERENCES pharmacies(id),
                user_id UUID REFERENCES users(id) ON DELETE SET NULL,
                user_name VARCHAR(100), action_type VARCHAR(50) NOT NULL,
                description TEXT NOT NULL, old_value TEXT, new_value TEXT,
                success BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        connection.execute(text("""
            CREATE TABLE stocktake_sessions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                pharmacy_id UUID REFERENCES pharmacies(id), user_id UUID REFERENCES users(id),
                notes TEXT, items_adjusted INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        connection.execute(text("""
            CREATE TABLE stocktake_items (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                session_id UUID REFERENCES stocktake_sessions(id),
                medicine_id UUID REFERENCES medicines(id), medicine_name VARCHAR(100),
                system_quantity INTEGER, actual_quantity INTEGER, difference INTEGER,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))

        old_pharmacy_id = uuid.uuid4()
        old_user_id = uuid.uuid4()
        old_sale_id = uuid.uuid4()
        connection.execute(text("""
            INSERT INTO pharmacies (id, product_key, name, is_active, type)
            VALUES (:pid, 'MIGRATION-OLD-PHARMACY', 'Existing Demo', TRUE, 'demo')
        """), {"pid": old_pharmacy_id})
        connection.execute(text("""
            INSERT INTO users (id, pharmacy_id, username, password_hash, role, is_active)
            VALUES (:uid, :pid, 'migration_demo', 'not-used', 'admin', TRUE)
        """), {"uid": old_user_id, "pid": old_pharmacy_id})
        connection.execute(text("""
            INSERT INTO sales
                (id, pharmacy_id, user_id, invoice_number, total_amount, payment_method)
            VALUES (:sid, :pid, :uid, 1, 10, 'cash')
        """), {"sid": old_sale_id, "pid": old_pharmacy_id, "uid": old_user_id})

    config = Config(str(os.path.join(os.path.dirname(__file__), "..", "alembic.ini")))
    config.set_main_option("sqlalchemy.url", DATABASE_URL)
    command.stamp(config, "20240618_rbac_phase1")
    command.upgrade(config, "head")

    with engine.connect() as connection:
        migrated_token = connection.execute(
            text("SELECT public_invoice_token FROM sales WHERE id = :sid"),
            {"sid": old_sale_id},
        ).scalar_one()
        assert len(migrated_token) == 32
        assert connection.execute(text("SELECT COUNT(*) FROM sales")).scalar_one() == 1
        assert connection.execute(text("""
            SELECT COUNT(*) FROM pg_constraint
            WHERE conname = 'uq_sales_public_invoice_token'
              AND contype = 'u'
        """)).scalar_one() == 1

    with engine.begin() as connection:
        connection.execute(text("DELETE FROM sale_items"))
        connection.execute(text("DELETE FROM sales"))
        connection.execute(text("DELETE FROM batches"))
        connection.execute(text("DELETE FROM medicines"))
        connection.execute(text("DELETE FROM users"))
        connection.execute(text("DELETE FROM pharmacies"))

    yield engine, factory
    engine.dispose()


@pytest.fixture(scope="module")
def seeded(postgres):
    engine, factory = postgres
    with factory.begin() as db:
        pharmacy_a = Pharmacy(product_key="P0-PHARMACY-A", name="PHARMACY_A", is_active=True)
        pharmacy_b = Pharmacy(product_key="P0-PHARMACY-B", name="PHARMACY_B", is_active=True)
        db.add_all([pharmacy_a, pharmacy_b])
        db.flush()
        owner_a = User(
            pharmacy_id=pharmacy_a.id, username="P0_OWNER_A", full_name="OWNER_A",
            password_hash=get_password_hash("Synthetic-A-Only!"), role="admin", is_active=True,
        )
        owner_b = User(
            pharmacy_id=pharmacy_b.id, username="P0_OWNER_B", full_name="OWNER_B",
            password_hash=get_password_hash("Synthetic-B-Only!"), role="admin", is_active=True,
        )
        medicine_a = Medicine(
            pharmacy_id=pharmacy_a.id, trade_name="MEDICINE_A", category="أخرى",
            sale_price=10, purchase_price=4, base_unit="unit", min_stock=1,
        )
        medicine_b = Medicine(
            pharmacy_id=pharmacy_b.id, trade_name="MEDICINE_B", category="أخرى",
            sale_price=20, purchase_price=8, base_unit="unit", min_stock=1,
        )
        db.add_all([owner_a, owner_b, medicine_a, medicine_b])
        db.flush()
        batch_a = Batch(
            medicine_id=medicine_a.id, batch_number="BATCH_A", quantity=10,
            expiry_date=date.today() + timedelta(days=365), purchase_price=4, is_active=True,
        )
        batch_b = Batch(
            medicine_id=medicine_b.id, batch_number="BATCH_B", quantity=20,
            expiry_date=date.today() + timedelta(days=365), purchase_price=8, is_active=True,
        )
        sale_a = Sale(
            pharmacy_id=pharmacy_a.id, user_id=owner_a.id, invoice_number=1,
            total_amount=10, payment_method="cash",
        )
        sale_b = Sale(
            pharmacy_id=pharmacy_b.id, user_id=owner_b.id, invoice_number=1,
            total_amount=20, payment_method="cash",
        )
        db.add_all([batch_a, batch_b, sale_a, sale_b])
        db.flush()
        db.add_all([
            SaleItem(sale_id=sale_a.id, medicine_id=medicine_a.id, batch_id=batch_a.id,
                     quantity=1, unit_name="unit", unit_price=10, total_price=10),
            SaleItem(sale_id=sale_b.id, medicine_id=medicine_b.id, batch_id=batch_b.id,
                     quantity=1, unit_name="unit", unit_price=20, total_price=20),
        ])
        ids = {
            "pharmacy_a": pharmacy_a.id, "pharmacy_b": pharmacy_b.id,
            "owner_a": owner_a.id, "owner_b": owner_b.id,
            "medicine_a": medicine_a.id, "medicine_b": medicine_b.id,
            "batch_a": batch_a.id, "batch_b": batch_b.id,
            "sale_a": sale_a.id, "sale_b": sale_b.id,
            "token_a": sale_a.public_invoice_token, "token_b": sale_b.public_invoice_token,
        }
    return engine, factory, ids


def _auth(owner_id, pharmacy_id, username):
    token = create_access_token({
        "user_id": str(owner_id), "pharmacy_id": str(pharmacy_id),
        "role": "admin", "username": username,
    })
    return {"Authorization": f"Bearer {token}"}


def _request(app, method, path, **kwargs):
    async def execute():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://p0.test") as client:
            return await client.request(method, path, **kwargs)
    return asyncio.run(execute())


@pytest.fixture(scope="module")
def api(seeded):
    _, factory, _ = seeded

    async def test_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(inventory_router)
    app.include_router(sales_router)
    app.include_router(public_router)
    app.dependency_overrides[get_db] = test_db
    return app


@pytest.mark.parametrize(
    "actor,foreign,own_batch,foreign_batch",
    [
        ("a", "b", "batch_a", "batch_b"),
        ("b", "a", "batch_b", "batch_a"),
    ],
)
def test_cross_tenant_stocktake_is_rejected_atomically(api, seeded, actor, foreign, own_batch, foreign_batch):
    _, factory, ids = seeded
    owner_id = ids[f"owner_{actor}"]
    pharmacy_id = ids[f"pharmacy_{actor}"]
    headers = _auth(owner_id, pharmacy_id, f"P0_OWNER_{actor.upper()}")

    with factory() as db:
        own_before = db.get(Batch, ids[own_batch]).quantity
        foreign_before = db.get(Batch, ids[foreign_batch]).quantity
        foreign_batch_count = db.query(Batch).filter(Batch.medicine_id == ids[f"medicine_{foreign}"]).count()
        sessions_before = db.execute(text("SELECT COUNT(*) FROM stocktake_sessions")).scalar_one()

    response = _request(api, "POST", "/api/inventory/stocktake/submit", headers=headers, json={
        "notes": "P0 atomic isolation test",
        "items": [
            {"medicine_id": str(ids[f"medicine_{actor}"]), "actual_quantity": own_before - 1},
            {"medicine_id": str(ids[f"medicine_{foreign}"]), "actual_quantity": foreign_before + 5},
        ],
    })
    assert response.status_code == 404
    assert response.json()["detail"] == "الدواء غير موجود"

    with factory() as db:
        assert db.get(Batch, ids[own_batch]).quantity == own_before
        assert db.get(Batch, ids[foreign_batch]).quantity == foreign_before
        assert db.query(Batch).filter(Batch.medicine_id == ids[f"medicine_{foreign}"]).count() == foreign_batch_count
        assert db.execute(text("SELECT COUNT(*) FROM stocktake_sessions")).scalar_one() == sessions_before


def test_same_tenant_stocktake_still_succeeds(api, seeded):
    _, factory, ids = seeded
    headers = _auth(ids["owner_a"], ids["pharmacy_a"], "P0_OWNER_A")
    with factory() as db:
        before = db.get(Batch, ids["batch_a"]).quantity

    response = _request(api, "POST", "/api/inventory/stocktake/submit", headers=headers, json={
        "notes": "same tenant",
        "items": [{"medicine_id": str(ids["medicine_a"]), "actual_quantity": before - 1}],
    })
    assert response.status_code == 200
    assert response.json()["success"] is True
    with factory() as db:
        assert db.get(Batch, ids["batch_a"]).quantity == before - 1
        assert db.execute(text("SELECT COUNT(*) FROM audit_log")).scalar_one() == 1


def test_public_invoice_tokens_are_unique_and_tenant_exact(api, seeded):
    _, _, ids = seeded
    assert ids["token_a"] != ids["token_b"]

    numeric = _request(api, "GET", "/api/public/invoice/1")
    invalid = _request(api, "GET", "/api/public/invoice/not-a-real-token")
    invoice_a = _request(api, "GET", f"/api/public/invoice/{ids['token_a']}")
    invoice_b = _request(api, "GET", f"/api/public/invoice/{ids['token_b']}")

    assert numeric.status_code == 404
    assert invalid.status_code == 404
    assert invoice_a.status_code == invoice_b.status_code == 200
    assert invoice_a.json()["sale_id"] == str(ids["sale_a"])
    assert invoice_b.json()["sale_id"] == str(ids["sale_b"])
    assert invoice_a.json()["pharmacy_name"] == "PHARMACY_A"
    assert invoice_b.json()["pharmacy_name"] == "PHARMACY_B"


def test_authenticated_sale_detail_remains_tenant_scoped(api, seeded):
    _, _, ids = seeded
    headers_a = _auth(ids["owner_a"], ids["pharmacy_a"], "P0_OWNER_A")
    headers_b = _auth(ids["owner_b"], ids["pharmacy_b"], "P0_OWNER_B")

    assert _request(api, "GET", f"/api/sales/{ids['sale_a']}", headers=headers_a).status_code == 200
    assert _request(api, "GET", f"/api/sales/{ids['sale_b']}", headers=headers_b).status_code == 200
    assert _request(api, "GET", f"/api/sales/{ids['sale_b']}", headers=headers_a).status_code == 404
    assert _request(api, "GET", f"/api/sales/{ids['sale_a']}", headers=headers_b).status_code == 404
