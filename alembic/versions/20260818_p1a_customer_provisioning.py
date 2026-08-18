"""Add atomic customer provisioning and owner activation schema.

Revision ID: 20260818_p1a_provisioning
Revises: 20260816_public_invoice_token
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "20260818_p1a_provisioning"
down_revision = "20260816_public_invoice_token"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing customer/demo rows deliberately remain NULL. All new P1-A customer
    # rows are required to provide both values in the domain service.
    op.add_column("pharmacies", sa.Column("customer_reference", sa.String(100), nullable=True))
    op.add_column("pharmacies", sa.Column("provisioning_request_id", UUID(as_uuid=True), nullable=True))
    op.create_index("ix_pharmacies_customer_reference", "pharmacies", ["customer_reference"], unique=True)
    op.create_index("ix_pharmacies_provisioning_request_id", "pharmacies", ["provisioning_request_id"], unique=True)

    op.create_table(
        "owner_activation_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("provisioning_request_id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token_hash", name="uq_owner_activation_token_hash"),
    )
    op.create_index("ix_owner_activation_tokens_user_id", "owner_activation_tokens", ["user_id"])
    op.create_index(
        "ix_owner_activation_tokens_request_id",
        "owner_activation_tokens",
        ["provisioning_request_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    activation_count = bind.execute(sa.text("SELECT count(*) FROM owner_activation_tokens")).scalar_one()
    provisioned_count = bind.execute(sa.text("""
        SELECT count(*) FROM pharmacies
        WHERE customer_reference IS NOT NULL OR provisioning_request_id IS NOT NULL
    """)).scalar_one()
    if activation_count or provisioned_count:
        raise RuntimeError(
            "cannot downgrade P1-A while provisioned customers or activation records exist"
        )
    op.drop_index("ix_owner_activation_tokens_request_id", table_name="owner_activation_tokens")
    op.drop_index("ix_owner_activation_tokens_user_id", table_name="owner_activation_tokens")
    op.drop_table("owner_activation_tokens")
    op.drop_index("ix_pharmacies_provisioning_request_id", table_name="pharmacies")
    op.drop_index("ix_pharmacies_customer_reference", table_name="pharmacies")
    op.drop_column("pharmacies", "provisioning_request_id")
    op.drop_column("pharmacies", "customer_reference")
