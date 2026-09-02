"""Add explicit customer classification and legacy representation semantics.

Revision ID: 20260902_customer_semantics
Revises: 20260901_operator_archive
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "20260902_customer_semantics"
down_revision = "20260901_operator_archive"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "customer_handovers",
        sa.Column("classification", sa.String(20), nullable=False, server_default="COMMERCIAL"),
    )
    op.add_column(
        "customer_handovers",
        sa.Column("origin", sa.String(20), nullable=False, server_default="HANDOVER"),
    )
    op.add_column(
        "customer_handovers",
        sa.Column("owner_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_unique_constraint("uq_customer_handovers_owner_user_id", "customer_handovers", ["owner_user_id"])
    op.alter_column("customer_handovers", "owner_email", existing_type=sa.String(320), nullable=True)
    op.drop_constraint("ck_customer_handovers_status", "customer_handovers", type_="check")
    op.create_check_constraint(
        "ck_customer_handovers_status", "customer_handovers",
        "status IN ('PAYMENT_PENDING','READY_TO_PROVISION','AWAITING_OWNER_ACTIVATION','ACTIVATION_EMAIL_FAILED','ACTIVE','ABANDONED','ARCHIVED')",
    )
    op.create_check_constraint(
        "ck_customer_handovers_classification", "customer_handovers",
        "classification IN ('COMMERCIAL','QA','DEMO')",
    )
    op.create_check_constraint(
        "ck_customer_handovers_origin", "customer_handovers",
        "origin IN ('HANDOVER','LEGACY_BACKFILL')",
    )
    op.create_index(
        "ix_customer_handovers_classification_status",
        "customer_handovers", ["classification", "status"],
    )


def downgrade():
    bind = op.get_bind()
    incompatible = bind.execute(sa.text("""
        SELECT count(*) FROM customer_handovers
        WHERE classification <> 'COMMERCIAL'
           OR origin <> 'HANDOVER'
           OR status = 'ABANDONED'
           OR owner_email IS NULL
    """)).scalar_one()
    if incompatible:
        raise RuntimeError("cannot downgrade while classified, legacy, abandoned, or email-less records exist")
    op.drop_index("ix_customer_handovers_classification_status", table_name="customer_handovers")
    op.drop_constraint("ck_customer_handovers_origin", "customer_handovers", type_="check")
    op.drop_constraint("ck_customer_handovers_classification", "customer_handovers", type_="check")
    op.drop_constraint("ck_customer_handovers_status", "customer_handovers", type_="check")
    op.create_check_constraint(
        "ck_customer_handovers_status", "customer_handovers",
        "status IN ('PAYMENT_PENDING','READY_TO_PROVISION','AWAITING_OWNER_ACTIVATION','ACTIVATION_EMAIL_FAILED','ACTIVE','ARCHIVED')",
    )
    op.alter_column("customer_handovers", "owner_email", existing_type=sa.String(320), nullable=False)
    op.drop_column("customer_handovers", "origin")
    op.drop_constraint("uq_customer_handovers_owner_user_id", "customer_handovers", type_="unique")
    op.drop_column("customer_handovers", "owner_user_id")
    op.drop_column("customer_handovers", "classification")
