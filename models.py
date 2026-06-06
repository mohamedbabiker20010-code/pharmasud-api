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
# Pydantic Models for Medicines (Stage 3)
# ═══════════════════════════════════════════════════════════

# Medicine categories (fixed list)
MEDICINE_CATEGORIES = [
    "مسكنات ومضادات الالتهاب",
    "مضادات حيوية",
    "أدوية القلب والضغط",
    "أدوية السكري",
    "أدوية الجهاز الهضمي",
    "أدوية الجهاز التنفسي",
    "فيتامينات ومكملات",
    "أدوية الجلد",
    "قطرات وأدوية العيون",
    "أدوية الأعصاب",
    "أدوية نسائية",
    "أدوية الأطفال",
    "مستلزمات طبية",
    "أخرى"
]


class MedicineCreate(BaseModel):
    """Schema for creating a new medicine."""
    trade_name: str = Field(..., min_length=1, max_length=100, description="Trade name in Arabic")
    scientific_name: Optional[str] = Field(None, max_length=100, description="Scientific name")
    category: str = Field(..., description="Medicine category")
    barcode: Optional[str] = Field(None, max_length=50, description="Barcode number")
    sale_price: float = Field(..., gt=0, description="Sale price")
    purchase_price: float = Field(..., gt=0, description="Purchase price (admin only)")
    base_unit: str = Field(..., description="Base unit: box, strip, tablet, etc.")
    min_stock: int = Field(default=10, ge=0, description="Minimum stock for alert")
    image_path: Optional[str] = Field(None, description="Path to medicine image")
    
    @validator('category')
    def validate_category(cls, v):
        if v not in MEDICINE_CATEGORIES:
            raise ValueError(f'التصنيف يجب أن يكون واحداً من: {", ".join(MEDICINE_CATEGORIES)}')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "trade_name": "بانادول أزرق",
                "scientific_name": "Paracetamol 500mg",
                "category": "مسكنات ومضادات الالتهاب",
                "barcode": "6251234567890",
                "sale_price": 350.00,
                "purchase_price": 280.00,
                "base_unit": "strip",
                "min_stock": 10
            }
        }


class MedicineUpdate(BaseModel):
    """Schema for updating a medicine."""
    trade_name: Optional[str] = Field(None, min_length=1, max_length=100)
    scientific_name: Optional[str] = Field(None, max_length=100)
    category: Optional[str] = None
    barcode: Optional[str] = Field(None, max_length=50)
    sale_price: Optional[float] = Field(None, gt=0)
    purchase_price: Optional[float] = Field(None, gt=0)
    base_unit: Optional[str] = None
    min_stock: Optional[int] = Field(None, ge=0)
    image_path: Optional[str] = None
    
    @validator('category')
    def validate_category(cls, v):
        if v is not None and v not in MEDICINE_CATEGORIES:
            raise ValueError(f'التصنيف يجب أن يكون واحداً من: {", ".join(MEDICINE_CATEGORIES)}')
        return v


class UnitCreate(BaseModel):
    """Schema for creating units for a medicine."""
    units: list = Field(..., description="List of units with conversion factors")
    
    class Config:
        json_schema_extra = {
            "example": {
                "units": [
                    {"unit_name": "علبة", "conversion_factor": 10},
                    {"unit_name": "شريط", "conversion_factor": 1},
                    {"unit_name": "قرص", "conversion_factor": 0.1}
                ]
            }
        }


class MedicineResponse(BaseModel):
    """Schema for medicine response (employee view - hides purchase_price)."""
    id: str
    trade_name: str
    scientific_name: Optional[str]
    category: str
    barcode: Optional[str]
    sale_price: float
    base_unit: str
    min_stock: int
    total_stock: int
    stock_status: str  # available, low, out
    image_url: Optional[str]
    units: list
    
    class Config:
        from_attributes = True


class MedicineResponseAdmin(BaseModel):
    """Schema for medicine response (admin view - includes purchase_price)."""
    id: str
    trade_name: str
    scientific_name: Optional[str]
    category: str
    barcode: Optional[str]
    sale_price: float
    purchase_price: float
    base_unit: str
    min_stock: int
    total_stock: int
    stock_status: str
    image_url: Optional[str]
    units: list
    
    class Config:
        from_attributes = True


class MedicineListResponse(BaseModel):
    """Schema for list of medicines."""
    medicines: list
    total: int


class BarcodeSearchResponse(BaseModel):
    """Schema for barcode search response."""
    found: bool
    medicine: Optional[dict] = None
    barcode: str


