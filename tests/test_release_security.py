import argparse
import ast
import asyncio
import uuid
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
from auth import authenticate_user, get_password_hash, verify_password
from database import validate_database_url
from demo import seed_demo_pharmacy as demo_seeder
from models import Base, PasswordChange, Pharmacy, Role, Sale, User
from employees import EmployeeCreateSchema, create_employee, delete_employee, toggle_employee
from settings import change_password
from rbac_seeder import seed_rbac_foundation
from scripts import bootstrap_marketing_demo

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def db_session():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with engine.begin() as connection:
        connection.execute(text("""CREATE TABLE audit_log (
            id CHAR(32) PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))), pharmacy_id CHAR(32), user_id CHAR(32),
            user_name VARCHAR(100), action_type VARCHAR(50), description TEXT,
            target_entity VARCHAR(50), target_id VARCHAR(100), success BOOLEAN, request_ip VARCHAR(64)
        )"""))
    session = factory()
    try:
        yield session, factory, engine
    finally:
        session.close()


def test_production_demo_http_routes_are_not_available(monkeypatch):
    monkeypatch.setattr(main, "initialize_database", lambda: {"schema_ready": True})
    client = TestClient(main.app)
    assert client.post("/api/auth/seed-demo", json={}).status_code == 404
    assert client.post("/api/auth/create-pharmacy", json={}).status_code == 404
    assert client.post("/api/auth/activate", json={"product_key": "retired"}).status_code == 404
    assert client.post("/api/auth/setup", json={}).status_code == 404
    assert "تفعيل بمفتاح المنتج" not in (ROOT / "templates" / "login.html").read_text(encoding="utf-8")


def test_database_url_validation_fails_closed():
    for value in ("", "sqlite:///test.db", "postgresql://user:pass@localhost/db"):
        with pytest.raises(RuntimeError):
            validate_database_url(value, "production")
    parsed = validate_database_url("postgresql://user:p%40ss@pooler.example.neon.tech/db?sslmode=require", "production")
    assert parsed.query["sslmode"] == "require"


def test_database_outage_returns_controlled_health_failure(monkeypatch):
    monkeypatch.setattr(main, "test_connection", lambda: False)
    monkeypatch.setattr(main, "get_tables_count", lambda: 0)
    response = TestClient(main.app).get("/health")
    assert response.status_code == 503
    assert response.json()["database"] == "disconnected"
    assert "DATABASE_URL" not in response.text


def _create_demo_admin(session, username="demo_admin", password="OriginalPassword123!"):
    seed_rbac_foundation(session)
    pharmacy = Pharmacy(id=uuid.uuid4(), product_key=f"DEMO-{uuid.uuid4().hex}", name="Demo", owner_name="Owner", is_active=True, type="demo")
    owner = session.query(Role).filter(Role.name == "owner").one()
    user = User(id=uuid.uuid4(), pharmacy_id=pharmacy.id, username=username, full_name="Demo Owner", password_hash=get_password_hash(password), role="admin", role_id=owner.id, is_active=True)
    session.add_all([pharmacy, user])
    session.commit()
    return pharmacy, user


def test_demo_reseed_preserves_all_users_and_password_hashes(db_session, monkeypatch):
    session, _, engine = db_session
    pharmacy, admin = _create_demo_admin(session)
    original = (admin.id, admin.password_hash, admin.role_id)
    monkeypatch.setattr(demo_seeder, "engine", engine)
    demo_seeder.seed_demo_pharmacy(str(pharmacy.id))
    first = {u.username: (u.id, u.password_hash, u.role_id) for u in session.query(User).all()}
    demo_seeder.seed_demo_pharmacy(str(pharmacy.id))
    session.expire_all()
    second = {u.username: (u.id, u.password_hash, u.role_id) for u in session.query(User).all()}
    assert first == second
    assert second["demo_admin"] == original


