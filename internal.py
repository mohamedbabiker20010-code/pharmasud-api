"""Private, non-tenant platform-operator customer handover console."""

from collections import OrderedDict, deque
from datetime import datetime
import base64
import binascii
import hmac
import math
import os
import threading
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from audit import add_audit_event
from auth import verify_password
from database import SessionLocal, get_db
from models import CustomerHandover, Pharmacy, Role, User
from services.mail import activation_message, get_mail_transport
from services.provisioning import (
    ACTIVATION_TTL_HOURS, ProvisioningError, ProvisioningInput, ProvisioningService, normalize_email,
)

router = APIRouter(tags=["internal-customers"])


class OperatorAuthRateLimiter:
    """Bounded, per-process failed-authentication throttle for the private console."""

    def __init__(
        self,
        *,
        failure_limit: int = 5,
        window_seconds: int = 600,
        cooldown_seconds: int = 600,
        max_identities: int = 2048,
        clock=time.monotonic,
    ) -> None:
        self.failure_limit = failure_limit
        self.window_seconds = window_seconds
        self.cooldown_seconds = cooldown_seconds
        self.max_identities = max_identities
        self._clock = clock
        self._entries: OrderedDict[str, tuple[deque[float], float, float]] = OrderedDict()
        self._lock = threading.Lock()

    def _prune(self, now: float) -> None:
        stale_before = now - max(self.window_seconds, self.cooldown_seconds)
        stale = [key for key, (_, blocked_until, last_seen) in self._entries.items()
                 if blocked_until <= now and last_seen < stale_before]
        for key in stale:
            self._entries.pop(key, None)

    def retry_after(self, identity: str) -> int:
        now = self._clock()
        with self._lock:
            self._prune(now)
            entry = self._entries.get(identity)
            if not entry:
                return 0
            _, blocked_until, _ = entry
            if blocked_until <= now:
                return 0
            self._entries.move_to_end(identity)
            return max(1, math.ceil(blocked_until - now))

    def record_failure(self, identity: str) -> int:
        now = self._clock()
        with self._lock:
            self._prune(now)
            failures, blocked_until, _ = self._entries.get(identity, (deque(), 0.0, now))
            cutoff = now - self.window_seconds
            while failures and failures[0] <= cutoff:
                failures.popleft()
            failures.append(now)
            if len(failures) >= self.failure_limit:
                blocked_until = max(blocked_until, now + self.cooldown_seconds)
            self._entries[identity] = (failures, blocked_until, now)
            self._entries.move_to_end(identity)
            while len(self._entries) > self.max_identities:
                self._entries.popitem(last=False)
            return max(0, math.ceil(blocked_until - now))

    def record_success(self, identity: str) -> None:
        with self._lock:
            self._entries.pop(identity, None)

    def clear(self) -> None:
        """Test isolation without exposing rate-limit state through HTTP."""
        with self._lock:
            self._entries.clear()


# Production currently runs one service replica/process. This deliberately avoids
# new infrastructure; multiple workers/replicas would each have an independent
# bucket and must move this state to a shared edge/store before horizontal scaling.
operator_auth_limiter = OperatorAuthRateLimiter()


def _basic_credentials(request: Request) -> tuple[str, str] | None:
    authorization = request.headers.get("Authorization", "")
    scheme, separator, encoded = authorization.partition(" ")
    if not separator or scheme.lower() != "basic" or not encoded or len(encoded) > 8192:
        return None
    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None
    username, separator, password = decoded.partition(":")
    if not separator:
        return None
    return username, password


def _operator_auth_error(status_code: int, retry_after: int = 0) -> HTTPException:
    if status_code == 429:
        return HTTPException(
            status_code=429,
            detail="Too many platform operator authentication attempts",
            headers={"Retry-After": str(retry_after)},
        )
    return HTTPException(
        status_code=401,
        detail="Invalid platform operator credentials",
        headers={"WWW-Authenticate": "Basic"},
    )


