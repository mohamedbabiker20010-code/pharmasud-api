import os

import pytest
from sqlalchemy import inspect, text


pytestmark = pytest.mark.postgres_integration


@pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_INTEGRATION") != "1",
    reason="Set RUN_POSTGRES_INTEGRATION=1 with a dedicated PostgreSQL DATABASE_URL",
)
def test_real_postgres_startup_is_idempotent_and_preserves_users():
    from database import engine
    from startup import initialize_database

    inspector = inspect(engine)
    before_users = {}
    before_pharmacies = 0
    if "users" in inspector.get_table_names():
        with engine.connect() as connection:
            before_users = dict(connection.execute(text("SELECT id::text, password_hash FROM users")).all())
            before_pharmacies = connection.execute(text("SELECT COUNT(*) FROM pharmacies")).scalar()

    initialize_database()
    initialize_database()

    with engine.connect() as connection:
        after_users = dict(connection.execute(text("SELECT id::text, password_hash FROM users")).all())
        after_pharmacies = connection.execute(text("SELECT COUNT(*) FROM pharmacies")).scalar()
        role_count = connection.execute(text("SELECT COUNT(*) FROM roles")).scalar()
        permission_count = connection.execute(text("SELECT COUNT(*) FROM permissions")).scalar()

    assert after_users == before_users
    assert after_pharmacies == before_pharmacies
    assert role_count == 5
    assert permission_count == 20