def test_customer_pharmacy_cannot_be_demo_seeded(db_session):
    session, _, _ = db_session
    pharmacy = Pharmacy(id=uuid.uuid4(), product_key="CUSTOMER-KEY-123", name="Customer", owner_name="Owner", is_active=True, type="customer")
    session.add(pharmacy)
    session.commit()
    with pytest.raises(ValueError, match="not a demo pharmacy"):
        demo_seeder.seed_demo_pharmacy(str(pharmacy.id), db=session)


def test_direct_demo_seeder_fails_closed_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(RuntimeError, match="bootstrap CLI"):
        demo_seeder.seed_demo_pharmacy(str(uuid.uuid4()))


def test_rbac_is_idempotent_and_preserves_user_identity(db_session):
    session, _, _ = db_session
    _, user = _create_demo_admin(session, username="owner")
    before = (user.id, user.username, user.password_hash, user.pharmacy_id, user.role)
    seed_rbac_foundation(session)
    second = seed_rbac_foundation(session)
    session.commit()
    session.refresh(user)
    after = (user.id, user.username, user.password_hash, user.pharmacy_id, user.role)
    assert before == after
    assert second["roles"] == second["permissions"] == second["role_permissions"] == 0


def test_bootstrap_is_repeatable_and_preserves_hash(db_session, monkeypatch):
    session, factory, _ = db_session
    session.close()
    monkeypatch.setattr(bootstrap_marketing_demo, "initialize_database", lambda: None)
    monkeypatch.setattr(bootstrap_marketing_demo, "SessionLocal", factory)
    args = argparse.Namespace(confirm_demo_bootstrap=True, username="marketing_admin", demo_key="MARKETING-DEMO-KEY", pharmacy_name="Marketing Demo", owner_name="Marketing Owner")
    first = bootstrap_marketing_demo.bootstrap(args, "VeryStrongPassword123!")
    with factory() as check:
        user = check.query(User).filter(User.username == "marketing_admin").one()
        first_identity = (user.id, user.password_hash, user.role_id)
    second = bootstrap_marketing_demo.bootstrap(args, "DifferentPassword456!")
    with factory() as check:
        user = check.query(User).filter(User.username == "marketing_admin").one()
        second_identity = (user.id, user.password_hash, user.role_id)
    assert first_identity == second_identity
    assert first["created"]["administrators"] == 1
    assert second["skipped"]["administrators"] == 1


def test_login_survives_reseed(db_session, monkeypatch):
    session, _, engine = db_session
    pharmacy, _ = _create_demo_admin(session)
    assert authenticate_user("demo_admin", "OriginalPassword123!", session)["success"] is True
    monkeypatch.setattr(demo_seeder, "engine", engine)
    demo_seeder.seed_demo_pharmacy(str(pharmacy.id))
    session.expire_all()
    assert authenticate_user("demo_admin", "OriginalPassword123!", session)["success"] is True
    assert authenticate_user("demo_admin", "wrong", session)["success"] is False


def _context(user):
    return {
        "user_id": str(user.id), "pharmacy_id": str(user.pharmacy_id),
        "role": user.role, "username": user.username, "full_name": user.full_name,
    }


def test_password_change_full_lifecycle_and_identity_invariants(db_session):
    session, _, _ = db_session
    pharmacy, owner = _create_demo_admin(session, username="password_owner", password="OriginalPassword123!")
    other = User(
        pharmacy_id=pharmacy.id, username="other_user", full_name="Other",
        password_hash=get_password_hash("OtherPassword123!"), role="employee", is_active=True,
    )
    session.add(other)
    session.commit()
    before = (owner.id, owner.pharmacy_id, owner.role_id, other.password_hash)

    asyncio.run(change_password(
        PasswordChange(
            current_password="OriginalPassword123!",
            new_password="ReplacementPassword456!",
            confirm_new_password="ReplacementPassword456!",
        ), current_user=_context(owner), db=session,
    ))
    session.refresh(owner)
    assert not verify_password("OriginalPassword123!", owner.password_hash)
    assert verify_password("ReplacementPassword456!", owner.password_hash)
    assert (owner.id, owner.pharmacy_id, owner.role_id, other.password_hash) == before

    with pytest.raises(Exception) as wrong:
        asyncio.run(change_password(PasswordChange(
            current_password="wrong-current",
            new_password="AnotherPassword789!",
            confirm_new_password="AnotherPassword789!",
        ), current_user=_context(owner), db=session))
    assert getattr(wrong.value, "status_code", None) == 400

    with pytest.raises(Exception) as mismatch:
        asyncio.run(change_password(PasswordChange(
            current_password="ReplacementPassword456!",
            new_password="AnotherPassword789!",
            confirm_new_password="MismatchPassword789!",
        ), current_user=_context(owner), db=session))
    assert getattr(mismatch.value, "status_code", None) == 400


