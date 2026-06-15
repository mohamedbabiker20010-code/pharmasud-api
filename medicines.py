"""
PharmaSUD - Medicines Module
Stage 3 - Version 3.0.0

Handles:
- Medicine CRUD operations
- Image upload and processing
- Barcode scanning and search
- Units management
- Stock tracking
"""

import os
import uuid
import shutil
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from PIL import Image

from database import get_db
from models import (
    Medicine, Unit, Batch, Pharmacy, User,
    MedicineCreate, MedicineUpdate, MedicineResponse, MedicineResponseAdmin,
    MedicineListResponse, BarcodeSearchResponse, MedicineDeleteResponse,
    MEDICINE_CATEGORIES
)
from auth import get_current_user, require_admin
from audit import log_action

# Create router
router = APIRouter(prefix="/api/medicines", tags=["medicines"])

# Image settings
UPLOAD_DIR = "static/medicines/images"
MAX_IMAGE_SIZE = 2 * 1024 * 1024  # 2MB
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
DEFAULT_IMAGE_SIZE = (300, 300)

# Ensure upload directory exists
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ═══════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════

def get_total_stock(medicine_id: str, db: Session) -> int:
    """Calculate total stock for a medicine from all batches."""
    result = db.query(func.sum(Batch.quantity)).filter(
        Batch.medicine_id == medicine_id,
        Batch.is_active == True
    ).scalar()
    return int(result) if result else 0


def get_stock_status(total_stock: int, min_stock: int) -> str:
    """Determine stock status based on quantity and minimum threshold."""
    if total_stock <= 0:
        return "out"  # 🔴 نفد
    elif total_stock <= min_stock:
        return "low"  # 🟡 منخفض
    else:
        return "available"  # 🟢 متوفر


import base64
import io

def process_image(image_file: UploadFile, medicine_id: str) -> str:
    """Process image and return Base64 data URL (persists across deploys)."""
    import tempfile
    
    # Validate extension
    ext = os.path.splitext(image_file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="يجب أن تكون الصورة بصيغة: JPG, PNG, أو WEBP"
        )
    
    # Process directly from upload file to Base64
    
    try:
        with Image.open(image_file.file) as img:
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            # Resize to 300x300
            img = img.resize(DEFAULT_IMAGE_SIZE, Image.Resampling.LANCZOS)
            
            # Save to bytes buffer and encode as Base64
            buffer = io.BytesIO()
            img.save(buffer, 'JPEG', quality=85, optimize=True)
            img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            return f"data:image/jpeg;base64,{img_base64}"
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"فشل في معالجة الصورة: {str(e)}"
        )


def delete_image(image_path: str):
    """No-op: Base64 images stored in DB, no file to delete."""
    pass


def format_medicine_response(medicine: Medicine, db: Session, is_admin: bool = False) -> dict:
    """Format medicine data for response."""
    total_stock = get_total_stock(str(medicine.id), db)
    stock_status = get_stock_status(total_stock, medicine.min_stock)
    
    # Get units
    units = [
        {
            "id": str(unit.id),
            "unit_name": unit.unit_name,
            "conversion_factor": float(unit.conversion_factor),
            "sale_price": float(unit.sale_price) if unit.sale_price else None
        }
        for unit in medicine.units
    ]
    
    response = {
        "id": str(medicine.id),
        "trade_name": medicine.trade_name,
        "scientific_name": medicine.scientific_name,
        "category": medicine.category,
        "barcode": medicine.barcode,
        "sale_price": float(medicine.sale_price),
        "base_unit": medicine.base_unit,
        "min_stock": medicine.min_stock,
        "total_stock": total_stock,
        "stock_status": stock_status,
        "image_url": medicine.image_path or "/static/images/default-medicine.svg",
            "image_is_base64": bool(medicine.image_path and medicine.image_path.startswith("data:")),
        "units": units
    }
    
    if is_admin:
        response["purchase_price"] = float(medicine.purchase_price) if medicine.purchase_price else None
    
    return response


# ═══════════════════════════════════════════════════════════
# Image Upload Endpoint
# ═══════════════════════════════════════════════════════════