def require_platform_operator(request: Request) -> str:
    expected_user = os.getenv("PLATFORM_OPERATOR_USERNAME", "")
    expected_hash = os.getenv("PLATFORM_OPERATOR_PASSWORD_HASH", "")
    if not expected_user or not expected_hash:
        raise HTTPException(status_code=503, detail="Platform operator access is not configured")

    # The deployment has no application-level trusted-proxy allowlist, so neither
    # Forwarded/X-Forwarded-For nor request.client is safe as an end-user identity.
    # Use one fail-closed bucket for the configured operator account. This cannot
    # be bypassed by changing source headers, username candidates, or paths.
    identity = "configured-platform-operator"
    retry_after = operator_auth_limiter.retry_after(identity)
    if retry_after:
        raise _operator_auth_error(429, retry_after)

    credentials = _basic_credentials(request)
    username = credentials[0] if credentials else ""
    password = credentials[1] if credentials else ""
    username_valid = hmac.compare_digest(username, expected_user)
    try:
        password_valid = verify_password(password, expected_hash)
    except ValueError:
        # bcrypt rejects oversized/malformed candidates; they are authentication
        # failures and must contribute to throttling rather than become a 500.
        password_valid = False
    if not username_valid or not password_valid:
        retry_after = operator_auth_limiter.record_failure(identity)
        if retry_after:
            raise _operator_auth_error(429, retry_after)
        raise _operator_auth_error(401)

    operator_auth_limiter.record_success(identity)
    return expected_user


