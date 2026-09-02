import os
import re
import uuid
import base64
import socket
import threading
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from auth import get_password_hash
from database import Base, SessionLocal, engine
from models import CustomerHandover, OwnerActivationToken, PasswordResetToken, Pharmacy, Role, User
from rbac_seeder import seed_rbac_foundation
from services.mail import CapturedMailTransport

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_HANDOVER_TESTS") != "1",
    reason="RUN_HANDOVER_TESTS=1 requires a dedicated PostgreSQL DATABASE_URL",
)


@pytest.fixture(scope="module")
def prepared():
    os.environ["PLATFORM_OPERATOR_PASSWORD_HASH"] = get_password_hash(os.environ["PLATFORM_OPERATOR_PASSWORD"])
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("""CREATE TABLE audit_log (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(), pharmacy_id UUID REFERENCES pharmacies(id),
            user_id UUID REFERENCES users(id) ON DELETE SET NULL, user_name VARCHAR(100),
            action_type VARCHAR(50) NOT NULL, description TEXT NOT NULL, target_entity VARCHAR(50),
            target_id VARCHAR(100), old_value TEXT, new_value TEXT, success BOOLEAN DEFAULT TRUE,
            request_ip VARCHAR(64), created_at TIMESTAMP DEFAULT NOW())"""))
        connection.execute(text("""CREATE TABLE stocktake_sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(), pharmacy_id UUID REFERENCES pharmacies(id),
            user_id UUID REFERENCES users(id), notes TEXT, items_adjusted INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW())"""))
        connection.execute(text("""CREATE TABLE stocktake_items (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(), session_id UUID REFERENCES stocktake_sessions(id),
            medicine_id UUID REFERENCES medicines(id), medicine_name VARCHAR(100), system_quantity INTEGER,
            actual_quantity INTEGER, difference INTEGER, created_at TIMESTAMP DEFAULT NOW())"""))
    with SessionLocal.begin() as db:
        seed_rbac_foundation(db)
        role = db.query(Role).filter(Role.name == "pharmacist").one()
        owner_role = db.query(Role).filter(Role.name == "owner").one()
        legacy_pharmacy = Pharmacy(id=uuid.uuid4(), product_key="LEGACY-HANDOVER", name="Legacy", is_active=True, type="demo")
        db.add(legacy_pharmacy); db.flush()
        db.add_all([
            User(id=uuid.uuid4(), pharmacy_id=legacy_pharmacy.id, username="legacy_employee",
                 password_hash=get_password_hash("LegacyEmployee123!"), role="employee", role_id=role.id, is_active=True),
            User(id=uuid.uuid4(), pharmacy_id=legacy_pharmacy.id, username="legacy.owner@example.test",
                 email="legacy.owner@example.test", password_hash=get_password_hash("LegacyOwnerPassword123!"),
                 role="admin", role_id=owner_role.id, is_active=True),
        ])
    return True


def _secret(message, page):
    match = re.search(rf"/{page}#token=([^\s<]+)", message.text)
    assert match
    return match.group(1)


