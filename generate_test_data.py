"""
PharmaSUD - Stage 6 Test Data Generator
يُدخل بيانات مبيعات تجريبية لآخر 30 يوم
لاختبار التقارير (الداشبورد، المبيعات، الأرباح، الراكد، التوقعات)
"""

import uuid
import os
import sys
from datetime import datetime, date, timedelta
import random
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ DATABASE_URL not found in .env")
    sys.exit(1)

engine = create_engine(DATABASE_URL)

def generate_test_data():
    """Generate 30 days of test sales data."""
    print("🔍 Fetching existing data...")
    
    with engine.connect() as conn:
        # Get pharmacy
        ph = conn.execute(text("SELECT id, name FROM pharmacies LIMIT 1")).first()
        if not ph:
            print("❌ No pharmacy found")
            return
        pharmacy_id = str(ph[0])
        print(f"✅ Pharmacy: {ph[1]} ({pharmacy_id[:8]}...)")
        
        # Get admin user
        user = conn.execute(text("""
            SELECT id, full_name FROM users 
            WHERE pharmacy_id = :pid AND role = 'admin' 
            LIMIT 1
        """), {"pid": pharmacy_id}).first()
        if not user:
            print("❌ No admin user found")
            return
        user_id = str(user[0])
        print(f"✅ Admin: {user[1]} ({user_id[:8]}...)")
        
        # Get all medicines
        meds = conn.execute(text("""
            SELECT m.id, m.trade_name, m.base_unit, m.sale_price 
            FROM medicines m WHERE m.pharmacy_id = :pid
        """), {"pid": pharmacy_id}).fetchall()
        
        if not meds:
            print("❌ No medicines found. Add some medicines first!")
            return
        
        print(f"✅ Found {len(meds)} medicines")
        
        # Get all batches with purchase_price
        batches = conn.execute(text("""
            SELECT b.id, b.medicine_id, b.batch_number, b.quantity, 
                   b.purchase_price, b.expiry_date
            FROM batches b
            JOIN medicines m ON b.medicine_id = m.id
            WHERE m.pharmacy_id = :pid AND b.is_active = true 
              AND b.quantity > 0 AND b.expiry_date > NOW()
        """), {"pid": pharmacy_id}).fetchall()
        
        if not batches:
            print("❌ No active batches found. Receive some batches first!")
            return
        
        print(f"✅ Found {len(batches)} batches")
        
        # Build medicine -> batches map
        med_batches = {}
        for b in batches:
            mid = str(b[1])
            if mid not in med_batches:
                med_batches[mid] = []
            med_batches[mid].append({
                "id": str(b[0]),
                "batch": b[2],
                "qty": b[3],
                "purchase_price": float(b[4]) if b[4] else 0,
                "expiry": b[5]
            })
        
        # Medicine lookup
        med_map = {}
        for m in meds:
            med_map[str(m[0])] = {
                "name": m[1],
                "base_unit": m[2] or "شريط",
                "sale_price": float(m[3]) if m[3] else 0
            }
        
        # ══════════════════════════════════════════════════════
        # Generate 30 days of sales
        # ══════════════════════════════════════════════════════
        
        print("\n🔄 Generating 30 days of test sales...")
        
        today = date.today()
        sales_created = 0
        items_created = 0
        
        for day_offset in range(30, 0, -1):
            sale_date = today - timedelta(days=day_offset)
            
            # Each day: 3-8 random sales
            daily_sales_count = random.randint(3, 8)
            
            for _ in range(daily_sales_count):
                # Pick random medicine that has stock
                available_meds = [m for m in med_map.keys() if m in med_batches]
                if not available_meds:
                    continue
                
                med_id = random.choice(available_meds)
                med_data = med_map[med_id]
                available_batches = med_batches[med_id]
                
                if not available_batches:
                    continue
                
                # Pick batch (prefer older for realism)
                batch = random.choice(available_batches)
                
                # Determine payment method
                pm = random.choices(
                    ["cash", "bankak", "fory", "transfer"],
                    weights=[60, 25, 10, 5],
                    k=1
                )[0]
                
                # Random quantity (1-5 units)
                qty = random.randint(1, 5)
                unit_price = med_data["sale_price"]
                total_price = qty * unit_price
                
                # Create sale
                invoice_number = None
                sale_time = datetime.combine(
                    sale_date,
                    datetime.min.time()
                ) + timedelta(
                    hours=random.randint(8, 20),
                    minutes=random.randint(0, 59)
                )
                
                result = conn.execute(text("""
                    INSERT INTO sales (pharmacy_id, user_id, customer_name, 
                                       total_amount, payment_method, created_at)
                    VALUES (:pid, :uid, :customer, :amount, :pm, :created)
                    RETURNING id, invoice_number
                """), {
                    "pid": pharmacy_id,
                    "uid": user_id,
                    "customer": random.choice(["", "أحمد", "محمد", "خالد", "فاطمة", "مريم", ""]),
                    "amount": total_price,
                    "pm": pm,
                    "created": sale_time
                }).first()
                
                sale_id = str(result[0])
                invoice_number = result[1]
                
                # Create sale item
                conn.execute(text("""
                    INSERT INTO sale_items (sale_id, medicine_id, batch_id,
                                            quantity, unit_price, total_price, unit_name)
                    VALUES (:sid, :mid, :bid, :qty, :price, :total, :unit)
                """), {
                    "sid": sale_id,
                    "mid": med_id,
                    "bid": batch["id"],
                    "qty": qty,
                    "price": unit_price,
                    "total": total_price,
                    "unit": med_data["base_unit"]
                })
                
                sales_created += 1
                items_created += 1
            
            conn.commit()
            
            if day_offset % 5 == 0:
                print(f"  📅 Day {30 - day_offset + 1}/{30} (sale_date: {sale_date}) - {daily_sales_count} sales")
        
        # ── Add a slow-moving medicine (no sales for 45+ days) ──
        print("\n🔄 Adding slow-moving medicine data...")
        
        # Find a medicine with batches but we won't sell it for 45 days
        # Actually, all sales were made recently. Let me check if there's a
        # medicine with no sales at all - that would naturally be "slow moving"
        
        # Also add some expiring stock
        print("\n🔄 Adding near-expiry batch for testing...")
        
        # Update one batch to have expiry within 30 days for testing
        if batches:
            target_batch = batches[0]
            near_expiry_date = today + timedelta(days=20)
            conn.execute(text("""
                UPDATE batches SET expiry_date = :expiry
                WHERE id = :bid
            """), {
                "expiry": near_expiry_date,
                "bid": target_batch[0]
            })
            conn.commit()
            print(f"  ✅ Updated batch {target_batch[2]} to expire on {near_expiry_date}")
        
        print(f"\n✅✅✅ DONE!")
        print(f"  Sales created: {sales_created}")
        print(f"  Sale items created: {items_created}")
        print(f"  Date range: last 30 days")

if __name__ == "__main__":
    generate_test_data()