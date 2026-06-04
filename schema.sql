-- PharmaSUD - Database Schema
-- Stage 1 - Version 1.0.0
-- PostgreSQL 13+ Required

-- ============================================================
-- 1. PHARMACIES TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS pharmacies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_key VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    owner_name VARCHAR(100),
    phone VARCHAR(20),
    address TEXT,
    is_active BOOLEAN DEFAULT false,
    activated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE pharmacies IS 'Pharmacies registered in the system';
COMMENT ON COLUMN pharmacies.product_key IS 'Unique activation key for the pharmacy';
COMMENT ON COLUMN pharmacies.is_active IS 'Whether pharmacy is activated';

-- ============================================================
-- 2. USERS TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pharmacy_id UUID REFERENCES pharmacies(id) ON DELETE CASCADE,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) CHECK (role IN ('admin', 'employee')),
    full_name VARCHAR(100),
    phone VARCHAR(20),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE users IS 'System users (admins and employees)';
COMMENT ON COLUMN users.password_hash IS 'Bcrypt hashed password';
COMMENT ON COLUMN users.role IS 'User role: admin or employee';

-- Indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_users_pharmacy_id ON users(pharmacy_id);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- ============================================================
-- 3. MEDICINES TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS medicines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pharmacy_id UUID REFERENCES pharmacies(id) ON DELETE CASCADE,
    barcode VARCHAR(50),
    trade_name VARCHAR(100) NOT NULL,
    scientific_name VARCHAR(100),
    category VARCHAR(50),
    sale_price DECIMAL(10,2) NOT NULL,
    purchase_price DECIMAL(10,2),
    base_unit VARCHAR(20) DEFAULT 'strip',
    min_stock INTEGER DEFAULT 10,
    created_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE medicines IS 'Medicine products';
COMMENT ON COLUMN medicines.trade_name IS 'Commercial name of medicine';
COMMENT ON COLUMN medicines.scientific_name IS 'Generic name';

-- Indexes for search
CREATE INDEX IF NOT EXISTS idx_medicines_pharmacy_id ON medicines(pharmacy_id);
CREATE INDEX IF NOT EXISTS idx_medicines_barcode ON medicines(barcode);
CREATE INDEX IF NOT EXISTS idx_medicines_trade_name ON medicines(trade_name);

-- ============================================================
-- 4. UNITS TABLE (Measurement Units)
-- ============================================================

CREATE TABLE IF NOT EXISTS units (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    medicine_id UUID REFERENCES medicines(id) ON DELETE CASCADE,
    unit_name VARCHAR(20) NOT NULL,
    conversion_factor DECIMAL(10,3) NOT NULL,
    sale_price DECIMAL(10,2)
);

COMMENT ON TABLE units IS 'Measurement units: box/strip/tablet';
COMMENT ON COLUMN units.conversion_factor IS 'Conversion to base unit';

CREATE INDEX IF NOT EXISTS idx_units_medicine_id ON units(medicine_id);

-- ============================================================
-- 5. BATCHES TABLE (FEFO - First Expired First Out)
-- ============================================================

CREATE TABLE IF NOT EXISTS batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    medicine_id UUID REFERENCES medicines(id) ON DELETE CASCADE,
    batch_number VARCHAR(50),
    quantity INTEGER NOT NULL DEFAULT 0,
    expiry_date DATE NOT NULL,
    purchase_price DECIMAL(10,2),
    supplier_invoice VARCHAR(50),
    received_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT true
);

COMMENT ON TABLE batches IS 'Medicine batches/lots for FEFO tracking';
COMMENT ON COLUMN batches.batch_number IS 'Production batch number';
COMMENT ON COLUMN batches.expiry_date IS 'Expiration date';

-- Critical indexes for FEFO
CREATE INDEX IF NOT EXISTS idx_batches_medicine_id ON batches(medicine_id);
CREATE INDEX IF NOT EXISTS idx_batches_expiry_date ON batches(expiry_date);
CREATE INDEX IF NOT EXISTS idx_batches_active ON batches(is_active) WHERE is_active = true;

-- ============================================================
-- 6. SALES TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS sales (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pharmacy_id UUID REFERENCES pharmacies(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    invoice_number SERIAL,
    customer_name VARCHAR(100),
    total_amount DECIMAL(10,2) NOT NULL,
    payment_method VARCHAR(20) CHECK (
        payment_method IN ('cash', 'bankak', 'fory', 'transfer')
    ),
    created_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE sales IS 'Sales transactions';
COMMENT ON COLUMN sales.invoice_number IS 'Auto-incrementing invoice number';
COMMENT ON COLUMN sales.payment_method IS 'Payment method: cash, bankak, fory, or transfer';

CREATE INDEX IF NOT EXISTS idx_sales_pharmacy_id ON sales(pharmacy_id);
CREATE INDEX IF NOT EXISTS idx_sales_user_id ON sales(user_id);
CREATE INDEX IF NOT EXISTS idx_sales_created_at ON sales(created_at);

-- ============================================================
-- 7. SALE ITEMS TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS sale_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sale_id UUID REFERENCES sales(id) ON DELETE CASCADE,
    medicine_id UUID REFERENCES medicines(id) ON DELETE SET NULL,
    batch_id UUID REFERENCES batches(id) ON DELETE SET NULL,
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    total_price DECIMAL(10,2) NOT NULL
);

COMMENT ON TABLE sale_items IS 'Individual line items in sales';
COMMENT ON COLUMN sale_items.batch_id IS 'FEFO: Which batch was sold from';

CREATE INDEX IF NOT EXISTS idx_sale_items_sale_id ON sale_items(sale_id);
CREATE INDEX IF NOT EXISTS idx_sale_items_medicine_id ON sale_items(medicine_id);
CREATE INDEX IF NOT EXISTS idx_sale_items_batch_id ON sale_items(batch_id);

-- ============================================================
-- VERIFICATION QUERY
-- ============================================================

SELECT 'pharmacies' as table_name, COUNT(*) as row_count FROM pharmacies
UNION ALL
SELECT 'users', COUNT(*) FROM users
UNION ALL
SELECT 'medicines', COUNT(*) FROM medicines
UNION ALL
SELECT 'units', COUNT(*) FROM units
UNION ALL
SELECT 'batches', COUNT(*) FROM batches
UNION ALL
SELECT 'sales', COUNT(*) FROM sales
UNION ALL
SELECT 'sale_items', COUNT(*) FROM sale_items;

-- END - schema.sql - Stage 1