class CustomerCreate(BaseModel):
    pharmacy_name: str = Field(..., min_length=2, max_length=100)
    owner_name: str = Field(..., min_length=2, max_length=100)
    owner_email: str = Field(..., min_length=5, max_length=320)
    owner_phone: str = Field("", max_length=20)
    city: str = Field("", max_length=100)
    payment_confirmed: bool = False

    @field_validator("pharmacy_name", "owner_name")
    @classmethod
    def clean_required_text(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 2:
            raise ValueError("required field is too short")
        return cleaned

    @field_validator("owner_email")
    @classmethod
    def valid_owner_email(cls, value: str) -> str:
        return normalize_email(value)


def require_internal_request(request: Request) -> None:
    """Block browser form CSRF against HTTP-Basic authenticated mutations."""
    if request.headers.get("X-PharmaSUD-Internal") != "1":
        raise HTTPException(status_code=403, detail="Internal request verification failed")


def _serialize(db: Session, row: CustomerHandover) -> dict:
    active = False
    pharmacy_active = False
    if row.pharmacy_id:
        pharmacy = db.get(Pharmacy, row.pharmacy_id)
        pharmacy_active = bool(pharmacy and pharmacy.is_active)
        owner_role = db.query(Role).filter(Role.name == "owner").one()
        owner = db.get(User, row.owner_user_id) if row.owner_user_id else None
        if owner is None:
            owner = db.query(User).filter(User.pharmacy_id == row.pharmacy_id, User.role_id == owner_role.id).one_or_none()
        active = bool(owner and owner.is_active)
        if active and pharmacy_active and row.status not in {"ACTIVE", "ABANDONED", "ARCHIVED"}:
            row.status = "ACTIVE"
            db.flush()
    return {
        "id": str(row.id), "pharmacy_name": row.pharmacy_name, "owner_name": row.owner_name,
        "owner_email": row.owner_email or "", "owner_phone": row.owner_phone or "", "city": row.city or "",
        "payment_confirmed": bool(row.payment_confirmed_at), "status": row.status,
        "classification": row.classification, "origin": row.origin,
        "payment_confirmed_at": row.payment_confirmed_at.isoformat() if row.payment_confirmed_at else None,
        "activation_active": active, "pharmacy_active": pharmacy_active,
        "activation_email_sent_at": row.activation_email_sent_at.isoformat() if row.activation_email_sent_at else None,
        "archived_at": row.archived_at.isoformat() if row.archived_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _commercial_summary(customers: list[dict]) -> dict:
    commercial = [
        row for row in customers
        if row["classification"] == "COMMERCIAL" and row["status"] not in {"ABANDONED", "ARCHIVED"}
    ]
    return {
        "total": len(commercial),
        "payment_pending": sum(row["status"] == "PAYMENT_PENDING" for row in commercial),
        "activation_pending": sum(
            row["status"] in {"AWAITING_OWNER_ACTIVATION", "ACTIVATION_EMAIL_FAILED"}
            for row in commercial
        ),
        "active": sum(
            row["status"] == "ACTIVE" and row["pharmacy_active"] and row["activation_active"]
            for row in commercial
        ),
    }


@router.get("/internal/customers", response_class=HTMLResponse)
def console(request: Request, operator: str = Depends(require_platform_operator)):
    from main import templates
    return templates.TemplateResponse("internal_customers.html", {"request": request, "operator": operator})


@router.get("/api/internal/customers")
def list_customers(operator: str = Depends(require_platform_operator), db: Session = Depends(get_db)):
    rows = db.query(CustomerHandover).order_by(CustomerHandover.created_at.desc()).all()
    result = [_serialize(db, row) for row in rows]
    db.commit()
    return {"customers": result, "summary": _commercial_summary(result)}


@router.post("/api/internal/customers", dependencies=[Depends(require_internal_request)])
def create_customer(data: CustomerCreate, operator: str = Depends(require_platform_operator), db: Session = Depends(get_db)):
    existing = db.query(CustomerHandover).filter(
        func.lower(CustomerHandover.owner_email) == data.owner_email,
        CustomerHandover.status != "ABANDONED",
    ).one_or_none()
    if existing:
        same = existing.pharmacy_name == data.pharmacy_name and existing.owner_name == data.owner_name
        if not same:
            raise HTTPException(status_code=409, detail="Owner email is already assigned to another customer")
        if existing.status in {"ABANDONED", "ARCHIVED"}:
            raise HTTPException(status_code=409, detail="Customer lifecycle does not allow this action")
        if data.payment_confirmed and not existing.payment_confirmed_at:
            existing.payment_confirmed_at = datetime.utcnow()
            existing.payment_confirmed_by = operator
            existing.status = "READY_TO_PROVISION"
            add_audit_event(db, pharmacy_id=None, user_id=None, user_name=operator,
                            action_type="customer_payment_confirmed", description="Offline payment confirmed",
                            target_entity="customer_handover", target_id=str(existing.id))
            db.commit()
        return {"customer": _serialize(db, existing), "idempotent": True}
    reference = "CUS-" + uuid.uuid4().hex.upper()
    row = CustomerHandover(
        id=uuid.uuid4(), customer_reference=reference,
        pharmacy_name=data.pharmacy_name.strip(), owner_name=data.owner_name.strip(),
        owner_email=data.owner_email.strip().lower(), owner_phone=data.owner_phone.strip(), city=data.city.strip(),
        classification="COMMERCIAL", origin="HANDOVER",
        status="READY_TO_PROVISION" if data.payment_confirmed else "PAYMENT_PENDING",
        payment_confirmed_at=datetime.utcnow() if data.payment_confirmed else None,
        payment_confirmed_by=operator if data.payment_confirmed else None,
    )
    db.add(row)
    if data.payment_confirmed:
        add_audit_event(db, pharmacy_id=None, user_id=None, user_name=operator,
                        action_type="customer_payment_confirmed", description="Offline payment confirmed",
                        target_entity="customer_handover", target_id=str(row.id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.query(CustomerHandover).filter(
            func.lower(CustomerHandover.owner_email) == data.owner_email,
            CustomerHandover.status != "ABANDONED",
        ).one_or_none()
        if existing and existing.pharmacy_name == data.pharmacy_name and existing.owner_name == data.owner_name:
            return {"customer": _serialize(db, existing), "idempotent": True}
        raise HTTPException(status_code=409, detail="Customer already exists")
    return {"customer": _serialize(db, row), "idempotent": False}


@router.post("/api/internal/customers/{customer_id}/confirm-payment", dependencies=[Depends(require_internal_request)])
def confirm_payment(customer_id: uuid.UUID, operator: str = Depends(require_platform_operator), db: Session = Depends(get_db)):
    row = db.get(CustomerHandover, customer_id)
    if not row:
        raise HTTPException(status_code=404, detail="Customer not found")
    if row.status in {"ABANDONED", "ARCHIVED"} or row.classification == "DEMO":
        raise HTTPException(status_code=409, detail="Customer lifecycle does not allow this action")
    if not row.payment_confirmed_at:
        row.payment_confirmed_at = datetime.utcnow(); row.payment_confirmed_by = operator
        row.status = "READY_TO_PROVISION"
        add_audit_event(db, pharmacy_id=None, user_id=None, user_name=operator,
                        action_type="customer_payment_confirmed", description="Offline payment confirmed",
                        target_entity="customer_handover", target_id=str(row.id))
        db.commit()
    return {"customer": _serialize(db, row)}


def _send_activation(row: CustomerHandover, secret: str) -> None:
    get_mail_transport().send(activation_message(
        recipient=row.owner_email, pharmacy=row.pharmacy_name, owner=row.owner_name,
        secret=secret, expires_hours=ACTIVATION_TTL_HOURS,
    ))


@router.post("/api/internal/customers/{customer_id}/provision", dependencies=[Depends(require_internal_request)])
def provision(customer_id: uuid.UUID, operator: str = Depends(require_platform_operator), db: Session = Depends(get_db)):
    row = db.get(CustomerHandover, customer_id)
    if not row:
        raise HTTPException(status_code=404, detail="Customer not found")
    if row.status in {"ABANDONED", "ARCHIVED"} or row.classification == "DEMO":
        raise HTTPException(status_code=409, detail="Customer lifecycle does not allow this action")
    if not row.payment_confirmed_at:
        raise HTTPException(status_code=409, detail="Payment must be confirmed before provisioning")
    if row.pharmacy_id:
        return {"customer": _serialize(db, row), "idempotent": True}
    try:
        result = ProvisioningService(SessionLocal).provision(ProvisioningInput(
            customer_reference=row.customer_reference, pharmacy_name=row.pharmacy_name,
            owner_name=row.owner_name, owner_email=row.owner_email, operator=operator,
            phone=row.owner_phone or "", address=row.city or "", provisioning_request_id=row.id,
        ))
    except (ProvisioningError, ValueError):
        raise HTTPException(status_code=409, detail="Customer could not be provisioned")
    pharmacy = db.query(Pharmacy).filter(Pharmacy.customer_reference == row.customer_reference).one()
    row.pharmacy_id = pharmacy.id
    owner_role = db.query(Role).filter(Role.name == "owner").one()
    owner = db.query(User).filter(User.pharmacy_id == pharmacy.id, User.role_id == owner_role.id).one()
    row.owner_user_id = owner.id
    activation_secret = result.activation_secret
    if not activation_secret:
        # Recover safely if provisioning committed but the handover row was not linked
        # before an interrupted request. Reissue is hash-only and revokes the old token.
        activation_secret = ProvisioningService(SessionLocal).reissue_activation(
            row.customer_reference, operator
        ).activation_secret
    try:
        _send_activation(row, activation_secret)
        row.status = "AWAITING_OWNER_ACTIVATION"; row.activation_email_sent_at = datetime.utcnow()
        row.activation_email_error = None
    except Exception:
        row.status = "ACTIVATION_EMAIL_FAILED"; row.activation_email_error = "Delivery failed"
    db.commit()
    return {"customer": _serialize(db, row), "idempotent": False}


@router.post("/api/internal/customers/{customer_id}/resend-activation", dependencies=[Depends(require_internal_request)])
def resend_activation(customer_id: uuid.UUID, operator: str = Depends(require_platform_operator), db: Session = Depends(get_db)):
    row = db.get(CustomerHandover, customer_id)
    if not row or not row.pharmacy_id:
        raise HTTPException(status_code=409, detail="Customer is not provisioned")
    if row.status in {"ABANDONED", "ARCHIVED"} or row.classification == "DEMO":
        raise HTTPException(status_code=409, detail="Customer lifecycle does not allow this action")
    try:
        result = ProvisioningService(SessionLocal).reissue_activation(row.customer_reference, operator)
    except ProvisioningError:
        raise HTTPException(status_code=409, detail="Activation cannot be reissued")
    try:
        _send_activation(row, result.activation_secret)
        row.status = "AWAITING_OWNER_ACTIVATION"; row.activation_email_sent_at = datetime.utcnow()
        row.activation_email_error = None
    except Exception:
        row.status = "ACTIVATION_EMAIL_FAILED"; row.activation_email_error = "Delivery failed"
    db.commit()
    return {"customer": _serialize(db, row)}


@router.post("/api/internal/customers/{customer_id}/archive", dependencies=[Depends(require_internal_request)])
def archive_customer(
    customer_id: uuid.UUID,
    operator: str = Depends(require_platform_operator),
    db: Session = Depends(get_db),
):
    """Archive without deleting tenant, identity, history, or audit records."""
    row = db.get(CustomerHandover, customer_id)
    if not row:
        raise HTTPException(status_code=404, detail="Customer not found")
    if row.status == "ARCHIVED":
        return {"customer": _serialize(db, row), "idempotent": True}
    if row.status == "ABANDONED":
        raise HTTPException(status_code=409, detail="Abandoned handover cannot be archived")

    previous_status = row.status
    row.status = "ARCHIVED"
    row.archived_at = datetime.utcnow()
    row.archived_by = operator
    if row.pharmacy_id:
        pharmacy = db.get(Pharmacy, row.pharmacy_id)
        if pharmacy:
            pharmacy.is_active = False
        users = db.query(User).filter(User.pharmacy_id == row.pharmacy_id).all()
        for user in users:
            user.is_active = False
            user.auth_version += 1
    add_audit_event(
        db, pharmacy_id=str(row.pharmacy_id) if row.pharmacy_id else None,
        user_id=None, user_name=operator, action_type="customer_archived",
        description="Customer archived without destructive deletion",
        target_entity="customer_handover", target_id=str(row.id),
        old_value=previous_status, new_value="ARCHIVED",
    )
    db.commit()
    return {"customer": _serialize(db, row), "idempotent": False}
