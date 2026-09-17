-- =============================================================
-- sandbox/seed-data.sql
-- Industry-like sample schema for testing gaet backup/restore
-- Simulates a transactional e-commerce/order system
-- =============================================================

-- --- Drop if exists (idempotent) ---
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders      CASCADE;
DROP TABLE IF EXISTS payments    CASCADE;
DROP TABLE IF EXISTS products    CASCADE;
DROP TABLE IF EXISTS users       CASCADE;
DROP TABLE IF EXISTS audit_log   CASCADE;
DROP TABLE IF EXISTS system_config CASCADE;

-- --- Core transactional tables ---

-- system_config: minimal configuration (5 rows)
CREATE TABLE system_config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

INSERT INTO system_config (key, value) VALUES
    ('app_name',         'hindsight-pos'),
    ('version',          '1.2.3'),
    ('timezone',         'UTC'),
    ('currency',         'USD'),
    ('maintenance_mode', 'false');

-- users: customer accounts (1,000 rows)
CREATE TABLE users (
    id         SERIAL PRIMARY KEY,
    email      TEXT UNIQUE NOT NULL,
    name       TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

INSERT INTO users (email, name, created_at, updated_at)
SELECT
    'user_' || g || '@example.com' AS email,
    'Customer [' || g || ']'        AS name,
    NOW() - (g || ' seconds')::INTERVAL,
    NOW() - (g || ' seconds')::INTERVAL
FROM generate_series(1, 1000) AS g;

-- products: catalog items (500 rows)
CREATE TABLE products (
    id          SERIAL PRIMARY KEY,
    sku         TEXT UNIQUE NOT NULL,
    name        TEXT NOT NULL,
    price_cents INTEGER NOT NULL CHECK (price_cents > 0),
    stock_qty   INTEGER NOT NULL DEFAULT 0,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

INSERT INTO products (sku, name, price_cents, stock_qty, created_at)
SELECT
    'SKU-' || lpad(g::TEXT, 5, '0')    AS sku,
    'Product [' || g || ']'             AS name,
    (floor(random() * 9900 + 100)::INT * 100) AS price_cents,
    (floor(random() * 1000)::INT)      AS stock_qty,
    NOW() - (g || ' days')::INTERVAL
FROM generate_series(1, 500) AS g;

-- orders: main transaction table (3,000 rows)
CREATE TABLE orders (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    total_cents INTEGER NOT NULL CHECK (total_cents >= 0),
    status      TEXT NOT NULL CHECK (status IN ('pending', 'paid', 'shipped', 'cancelled')),
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

INSERT INTO orders (user_id, total_cents, status, created_at)
SELECT
    floor(random() * 1000 + 1)::INT   AS user_id,
    (floor(random() * 990000 + 1000)::INT) AS total_cents,
    CASE floor(random() * 4)
        WHEN 0 THEN 'pending'
        WHEN 1 THEN 'paid'
        WHEN 2 THEN 'shipped'
        ELSE 'cancelled'
    END AS status,
    NOW() - (g || ' hours')::INTERVAL
FROM generate_series(1, 3000) AS g;

-- payments: one-to-one with paid/shipped orders (3,000 rows)
CREATE TABLE payments (
    id             SERIAL PRIMARY KEY,
    order_id       INTEGER NOT NULL REFERENCES orders(id),
    amount_cents   INTEGER NOT NULL CHECK (amount_cents > 0),
    method         TEXT NOT NULL CHECK (method IN ('card', 'bank', 'ewallet', 'cash')),
    processed_at   TIMESTAMP NOT NULL DEFAULT NOW()
);

INSERT INTO payments (order_id, amount_cents, method, processed_at)
SELECT
    g            AS order_id,  -- 1:1 mapping for simplicity
    (floor(random() * 990000 + 1000)::INT) AS amount_cents,
    CASE floor(random() * 4)
        WHEN 0 THEN 'card'
        WHEN 1 THEN 'bank'
        WHEN 2 THEN 'ewallet'
        ELSE 'cash'
    END AS method,
    NOW() - (g || ' minutes')::INTERVAL
FROM generate_series(1, 3000) AS g;

-- order_items: line items per order (6,000 rows)
CREATE TABLE order_items (
    id         SERIAL PRIMARY KEY,
    order_id   INTEGER NOT NULL REFERENCES orders(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    qty        INTEGER NOT NULL CHECK (qty > 0),
    unit_price INTEGER NOT NULL CHECK (unit_price > 0)
);

INSERT INTO order_items (order_id, product_id, qty, unit_price)
SELECT
    floor(random() * 3000 + 1)::INT  AS order_id,
    floor(random() * 500 + 1)::INT   AS product_id,
    (floor(random() * 5 + 1)::INT)   AS qty,
    (floor(random() * 9900 + 100)::INT * 100) AS unit_price
FROM generate_series(1, 6000) AS g;

-- audit_log: event trail (2,000 rows)
CREATE TABLE audit_log (
    id          SERIAL PRIMARY KEY,
    event_type  TEXT NOT NULL CHECK (event_type IN ('order_created', 'payment_processed', 'order_shipped', 'order_cancelled')),
    order_id    INTEGER,
    user_id     INTEGER,
    message     TEXT,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

INSERT INTO audit_log (event_type, order_id, user_id, message, created_at)
SELECT
    CASE floor(random() * 4)
        WHEN 0 THEN 'order_created'
        WHEN 1 THEN 'payment_processed'
        WHEN 2 THEN 'order_shipped'
        ELSE 'order_cancelled'
    END AS event_type,
    floor(random() * 3000 + 1)::INT AS order_id,
    floor(random() * 1000 + 1)::INT AS user_id,
    'System event log entry [' || g || ']' AS message,
    NOW() - (g || ' minutes')::INTERVAL
FROM generate_series(1, 2000) AS g;

-- --- Indices for performance realism ---
CREATE INDEX idx_orders_user_id    ON orders(user_id);
CREATE INDEX idx_orders_status     ON orders(status);
CREATE INDEX idx_payments_order_id ON payments(order_id);
CREATE INDEX idx_order_items_order ON order_items(order_id);
CREATE INDEX idx_order_items_prod  ON order_items(product_id);
CREATE INDEX idx_audit_order_id    ON audit_log(order_id);
CREATE INDEX idx_audit_user_id     ON audit_log(user_id);
