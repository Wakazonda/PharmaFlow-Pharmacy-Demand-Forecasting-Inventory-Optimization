-- Enable UUID extension for generating UUIDs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table 1: Products (Master Catalog)
CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    category TEXT, -- Added category to match CSV data (e.g. 'Fever', 'Antibiotic')
    seasonal_tag TEXT, -- 'Winter', 'Summer', 'Viral', 'None'
    requires_prescription BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table 2: Batches (Inventory)
CREATE TABLE batches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    supplier_batch_number TEXT, -- External ID from supplier
    internal_batch_code TEXT NOT NULL, -- Our format: PRODUCT-YYYYMM-XXX
    manufacture_date DATE,
    expiry_date DATE NOT NULL,
    quantity_remaining INTEGER DEFAULT 0 CHECK (quantity_remaining >= 0),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table 3: Transactions (Sales History)
CREATE TABLE transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID NOT NULL REFERENCES products(id), -- Nullable? Preferably not, but for migration safety maybe. Let's keep strict.
    batch_id UUID REFERENCES batches(id), -- Nullable to support legacy data if batch info is missing
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    transaction_type TEXT DEFAULT 'SALE', -- 'SALE', 'RETURN', 'STOCK_IN'
    unit_price NUMERIC(10, 2), -- 10 digits, 2 decimal places
    total_amount NUMERIC(10, 2), -- Added for convenience (qty * price)
    transaction_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    customer_phone TEXT -- To track for safety alerts
);

-- Indexes for performance
CREATE INDEX idx_batches_product_id ON batches(product_id);
CREATE INDEX idx_batches_expiry_date ON batches(expiry_date);
CREATE INDEX idx_transactions_product_id ON transactions(product_id);
CREATE INDEX idx_transactions_batch_id ON transactions(batch_id);
CREATE INDEX idx_transactions_date ON transactions(transaction_date);
