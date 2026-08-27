"""Add owner email identity and nullable pre-activation password.

Revision ID: 20260827_owner_email_password
Revises: 20260818_p1a_provisioning
"""

from alembic import op
import sqlalchemy as sa


revision = "20260827_owner_email_password"
down_revision = "20260818_p1a_provisioning"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email", sa.String(320), nullable=True))
    op.alter_column(
        "users", "username", existing_type=sa.String(50),
        type_=sa.String(320), existing_nullable=False,
    )
    op.alter_column(
        "users", "password_hash", existing_type=sa.String(255),
        nullable=True,
    )
    op.create_index(
        "uq_users_email_normalized", "users", [sa.text("lower(email)")],
        unique=True, postgresql_where=sa.text("email IS NOT NULL"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT count(*) FROM users WHERE password_hash IS NULL")).scalar_one():
        raise RuntimeError("cannot downgrade while pre-activation users exist")
    if bind.execute(sa.text("SELECT count(*) FROM users WHERE length(username) > 50")).scalar_one():
        raise RuntimeError("cannot downgrade while usernames longer than 50 characters exist")
    op.drop_index("uq_users_email_normalized", table_name="users")
    op.alter_column(
        "users", "password_hash", existing_type=sa.String(255),
        nullable=False,
    )
    op.alter_column(
        "users", "username", existing_type=sa.String(320),
        type_=sa.String(50), existing_nullable=False,
    )
    op.drop_column("users", "email")
