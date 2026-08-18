#!/usr/bin/env python3
"""Production-safe CLI adapter for atomic customer provisioning."""

from __future__ import annotations

import argparse
import os
import sys
import uuid

from sqlalchemy import inspect, text

from database import ENVIRONMENT, SessionLocal, database_identity, engine
from models import Pharmacy
from services.provisioning import (
    P1A_ALEMBIC_HEAD,
    ProvisioningInput,
    ProvisioningService,
)


def current_alembic_revision() -> str:
    with engine.connect() as connection:
        if not inspect(connection).has_table("alembic_version"):
            return "UNINITIALIZED"
        return connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()


def collect_safe_environment() -> dict:
    identity = database_identity()
    with SessionLocal() as session:
        pharmacy_count = session.query(Pharmacy).count()
        ProvisioningService.validate_rbac(session)
    return {
        "environment": identity["environment"],
        "database_type": engine.dialect.name,
        "masked_host": identity["masked_host"],
        "database_name": identity["database"],
        "database_fingerprint": identity["fingerprint"],
        "current_pharmacy_count": pharmacy_count,
        "current_alembic_revision": current_alembic_revision(),
    }


def enforce_environment_gate(args, metadata: dict) -> None:
    if metadata["database_type"] != "postgresql":
        raise RuntimeError("PostgreSQL is required")
    if metadata["current_alembic_revision"] != P1A_ALEMBIC_HEAD:
        raise RuntimeError("Database is not at the approved P1-A Alembic head")
    if metadata["environment"] == "production":
        if args.non_interactive:
            if not args.confirm_production:
                raise RuntimeError("--confirm-production is required")
            if not args.expected_db_fingerprint:
                raise RuntimeError("--expected-db-fingerprint is required")
            if args.expected_db_fingerprint != metadata["database_fingerprint"]:
                raise RuntimeError("Database fingerprint mismatch")
            if not args.customer_reference or not args.operator:
                raise RuntimeError("customer reference and operator are required")
        else:
            expected = f"PROVISION {args.customer_reference.strip().upper()} ON {metadata['database_fingerprint']}"
            entered = input(f"Type exactly: {expected}\n> ")
            if entered != expected:
                raise RuntimeError("Production confirmation did not match")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Provision a PharmaSUD customer pharmacy")
    parser.add_argument("--customer-reference")
    parser.add_argument("--pharmacy-name")
    parser.add_argument("--owner-name")
    parser.add_argument("--owner-username")
    parser.add_argument("--operator")
    parser.add_argument("--phone", default="")
    parser.add_argument("--address", default="")
    parser.add_argument("--provisioning-request-id", type=uuid.UUID)
    parser.add_argument("--reissue-activation", action="store_true")
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--confirm-production", action="store_true")
    parser.add_argument("--expected-db-fingerprint")
    return parser


def _complete_interactive(args):
    if args.non_interactive:
        required = ("customer_reference", "pharmacy_name", "owner_name", "owner_username", "operator")
        missing = [name for name in required if not getattr(args, name)]
        if missing and not args.reissue_activation:
            raise RuntimeError("Missing required arguments: " + ", ".join(missing))
        return args
    args.customer_reference = args.customer_reference or input("Customer reference: ")
    args.operator = args.operator or input("Operator identity: ")
    if not args.reissue_activation:
        args.pharmacy_name = args.pharmacy_name or input("Pharmacy name: ")
        args.owner_name = args.owner_name or input("Owner full name: ")
        args.owner_username = args.owner_username or input("Owner username: ")
    return args


def _print_environment(metadata):
    labels = {
        "environment": "ENVIRONMENT", "database_type": "DATABASE_TYPE",
        "masked_host": "MASKED_HOST", "database_name": "DATABASE_NAME",
        "database_fingerprint": "DATABASE_FINGERPRINT",
        "current_pharmacy_count": "CURRENT_PHARMACY_COUNT",
        "current_alembic_revision": "CURRENT_ALEMBIC_REVISION",
    }
    for key, label in labels.items():
        print(f"{label}={metadata[key]}")


def main(argv=None) -> int:
    args = _complete_interactive(build_parser().parse_args(argv))
    try:
        metadata = collect_safe_environment()
        _print_environment(metadata)
        enforce_environment_gate(args, metadata)
        service = ProvisioningService(SessionLocal)
        if args.reissue_activation:
            result = service.reissue_activation(args.customer_reference, args.operator)
        else:
            result = service.provision(ProvisioningInput(
                customer_reference=args.customer_reference,
                pharmacy_name=args.pharmacy_name,
                owner_name=args.owner_name,
                owner_username=args.owner_username,
                operator=args.operator,
                phone=args.phone,
                address=args.address,
                provisioning_request_id=args.provisioning_request_id,
            ))
        print("\n" + result.status)
        print(f"Pharmacy: {result.pharmacy_name}")
        print(f"Customer Reference: {result.customer_reference}")
        print(f"Owner Username: {result.owner_username}")
        if result.product_key:
            print(f"License Key: {result.product_key}")
        if result.activation_secret:
            base_url = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
            # The URL fragment is consumed by browser JavaScript and is never sent
            # in the HTTP request or routine server access logs.
            activation_path = f"/owner-activation#token={result.activation_secret}"
            print(f"Owner Activation: {base_url + activation_path if base_url else activation_path}")
            print(f"Activation Expires: {result.activation_expires_at.isoformat()}Z")
        elif result.status == "ALREADY_PROVISIONED":
            print("Owner Activation: not reissued; use --reissue-activation explicitly if needed")
        print(f"Tenant Verification: {'PASS' if result.tenant_verification else 'FAIL'}")
        print(f"RBAC Verification: {'PASS' if result.rbac_verification else 'FAIL'}")
        print(f"Audit: {'PASS' if result.audit_verification else 'FAIL'}")
        return 0
    except Exception as exc:
        print(f"PROVISIONING_FAILED: {getattr(exc, 'code', type(exc).__name__)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