class MedicineDeleteResponse(BaseModel):
    """Schema for medicine deletion response."""
    success: bool
    message: str


# ═══════════════════════════════════════════════════════════
# Pydantic Models for Batches & Inventory (Stage 4)
# ═══════════════════════════════════════════════════════════


class BatchReceive(BaseModel):
    """Schema for receiving a new batch/shipment."""
    medicine_id: str = Field(..., description="Medicine UUID")
    batch_number: str = Field(..., min_length=1, max_length=50, description="Batch number")
    quantity: float = Field(..., gt=0, description="Quantity received")
    unit_name: str = Field(..., description="Unit of the quantity (e.g. علبة, شريط)")
    expiry_date: str = Field(..., description="Expiry date (YYYY-MM-DD)")
    purchase_price: float = Field(..., gt=0, description="Purchase price per unit")
    supplier_invoice: Optional[str] = Field(None, max_length=50, description="Supplier invoice number")
    supplier_name: Optional[str] = Field(None, max_length=100, description="Supplier name")

    class Config:
        json_schema_extra = {
            "example": {
                "medicine_id": "uuid...",
                "batch_number": "BATCH-2026-001",
                "quantity": 5,
                "unit_name": "علبة",
                "expiry_date": "2028-06-15",
                "purchase_price": 280.00,
                "supplier_invoice": "INV-2026-4455",
                "supplier_name": "شركة الدواء السودانية"
            }
        }


class BatchReceiveConfirm(BaseModel):
    """Schema for confirming receipt of short-expiry batch."""
    batch_data: BatchReceive
    confirmed: bool = Field(..., description="User confirmation for short expiry")


class BatchResponse(BaseModel):
    """Schema for a single batch in response."""
    batch_id: str
    batch_number: str
    quantity: int
    expiry_date: str
    expiry_status: str  # منتهي, ينتهي قريباً, تحذير, سليم
    days_remaining: int
    purchase_price: Optional[float] = None
    supplier_invoice: Optional[str] = None
    supplier_name: Optional[str] = None
    received_at: Optional[str] = None

    class Config:
        from_attributes = True


class BatchReceiveResponse(BaseModel):
    """Schema for batch receive response."""
    success: bool
    batch_id: Optional[str] = None
    quantity_stored: Optional[int] = None
    unit_converted: Optional[str] = None
    expiry_warning: Optional[str] = None
    message: Optional[str] = None


class FEFOAllocation(BaseModel):
    """Schema for a single batch allocation in FEFO."""
    batch_id: str
    quantity: int
    expiry_date: str


class FEFOResult(BaseModel):
    """Schema for FEFO batch allocation result."""
    success: bool
    medicine_id: str
    trade_name: str
    quantity_needed: int
    allocated: list[FEFOAllocation]
    remaining: int


class MedicineInventoryItem(BaseModel):
    """Schema for inventory list item."""
    medicine_id: str
    trade_name: str
    scientific_name: Optional[str] = None
    category: str
    image_url: Optional[str] = None
    total_stock: int
    base_unit: str
    stock_status: str  # available, low, out
    nearest_expiry: Optional[str] = None
    nearest_expiry_status: Optional[str] = None
    batches_count: int

    class Config:
        from_attributes = True


class InventoryListResponse(BaseModel):
    """Schema for inventory list."""
    medicines: list[MedicineInventoryItem]
    total: int


class BatchDetailResponse(BaseModel):
    """Schema for batch details of a medicine."""
    medicine_id: str
    trade_name: str
    scientific_name: Optional[str] = None
    image_url: Optional[str] = None
    base_unit: str
    total_stock: int
    batches: list[BatchResponse]


class ExpiredItem(BaseModel):
    """Schema for expired item in report."""
    medicine_name: str
    batch_number: str
    quantity: int
    expiry_date: str
    days_expired: int


class ExpiredReportResponse(BaseModel):
    """Schema for expired items report."""
    expired: list[ExpiredItem]
    total_expired_items: int


class AvailableBatchResponse(BaseModel):
    """Schema for available batches (FEFO-ready)."""
    medicine_id: str
    trade_name: str
    total_available: int
    batches: list[BatchResponse]


# ✅ انتهى - Pydantic Models للمرحلة 4
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
    image_path = Column(String(255))  # New: Image path for medicine
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
    supplier_name = Column(String(100))
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


# ✅ انتهى - models.py - المرحلة 4
