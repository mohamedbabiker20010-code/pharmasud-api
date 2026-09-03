"""Release abandoned handover emails while preserving live identity uniqueness.

Revision ID: 20260903_abandoned_owner_email
Revises: 20260902_customer_semantics
"""
from alembic import op
import sqlalchemy as sa

revision = "20260903_abandoned_owner_email"
down_revision = "20260902_customer_semantics"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index("uq_customer_handovers_owner_email_normalized", table_name="customer_handovers")
    op.create_index(
        "uq_customer_handovers_owner_email_normalized",
        "customer_handovers",
        [sa.text("lower(owner_email)")],
        unique=True,
        postgresql_where=sa.text("owner_email IS NOT NULL AND status <> 'ABANDONED'"),
    )


def downgrade():
    bind = op.get_bind()
    duplicate_email = bind.execute(sa.text("""
        SELECT 1
        FROM customer_handovers
        WHERE owner_email IS NOT NULL
        GROUP BY lower(owner_email)
        HAVING count(*) > 1
        LIMIT 1
    """)).first()
    if duplicate_email:
        raise RuntimeError(
            "cannot restore global owner-email uniqueness while preserved abandoned duplicates exist"
        )
    op.drop_index("uq_customer_handovers_owner_email_normalized", table_name="customer_handovers")
    op.create_index(
        "uq_customer_handovers_owner_email_normalized",
        "customer_handovers",
        [sa.text("lower(owner_email)")],
        unique=True,
    )