@router.post("/upload-image")
async def upload_medicine_image(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload and process medicine image."""
    # Check file size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning
    
    if file_size > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=400,
            detail="حجم الصورة كبير جداً. الحد الأقصى 2MB"
        )
    
    # Generate temporary medicine ID for image naming
    temp_id = str(uuid.uuid4())[:8]
    
    try:
        image_path = process_image(file, temp_id)
        return {
            "success": True,
            "image_url": image_path,
            "message": "تم رفع الصورة بنجاح"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"فشل في رفع الصورة: {str(e)}"
        )


# ═══════════════════════════════════════════════════════════
# Medicine CRUD Endpoints
# ═══════════════════════════════════════════════════════════

@router.post("/")
async def create_medicine(
    data: MedicineCreate,
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Create a new medicine (Admin only)."""
    # Check for duplicate barcode
    if data.barcode:
        existing = db.query(Medicine).filter(
            Medicine.barcode == data.barcode,
            Medicine.pharmacy_id == current_user["pharmacy_id"]
        ).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail="الباركود مستخدم مسبقاً لدواء آخر"
            )
    
    # Create medicine
    medicine = Medicine(
        id=uuid.uuid4(),
        pharmacy_id=current_user["pharmacy_id"],
        barcode=data.barcode,
        trade_name=data.trade_name,
        scientific_name=data.scientific_name,
        category=data.category,
        sale_price=data.sale_price,
        purchase_price=data.purchase_price,
        base_unit=data.base_unit,
        min_stock=data.min_stock,
        image_path=data.image_path
    )
    
    db.add(medicine)
    db.commit()
    db.refresh(medicine)
    
    # Create default units
    default_units = [
        Unit(
            id=uuid.uuid4(),
            medicine_id=medicine.id,
            unit_name=data.base_unit,
            conversion_factor=1.0,
            sale_price=data.sale_price
        )
    ]
    
    for unit in default_units:
        db.add(unit)
    
    db.commit()
    
    return {
        "success": True,
        "medicine_id": str(medicine.id),
        "message": "تم إضافة الدواء بنجاح"
    }


