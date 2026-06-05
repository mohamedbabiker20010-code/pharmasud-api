"""
PharmaSUD - SQLAlchemy Models + Pydantic Schemas
Stage 2 - Version 2.0.0

Defines all database tables and relationships for the pharmacy POS system.
Includes Pydantic models for authentication and validation.
"""

import uuid
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Date, Numeric, ForeignKey, CheckConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field, validator
from typing import Optional
from database import Base


# ═══════════════════════════════════════════════════════════
# Pydantic Models for Authentication (Stage 2)
# ═══════════════════════════════════════════════════════════

class ProductKeyActivate(BaseModel):
    """Schema for product key activation."""
    product_key: str = Field(..., min_length=10, max_length=100, description="Product activation key")
    
    class Config:
        json_schema_extra = {
            "example": {
                "product_key": "PHARM-SDN-2026-RAHMA-X7K9"
            }
        }


class AdminCreate(BaseModel):
    """Schema for creating first admin user."""
    pharmacy_id: str = Field(..., description="Pharmacy UUID")
    full_name: str = Field(..., min_length=2, max_length=100, description="Full name in Arabic or English")
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    password: str = Field(..., min_length=6, max_length=100, description="Password (min 6 characters)")
    confirm_password: str = Field(..., description="Password confirmation")
    
    @validator('username')
    def username_alphanumeric(cls, v):
        if not v.isalnum():
            raise ValueError('اسم المستخدم يجب أن يكون حروف أبجدية وأرقام فقط')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "pharmacy_id": "550e8400-e29b-41d4-a716-446655440000",
                "full_name": "محمد أحمد",
                "username": "admin",
                "password": "123456",
                "confirm_password": "123456"
            }
        }


class UserLogin(BaseModel):
    """Schema for user login."""
    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")
    
    class Config:
        json_schema_extra = {
            "example": {
                "username": "admin",
                "password": "123456"
            }
        }


class TokenResponse(BaseModel):
    """Schema for token response."""
    success: bool
    token: Optional[str] = None
    role: Optional[str] = None
    full_name: Optional[str] = None
    pharmacy_name: Optional[str] = None
    message: Optional[str] = None


class UserResponse(BaseModel):
    """Schema for current user info."""
    user_id: str
    username: str
    role: str
    full_name: Optional[str] = None
    pharmacy_name: Optional[str] = None


class SystemStatus(BaseModel):
    """Schema for system activation status."""
    status: str = Field(..., description="needs_activation, needs_setup, or ready")
    pharmacy_id: Optional[str] = None
    message: str


# ═══════════════════════════════════════════════════════════
# SQLAlchemy Database Models (Original - Stage 1)
# ═══════════════════════════════════════════════════════════


class Pharmacy(Base):
    """Pharmacy entity - each pharmacy has isolated data."""
    __tablename__ = "pharmacies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_key = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    owner_name = Column(String(100))
    phone = Column(String(20))
    address = Column(String)
    is_active = Column(Boolean, default=False)
    activated_at = Column(DateTime)
    created_at = Column(DateTime, server_default=text("NOW()"))

    # Relationships
    users = relationship("User", back_populates="pharmacy", cascade="all, delete-orphan")
    medicines = relationship("Medicine", back_populates="pharmacy", cascade="all, delete-orphan")
    sales = relationship("Sale", back_populates="pharmacy", cascade="all, delete-orphan")


class User(Base):
    """User entity - admin and employee accounts."""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pharmacy_id = Column(UUID(as_uuid=True), ForeignKey("pharmacies.id"), nullable=False)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)
    full_name = Column(String(100))
    phone = Column(String(20))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=text("NOW()"))

    # Enforce valid roles
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'employee')", name="check_user_role"),
    )

    # Relationships
    pharmacy = relationship("Pharmacy", back_populates="users")
    sales = relationship("Sale", back_populates="user")


class Medicine(Base):
    """Medicine entity - products in the pharmacy."""
    __tablename__ = "medicines"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pharmacy_id = Column(UUID(as_uuid=True), ForeignKey("pharmacies.id"), nullable=False)
    barcode = Column(String(50))
    trade_name = Column(String(100), nullable=False)
    scientific_name = Column(String(100))
    category = Column(String(50))
    sale_price = Column(Numeric(10, 2), nullable=False)
    purchase_price = Column(Numeric(10, 2))
    base_unit = Column(String(20), default="strip")
    min_stock = Column(Integer, default=10)
    created_at = Column(DateTime, server_default=text("NOW()"))

    # Relationships
    pharmacy = relationship("Pharmacy", back_populates="medicines")
    units = relationship("Unit", back_populates="medicine", cascade="all, delete-orphan")
    batches = relationship("Batch", back_populates="medicine", cascade="all, delete-orphan")
    sale_items = relationship("SaleItem", back_populates="medicine")


class Unit(Base):
    """Unit of measurement - e.g., box=10 strips=100 tablets."""
    __tablename__ = "units"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    medicine_id = Column(UUID(as_uuid=True), ForeignKey("medicines.id"), nullable=False)
    unit_name = Column(String(20), nullable=False)
    conversion_factor = Column(Numeric(10, 3), nullable=False)
    sale_price = Column(Numeric(10, 2))

    medicine = relationship("Medicine", back_populates="units")


class Batch(Base):
    """Batch/Lot tracking for FEFO (First Expired First Out)."""
    __tablename__ = "batches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    medicine_id = Column(UUID(as_uuid=True), ForeignKey("medicines.id"), nullable=False)
    batch_number = Column(String(50))
    quantity = Column(Integer, nullable=False, default=0)
    expiry_date = Column(Date, nullable=False)
    purchase_price = Column(Numeric(10, 2))
    supplier_invoice = Column(String(50))
    received_at = Column(DateTime, server_default=text("NOW()"))
    is_active = Column(Boolean, default=True)

    # Relationships
    medicine = relationship("Medicine", back_populates="batches")
    sale_items = relationship("SaleItem", back_populates="batch")


class Sale(Base):
    """Sale transaction - each sale operation."""
    __tablename__ = "sales"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pharmacy_id = Column(UUID(as_uuid=True), ForeignKey("pharmacies.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    invoice_number = Column(Integer)
    customer_name = Column(String(100))
    total_amount = Column(Numeric(10, 2), nullable=False)
    payment_method = Column(String(20), nullable=False)
    created_at = Column(DateTime, server_default=text("NOW()"))

    # Valid payment methods
    __table_args__ = (
        CheckConstraint(
            "payment_method IN ('cash', 'bankak', 'fory', 'transfer')",
            name="check_payment_method"
        ),
    )

    # Relationships
    pharmacy = relationship("Pharmacy", back_populates="sales")
    user = relationship("User", back_populates="sales")
    items = relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan")


class SaleItem(Base):
    """Sale line items - individual products in a sale."""
    __tablename__ = "sale_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sale_id = Column(UUID(as_uuid=True), ForeignKey("sales.id"), nullable=False)
    medicine_id = Column(UUID(as_uuid=True), ForeignKey("medicines.id"))
    batch_id = Column(UUID(as_uuid=True), ForeignKey("batches.id"))
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    total_price = Column(Numeric(10, 2), nullable=False)

    # Relationships
    sale = relationship("Sale", back_populates="items")
    medicine = relationship("Medicine", back_populates="sale_items")
    batch = relationship("Batch", back_populates="sale_items")


# ✅ انتهى - models.py - المرحلة 2
