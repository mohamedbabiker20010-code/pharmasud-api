"""Adopt the existing production schema into Alembic history.

Revision ID: 20260818_schema_adoption
Revises: 20240618_rbac_phase1

This revision is intentionally non-destructive.  It validates the tables that
were historically created by Base.metadata.create_all() and startup DDL, then
records the two known differences between the historical RBAC migration and
the current production/model contract.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision = "20260818_schema_adoption"
down_revision = "20240618_rbac_phase1"
branch_labels = None
depends_on = None


_REQUIRED_COLUMNS = {
    "pharmacies": {
        "id", "product_key", "name", "owner_name", "phone", "address",
        "is_active", "activated_at", "created_at", "type",
    },
    "users": {
        "id", "pharmacy_id", "username", "password_hash", "role", "role_id",
        "full_name", "phone", "is_active", "created_at",
    },
    "roles": {"id", "name", "display_name", "description", "created_at"},
    "permissions": {"id", "code", "category", "description", "created_at"},
    "role_permissions": {"role_id", "permission_id"},
    "medicines": {
        "id", "pharmacy_id", "barcode", "trade_name", "scientific_name",
        "category", "sale_price", "purchase_price", "base_unit", "min_stock",
        "image_path", "created_at",
    },
    "units": {"id", "medicine_id", "unit_name", "conversion_factor", "sale_price"},
    "batches": {
        "id", "medicine_id", "batch_number", "quantity", "expiry_date",
        "purchase_price", "supplier_invoice", "supplier_name", "received_at",
        "is_active",
    },
    "sales": {
        "id", "pharmacy_id", "user_id", "invoice_number", "customer_name",
        "total_amount", "payment_method", "created_at",
    },
    "sale_items": {
        "id", "sale_id", "medicine_id", "batch_id", "quantity", "unit_name",
        "unit_price", "total_price",
    },
    "audit_log": {
        "id", "pharmacy_id", "user_id", "user_name", "action_type",
        "description", "target_entity", "target_id", "old_value", "new_value",
        "success", "request_ip", "created_at",
    },
    "stocktake_sessions": {
        "id", "pharmacy_id", "user_id", "notes", "items_adjusted", "created_at",
    },
    "stocktake_items": {
        "id", "session_id", "medicine_id", "medicine_name", "system_quantity",
        "actual_quantity", "difference", "created_at",
    },
}


_REQUIRED_FOREIGN_KEYS = {
    "users": {("pharmacy_id",): "pharmacies", ("role_id",): "roles"},
    "medicines": {("pharmacy_id",): "pharmacies"},
    "units": {("medicine_id",): "medicines"},
    "batches": {("medicine_id",): "medicines"},
    "sales": {("pharmacy_id",): "pharmacies", ("user_id",): "users"},
    "sale_items": {
        ("sale_id",): "sales", ("medicine_id",): "medicines", ("batch_id",): "batches",
    },
    "audit_log": {("pharmacy_id",): "pharmacies", ("user_id",): "users"},
    "stocktake_sessions": {("pharmacy_id",): "pharmacies", ("user_id",): "users"},
    "stocktake_items": {
        ("session_id",): "stocktake_sessions", ("medicine_id",): "medicines",
    },
}


def _validate_existing_schema() -> None:
    inspector = inspect(op.get_bind())
    existing_tables = set(inspector.get_table_names())
    missing_tables = sorted(set(_REQUIRED_COLUMNS) - existing_tables)
    if missing_tables:
        raise RuntimeError(f"production schema adoption: missing tables: {missing_tables}")

    for table_name, required in _REQUIRED_COLUMNS.items():
        existing = {column["name"] for column in inspector.get_columns(table_name)}
        missing = sorted(required - existing)
        if missing:
            raise RuntimeError(
                f"production schema adoption: {table_name} missing columns: {missing}"
            )

    for table_name, expected_targets in _REQUIRED_FOREIGN_KEYS.items():
        actual_targets = {
            tuple(fk["constrained_columns"]): fk["referred_table"]
            for fk in inspector.get_foreign_keys(table_name)
        }
        missing = {
            columns: target
            for columns, target in expected_targets.items()
            if actual_targets.get(columns) != target
        }
        if missing:
            raise RuntimeError(
                f"production schema adoption: {table_name} missing FKs: {missing}"
            )

    role_permission_pk = set(
        inspector.get_pk_constraint("role_permissions")["constrained_columns"]
    )
    if role_permission_pk != {"role_id", "permission_id"}:
        raise RuntimeError(
            "production schema adoption: role_permissions composite PK is missing"
        )

    expected_unique = {
        "pharmacies": {("product_key",)},
        "users": {("username",)},
        "roles": {("name",)},
        "permissions": {("code",)},
    }
    for table_name, expected in expected_unique.items():
        actual = {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints(table_name)
        }
        if not expected.issubset(actual):
            raise RuntimeError(
                f"production schema adoption: {table_name} unique constraint is missing"
            )

    expected_checks = {
        "pharmacies": "ck_pharmacies_type",
        "users": "check_user_role",
        "sales": "check_payment_method",
    }
    for table_name, constraint_name in expected_checks.items():
        actual = {
            constraint["name"]
            for constraint in inspector.get_check_constraints(table_name)
        }
        if constraint_name not in actual:
            raise RuntimeError(
                f"production schema adoption: {constraint_name} is missing"
            )


def upgrade() -> None:
    _validate_existing_schema()

    # The current SQLAlchemy model intentionally permits a temporarily absent
    # role assignment, unlike the historical RBAC migration.
    op.alter_column(
        "users",
        "role_id",
        existing_type=sa.UUID(),
        nullable=True,
    )

    # The current model uses an application-side default.  Production has no
    # persistent database default on this column.
    op.alter_column(
        "pharmacies",
        "type",
        existing_type=sa.String(length=20),
        server_default=None,
    )


def downgrade() -> None:
    bind = op.get_bind()
    null_roles = bind.execute(
        text("SELECT count(*) FROM users WHERE role_id IS NULL")
    ).scalar_one()
    if null_roles:
        raise RuntimeError(
            "cannot downgrade schema adoption while users.role_id contains NULL"
        )

    op.alter_column(
        "pharmacies",
        "type",
        existing_type=sa.String(length=20),
        server_default="customer",
    )
    op.alter_column(
        "users",
        "role_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
