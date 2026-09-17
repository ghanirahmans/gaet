-- =============================================================
-- sandbox/cleanup-schema.sql
-- Drop all test tables and reset schema to clean state
-- Idempotent: safe to run multiple times
-- =============================================================

-- Drop tables in reverse dependency order
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders      CASCADE;
DROP TABLE IF EXISTS payments    CASCADE;
DROP TABLE IF EXISTS products    CASCADE;
DROP TABLE IF EXISTS users       CASCADE;
DROP TABLE IF EXISTS audit_log   CASCADE;
DROP TABLE IF EXISTS system_config CASCADE;

-- Reset any remaining sequences from dropped tables
DROP SEQUENCE IF EXISTS order_items_id_seq;
DROP SEQUENCE IF EXISTS orders_id_seq;
DROP SEQUENCE IF EXISTS payments_id_seq;
DROP SEQUENCE IF EXISTS products_id_seq;
DROP SEQUENCE IF EXISTS users_id_seq;
DROP SEQUENCE IF EXISTS audit_log_id_seq;
DROP SEQUENCE IF EXISTS system_config_key_seq;
