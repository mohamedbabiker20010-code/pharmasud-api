"""Add non-destructive customer archive lifecycle.

Revision ID: 20260901_operator_archive
Revises: 20260901_handover_recovery
"""
from alembic import op
import sqlalchemy as sa

revision = "20260901_operator_archive"
down_revision = "20260901_handover_recovery"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("customer_handovers", sa.Column("archived_at", sa.DateTime(), nullable=True))
    op.add_column("customer_handovers", sa.Column("archived_by", sa.String(100), nullable=True))
    op.drop_constraint("ck_customer_handovers_status", "customer_handovers", type_="check")
    op.create_check_constraint(
        "ck_customer_handovers_status", "customer_handovers",
        "status IN ('PAYMENT_PENDING','READY_TO_PROVISION','AWAITING_OWNER_ACTIVATION','ACTIVATION_EMAIL_FAILED','ACTIVE','ARCHIVED')",
    )


def downgrade():
    bind = op.get_bind()
    archived = bind.execute(
        sa.text("SELECT count(*) FROM customer_handovers WHERE status='ARCHIVED'")
    ).scalar_one()
    if archived:
        raise RuntimeError("cannot downgrade while archived customer records exist")
    op.drop_constraint("ck_customer_handovers_status", "customer_handovers", type_="check")
    op.create_check_constraint(
        "ck_customer_handovers_status", "customer_handovers",
        "status IN ('PAYMENT_PENDING','READY_TO_PROVISION','AWAITING_OWNER_ACTIVATION','ACTIVATION_EMAIL_FAILED','ACTIVE')",
    )
    op.drop_column("customer_handovers", "archived_by")
    op.drop_column("customer_handovers", "archived_at")
