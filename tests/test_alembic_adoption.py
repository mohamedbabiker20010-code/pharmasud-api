from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


ROOT = Path(__file__).resolve().parents[1]


def test_alembic_uses_validated_application_engine():
    env_source = (ROOT / "alembic" / "env.py").read_text(encoding="utf-8")

    assert "from database import DATABASE_URL, engine" in env_source
    assert "with engine.connect() as connection" in env_source
    assert "engine_from_config" not in env_source


def test_public_invoice_migration_follows_schema_adoption():
    config = Config(str(ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(config)

    invoice = script.get_revision("20260816_public_invoice_token")
    provisioning = script.get_revision("20260818_p1a_provisioning")
    activation_contract = script.get_revision("20260827_owner_email_password")
    adoption = script.get_revision("20260818_schema_adoption")

    handover = script.get_revision("20260901_handover_recovery")
    assert script.get_current_head() == "20260901_handover_recovery"
    assert handover.down_revision == "20260827_owner_email_password"
    assert activation_contract.down_revision == "20260818_p1a_provisioning"
    assert provisioning.down_revision == "20260816_public_invoice_token"
    assert invoice.down_revision == "20260818_schema_adoption"
    assert adoption.down_revision == "20240618_rbac_phase1"