def test_complete_paid_customer_activation_and_recovery(prepared, monkeypatch):
    import internal
    import recovery
    from main import app
    from services.recovery import hash_reset_secret

    activation_mail = CapturedMailTransport()
    reset_mail = CapturedMailTransport()
    monkeypatch.setattr(internal, "get_mail_transport", lambda: activation_mail)
    monkeypatch.setattr(recovery, "get_mail_transport", lambda: reset_mail)
    auth = (os.environ["PLATFORM_OPERATOR_USERNAME"], os.environ["PLATFORM_OPERATOR_PASSWORD"])
    client = TestClient(app)

    payload = {"pharmacy_name": "Handover A", "owner_name": "Owner A", "owner_email": "owner.a@example.test",
               "owner_phone": "", "city": "Khartoum", "payment_confirmed": False}
    internal_headers = {"X-PharmaSUD-Internal": "1"}
    created = client.post("/api/internal/customers", auth=auth, headers=internal_headers, json=payload)
    assert created.status_code == 200
    customer_id = created.json()["customer"]["id"]
    duplicate = client.post("/api/internal/customers", auth=auth, headers=internal_headers, json=payload)
    assert duplicate.status_code == 200 and duplicate.json()["idempotent"] is True
    assert duplicate.json()["customer"]["id"] == customer_id
    assert client.post("/api/internal/customers", auth=auth, json=payload).status_code == 403
    assert client.post(f"/api/internal/customers/{customer_id}/provision", auth=auth, headers=internal_headers).status_code == 409
    assert client.post(f"/api/internal/customers/{customer_id}/confirm-payment", auth=auth, headers=internal_headers).status_code == 200

    provisioned = client.post(f"/api/internal/customers/{customer_id}/provision", auth=auth, headers=internal_headers)
    assert provisioned.status_code == 200 and len(activation_mail.messages) == 1
    assert activation_mail.messages[0].recipient == "owner.a@example.test"
    assert "PharmaSUD" in activation_mail.messages[0].subject
    assert "Handover A" in activation_mail.messages[0].text
    assert "Owner A" in activation_mail.messages[0].text
    activation_secret = _secret(activation_mail.messages[0], "owner-activation")
    with SessionLocal() as db:
        row = db.get(CustomerHandover, uuid.UUID(customer_id))
        owner = db.query(User).filter(User.email == "owner.a@example.test").one()
        owner_identity = (owner.id, owner.pharmacy_id, owner.role_id)
        tokens = db.query(OwnerActivationToken).filter(OwnerActivationToken.user_id == owner.id).all()
        assert row.status == "AWAITING_OWNER_ACTIVATION" and owner.password_hash is None and not owner.is_active
        assert len(tokens) == 1 and activation_secret not in tokens[0].token_hash
        counts = (db.query(Pharmacy).filter(Pharmacy.name == "Handover A").count(),
                  db.query(User).filter(User.email == "owner.a@example.test").count())
        payment_audits = db.execute(text(
            "SELECT count(*) FROM audit_log WHERE action_type='customer_payment_confirmed' AND target_id=:id"
        ), {"id": customer_id}).scalar_one()
        assert payment_audits == 1
    retry = client.post(f"/api/internal/customers/{customer_id}/provision", auth=auth, headers=internal_headers)
    assert retry.status_code == 200 and retry.json()["idempotent"] is True
    with SessionLocal() as db:
        assert counts == (1, 1)

    first_password = "OwnerFirstPassword123!"
    activated = client.post("/api/auth/owner-activation", json={
        "token": activation_secret, "password": first_password, "confirm_password": first_password})
    assert activated.status_code == 200
    assert client.post("/api/auth/owner-activation", json={
        "token": activation_secret, "password": first_password, "confirm_password": first_password}).status_code == 400
    login = client.post("/api/auth/login", json={"username": "owner.a@example.test", "password": first_password})
    assert login.status_code == 200 and login.json()["success"]
    old_token = login.json()["token"]

    generic_existing = client.post("/api/auth/forgot-password", json={"email": "owner.a@example.test"})
    generic_missing = client.post("/api/auth/forgot-password", json={"email": "missing@example.test"})
    assert generic_existing.json()["message"] == generic_missing.json()["message"] and len(reset_mail.messages) == 1
    reset_secret = _secret(reset_mail.messages[0], "reset-password")
    assert reset_mail.messages[0].recipient == "owner.a@example.test"
    assert "PharmaSUD" in reset_mail.messages[0].subject
    with SessionLocal() as db:
        legacy_owner_hash = db.query(User).filter(User.email == "legacy.owner@example.test").one().password_hash
        stored_reset = db.query(PasswordResetToken).filter(
            PasswordResetToken.token_hash == hash_reset_secret(reset_secret)
        ).one()
        assert reset_secret not in stored_reset.token_hash
    new_password = "OwnerResetPassword456!"
    reset = client.post("/api/auth/reset-password", json={
        "token": reset_secret, "password": new_password, "confirm_password": new_password})
    assert reset.status_code == 200
    assert client.post("/api/auth/reset-password", json={
        "token": reset_secret, "password": new_password, "confirm_password": new_password}).status_code == 400
    assert not client.post("/api/auth/login", json={"username": "owner.a@example.test", "password": first_password}).json()["success"]
    assert client.post("/api/auth/login", json={"username": "owner.a@example.test", "password": new_password}).json()["success"]
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer " + old_token}).status_code == 401
    assert client.post("/api/auth/login", json={
        "username": "legacy.owner@example.test", "password": "LegacyOwnerPassword123!"
    }).json()["success"]
    with SessionLocal() as db:
        assert db.query(User).filter(User.email == "legacy.owner@example.test").one().password_hash == legacy_owner_hash
        owner = db.query(User).filter(User.email == "owner.a@example.test").one()
        assert (owner.id, owner.pharmacy_id, owner.role_id) == owner_identity
        assert db.get(CustomerHandover, uuid.UUID(customer_id)).status == "ACTIVE"

    tenant_token = client.post("/api/auth/login", json={"username": "legacy_employee", "password": "LegacyEmployee123!"}).json()["token"]
    assert client.get("/api/internal/customers", headers={"Authorization": "Bearer " + tenant_token}).status_code == 401
    owner_token = client.post("/api/auth/login", json={"username": "owner.a@example.test", "password": new_password}).json()["token"]
    assert client.get("/api/internal/customers", headers={"Authorization": "Bearer " + owner_token}).status_code == 401