def test_employee_lifecycle_owner_safety_and_cross_tenant_guards(db_session):
    session, _, _ = db_session
    pharmacy, owner = _create_demo_admin(session, username="employee_owner")
    employee_role = session.query(Role).filter(Role.name == "cashier").one()
    created = asyncio.run(create_employee(EmployeeCreateSchema(
        full_name="Disposable Cashier", username="disposable_cashier",
        password="DisposablePassword123!", role="cashier",
    ), current_user=_context(owner), db=session))
    employee = session.get(User, uuid.UUID(created["employee_id"]))
    assert employee.pharmacy_id == pharmacy.id
    assert employee.role_id == employee_role.id
    assert verify_password("DisposablePassword123!", employee.password_hash)

    asyncio.run(toggle_employee(str(employee.id), current_user=_context(owner), db=session))
    session.refresh(employee)
    assert employee.is_active is False
    assert authenticate_user(employee.username, "DisposablePassword123!", session)["success"] is False
    asyncio.run(toggle_employee(str(employee.id), current_user=_context(owner), db=session))
    session.refresh(employee)
    assert employee.is_active is True
    assert authenticate_user(employee.username, "DisposablePassword123!", session)["success"] is True

    with pytest.raises(Exception) as self_toggle:
        asyncio.run(toggle_employee(str(owner.id), current_user=_context(owner), db=session))
    assert getattr(self_toggle.value, "status_code", None) == 400
    with pytest.raises(Exception) as self_delete:
        asyncio.run(delete_employee(str(owner.id), current_user=_context(owner), db=session))
    assert getattr(self_delete.value, "status_code", None) == 400

    foreign_pharmacy, foreign_owner = _create_demo_admin(session, username="foreign_owner")
    with pytest.raises(Exception) as foreign_toggle:
        asyncio.run(toggle_employee(str(employee.id), current_user=_context(foreign_owner), db=session))
    assert getattr(foreign_toggle.value, "status_code", None) == 404

    session.add(Sale(
        pharmacy_id=pharmacy.id, user_id=employee.id, invoice_number=1,
        total_amount=10, payment_method="cash",
    ))
    session.commit()
    archived = asyncio.run(delete_employee(str(employee.id), current_user=_context(owner), db=session))
    assert archived["lifecycle"] == "archived"
    session.refresh(employee)
    assert employee.is_active is False

    unused = asyncio.run(create_employee(EmployeeCreateSchema(
        full_name="Unused Cashier", username="unused_cashier",
        password="UnusedPassword123!", role="cashier",
    ), current_user=_context(owner), db=session))
    unused_id = uuid.UUID(unused["employee_id"])
    deleted = asyncio.run(delete_employee(str(unused_id), current_user=_context(owner), db=session))
    assert deleted["lifecycle"] == "deleted"
    assert session.get(User, unused_id) is None