@router.get("/")
async def list_medicines(
    search: Optional[str] = Query(None, description="البحث بالاسم أو الباركود"),
    category: Optional[str] = Query(None, description="تصنيف الدواء"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all medicines with optional search and filter."""
    query = db.query(Medicine).filter(
        Medicine.pharmacy_id == current_user["pharmacy_id"]
    )
    
    # Apply search filter
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Medicine.trade_name.ilike(search_term)) |
            (Medicine.scientific_name.ilike(search_term)) |
            (Medicine.barcode.ilike(search_term))
        )
    
    # Apply category filter
    if category:
        query = query.filter(Medicine.category == category)
    
    # Order by trade name
    query = query.order_by(Medicine.trade_name)
    
    medicines = query.all()
    
    # Format response based on user role
    is_admin = current_user.get("role") == "admin"
    formatted_medicines = [
        format_medicine_response(med, db, is_admin) for med in medicines
    ]
    
    return {
        "medicines": formatted_medicines,
        "total": len(formatted_medicines)
    }


@router.get("/barcode/{barcode}", response_model=BarcodeSearchResponse)
async def search_by_barcode(
    barcode: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Search medicine by barcode."""
    medicine = db.query(Medicine).filter(
        Medicine.barcode == barcode,
        Medicine.pharmacy_id == current_user["pharmacy_id"]
    ).first()
    
    if not medicine:
        return {
            "found": False,
            "barcode": barcode
        }
    
    is_admin = current_user.get("role") == "admin"
    return {
        "found": True,
        "medicine": format_medicine_response(medicine, db, is_admin),
        "barcode": barcode
    }


@router.get("/{medicine_id}")
async def get_medicine(
    medicine_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a single medicine by ID."""
    from uuid import UUID
    
    try:
        med_uuid = UUID(medicine_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="معرف الدواء غير صالح")
    
    medicine = db.query(Medicine).filter(
        Medicine.id == med_uuid,
        Medicine.pharmacy_id == current_user["pharmacy_id"]
    ).first()
    
    if not medicine:
        raise HTTPException(status_code=404, detail="الدواء غير موجود")
    
    is_admin = current_user.get("role") == "admin"
    return format_medicine_response(medicine, db, is_admin)


@router.put("/{medicine_id}")
async def update_medicine(
    medicine_id: str,
    data: MedicineUpdate,
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update a medicine (Admin only)."""
    from uuid import UUID
    
    try:
        med_uuid = UUID(medicine_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="معرف الدواء غير صالح")
    
    medicine = db.query(Medicine).filter(
        Medicine.id == med_uuid,
        Medicine.pharmacy_id == current_user["pharmacy_id"]
    ).first()
    
    if not medicine:
        raise HTTPException(status_code=404, detail="الدواء غير موجود")
    
    # Check for duplicate barcode
    if data.barcode and data.barcode != medicine.barcode:
        existing = db.query(Medicine).filter(
            Medicine.barcode == data.barcode,
            Medicine.pharmacy_id == current_user["pharmacy_id"],
            Medicine.id != medicine.id
        ).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail="الباركود مستخدم مسبقاً لدواء آخر"
            )
    
    # Track price changes for audit log
    price_changed = False
    old_sale_price = None
    old_purchase_price = None
    new_sale_price = None
    new_purchase_price = None

    # Update fields
    if data.trade_name:
        medicine.trade_name = data.trade_name
    if data.scientific_name is not None:
        medicine.scientific_name = data.scientific_name
    if data.category:
        medicine.category = data.category
    if data.barcode is not None:
        medicine.barcode = data.barcode
    if data.sale_price:
        old_sale_price = float(medicine.sale_price)
        medicine.sale_price = data.sale_price
        new_sale_price = data.sale_price
        price_changed = True
        # Also sync the default unit's sale price
        default_unit = db.query(Unit).filter(
            Unit.medicine_id == medicine.id,
            Unit.unit_name == medicine.base_unit
        ).first()
        if default_unit:
            default_unit.sale_price = data.sale_price
    if data.purchase_price:
        old_purchase_price = float(medicine.purchase_price) if medicine.purchase_price else None
        medicine.purchase_price = data.purchase_price
        new_purchase_price = data.purchase_price
        price_changed = True
    if data.base_unit:
        medicine.base_unit = data.base_unit
    if data.min_stock is not None:
        medicine.min_stock = data.min_stock
    if data.image_path is not None:
        # Delete old image if exists
        if medicine.image_path:
            delete_image(medicine.image_path)
        medicine.image_path = data.image_path

    db.commit()
    db.refresh(medicine)

    # Audit log if price changed
    if price_changed:
        old_val_parts = []
        new_val_parts = []
        if old_sale_price is not None:
            old_val_parts.append(f"{old_sale_price} ج.س")
            new_val_parts.append(f"{new_sale_price} ج.س")
        if old_purchase_price is not None:
            old_val_parts.append(f"(شراء: {old_purchase_price} ج.س)")
            new_val_parts.append(f"(شراء: {new_purchase_price} ج.س)")
        log_action(
            db=db,
            pharmacy_id=current_user["pharmacy_id"],
            user_id=current_user["user_id"],
            user_name=current_user.get("full_name", current_user["username"]),
            action_type="price_update",
            description=f"تعديل سعر {medicine.trade_name}",
            old_value=", ".join(old_val_parts) if old_val_parts else None,
            new_value=", ".join(new_val_parts) if new_val_parts else None
        )
    
    return {
        "success": True,
        "message": "تم تحديث الدواء بنجاح"
    }


@router.delete("/{medicine_id}", response_model=MedicineDeleteResponse)
async def delete_medicine(
    medicine_id: str,
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Delete a medicine (Admin only). Checks for associated sales."""
    from uuid import UUID
    
    try:
        med_uuid = UUID(medicine_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="معرف الدواء غير صالح")
    
    medicine = db.query(Medicine).filter(
        Medicine.id == med_uuid,
        Medicine.pharmacy_id == current_user["pharmacy_id"]
    ).first()
    
    if not medicine:
        raise HTTPException(status_code=404, detail="الدواء غير موجود")
    
    # Check for associated sales
    from models import SaleItem
    sales_count = db.query(SaleItem).filter(
        SaleItem.medicine_id == medicine.id
    ).count()
    
    if sales_count > 0:
        return {
            "success": False,
            "message": "لا يمكن الحذف - يوجد مبيعات مرتبطة بهذا الدواء"
        }
    
    # Delete image if exists
    if medicine.image_path:
        delete_image(medicine.image_path)

    med_name = medicine.trade_name

    # Delete medicine (cascade will delete units and batches)
    db.delete(medicine)
    db.commit()

    # Audit log
    log_action(
        db=db,
        pharmacy_id=current_user["pharmacy_id"],
        user_id=current_user["user_id"],
        user_name=current_user.get("full_name", current_user["username"]),
        action_type="medicine_delete",
        description=f"حذف الدواء: {med_name}"
    )

    return {
        "success": True,
        "message": "تم حذف الدواء بنجاح"
    }


# ═══════════════════════════════════════════════════════════
# Units Management Endpoints
# ═══════════════════════════════════════════════════════════

@router.post("/{medicine_id}/units")
async def create_units(
    medicine_id: str,
    data: dict,
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Create units for a medicine (Admin only)."""
    from uuid import UUID
    
    try:
        med_uuid = UUID(medicine_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="معرف الدواء غير صالح")
    
    medicine = db.query(Medicine).filter(
        Medicine.id == med_uuid,
        Medicine.pharmacy_id == current_user["pharmacy_id"]
    ).first()
    
    if not medicine:
        raise HTTPException(status_code=404, detail="الدواء غير موجود")
    
    # Delete existing units
    db.query(Unit).filter(Unit.medicine_id == medicine.id).delete()
    
    # Create new units
    units_data = data.get("units", [])
    for unit_data in units_data:
        unit = Unit(
            id=uuid.uuid4(),
            medicine_id=medicine.id,
            unit_name=unit_data["unit_name"],
            conversion_factor=unit_data["conversion_factor"],
            sale_price=medicine.sale_price * unit_data["conversion_factor"]
        )
        db.add(unit)
    
    db.commit()
    
    return {
        "success": True,
        "message": "تم إضافة الوحدات بنجاح"
    }


# ═══════════════════════════════════════════════════════════
# Categories Endpoint
# ═══════════════════════════════════════════════════════════

@router.get("/categories/list")
async def get_categories(
    current_user: dict = Depends(get_current_user)
):
    """Get list of medicine categories."""
    return {
        "categories": MEDICINE_CATEGORIES
    }


# ✅ انتهى - medicines.py - المرحلة 3