def test_reset_expiry_replacement_and_email_failure_reissue(prepared, monkeypatch):
    from datetime import datetime, timedelta
    import internal
    from services.recovery import ResetError, hash_reset_secret, request_password_reset, reset_password

    capture = CapturedMailTransport()
    with SessionLocal.begin() as db:
        request_password_reset(db, email="owner.a@example.test", transport=capture)
        first = _secret(capture.messages[-1], "reset-password")
        request_password_reset(db, email="owner.a@example.test", transport=capture)
        second = _secret(capture.messages[-1], "reset-password")
    with SessionLocal.begin() as db:
        with pytest.raises(ResetError): reset_password(db, secret=first, password="ReplacementPassword123!")
        token = db.query(PasswordResetToken).filter(
            PasswordResetToken.token_hash == hash_reset_secret(second)
        ).one()
        token.expires_at = datetime.utcnow() - timedelta(seconds=1)
    with SessionLocal.begin() as db:
        with pytest.raises(ResetError): reset_password(db, secret=second, password="ExpiredPassword123!")

    class Failing:
        def send(self, message): raise RuntimeError("mail unavailable")
    monkeypatch.setattr(internal, "get_mail_transport", lambda: Failing())
    from main import app
    client = TestClient(app)
    auth = (os.environ["PLATFORM_OPERATOR_USERNAME"], os.environ["PLATFORM_OPERATOR_PASSWORD"])
    internal_headers = {"X-PharmaSUD-Internal": "1"}
    created = client.post("/api/internal/customers", auth=auth, headers=internal_headers, json={
        "pharmacy_name": "Handover B", "owner_name": "Owner B",
        "owner_email": "owner.b@example.test", "payment_confirmed": True,
    })
    customer_id = created.json()["customer"]["id"]
    failed = client.post(f"/api/internal/customers/{customer_id}/provision", auth=auth, headers=internal_headers)
    assert failed.status_code == 200
    assert failed.json()["customer"]["status"] == "ACTIVATION_EMAIL_FAILED"
    with SessionLocal() as db:
        assert db.query(Pharmacy).filter(Pharmacy.name == "Handover B").count() == 1
        assert db.query(User).filter(User.email == "owner.b@example.test").count() == 1

    resent_mail = CapturedMailTransport()
    monkeypatch.setattr(internal, "get_mail_transport", lambda: resent_mail)
    resent = client.post(f"/api/internal/customers/{customer_id}/resend-activation", auth=auth, headers=internal_headers)
    assert resent.status_code == 200
    assert resent.json()["customer"]["status"] == "AWAITING_OWNER_ACTIVATION"
    assert len(resent_mail.messages) == 1
    with SessionLocal() as db:
        owner = db.query(User).filter(User.email == "owner.b@example.test").one()
        valid = db.query(OwnerActivationToken).filter(
            OwnerActivationToken.user_id == owner.id,
            OwnerActivationToken.used_at.is_(None),
            OwnerActivationToken.revoked_at.is_(None),
        ).all()
        assert len(valid) == 1
        assert db.query(Pharmacy).filter(Pharmacy.name == "Handover B").count() == 1
        resend_audits = db.execute(text(
            "SELECT count(*) FROM audit_log WHERE action_type='owner_activation_reissued' AND target_id=:id"
        ), {"id": str(owner.id)}).scalar_one()
        assert resend_audits == 1


