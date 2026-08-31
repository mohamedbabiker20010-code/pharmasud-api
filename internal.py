"""Private, non-tenant platform-operator customer handover console."""

from datetime import datetime
import hmac
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
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
basic = HTTPBasic()


def require_platform_operator(credentials: HTTPBasicCredentials = Depends(basic)) -> str:
    expected_user = os.getenv("PLATFORM_OPERATOR_USERNAME", "")
    expected_hash = os.getenv("PLATFORM_OPERATOR_PASSWORD_HASH", "")
    if not expected_user or not expected_hash:
        raise HTTPException(status_code=503, detail="Platform operator access is not configured")
    if not hmac.compare_digest(credentials.username, expected_user) or not verify_password(credentials.password, expected_hash):
        raise HTTPException(status_code=401, detail="Invalid platform operator credentials", headers={"WWW-Authenticate": "Basic"})
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
    if row.pharmacy_id:
        owner_role = db.query(Role).filter(Role.name == "owner").one()
        owner = db.query(User).filter(User.pharmacy_id == row.pharmacy_id, User.role_id == owner_role.id).one_or_none()
        active = bool(owner and owner.is_active)
        if active and row.status != "ACTIVE":
            row.status = "ACTIVE"
            db.flush()
    return {
        "id": str(row.id), "pharmacy_name": row.pharmacy_name, "owner_name": row.owner_name,
        "owner_email": row.owner_email, "owner_phone": row.owner_phone or "", "city": row.city or "",
        "payment_confirmed": bool(row.payment_confirmed_at), "status": row.status,
        "activation_active": active, "created_at": row.created_at.isoformat() if row.created_at else None,
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
    return {"customers": result}


@router.post("/api/internal/customers", dependencies=[Depends(require_internal_request)])
def create_customer(data: CustomerCreate, operator: str = Depends(require_platform_operator), db: Session = Depends(get_db)):
    existing = db.query(CustomerHandover).filter(
        func.lower(CustomerHandover.owner_email) == data.owner_email
    ).one_or_none()
    if existing:
        same = existing.pharmacy_name == data.pharmacy_name and existing.owner_name == data.owner_name
        if not same:
            raise HTTPException(status_code=409, detail="Owner email is already assigned to another customer")
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
            func.lower(CustomerHandover.owner_email) == data.owner_email
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
