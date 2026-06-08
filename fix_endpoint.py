@app.get("/api/fix/unit-prices")
def fix_unit_prices(current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """Fix: Sync all unit prices with medicine prices."""
    mismatches = db.execute(text("""
        SELECT m.id, m.trade_name, m.sale_price, u.id as unit_id, u.sale_price as unit_price, u.unit_name
        FROM medicines m
        JOIN units u ON u.medicine_id = m.id AND u.unit_name = m.base_unit
        WHERE m.sale_price != u.sale_price
    """)).fetchall()
    
    fixed = 0
    for r in mismatches:
        db.execute(text("UPDATE units SET sale_price = :price WHERE id = :uid"),
                   {"price": float(r[2]), "uid": str(r[3])})
        fixed += 1
    
    if fixed > 0:
        db.commit()
        return {"fixed": fixed, "message": f"Done: {fixed} units fixed"}
    return {"fixed": 0, "message": "All prices already synced"}