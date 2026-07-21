"""Database configuration and production identity validation."""

import hashlib
import logging
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import declarative_base, sessionmaker


load_dotenv()

logger = logging.getLogger("pharmasud.database")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()


def _normalize_database_url(value: str) -> str:
    if value.startswith("postgres://"):
        return "postgresql://" + value[len("postgres://"):]
    return value


def validate_database_url(value: str, environment: str = ENVIRONMENT):
    """Validate the configured database without exposing credentials."""
    if not value:
        raise RuntimeError("DATABASE_URL is required")

    normalized = _normalize_database_url(value)
    try:
        parsed = make_url(normalized)
    except (ArgumentError, ValueError) as exc:
        raise RuntimeError("DATABASE_URL is malformed") from exc

    if parsed.drivername not in {"postgresql", "postgresql+psycopg2"}:
        raise RuntimeError("DATABASE_URL must use PostgreSQL")
    if not parsed.host or not parsed.database:
        raise RuntimeError("DATABASE_URL must include a host and database name")

    host = parsed.host.lower().strip("[]")
    if environment == "production" and host in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("A localhost database is not allowed in production")

    rejected_hosts = {
        item.strip().lower()
        for item in os.getenv("REJECTED_DATABASE_HOSTS", "").split(",")
        if item.strip()
    }
    if host in rejected_hosts:
        raise RuntimeError("DATABASE_URL points to a rejected database host")

    return parsed


def database_identity(value: str = DATABASE_URL) -> dict:
    parsed = validate_database_url(value)
    host = parsed.host or "unknown"
    labels = host.split(".")
    masked_host = f"{labels[0][:4]}***"
    if len(labels) > 1:
        masked_host += "." + ".".join(labels[-2:])
    fingerprint_source = f"{host.lower()}/{parsed.database}"
    return {
        "environment": ENVIRONMENT,
        "masked_host": masked_host,
        "database": parsed.database,
        "fingerprint": hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()[:12],
    }


DATABASE_URL = _normalize_database_url(DATABASE_URL)
validate_database_url(DATABASE_URL)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_connection() -> bool:
    identity = database_identity()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info(
            "database_connection_success environment=%s host=%s database=%s fingerprint=%s",
            identity["environment"], identity["masked_host"], identity["database"], identity["fingerprint"],
        )
        return True
    except Exception as exc:
        logger.error(
            "database_connection_failure environment=%s host=%s database=%s fingerprint=%s error=%s",
            identity["environment"], identity["masked_host"], identity["database"], identity["fingerprint"],
            type(exc).__name__,
        )
        return False


def get_tables_count() -> int:
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = 'public'
            """))
            return result.scalar() or 0
    except Exception as exc:
        logger.error("database_schema_check_failed error=%s", type(exc).__name__)
        return 0
