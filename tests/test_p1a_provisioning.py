import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
import os
import uuid

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from auth import authenticate_user, create_access_token, get_current_user
from batches import router as batches_router
from database import get_db
from medicines import router as medicines_router
from models import Base, Batch, Medicine, OwnerActivationToken, Pharmacy, Role, Sale, User
from reports import router as reports_router
from rbac_seeder import ROLE_PERMISSIONS, seed_rbac_foundation
from sales import router as sales_router
from services import provisioning as provisioning_module
from services.provisioning import (
    ActivationError, CustomerReferenceConflict, ProvisioningInput,
    ProvisioningService, activate_owner, hash_activation_secret,
)
from scripts.provision_customer_pharmacy import enforce_environment_gate


DATABASE_URL = os.environ.get("P1A_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="P1A_TEST_DATABASE_URL must point to disposable PostgreSQL",
)


def _schema_support(engine):
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE audit_log (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                pharmacy_id UUID REFERENCES pharmacies(id),
                user_id UUID REFERENCES users(id) ON DELETE SET NULL,
                user_name VARCHAR(100), action_type VARCHAR(50) NOT NULL,
                description TEXT NOT NULL, target_entity VARCHAR(50), target_id VARCHAR(100),
                old_value TEXT, new_value TEXT, success BOOLEAN NOT NULL DEFAULT TRUE,
                request_ip VARCHAR(64), created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        connection.execute(text("""
            CREATE TABLE stocktake_sessions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(), pharmacy_id UUID REFERENCES pharmacies(id),
                user_id UUID REFERENCES users(id), notes TEXT, items_adjusted INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        connection.execute(text("""
            CREATE TABLE stocktake_items (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                session_id UUID REFERENCES stocktake_sessions(id), medicine_id UUID REFERENCES medicines(id),
                medicine_name VARCHAR(100), system_quantity INTEGER, actual_quantity INTEGER,
                difference INTEGER, created_at TIMESTAMP DEFAULT NOW()
            )
        """))


@pytest.fixture(scope="module")
def p1a_db():
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    Base.metadata.create_all(engine)
    _schema_support(engine)
    with factory.begin() as session:
        seed_rbac_foundation(session)
    config = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    config.set_main_option("sqlalchemy.url", DATABASE_URL)
    command.stamp(config, "20260827_owner_email_password")
    yield engine, factory
    engine.dispose()


@pytest.fixture(scope="module")
def provisioned(p1a_db):
    engine, factory = p1a_db
    service = ProvisioningService(factory)
    a = service.provision(ProvisioningInput(
        customer_reference="ORDER-A", pharmacy_name="PHARMACY_A", owner_name="OWNER A",
        owner_email="owner.a@example.com", operator="TEST OPERATOR",
        provisioning_request_id=uuid.uuid4(),
    ))
    b = service.provision(ProvisioningInput(
        customer_reference="ORDER-B", pharmacy_name="PHARMACY_B", owner_name="OWNER B",
        owner_email="owner.b@example.com", operator="TEST OPERATOR",
        provisioning_request_id=uuid.uuid4(),
    ))
    return engine, factory, service, a, b


def _owner(session, reference):
    return session.query(User).join(Pharmacy).filter(Pharmacy.customer_reference == reference).one()


def test_provisions_two_fully_linked_inactive_owners(provisioned):
    _, factory, _, a, b = provisioned
    assert a.status == b.status == "PROVISIONING_SUCCESS"
    assert a.product_key != b.product_key
    assert len(a.product_key.removeprefix("PHARM-")) >= 32
    with factory() as session:
        owner_role = session.query(Role).filter(Role.name == "owner").one()
        assert {p.code for p in owner_role.permissions} == set(ROLE_PERMISSIONS["owner"])
        owner_a, owner_b = _owner(session, "ORDER-A"), _owner(session, "ORDER-B")
        assert owner_a.pharmacy_id != owner_b.pharmacy_id
        assert owner_a.role_id == owner_b.role_id == owner_role.id
        assert owner_a.role == owner_b.role == "admin"
        assert owner_a.is_active is owner_b.is_active is False
        assert owner_a.password_hash is owner_b.password_hash is None
        assert owner_a.email == owner_a.username == "owner.a@example.com"


def test_provisioning_requires_valid_email_and_never_hashes_a_password(p1a_db, monkeypatch):
    _, factory = p1a_db
    monkeypatch.setattr(
        provisioning_module, "get_password_hash",
        lambda _password: (_ for _ in ()).throw(AssertionError("provisioning must not hash a password")),
    )
    result = ProvisioningService(factory).provision(ProvisioningInput(
        customer_reference="ORDER-NO-PASSWORD", pharmacy_name="No Password Pharmacy",
        owner_name="No Password Owner", owner_email="new.owner@example.com",
        operator="TEST OPERATOR",
    ))
    assert result.status == "PROVISIONING_SUCCESS"
    with factory() as session:
        owner = _owner(session, "ORDER-NO-PASSWORD")
        assert owner.password_hash is None
        assert owner.is_active is False
    with pytest.raises(ValueError):
        ProvisioningService(factory).provision(ProvisioningInput(
            customer_reference="ORDER-BAD-EMAIL", pharmacy_name="Bad Email Pharmacy",
            owner_name="Bad Email Owner", owner_email="not-an-email",
            operator="TEST OPERATOR",
        ))


def test_activation_hash_only_expiry_and_single_use(provisioned):
    _, factory, _, a, _ = provisioned
    with factory() as session:
        token = session.query(OwnerActivationToken).filter(
            OwnerActivationToken.provisioning_request_id == a.provisioning_request_id
        ).one()
        assert token.token_hash == hash_activation_secret(a.activation_secret)
        assert a.activation_secret not in token.token_hash
        assert a.activation_secret not in str(token.__dict__)
    assert authenticate_user("owner.a@example.com", "Owner-A-Password!", factory())["success"] is False
    with factory.begin() as session:
        activate_owner(session, secret=a.activation_secret, password="Owner-A-Password!")
    with factory() as session:
        assert _owner(session, "ORDER-A").is_active is True
        owner = _owner(session, "ORDER-A")
        assert owner.password_hash and owner.password_hash.startswith("$2")
        assert authenticate_user("owner.a@example.com", "Owner-A-Password!", session)["success"] is True
        assert authenticate_user("OWNER.A@EXAMPLE.COM", "Owner-A-Password!", session)["success"] is True
        assert session.execute(text("""
            SELECT count(*) FROM audit_log
            WHERE action_type='owner_first_login_activated'
              AND pharmacy_id=(SELECT id FROM pharmacies WHERE customer_reference='ORDER-A')
        """)).scalar_one() == 1
    with pytest.raises(ActivationError), factory.begin() as session:
        activate_owner(session, secret=a.activation_secret, password="Another-Password!")

    expired_secret = "expired-" + "x" * 40
    with factory.begin() as session:
        owner_b = _owner(session, "ORDER-B")
        session.add(OwnerActivationToken(
            id=uuid.uuid4(), user_id=owner_b.id, token_hash=hash_activation_secret(expired_secret),
            expires_at=datetime.utcnow() - timedelta(seconds=1),
            provisioning_request_id=owner_b.pharmacy.provisioning_request_id,
        ))
    with pytest.raises(ActivationError), factory.begin() as session:
        activate_owner(session, secret=expired_secret, password="Owner-B-Password!")


def test_null_password_fails_closed_even_if_account_is_active(p1a_db):
    _, factory = p1a_db
    with factory.begin() as session:
        owner = _owner(session, "ORDER-B")
        owner.is_active = True
        assert owner.password_hash is None
    with factory() as session:
        assert authenticate_user("owner.b@example.com", "any-password", session)["success"] is False
    with factory.begin() as session:
        _owner(session, "ORDER-B").is_active = False


def test_activation_hash_failure_rolls_back_atomically(provisioned, monkeypatch):
    _, factory, _, _, b = provisioned
    monkeypatch.setattr(
        provisioning_module, "get_password_hash",
        lambda _password: (_ for _ in ()).throw(RuntimeError("hash failure")),
    )
    with pytest.raises(RuntimeError), factory.begin() as session:
        activate_owner(session, secret=b.activation_secret, password="Owner-B-Password!")
    with factory() as session:
        owner = _owner(session, "ORDER-B")
        token = session.query(OwnerActivationToken).filter(
            OwnerActivationToken.token_hash == hash_activation_secret(b.activation_secret)
        ).one()
        assert owner.is_active is False
        assert owner.password_hash is None
        assert token.used_at is None


def test_idempotency_reference_request_and_conflict(provisioned):
    _, factory, service, _, b = provisioned
    same = ProvisioningInput(
        customer_reference="order-b", pharmacy_name="PHARMACY_B", owner_name="OWNER B",
        owner_email="OWNER.B@EXAMPLE.COM", operator="TEST OPERATOR",
        provisioning_request_id=b.provisioning_request_id,
    )
    retry = service.provision(same)
    assert retry.status == "ALREADY_PROVISIONED"
    assert retry.activation_secret is None
    with factory() as session:
        assert session.query(Pharmacy).filter(Pharmacy.customer_reference == "ORDER-B").count() == 1
    with pytest.raises(CustomerReferenceConflict):
        service.provision(ProvisioningInput(
            customer_reference="ORDER-B", pharmacy_name="DIFFERENT", owner_name="OWNER B",
            owner_email="owner.b@example.com", operator="TEST OPERATOR",
        ))


def test_activation_reissue_is_explicit_and_revokes_previous(provisioned):
    _, factory, service, _, _ = provisioned
    initial = service.provision(ProvisioningInput(
        customer_reference="ORDER-REISSUE", pharmacy_name="Reissue Pharmacy",
        owner_name="Reissue Owner", owner_email="owner.reissue@example.com",
        operator="TEST OPERATOR",
    ))
    original = initial.activation_secret
    reissued = service.reissue_activation("ORDER-REISSUE", "TEST OPERATOR")
    assert reissued.status == "ACTIVATION_REISSUED"
    assert reissued.activation_secret != original
    with pytest.raises(ActivationError), factory.begin() as session:
        activate_owner(session, secret=original, password="Owner-B-Password!")
    with factory() as session:
        assert session.execute(text("""
            SELECT count(*) FROM audit_log
            WHERE action_type='owner_activation_reissued'
              AND pharmacy_id=(SELECT id FROM pharmacies WHERE customer_reference='ORDER-REISSUE')
        """)).scalar_one() == 1


def test_concurrent_retry_creates_one_tenant(p1a_db):
    _, factory = p1a_db
    request_id = uuid.uuid4()
    data = ProvisioningInput(
        customer_reference="ORDER-CONCURRENT", pharmacy_name="Concurrent Pharmacy",
        owner_name="Concurrent Owner", owner_email="owner.concurrent@example.com",
        operator="TEST OPERATOR", provisioning_request_id=request_id,
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: ProvisioningService(factory).provision(data), range(2)))
    assert sorted(r.status for r in results) == ["ALREADY_PROVISIONED", "PROVISIONING_SUCCESS"]
    with factory() as session:
        assert session.query(Pharmacy).filter(Pharmacy.customer_reference == "ORDER-CONCURRENT").count() == 1
        pharmacy = session.query(Pharmacy).filter(Pharmacy.customer_reference == "ORDER-CONCURRENT").one()
        assert session.query(User).filter(User.pharmacy_id == pharmacy.id).count() == 1


@pytest.mark.parametrize("stage", [
    "after_pharmacy_flush", "after_owner_flush", "after_role_assignment",
    "after_activation_creation", "after_audit_insertion",
])
def test_failure_injection_rolls_back_everything(p1a_db, stage):
    _, factory = p1a_db
    reference = "FAIL-" + stage.upper().replace("_", "-")
    def fail(current):
        if current == stage:
            raise RuntimeError("injected")
    service = ProvisioningService(factory, failure_injector=fail)
    with pytest.raises(RuntimeError):
        service.provision(ProvisioningInput(
            customer_reference=reference, pharmacy_name="Rollback Pharmacy",
            owner_name="Rollback Owner", owner_email=("rb." + stage + "@example.com"),
            operator="TEST OPERATOR",
        ))
    with factory() as session:
        assert session.query(Pharmacy).filter(Pharmacy.customer_reference == reference).count() == 0


def test_audit_failure_rolls_back(p1a_db, monkeypatch):
    _, factory = p1a_db
    monkeypatch.setattr(provisioning_module, "add_audit_event", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("audit")))
    with pytest.raises(RuntimeError):
        ProvisioningService(factory).provision(ProvisioningInput(
            customer_reference="FAIL-AUDIT", pharmacy_name="Audit Rollback",
            owner_name="Audit Owner", owner_email="audit.owner@example.com", operator="TEST OPERATOR",
        ))
    with factory() as session:
        assert session.query(Pharmacy).filter(Pharmacy.customer_reference == "FAIL-AUDIT").count() == 0


def test_email_identity_and_product_key_uniqueness(provisioned):
    _, factory, service, _, _ = provisioned
    with pytest.raises(Exception):
        service.provision(ProvisioningInput(
            customer_reference="DUP-USERNAME", pharmacy_name="Duplicate Username",
            owner_name="Duplicate", owner_email="OWNER.A@EXAMPLE.COM", operator="TEST OPERATOR",
        ))
    with factory() as session:
        assert session.query(Pharmacy).filter(Pharmacy.customer_reference == "DUP-USERNAME").count() == 0
        existing_key = session.query(Pharmacy.product_key).first()[0]
    with pytest.raises(IntegrityError), factory.begin() as session:
        session.add(Pharmacy(product_key=existing_key, name="Duplicate Key", is_active=True, type="customer"))


def _credentials(token):
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_jwt_tenant_mismatch_and_suspension(provisioned):
    _, factory, _, _, _ = provisioned
    with factory() as session:
        owner = _owner(session, "ORDER-A")
        pharmacy_id, owner_id = owner.pharmacy_id, owner.id
    valid = create_access_token({"user_id": str(owner_id), "pharmacy_id": str(pharmacy_id), "role": "admin"})
    mismatch = create_access_token({"user_id": str(owner_id), "pharmacy_id": str(uuid.uuid4()), "role": "admin"})
    with factory() as session:
        context = asyncio.run(get_current_user(_credentials(valid), session))
        assert context["pharmacy_id"] == str(pharmacy_id)
        with pytest.raises(Exception):
            asyncio.run(get_current_user(_credentials(mismatch), session))
    with factory() as session:
        before = {
            "users": session.query(User).filter(User.pharmacy_id == pharmacy_id).count(),
            "medicines": session.query(Medicine).filter(Medicine.pharmacy_id == pharmacy_id).count(),
            "sales": session.query(Sale).filter(Sale.pharmacy_id == pharmacy_id).count(),
        }
    with factory.begin() as session:
        pharmacy = session.get(Pharmacy, pharmacy_id)
        pharmacy.is_active = False
    with factory() as session:
        assert authenticate_user("owner.a@example.com", "Owner-A-Password!", session)["success"] is False
        with pytest.raises(Exception):
            asyncio.run(get_current_user(_credentials(valid), session))
        assert session.query(User).filter(User.pharmacy_id == pharmacy_id).count() == 1
        assert {
            "users": session.query(User).filter(User.pharmacy_id == pharmacy_id).count(),
            "medicines": session.query(Medicine).filter(Medicine.pharmacy_id == pharmacy_id).count(),
            "sales": session.query(Sale).filter(Sale.pharmacy_id == pharmacy_id).count(),
        } == before
    with factory.begin() as session:
        session.get(Pharmacy, pharmacy_id).is_active = True
    with factory() as session:
        assert authenticate_user("owner.a@example.com", "Owner-A-Password!", session)["success"] is True


def _request(app, method, path, **kwargs):
    async def execute():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://p1a.test") as client:
            return await client.request(method, path, **kwargs)
    return asyncio.run(execute())


@pytest.fixture(scope="module")
def api(provisioned):
    _, factory, _, _, b = provisioned
    with factory.begin() as session:
        activate_owner(session, secret=b.activation_secret, password="Owner-B-Password!")

    async def test_db():
        session = factory()
        try:
            yield session
        finally:
            session.close()
    app = FastAPI()
    for router in (medicines_router, batches_router, sales_router, reports_router):
        app.include_router(router)
    app.dependency_overrides[get_db] = test_db
    return app


def _headers(factory, reference, password):
    with factory() as session:
        owner = _owner(session, reference)
        result = authenticate_user(owner.username, password, session)
        assert result["success"] is True
        return {"Authorization": f"Bearer {result['token']}"}


def test_business_lifecycle_and_bidirectional_isolation(api, provisioned):
    _, factory, _, _, _ = provisioned
    headers_a = _headers(factory, "ORDER-A", "Owner-A-Password!")
    headers_b = _headers(factory, "ORDER-B", "Owner-B-Password!")
    med_payload = {
        "trade_name": "A_ONLY_MEDICINE", "scientific_name": "A", "category": "أخرى",
        "barcode": "P1A-A-001", "sale_price": 10, "purchase_price": 4,
        "base_unit": "unit", "min_stock": 1,
    }
    created = _request(api, "POST", "/api/medicines/", headers=headers_a, json=med_payload)
    assert created.status_code == 200
    medicine_id = created.json()["medicine_id"]
    received = _request(api, "POST", "/api/batches/receive", headers=headers_a, json={
        "medicine_id": medicine_id, "batch_number": "P1A-A-BATCH", "quantity": 10,
        "unit_name": "unit", "expiry_date": str(date.today() + timedelta(days=365)),
        "purchase_price": 4,
    })
    assert received.status_code == 200
    sale = _request(api, "POST", "/api/sales/create", headers=headers_a, json={
        "items": [{"medicine_id": medicine_id, "unit_name": "unit", "quantity": 1, "unit_price": 10}],
        "payment_method": "cash", "total_amount": 10,
    })
    assert sale.status_code == 200
    list_a = _request(api, "GET", "/api/medicines/", headers=headers_a)
    list_b = _request(api, "GET", "/api/medicines/", headers=headers_b)
    assert any(m["id"] == medicine_id for m in list_a.json()["medicines"])
    assert all(m["id"] != medicine_id for m in list_b.json()["medicines"])
    assert _request(api, "GET", f"/api/medicines/{medicine_id}", headers=headers_b).status_code == 404
    assert _request(api, "PUT", f"/api/medicines/{medicine_id}", headers=headers_b, json={"trade_name": "B_WRITE"}).status_code == 404
    created_b = _request(api, "POST", "/api/medicines/", headers=headers_b, json={
        **med_payload, "trade_name": "B_ONLY_MEDICINE", "scientific_name": "B",
        "barcode": "P1A-B-001", "sale_price": 20, "purchase_price": 8,
    })
    assert created_b.status_code == 200
    b_id = created_b.json()["medicine_id"]
    received_b = _request(api, "POST", "/api/batches/receive", headers=headers_b, json={
        "medicine_id": b_id, "batch_number": "P1A-B-BATCH", "quantity": 8,
        "unit_name": "unit", "expiry_date": str(date.today() + timedelta(days=365)),
        "purchase_price": 8,
    })
    assert received_b.status_code == 200
    sale_b = _request(api, "POST", "/api/sales/create", headers=headers_b, json={
        "items": [{"medicine_id": b_id, "unit_name": "unit", "quantity": 1, "unit_price": 20}],
        "payment_method": "cash", "total_amount": 20,
    })
    assert sale_b.status_code == 200
    assert _request(api, "GET", f"/api/medicines/{b_id}", headers=headers_a).status_code == 404
    assert _request(api, "PUT", f"/api/medicines/{b_id}", headers=headers_a, json={"trade_name": "A_WRITE"}).status_code == 404
    report_a = _request(api, "GET", "/api/reports/sales", headers=headers_a)
    report_b = _request(api, "GET", "/api/reports/sales", headers=headers_b)
    assert report_a.status_code == report_b.status_code == 200
    assert report_a.json() != report_b.json()
    history = _request(api, "GET", "/api/sales/", headers=headers_a)
    history_b = _request(api, "GET", "/api/sales/", headers=headers_b)
    assert history.status_code == history_b.status_code == 200
    sale_ids_a = {item["sale_id"] for item in history.json()["sales"]}
    sale_ids_b = {item["sale_id"] for item in history_b.json()["sales"]}
    assert sale_ids_a and sale_ids_b and sale_ids_a.isdisjoint(sale_ids_b)
    # A fresh login after the sale proves persisted credentials and business data.
    relogin_headers = _headers(factory, "ORDER-A", "Owner-A-Password!")
    persisted = _request(api, "GET", "/api/sales/", headers=relogin_headers)
    assert persisted.status_code == 200 and len(persisted.json()["sales"]) >= 1


class Args:
    non_interactive = True
    confirm_production = True
    expected_db_fingerprint = "abc123"
    customer_reference = "ORDER-X"
    operator = "operator"


def test_environment_gate_fail_closed():
    metadata = {
        "environment": "production", "database_type": "postgresql",
        "database_fingerprint": "abc123", "current_alembic_revision": "20260827_owner_email_password",
    }
    enforce_environment_gate(Args(), metadata)
    for key, value in [
        ("database_type", "sqlite"),
        ("database_fingerprint", "wrong"),
        ("current_alembic_revision", "old"),
    ]:
        bad = {**metadata, key: value}
        with pytest.raises(RuntimeError):
            enforce_environment_gate(Args(), bad)
    args = Args(); args.confirm_production = False
    with pytest.raises(RuntimeError):
        enforce_environment_gate(args, metadata)


def test_interactive_production_confirmation(monkeypatch):
    metadata = {
        "environment": "production", "database_type": "postgresql",
        "database_fingerprint": "abc123", "current_alembic_revision": "20260827_owner_email_password",
    }
    args = Args(); args.non_interactive = False
    monkeypatch.setattr("builtins.input", lambda _prompt: "PROVISION ORDER-X ON abc123")
    enforce_environment_gate(args, metadata)
    monkeypatch.setattr("builtins.input", lambda _prompt: "yes")
    with pytest.raises(RuntimeError):
        enforce_environment_gate(args, metadata)


def test_activation_handoff_uses_url_fragment_not_query_string():
    root = os.path.dirname(os.path.dirname(__file__))
    cli_source = open(
        os.path.join(root, "scripts", "provision_customer_pharmacy.py"),
        encoding="utf-8",
    ).read()
    template_source = open(
        os.path.join(root, "templates", "owner_activation.html"),
        encoding="utf-8",
    ).read()
    assert "/owner-activation#token=" in cli_source
    assert "/owner-activation?token=" not in cli_source
    assert "window.location.hash" in template_source
    assert "window.location.search" not in template_source
