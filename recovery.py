"""Public privacy-preserving email password recovery routes."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from services.mail import get_mail_transport
from services.recovery import ResetError, request_password_reset, reset_password

router = APIRouter(tags=["password-recovery"])
GENERIC = "If an account exists for this email, password reset instructions have been sent."


class ForgotRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=320)


class ResetRequest(BaseModel):
    token: str = Field(..., min_length=32, max_length=200)
    password: str = Field(..., min_length=12, max_length=72)
    confirm_password: str = Field(..., min_length=12, max_length=72)


@router.get("/forgot-password", response_class=HTMLResponse)
def forgot_page(request: Request):
    from main import templates
    return templates.TemplateResponse("forgot_password.html", {"request": request})


@router.get("/reset-password", response_class=HTMLResponse)
def reset_page(request: Request):
    from main import templates
    return templates.TemplateResponse("reset_password.html", {"request": request})


@router.post("/api/auth/forgot-password")
def forgot(data: ForgotRequest, db: Session = Depends(get_db)):
    try:
        request_password_reset(db, email=data.email, transport=get_mail_transport())
        db.commit()
    except Exception:
        db.rollback()
    return {"success": True, "message": GENERIC}


@router.post("/api/auth/reset-password")
def reset(data: ResetRequest, db: Session = Depends(get_db)):
    if data.password != data.confirm_password:
        raise HTTPException(status_code=400, detail="Reset link is invalid or expired")
    try:
        reset_password(db, secret=data.token, password=data.password)
        db.commit()
    except ResetError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Reset link is invalid or expired")
    return {"success": True, "message": "Password reset completed"}
