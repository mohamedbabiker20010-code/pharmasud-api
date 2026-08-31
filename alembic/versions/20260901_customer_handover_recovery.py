"""Add internal customer handover and email password recovery.

Revision ID: 20260901_handover_recovery
Revises: 20260827_owner_email_password
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "20260901_handover_recovery"
down_revision = "20260827_owner_email_password"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("auth_version", sa.Integer(), server_default="0", nullable=False))
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime()), sa.Column("revoked_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
    op.create_table(
        "customer_handovers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_reference", sa.String(100), nullable=False, unique=True),
        sa.Column("pharmacy_name", sa.String(100), nullable=False),
        sa.Column("owner_name", sa.String(100), nullable=False),
        sa.Column("owner_email", sa.String(320), nullable=False),
        sa.Column("owner_phone", sa.String(20)), sa.Column("city", sa.String(100)),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("payment_confirmed_at", sa.DateTime()),
        sa.Column("payment_confirmed_by", sa.String(100)),
        sa.Column("pharmacy_id", UUID(as_uuid=True), sa.ForeignKey("pharmacies.id"), unique=True),
        sa.Column("activation_email_sent_at", sa.DateTime()),
        sa.Column("activation_email_error", sa.String(200)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('PAYMENT_PENDING','READY_TO_PROVISION','AWAITING_OWNER_ACTIVATION','ACTIVATION_EMAIL_FAILED','ACTIVE')",
            name="ck_customer_handovers_status",
        ),
    )
    op.create_index(
        "uq_customer_handovers_owner_email_normalized", "customer_handovers",
        [sa.text("lower(owner_email)")], unique=True,
    )


def downgrade():
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT count(*) FROM customer_handovers")).scalar_one() or bind.execute(sa.text("SELECT count(*) FROM password_reset_tokens")).scalar_one():
        raise RuntimeError("cannot downgrade while handover or recovery records exist")
    op.drop_index("uq_customer_handovers_owner_email_normalized", table_name="customer_handovers")
    op.drop_table("customer_handovers")
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_column("users", "auth_version")