def test_internal_console_and_forgot_pages(prepared):
    from main import app
    client = TestClient(app)
    auth = (os.environ["PLATFORM_OPERATOR_USERNAME"], os.environ["PLATFORM_OPERATOR_PASSWORD"])
    assert client.get("/internal/customers", auth=auth).status_code == 200
    assert client.get("/internal/customers").status_code == 401
    assert client.get("/forgot-password").status_code == 200
    assert client.get("/reset-password").status_code == 200


def test_customer_classification_backfill_and_commercial_summary(prepared):
    from datetime import datetime
    from internal import _commercial_summary, _serialize
    from scripts.backfill_customer_semantics import apply_semantics

    with SessionLocal.begin() as db:
        owner_role = db.query(Role).filter(Role.name == "owner").one()

        def tenant(name, key, kind="customer", email=None):
            pharmacy = Pharmacy(
                id=uuid.uuid4(), product_key=key, name=name,
                is_active=True, type=kind,
            )
            db.add(pharmacy); db.flush()
            owner = User(
                id=uuid.uuid4(), pharmacy_id=pharmacy.id,
                username=email or f"{key.lower()}_owner",
                email=email, password_hash=get_password_hash("SemanticOwnerPassword123!"),
                role="admin", role_id=owner_role.id, full_name=name + " Owner", is_active=True,
            )
            db.add(owner); db.flush()
            return pharmacy, owner

        legacy, legacy_owner = tenant("Legacy Commercial", "SEM-LEGACY", email="legacy.semantic@example.test")
        demo, demo_owner = tenant("Marketing Semantics Demo", "SEM-DEMO", kind="demo", email=None)
        qa, qa_owner = tenant("Active QA", "SEM-QA", email="qa.semantic@example.test")
        qa_row = CustomerHandover(
            id=uuid.uuid4(), customer_reference="SEM-QA-CUS", pharmacy_name=qa.name,
            owner_name=qa_owner.full_name, owner_email=qa_owner.email,
            status="ACTIVE", classification="COMMERCIAL", origin="HANDOVER",
            pharmacy_id=qa.id, owner_user_id=qa_owner.id,
        )
        abandoned = CustomerHandover(
            id=uuid.uuid4(), customer_reference="SEM-ABANDONED",
            pharmacy_name="Failed QA", owner_name="Failed QA Owner",
            owner_email="failed.qa@example.test", status="READY_TO_PROVISION",
            classification="COMMERCIAL", origin="HANDOVER",
        )
        db.add_all([qa_row, abandoned])
        legacy_id, legacy_owner_id = legacy.id, legacy_owner.id
        demo_id = demo.id
        qa_id, qa_row_id = qa.id, qa_row.id
        abandoned_id = abandoned.id

    ids = dict(
        commercial_pharmacy_id=str(legacy_id), demo_pharmacy_id=str(demo_id),
        qa_pharmacy_id=str(qa_id), abandoned_handover_id=str(abandoned_id),
        actor="test-operator",
    )
    before_counts = None
    with SessionLocal() as db:
        before_counts = (db.query(Pharmacy).count(), db.query(User).count(), db.query(CustomerHandover).count())
        dry = apply_semantics(db, **ids, apply=False)
        assert dry["mode"] == "DRY_RUN" and dry["changed"]
    with SessionLocal() as db:
        assert db.query(CustomerHandover).filter(CustomerHandover.pharmacy_id == legacy_id).count() == 0

    with SessionLocal() as db:
        applied = apply_semantics(db, **ids, apply=True)
        assert applied["mode"] == "APPLY" and applied["changed"]
    with SessionLocal() as db:
        again = apply_semantics(db, **ids, apply=True)
        assert not again["changed"]
        assert (db.query(Pharmacy).count(), db.query(User).count()) == before_counts[:2]
        commercial_legacy = db.query(CustomerHandover).filter(CustomerHandover.pharmacy_id == legacy_id).one()
        demo_legacy = db.query(CustomerHandover).filter(CustomerHandover.pharmacy_id == demo_id).one()
        assert commercial_legacy.classification == "COMMERCIAL" and commercial_legacy.origin == "LEGACY_BACKFILL"
        assert commercial_legacy.status == "ACTIVE" and commercial_legacy.payment_confirmed_at is None
        assert commercial_legacy.owner_user_id == legacy_owner_id
        assert demo_legacy.classification == "DEMO" and demo_legacy.owner_email is None
        assert qa_row_id == db.get(CustomerHandover, qa_row_id).id
        assert db.get(CustomerHandover, qa_row_id).classification == "QA"
        assert db.get(CustomerHandover, abandoned_id).status == "ABANDONED"
        production_shape = [commercial_legacy, demo_legacy, db.get(CustomerHandover, qa_row_id),
                            db.get(CustomerHandover, abandoned_id)]
        assert _commercial_summary([_serialize(db, row) for row in production_shape]) == {
            "total": 1, "payment_pending": 0, "activation_pending": 0, "active": 1,
        }

        pending = CustomerHandover(
            id=uuid.uuid4(), customer_reference="SEM-PENDING", pharmacy_name="Pending Commercial",
            owner_name="Pending Owner", owner_email="pending.semantic@example.test",
            status="PAYMENT_PENDING", classification="COMMERCIAL", origin="HANDOVER",
        )
        awaiting = CustomerHandover(
            id=uuid.uuid4(), customer_reference="SEM-AWAITING", pharmacy_name="Awaiting Commercial",
            owner_name="Awaiting Owner", owner_email="awaiting.semantic@example.test",
            status="AWAITING_OWNER_ACTIVATION", classification="COMMERCIAL", origin="HANDOVER",
        )
        archived = CustomerHandover(
            id=uuid.uuid4(), customer_reference="SEM-ARCHIVED", pharmacy_name="Archived Commercial",
            owner_name="Archived Owner", owner_email="archived.semantic@example.test",
            status="ARCHIVED", classification="COMMERCIAL", origin="HANDOVER",
            archived_at=datetime.utcnow(),
        )
        db.add_all([pending, awaiting, archived]); db.flush()
        rows = [commercial_legacy, demo_legacy, db.get(CustomerHandover, qa_row_id),
                db.get(CustomerHandover, abandoned_id), pending, awaiting, archived]
        summary = _commercial_summary([_serialize(db, row) for row in rows])
        assert summary == {"total": 3, "payment_pending": 1, "activation_pending": 1, "active": 1}

    from main import app
    client = TestClient(app)
    auth = (os.environ["PLATFORM_OPERATOR_USERNAME"], os.environ["PLATFORM_OPERATOR_PASSWORD"])
    headers = {"X-PharmaSUD-Internal": "1"}
    for action in ("confirm-payment", "provision", "resend-activation", "archive"):
        response = client.post(f"/api/internal/customers/{abandoned_id}/{action}", auth=auth, headers=headers)
        assert response.status_code == 409


