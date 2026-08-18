"""Atomic, reusable customer-pharmacy provisioning domain service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json
import re
import secrets
import uuid
from typing import Callable, Optional

from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from audit import add_audit_event
from auth import get_password_hash
from models import OwnerActivationToken, Pharmacy, Role, User
from rbac_seeder import PERMISSION_DEFINITIONS, ROLE_PERMISSIONS


P1A_ALEMBIC_HEAD = "20260818_p1a_provisioning"
ACTIVATION_TTL_HOURS = 24
_USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,49}$")
_REFERENCE_RE = re.compile(r"^[A-Z0-9][A-Z0-9._/-]{2,99}$")


class ProvisioningError(RuntimeError):
    code = "PROVISIONING_FAILED"


class CustomerReferenceConflict(ProvisioningError):
    code = "CUSTOMER_REFERENCE_CONFLICT"


class RbacFoundationError(ProvisioningError):
    code = "RBAC_FOUNDATION_INVALID"


class ActivationError(RuntimeError):
    """Generic activation rejection; deliberately carries no user detail."""


@dataclass(frozen=True)
class ProvisioningInput:
    customer_reference: str
    pharmacy_name: str
    owner_name: str
    owner_username: str
    operator: str
    phone: str = ""
    address: str = ""
    provisioning_request_id: Optional[uuid.UUID] = None


@dataclass(frozen=True)
class ProvisioningResult:
    status: str
    pharmacy_name: str
    customer_reference: str
    owner_username: str
    provisioning_request_id: uuid.UUID
    product_key: Optional[str]
    activation_secret: Optional[str]
    activation_expires_at: Optional[datetime]
    tenant_verification: bool
    rbac_verification: bool
    audit_verification: bool


def normalize_customer_reference(value: str) -> str:
    normalized = value.strip().upper()
    if not _REFERENCE_RE.fullmatch(normalized):
        raise ValueError("customer_reference must be 3-100 safe uppercase characters")
    return normalized


def normalize_username(value: str) -> str:
    normalized = value.strip().lower()
    if not _USERNAME_RE.fullmatch(normalized):
        raise ValueError("owner_username must be 3-50 lowercase ASCII characters")
    return normalized


def _clean(value: str, field: str, maximum: int, minimum: int = 1) -> str:
    normalized = " ".join(value.strip().split())
    if len(normalized) < minimum or len(normalized) > maximum:
        raise ValueError(f"{field} length must be {minimum}-{maximum}")
    return normalized


def canonicalize(data: ProvisioningInput) -> ProvisioningInput:
    return ProvisioningInput(
        customer_reference=normalize_customer_reference(data.customer_reference),
        pharmacy_name=_clean(data.pharmacy_name, "pharmacy_name", 100, 2),
        owner_name=_clean(data.owner_name, "owner_name", 100, 2),
        owner_username=normalize_username(data.owner_username),
        operator=_clean(data.operator, "operator", 100, 2),
        phone=data.phone.strip()[:20],
        address=data.address.strip()[:500],
        provisioning_request_id=data.provisioning_request_id,
    )


def generate_license_key() -> str:
    """Return an opaque license identifier with at least 192 bits of entropy."""
    return "PHARM-" + secrets.token_urlsafe(24)


def generate_activation_secret() -> str:
    """Return a 256-bit owner activation secret."""
    return secrets.token_urlsafe(32)


def hash_activation_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


class ProvisioningService:
    def __init__(
        self,
        session_factory: sessionmaker,
        *,
        now: Callable[[], datetime] = datetime.utcnow,
        failure_injector: Optional[Callable[[str], None]] = None,
    ):
        self.session_factory = session_factory
        self.now = now
        self.failure_injector = failure_injector or (lambda _stage: None)

    @staticmethod
    def validate_rbac(session: Session) -> Role:
        roles = session.query(Role).filter(Role.name == "owner").all()
        if len(roles) != 1:
            raise RbacFoundationError("exactly one canonical owner role is required")
        owner = roles[0]
        actual = {permission.code for permission in owner.permissions}
        expected = set(ROLE_PERMISSIONS["owner"])
        if actual != expected or not expected.issubset(PERMISSION_DEFINITIONS):
            raise RbacFoundationError("owner role permissions do not match canonical mapping")
        return owner

    def provision(self, raw: ProvisioningInput) -> ProvisioningResult:
        data = canonicalize(raw)
        request_id = data.provisioning_request_id or uuid.uuid4()

        with self.session_factory() as lookup:
            existing = self._find_existing(lookup, data.customer_reference, request_id)
            if existing:
                return self._existing_result(lookup, existing, data, request_id)

        activation_secret = generate_activation_secret()
        expires_at = self.now() + timedelta(hours=ACTIVATION_TTL_HOURS)
        product_key = generate_license_key()

        try:
            with self.session_factory.begin() as session:
                owner_role = self.validate_rbac(session)
                if session.query(User).filter(func.lower(User.username) == data.owner_username).first():
                    raise ProvisioningError("owner username is already in use")

                pharmacy = Pharmacy(
                    id=uuid.uuid4(),
                    product_key=product_key,
                    customer_reference=data.customer_reference,
                    provisioning_request_id=request_id,
                    name=data.pharmacy_name,
                    owner_name=data.owner_name,
                    phone=data.phone,
                    address=data.address,
                    is_active=True,
                    activated_at=self.now(),
                    type="customer",
                )
                session.add(pharmacy)
                session.flush()
                self.failure_injector("after_pharmacy_flush")

                discarded_password = secrets.token_urlsafe(48)
                owner = User(
                    id=uuid.uuid4(),
                    pharmacy_id=pharmacy.id,
                    username=data.owner_username,
                    full_name=data.owner_name,
                    password_hash=get_password_hash(discarded_password),
                    role="admin",
                    role_id=owner_role.id,
                    is_active=False,
                )
                discarded_password = ""
                session.add(owner)
                session.flush()
                self.failure_injector("after_owner_flush")
                if owner.role_id != owner_role.id:
                    raise ProvisioningError("owner role assignment failed")
                self.failure_injector("after_role_assignment")

                activation = OwnerActivationToken(
                    id=uuid.uuid4(),
                    user_id=owner.id,
                    token_hash=hash_activation_secret(activation_secret),
                    expires_at=expires_at,
                    provisioning_request_id=request_id,
                )
                session.add(activation)
                session.flush()
                self.failure_injector("after_activation_creation")

                add_audit_event(
                    session,
                    pharmacy_id=str(pharmacy.id),
                    user_id=None,
                    user_name=data.operator,
                    action_type="customer_pharmacy_provisioned",
                    description="Customer pharmacy provisioned",
                    target_entity="pharmacy",
                    target_id=str(pharmacy.id),
                    new_value=json.dumps({
                        "customer_reference": data.customer_reference,
                        "owner_username": data.owner_username,
                        "provisioning_request_id": str(request_id),
                        "pharmacy_type": "customer",
                    }, sort_keys=True),
                )
                self.failure_injector("after_audit_insertion")
                self._verify_in_transaction(session, pharmacy, owner, owner_role, activation)
        except IntegrityError:
            with self.session_factory() as retry_session:
                existing = self._find_existing(retry_session, data.customer_reference, request_id)
                if existing:
                    return self._existing_result(retry_session, existing, data, request_id)
            raise

        return self.verify_persisted(
            customer_reference=data.customer_reference,
            request_id=request_id,
            activation_secret=activation_secret,
            product_key=product_key,
            expires_at=expires_at,
            status="PROVISIONING_SUCCESS",
        )

    @staticmethod
    def _find_existing(session: Session, reference: str, request_id: uuid.UUID):
        by_reference = session.query(Pharmacy).filter(Pharmacy.customer_reference == reference).first()
        by_request = session.query(Pharmacy).filter(Pharmacy.provisioning_request_id == request_id).first()
        if by_reference and by_request and by_reference.id != by_request.id:
            raise CustomerReferenceConflict("reference and request identify different pharmacies")
        return by_reference or by_request

    def _existing_result(self, session: Session, pharmacy: Pharmacy, data: ProvisioningInput, request_id: uuid.UUID):
        owners = session.query(User).filter(User.pharmacy_id == pharmacy.id, User.role_id.isnot(None)).all()
        owner = next((u for u in owners if u.role_obj and u.role_obj.name == "owner"), None)
        same = (
            pharmacy.customer_reference == data.customer_reference
            and pharmacy.name == data.pharmacy_name
            and pharmacy.owner_name == data.owner_name
            and (pharmacy.phone or "") == data.phone
            and (pharmacy.address or "") == data.address
            and owner is not None
            and owner.username == data.owner_username
        )
        if data.provisioning_request_id and pharmacy.provisioning_request_id != request_id:
            same = False
        if not same:
            raise CustomerReferenceConflict("customer reference already exists with different canonical input")
        return self.verify_persisted(
            customer_reference=data.customer_reference,
            request_id=pharmacy.provisioning_request_id,
            activation_secret=None,
            product_key=None,
            expires_at=None,
            status="ALREADY_PROVISIONED",
        )

    @staticmethod
    def _verify_in_transaction(session, pharmacy, owner, owner_role, activation):
        if owner.pharmacy_id != pharmacy.id or owner.role_id != owner_role.id:
            raise ProvisioningError("owner tenant/RBAC linkage failed")
        if owner.is_active or owner.role != "admin":
            raise ProvisioningError("owner pre-activation state is invalid")
        if activation.user_id != owner.id or activation.provisioning_request_id != pharmacy.provisioning_request_id:
            raise ProvisioningError("activation linkage failed")
        foreign_counts = [
            session.execute(text("SELECT count(*) FROM medicines WHERE pharmacy_id=:pid"), {"pid": pharmacy.id}).scalar_one(),
            session.execute(text("SELECT count(*) FROM sales WHERE pharmacy_id=:pid"), {"pid": pharmacy.id}).scalar_one(),
            session.execute(text("SELECT count(*) FROM stocktake_sessions WHERE pharmacy_id=:pid"), {"pid": pharmacy.id}).scalar_one(),
        ]
        if any(foreign_counts):
            raise ProvisioningError("new tenant unexpectedly owns business data")

    def verify_persisted(self, *, customer_reference, request_id, activation_secret, product_key, expires_at, status):
        with self.session_factory() as session:
            pharmacies = session.query(Pharmacy).filter(Pharmacy.customer_reference == customer_reference).all()
            if len(pharmacies) != 1:
                raise ProvisioningError("persisted pharmacy verification failed")
            pharmacy = pharmacies[0]
            if pharmacy.provisioning_request_id != request_id:
                raise ProvisioningError("persisted request identity mismatch")
            owner_role = self.validate_rbac(session)
            owners = session.query(User).filter(User.pharmacy_id == pharmacy.id, User.role_id == owner_role.id).all()
            if len(owners) != 1:
                raise ProvisioningError("persisted owner verification failed")
            owner = owners[0]
            activations = session.query(OwnerActivationToken).filter(
                OwnerActivationToken.user_id == owner.id,
                OwnerActivationToken.provisioning_request_id == request_id,
            ).all()
            if not activations:
                raise ProvisioningError("persisted activation verification failed")
            audit_count = session.execute(text("""
                SELECT count(*) FROM audit_log
                WHERE pharmacy_id=:pid AND action_type='customer_pharmacy_provisioned'
            """), {"pid": pharmacy.id}).scalar_one()
            if audit_count != 1:
                raise ProvisioningError("persisted audit verification failed")
            return ProvisioningResult(
                status=status, pharmacy_name=pharmacy.name,
                customer_reference=customer_reference, owner_username=owner.username,
                provisioning_request_id=request_id, product_key=product_key,
                activation_secret=activation_secret, activation_expires_at=expires_at,
                tenant_verification=True, rbac_verification=True, audit_verification=True,
            )

    def reissue_activation(self, customer_reference: str, operator: str) -> ProvisioningResult:
        reference = normalize_customer_reference(customer_reference)
        operator_name = _clean(operator, "operator", 100, 2)
        secret = generate_activation_secret()
        expires_at = self.now() + timedelta(hours=ACTIVATION_TTL_HOURS)
        with self.session_factory.begin() as session:
            pharmacy = session.query(Pharmacy).filter(Pharmacy.customer_reference == reference).one_or_none()
            if not pharmacy:
                raise ProvisioningError("customer not found")
            owner_role = self.validate_rbac(session)
            owner = session.query(User).filter(
                User.pharmacy_id == pharmacy.id, User.role_id == owner_role.id
            ).one()
            if owner.is_active:
                raise ProvisioningError("owner is already active")
            now = self.now()
            for token in session.query(OwnerActivationToken).filter(
                OwnerActivationToken.user_id == owner.id,
                OwnerActivationToken.used_at.is_(None),
                OwnerActivationToken.revoked_at.is_(None),
            ).all():
                token.revoked_at = now
            session.add(OwnerActivationToken(
                id=uuid.uuid4(), user_id=owner.id,
                token_hash=hash_activation_secret(secret), expires_at=expires_at,
                provisioning_request_id=pharmacy.provisioning_request_id,
            ))
            add_audit_event(
                session, pharmacy_id=str(pharmacy.id), user_id=None,
                user_name=operator_name, action_type="owner_activation_reissued",
                description="Owner activation reissued", target_entity="user",
                target_id=str(owner.id),
            )
            request_id = pharmacy.provisioning_request_id
        return self.verify_persisted(
            customer_reference=reference, request_id=request_id,
            activation_secret=secret, product_key=None, expires_at=expires_at,
            status="ACTIVATION_REISSUED",
        )


def activate_owner(session: Session, *, secret: str, password: str, now: Optional[datetime] = None) -> User:
    """Activate one pre-provisioned owner; caller owns the transaction."""
    current_time = now or datetime.utcnow()
    if len(password) < 12 or len(password.encode("utf-8")) > 72:
        raise ActivationError("Activation link is invalid or expired")
    token = session.query(OwnerActivationToken).filter(
        OwnerActivationToken.token_hash == hash_activation_secret(secret)
    ).with_for_update().one_or_none()
    if (
        token is None or token.used_at is not None or token.revoked_at is not None
        or token.expires_at <= current_time
    ):
        raise ActivationError("Activation link is invalid or expired")
    owner = session.query(User).filter(User.id == token.user_id).with_for_update().one_or_none()
    if owner is None or owner.is_active or owner.role_id is None:
        raise ActivationError("Activation link is invalid or expired")
    pharmacy = session.query(Pharmacy).filter(Pharmacy.id == owner.pharmacy_id).one_or_none()
    if pharmacy is None or not pharmacy.is_active:
        raise ActivationError("Activation link is invalid or expired")
    role = session.query(Role).filter(Role.id == owner.role_id).one_or_none()
    if role is None or role.name != "owner" or owner.role != "admin":
        raise ActivationError("Activation link is invalid or expired")
    owner.password_hash = get_password_hash(password)
    owner.is_active = True
    token.used_at = current_time
    add_audit_event(
        session, pharmacy_id=str(pharmacy.id), user_id=str(owner.id),
        user_name=owner.username, action_type="owner_first_login_activated",
        description="Owner established first-login password", target_entity="user",
        target_id=str(owner.id),
    )
    session.flush()
    return owner
