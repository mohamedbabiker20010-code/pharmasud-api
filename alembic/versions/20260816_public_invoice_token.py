"""Add unique opaque public invoice tokens.

Revision ID: 20260816_public_invoice_token
Revises: 20260818_schema_adoption
"""

from alembic import op
import sqlalchemy as sa


revision = "20260816_public_invoice_token"
down_revision = "20260818_schema_adoption"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sales",
        sa.Column("public_invoice_token", sa.String(length=64), nullable=True),
    )
    # gen_random_uuid() is already required by the application's PostgreSQL schema.
    # Existing sales receive an opaque 122-bit random identifier without data loss.
    op.execute(sa.text("""
        UPDATE sales
        SET public_invoice_token = replace(gen_random_uuid()::text, '-', '')
        WHERE public_invoice_token IS NULL
    """))
    op.alter_column("sales", "public_invoice_token", nullable=False)
    op.create_unique_constraint(
        "uq_sales_public_invoice_token", "sales", ["public_invoice_token"]
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_sales_public_invoice_token", "sales", type_="unique"
    )
    op.drop_column("sales", "public_invoice_token")
