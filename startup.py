"""Fail-closed database schema and RBAC initialization."""

import logging

from sqlalchemy import text

from database import Base, SessionLocal, database_identity, engine
from rbac_seeder import seed_rbac_foundation


logger = logging.getLogger("pharmasud.startup")


def initialize_database() -> dict:
    """Initialize schema and RBAC. This function never creates business/demo data."""
    identity = database_identity()
    logger.info(
        "database_startup environment=%s host=%s database=%s fingerprint=%s",
        identity["environment"], identity["masked_host"], identity["database"], identity["fingerprint"],
    )

    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE batches ADD COLUMN IF NOT EXISTS supplier_name VARCHAR(100)"))
        conn.execute(text("ALTER TABLE sale_items ADD COLUMN IF NOT EXISTS unit_name VARCHAR(20)"))
        conn.execute(text("ALTER TABLE medicines ALTER COLUMN image_path TYPE TEXT"))
        conn.execute(text("ALTER TABLE pharmacies ADD COLUMN IF NOT EXISTS type VARCHAR(20) NOT NULL DEFAULT 'customer'"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS role_id UUID REFERENCES roles(id)"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                pharmacy_id UUID REFERENCES pharmacies(id),
                user_id UUID REFERENCES users(id) ON DELETE SET NULL,
                user_name VARCHAR(100),
                action_type VARCHAR(50) NOT NULL,
                description TEXT NOT NULL,
                target_entity VARCHAR(50),
                target_id VARCHAR(100),
                old_value TEXT,
                new_value TEXT,
                success BOOLEAN NOT NULL DEFAULT TRUE,
                request_ip VARCHAR(64),
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        conn.execute(text("ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS target_entity VARCHAR(50)"))
        conn.execute(text("ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS target_id VARCHAR(100)"))
        conn.execute(text("ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS success BOOLEAN NOT NULL DEFAULT TRUE"))
        conn.execute(text("ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS request_ip VARCHAR(64)"))
        conn.execute(text("ALTER TABLE audit_log DROP CONSTRAINT IF EXISTS audit_log_user_id_fkey"))
        conn.execute(text("ALTER TABLE audit_log ADD CONSTRAINT audit_log_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS stocktake_sessions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                pharmacy_id UUID REFERENCES pharmacies(id),
                user_id UUID REFERENCES users(id),
                notes TEXT,
                items_adjusted INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS stocktake_items (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                session_id UUID REFERENCES stocktake_sessions(id),
                medicine_id UUID REFERENCES medicines(id),
                medicine_name VARCHAR(100),
                system_quantity INTEGER,
                actual_quantity INTEGER,
                difference INTEGER,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))

    with SessionLocal.begin() as db:
        rbac_result = seed_rbac_foundation(db)

    logger.info(
        "database_startup_complete roles=%s permissions=%s mappings=%s migrated_users=%s",
        rbac_result["roles"], rbac_result["permissions"],
        rbac_result["role_permissions"], rbac_result["migration"]["updated"],
    )
    return {"schema_ready": True, "rbac": rbac_result}
