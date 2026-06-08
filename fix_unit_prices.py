"""
Fix: Sync medicine unit prices with main medicine prices.
Run: python3 fix_unit_prices.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    print("❌ DATABASE_URL not found in .env")
    sys.exit(1)

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    # Find medicines where unit price != medicine price
    result = conn.execute(text("""
        SELECT m.id, m.trade_name, m.sale_price, m.base_unit,
               u.id as unit_id, u.sale_price as unit_price, u.unit_name
        FROM medicines m
        JOIN units u ON u.medicine_id = m.id AND u.unit_name = m.base_unit
        WHERE m.sale_price != u.sale_price
    """)).fetchall()
    
    print(f"Found {len(result)} mismatches:")
    for r in result:
        print(f"  - {r[1]}: medicine={r[2]}, unit={r[4]} ({r[5]})")
    
    if result:
        confirm = input("\nSync all unit prices to match medicine prices? (y/N): ")
        if confirm.lower() == 'y':
            for r in result:
                conn.execute(text("UPDATE units SET sale_price = :price WHERE id = :uid"),
                           {"price": r[2], "uid": r[4]})
            conn.commit()
            print(f"✅ Updated {len(result)} units")
        else:
            print("❌ Cancelled")
    else:
        print("✅ All prices are already in sync!")