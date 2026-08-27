import os
import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from auth import get_password_hash
from models import Base, Pharmacy, User


DATABASE_URL = os.getenv("OWNER_CONTRACT_MIGRATION_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="OWNER_CONTRACT_MIGRATION_DATABASE_URL must point to disposable PostgreSQL",
)


def test_upgrade_preserves_existing_user_and_enables_unset_password():
    engine = create_engine(DATABASE_URL)
    config = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    Base.metadata.create_all(engine)
    command.stamp(config, "20260827_owner_email_password")

    legacy_hash = get_password_hash("Legacy-Password-123!")
    pharmacy_id, user_id = uuid.uuid4(), uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(Pharmacy.__table__.insert().values(
            id=pharmacy_id, product_key="PHARM-LEGACY-MIGRATION", name="Legacy",
            is_active=True, type="demo",
        ))
        connection.execute(User.__table__.insert().values(
            id=user_id, pharmacy_id=pharmacy_id, username="legacy_admin",
            email=None, password_hash=legacy_hash, role="admin", is_active=True,
        ))

    command.downgrade(config, "20260818_p1a_provisioning")
    old_columns = {column["name"]: column for column in inspect(engine).get_columns("users")}
    assert "email" not in old_columns
    assert old_columns["password_hash"]["nullable"] is False

    command.upgrade(config, "20260827_owner_email_password")
    new_columns = {column["name"]: column for column in inspect(engine).get_columns("users")}
    assert new_columns["email"]["nullable"] is True
    assert new_columns["password_hash"]["nullable"] is True
    with engine.connect() as connection:
        row = connection.execute(text(
            "SELECT username, email, password_hash, is_active FROM users WHERE id=:id"
        ), {"id": user_id}).one()
        assert row == ("legacy_admin", None, legacy_hash, True)
        indexes = {item["name"] for item in inspect(connection).get_indexes("users")}
        assert "uq_users_email_normalized" in indexes
    engine.dispose()
