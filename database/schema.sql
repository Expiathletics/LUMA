-- LUMA Database Schema
-- Funeral Home Form Automation Platform
-- Run this in Supabase SQL editor to set up your database

-- ─────────────────────────────────────────────
-- CUSTOMERS (one row per funeral home)
-- ─────────────────────────────────────────────
CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    city TEXT,
    state TEXT DEFAULT 'CA',
    license_number TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- CASES (one row per deceased person / funeral case)
-- ─────────────────────────────────────────────
CREATE TABLE cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID REFERENCES customers(id),
    
    -- SEED FIELDS (staff enters these - ~2 minutes)
    deceased_name TEXT,
    date_of_birth DATE,
    date_of_death DATE,
    ssn_last4 TEXT,
    address TEXT,
    city TEXT,
    state TEXT,
    zip TEXT,
    place_of_death TEXT,
    next_of_kin_name TEXT,
    next_of_kin_relationship TEXT,
    next_of_kin_phone TEXT,
    next_of_kin_address TEXT,
    disposition_method TEXT, -- burial, cremation, entombment
    
    -- PREDICTED FIELDS (LUMA fills these)
    gender TEXT,
    race TEXT,
    marital_status TEXT,
    occupation TEXT,
    education TEXT,
    birth_city TEXT,
    birth_state TEXT,
    birth_country TEXT,
    father_name TEXT,
    mother_maiden_name TEXT,
    veteran_status BOOLEAN DEFAULT FALSE,
    military_branch TEXT,
    military_service_dates TEXT,
    religion TEXT,
    cemetery_name TEXT,
    cemetery_address TEXT,
    funeral_director TEXT,
    funeral_home_license TEXT,
    service_date DATE,
    service_time TEXT,
    service_location TEXT,
    
    -- METADATA
    raw_doc_path TEXT,        -- path to original uploaded document
    processing_status TEXT DEFAULT 'pending', -- pending / processing / complete / error
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- PREDICTIONS (LUMA's field predictions with confidence)
-- ─────────────────────────────────────────────
CREATE TABLE predictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID REFERENCES cases(id),
    field_name TEXT NOT NULL,
    predicted_value TEXT,
    confidence FLOAT,           -- 0.0 to 1.0
    status TEXT DEFAULT 'pending', -- green (>90%) / yellow (70-90%) / red (<70%)
    was_corrected BOOLEAN DEFAULT FALSE,
    corrected_value TEXT,
    corrected_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- TRAINING DATA (corrections become training records)
-- ─────────────────────────────────────────────
CREATE TABLE training_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID REFERENCES customers(id),
    field_name TEXT NOT NULL,
    input_features JSONB,       -- the seed fields that were known
    correct_value TEXT,         -- what the correct answer was
    source TEXT DEFAULT 'correction', -- 'historical' or 'correction'
    created_at TIMESTAMP DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- MODEL VERSIONS (track retraining history)
-- ─────────────────────────────────────────────
CREATE TABLE model_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID REFERENCES customers(id),
    field_name TEXT,
    accuracy FLOAT,
    training_records_count INTEGER,
    model_path TEXT,
    deployed_at TIMESTAMP DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- INDEXES
-- ─────────────────────────────────────────────
CREATE INDEX idx_cases_customer ON cases(customer_id);
CREATE INDEX idx_cases_status ON cases(processing_status);
CREATE INDEX idx_predictions_case ON predictions(case_id);
CREATE INDEX idx_training_customer ON training_records(customer_id);
CREATE INDEX idx_training_field ON training_records(field_name);
