-- SQLite schema for module toolkit index cache

CREATE TABLE IF NOT EXISTS items (
    resref TEXT PRIMARY KEY,
    name TEXT,
    base_item INTEGER,
    cost INTEGER,
    stack_size INTEGER,
    identified INTEGER,
    file_modified TEXT,
    content_hash TEXT
);

CREATE TABLE IF NOT EXISTS creatures (
    resref TEXT PRIMARY KEY,
    first_name TEXT,
    last_name TEXT,
    race INTEGER,
    appearance INTEGER,
    equipment_count INTEGER,
    inventory_count INTEGER,
    file_modified TEXT,
    content_hash TEXT
);

CREATE TABLE IF NOT EXISTS stores (
    resref TEXT PRIMARY KEY,
    name TEXT,
    markup INTEGER,
    markdown INTEGER,
    max_buy_price INTEGER,
    store_gold INTEGER,
    item_count INTEGER,
    file_modified TEXT,
    content_hash TEXT
);

CREATE TABLE IF NOT EXISTS areas (
    resref TEXT PRIMARY KEY,
    name TEXT,
    store_count INTEGER,
    creature_count INTEGER,
    file_modified TEXT,
    content_hash TEXT
);

-- Full-text search tables
CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(resref, name);
CREATE VIRTUAL TABLE IF NOT EXISTS creatures_fts USING fts5(resref, first_name, last_name);
CREATE VIRTUAL TABLE IF NOT EXISTS stores_fts USING fts5(resref, name);
CREATE VIRTUAL TABLE IF NOT EXISTS areas_fts USING fts5(resref, name);

-- Item reference tracking for fast lookup
-- reference_type: creature_inventory, creature_equipment, store_template, area_store
-- extra_data: JSON with slot_id, category_id, index, etc.
CREATE TABLE IF NOT EXISTS item_references (
    item_resref TEXT NOT NULL,
    reference_type TEXT NOT NULL,
    source_resref TEXT NOT NULL,
    extra_data TEXT,
    PRIMARY KEY (item_resref, reference_type, source_resref, extra_data)
);
CREATE INDEX IF NOT EXISTS idx_item_refs_item ON item_references(item_resref);
CREATE INDEX IF NOT EXISTS idx_item_refs_source ON item_references(source_resref);

-- Module metadata key-value store (fingerprints, settings, etc.)
CREATE TABLE IF NOT EXISTS module_metadata (
    key TEXT PRIMARY KEY,
    value TEXT
);