@pytest.mark.skipif(
    os.getenv("RUN_HANDOVER_BROWSER") != "1",
    reason="RUN_HANDOVER_BROWSER=1 enables the real Chromium workflow",
)
def test_real_browser_operator_and_recovery_ui(prepared, monkeypatch):
    import main
    import uvicorn
    from playwright.sync_api import sync_playwright

    monkeypatch.setattr(main, "initialize_database", lambda: {"schema_ready": True})
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    assert server.started

    credentials = base64.b64encode(
        f'{os.environ["PLATFORM_OPERATOR_USERNAME"]}:{os.environ["PLATFORM_OPERATOR_PASSWORD"]}'.encode()
    ).decode()
    chrome = "/home/lenovo/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome"
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, executable_path=chrome)
            context = browser.new_context(extra_http_headers={"Authorization": f"Basic {credentials}"})
            page = context.new_page()
            page.goto(f"http://127.0.0.1:{port}/internal/customers")
            assert page.get_by_role("heading", name="إدارة عملاء Daryonix").is_visible()
            assert page.get_by_text("إجمالي العملاء التجاريين", exact=True).is_visible()
            assert page.get_by_text("العملاء التجاريون النشطون", exact=True).is_visible()
            assert page.locator("#filter option").all_text_contents() == [
                "الكل", "العملاء", "بانتظار الدفع", "بانتظار التفعيل", "النشطون",
                "QA / اختبار", "Demo / تجريبي", "غير مكتمل / ملغى", "مؤرشف",
            ]
            page.locator("#open-create").click()
            assert page.locator("#create-dialog").is_visible()
            page.locator("#pharmacy").fill("Browser Handover")
            page.locator("#owner").fill("Browser Owner")
            page.locator("#email").fill("browser.owner@example.test")
            page.locator("#customer-form button[type=submit]").click()
            page.get_by_text("Browser Handover").wait_for()
            card = page.locator("article.customer", has_text="Browser Handover")
            assert "بانتظار الدفع" in card.inner_text()
            page.once("dialog", lambda dialog: dialog.accept())
            card.get_by_text("تأكيد استلام الدفع").click()
            provision = page.locator("article.customer", has_text="Browser Handover").get_by_role("button", name="إنشاء الصيدلية")
            provision.wait_for()
            provision.click()
            card = page.locator("article.customer", has_text="Browser Handover")
            card.get_by_text("إعادة إرسال رابط التفعيل").wait_for()
            page.locator("#search").fill("browser.owner@example.test")
            assert page.locator("article.customer").count() == 1
            page.locator("#search").fill("")
            archive_messages = []
            def accept_archive(dialog):
                archive_messages.append(dialog.message)
                dialog.accept()
            page.once("dialog", accept_archive)
            card.get_by_text("أرشفة العميل").click()
            assert archive_messages == ["هل أنت متأكد من أرشفة هذا العميل؟"]
            page.locator("#filter").select_option("ARCHIVED")
            archived = page.locator("article.customer", has_text="Browser Handover")
            archived.wait_for()
            assert "مؤرشف" in archived.inner_text()
            assert archived.locator("[data-action]").count() == 0
            archived_id = archived.get_attribute("data-customer-id")
            repeated_archive = page.evaluate("""async id => {
                const response = await fetch(`/api/internal/customers/${id}/archive`, {
                    method: 'POST', headers: {'X-PharmaSUD-Internal': '1'}
                });
                return {status: response.status, body: await response.json()};
            }""", archived_id)
            assert repeated_archive["status"] == 200
            assert repeated_archive["body"]["idempotent"] is True
            blocked_payment = page.evaluate("""async id => {
                const response = await fetch(`/api/internal/customers/${id}/confirm-payment`, {
                    method: 'POST', headers: {'X-PharmaSUD-Internal': '1'}
                });
                return response.status;
            }""", archived_id)
            assert blocked_payment == 409

            for viewport in ({"width": 390, "height": 844}, {"width": 360, "height": 800}):
                page.set_viewport_size(viewport)
                page.locator("#filter").select_option("ALL")
                assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
                assert page.get_by_role("button", name="إضافة عميل جديد").is_visible()
                assert page.locator("html").get_attribute("dir") == "rtl"

            page.set_viewport_size({"width": 1280, "height": 800})
            page.goto(f"http://127.0.0.1:{port}/login")
            page.locator('input[x-model="username"]').fill("legacy_employee")
            page.locator('input[x-model="password"]').fill("LegacyEmployee123!")
            page.locator(".btn-signin").click()
            page.wait_for_url("**/dashboard")
            assert page.url.endswith("/dashboard")

            page.goto(f"http://127.0.0.1:{port}/forgot-password")
            page.locator("#email").fill("absent@example.test")
            page.locator("button").click()
            page.locator("#message").get_by_text("If an account exists", exact=False).wait_for()
            page.goto(f"http://127.0.0.1:{port}/reset-password#token=invalid-browser-token-value-123456")
            assert page.locator("#password").get_attribute("autocomplete") == "new-password"
            assert page.locator("#confirm").get_attribute("autocomplete") == "new-password"
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
    assert not thread.is_alive()
    with SessionLocal() as db:
        handover = db.query(CustomerHandover).filter(CustomerHandover.pharmacy_name == "Browser Handover").one()
        pharmacy = db.get(Pharmacy, handover.pharmacy_id)
        owner = db.query(User).filter(User.pharmacy_id == pharmacy.id).one()
        archived_audits = db.execute(text(
            "SELECT count(*) FROM audit_log WHERE action_type='customer_archived' AND target_id=:id"
        ), {"id": str(handover.id)}).scalar_one()
        assert handover.status == "ARCHIVED" and handover.archived_at and handover.archived_by
        assert not pharmacy.is_active and not owner.is_active
        assert db.query(Pharmacy).filter(Pharmacy.id == pharmacy.id).count() == 1
        assert db.query(User).filter(User.id == owner.id).count() == 1
        assert archived_audits == 1