def test_post_acceptance_ui_contracts_have_no_runtime_dashboard_fixtures():
    dashboard = (ROOT / "templates" / "dashboard.html").read_text(encoding="utf-8")
    login = (ROOT / "templates" / "login.html").read_text(encoding="utf-8")
    employees = (ROOT / "templates" / "employees.html").read_text(encoding="utf-8")
    sales_history = (ROOT / "templates" / "sales_history.html").read_text(encoding="utf-8")
    settings = (ROOT / "templates" / "settings.html").read_text(encoding="utf-8")
    shared = (ROOT / "templates" / "shared_layout.html").read_text(encoding="utf-8")
    sidebar = (ROOT / "templates" / "partials" / "sidebar.html").read_text(encoding="utf-8")

    for fake in ("1.42M", "12.4%", "8.1%", "INV-2841", "سارة م.", "Augmentin 625mg"):
        assert fake not in dashboard
    assert "البريد الإلكتروني أو اسم المستخدم" in login
    assert "أدخل البريد الإلكتروني أو اسم المستخدم" in login
    assert "Email or username" in login
    assert "Enter email or username" in login
    assert "showAddModal()" in employees and "deleteEmployee(" in employees
    assert ".modal-overlay.show{display:flex;opacity:1;visibility:visible}" in employees
    assert "viewDetail(sale.sale_id)" in sales_history
    assert "opacity: 1;" in sales_history and "visibility: visible;" in sales_history
    assert 'href="/employees"' in settings
    assert "async addEmployee()" not in settings
    assert "/api/settings/employees" not in settings
    assert "sidebar-collapsed" in shared
    assert "body.mobile-drawer-open { overflow: hidden; }" in shared
    assert "html, body { overflow-x: hidden; }" in shared
    assert ":class=\"{ 'visible': sidebarOpen }\"" in shared
    assert "sidebar-close-btn" in sidebar and "sidebar-collapse-btn" in sidebar


def test_report_module_navigation_is_only_in_sidebar():
    for name in ("reports_sales.html", "reports_profits.html"):
        source = (ROOT / "templates" / name).read_text(encoding="utf-8")
        assert "<!-- Report Tabs -->" not in source


def test_employee_creation_form_blocks_owner_autofill_and_resets():
    employees = (ROOT / "templates" / "employees.html").read_text(encoding="utf-8")

    assert 'id="add-employee-form" autocomplete="off"' in employees
    assert 'name="employee_creation_username"' in employees
    assert 'name="employee_creation_password"' in employees
    assert 'autocomplete="new-password"' in employees
    assert 'placeholder="مثال: ahmed.ibrahim"' in employees
    assert "function resetAddEmployeeForm()" in employees
    assert employees.count("resetAddEmployeeForm();") >= 2


def test_render_yaml_uses_external_secret_database():
    config = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))
    assert "databases" not in config
    env = {item["key"]: item for item in config["services"][0]["envVars"]}
    assert env["DATABASE_URL"] == {"key": "DATABASE_URL", "sync": False}
    assert env["ENVIRONMENT"]["value"] == "production"


def test_no_unprotected_admin_or_demo_mutation_route():
    allowed_onboarding = {
        "/api/auth/activate", "/api/auth/setup", "/api/auth/login",
        "/api/auth/owner-activation",
    }
    source_text = (ROOT / "main.py").read_text(encoding="utf-8")
    source_tree = ast.parse(source_text)
    functions = {node.name: node for node in ast.walk(source_tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    for route in main.app.routes:
        methods = set(getattr(route, "methods", set())) & {"POST", "PUT", "PATCH", "DELETE"}
        if not methods or route.path in allowed_onboarding:
            continue
        if route.path in {"/api/auth/seed-demo", "/api/auth/create-pharmacy"}:
            source = ast.get_source_segment(source_text, functions[route.endpoint.__name__])
            assert 'raise HTTPException(status_code=404, detail="Not found")' in source
            continue
        dependency_names = {getattr(dependency.call, "__name__", "") for dependency in route.dependant.dependencies}
        assert dependency_names & {"get_current_user", "require_admin", "permission_checker"}, route.path


def test_repository_contains_no_committed_credentials_or_database_url():
    forbidden = ["abeer" + "2026", "BEGIN " + "OPENSSH PRIVATE KEY"]
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or ".venv" in path.parts:
            continue
        if path.suffix.lower() not in {".py", ".yaml", ".yml", ".json", ".env"}:
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        assert not any(value in content for value in forbidden), path


def test_production_startup_source_contains_no_demo_business_creation():
    startup_source = (ROOT / "startup.py").read_text(encoding="utf-8")
    assert "seed_demo" not in startup_source
    assert "Pharmacy(" not in startup_source
    assert "User(" not in startup_source
