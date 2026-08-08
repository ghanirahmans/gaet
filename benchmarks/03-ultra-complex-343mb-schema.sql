-- ═══════════════════════════════════════════════════════════════
-- gaet benchmark: HIGH COMPLEXITY schema (target ~400 MB)
-- Trades row count for schema complexity
-- ═══════════════════════════════════════════════════════════════

DROP TABLE IF EXISTS user_sessions CASCADE;
DROP TABLE IF EXISTS media CASCADE;
DROP TABLE IF EXISTS post_reactions CASCADE;
DROP TABLE IF EXISTS notifications CASCADE;
DROP TABLE IF EXISTS api_keys CASCADE;
DROP TABLE IF EXISTS rate_limits CASCADE;
DROP TABLE IF EXISTS feature_flags CASCADE;
DROP TABLE IF EXISTS org_members CASCADE;
DROP TABLE IF EXISTS organizations CASCADE;
DROP TABLE IF EXISTS invoices CASCADE;
DROP TABLE IF EXISTS post_tags CASCADE;
DROP TABLE IF EXISTS tags CASCADE;
DROP TABLE IF EXISTS comments CASCADE;
DROP TABLE IF EXISTS posts CASCADE;
DROP TABLE IF EXISTS categories CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TYPE IF EXISTS reaction_type CASCADE;
DROP TYPE IF EXISTS invoice_status CASCADE;
DROP TYPE IF EXISTS member_role CASCADE;
DROP TYPE IF EXISTS event_type CASCADE;
DROP TYPE IF EXISTS log_level CASCADE;
DROP TYPE IF EXISTS post_status CASCADE;
DROP MATERIALIZED VIEW IF EXISTS mv_post_stats;

-- ── Enums (5 types) ────────────────────────────
CREATE TYPE post_status   AS ENUM ('draft','published','archived','deleted','scheduled');
CREATE TYPE log_level     AS ENUM ('DEBUG','INFO','WARN','ERROR','FATAL','TRACE');
CREATE TYPE event_type    AS ENUM ('click','view','purchase','signup','login','logout','error','share');
CREATE TYPE member_role   AS ENUM ('owner','admin','member','viewer','billing');
CREATE TYPE invoice_status AS ENUM ('pending','paid','overdue','cancelled','refunded');
CREATE TYPE reaction_type AS ENUM ('like','love','laugh','surprise','sad','angry');

-- ── 1. Users ────────────────────────────────────
CREATE TABLE users (
    id            SERIAL PRIMARY KEY,
    username      VARCHAR(50) NOT NULL UNIQUE,
    email         VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    full_name     VARCHAR(150),
    bio           TEXT,
    avatar_url    VARCHAR(500),
    metadata      JSONB DEFAULT '{}',
    preferences   JSONB DEFAULT '{}',
    search_vector tsvector,
    is_active     BOOLEAN DEFAULT true,
    last_login_ip INET,
    created_at    TIMESTAMPTZ DEFAULT now(),
    updated_at    TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT chk_email CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);
CREATE INDEX idx_users_email_gin ON users(email);
CREATE INDEX idx_users_metadata  ON users USING gin(metadata);
CREATE INDEX idx_users_search    ON users USING gin(search_vector);
CREATE INDEX idx_users_created   ON users(created_at);
CREATE INDEX idx_users_active    ON users(is_active) WHERE is_active;
CREATE INDEX idx_users_brin      ON users USING brin(created_at);

-- ── 2. Categories (self-referencing hierarchy) ──
CREATE TABLE categories (
    id          SERIAL PRIMARY KEY,
    parent_id   INTEGER REFERENCES categories(id),
    name        VARCHAR(100) NOT NULL,
    slug        VARCHAR(120) NOT NULL UNIQUE,
    description TEXT,
    path        INTEGER[] DEFAULT '{}',
    depth       INTEGER DEFAULT 0,
    sort_order  INTEGER DEFAULT 0,
    is_active   BOOLEAN DEFAULT true,
    created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_cat_parent ON categories(parent_id);
CREATE INDEX idx_cat_path   ON categories USING gin(path);

-- ── 3. Posts ────────────────────────────────────
CREATE TABLE posts (
    id             SERIAL PRIMARY KEY,
    user_id        INTEGER NOT NULL REFERENCES users(id),
    category_id    INTEGER REFERENCES categories(id),
    title          VARCHAR(300) NOT NULL,
    slug           VARCHAR(350) NOT NULL UNIQUE,
    content        TEXT,
    excerpt        VARCHAR(500),
    tags_array     TEXT[] DEFAULT '{}',
    metadata       JSONB DEFAULT '{}',
    search_vector  tsvector,
    status         post_status DEFAULT 'published',
    view_count     INTEGER DEFAULT 0,
    reading_time   INTEGER DEFAULT 0,
    published_at   TIMESTAMPTZ DEFAULT now(),
    created_at     TIMESTAMPTZ DEFAULT now(),
    updated_at     TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT chk_title_len CHECK (char_length(title) BETWEEN 5 AND 300)
);
CREATE INDEX idx_posts_user       ON posts(user_id);
CREATE INDEX idx_posts_cat        ON posts(category_id);
CREATE INDEX idx_posts_status     ON posts(status);
CREATE INDEX idx_posts_published  ON posts(published_at DESC);
CREATE INDEX idx_posts_tags       ON posts USING gin(tags_array);
CREATE INDEX idx_posts_metadata   ON posts USING gin(metadata);
CREATE INDEX idx_posts_search     ON posts USING gin(search_vector);
CREATE INDEX idx_posts_brin       ON posts USING brin(created_at);

-- ── 4. Comments (threaded, self-ref, with full text) ────
CREATE TABLE comments (
    id            SERIAL PRIMARY KEY,
    post_id       INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    user_id       INTEGER REFERENCES users(id) ON DELETE SET NULL,
    parent_id     INTEGER REFERENCES comments(id) ON DELETE CASCADE,
    body          TEXT NOT NULL,
    search_vector tsvector,
    depth         INTEGER DEFAULT 0,
    path          INTEGER[] DEFAULT '{}',
    is_edited     BOOLEAN DEFAULT false,
    ip_address    INET,
    created_at    TIMESTAMPTZ DEFAULT now(),
    updated_at    TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_comments_post    ON comments(post_id);
CREATE INDEX idx_comments_user    ON comments(user_id);
CREATE INDEX idx_comments_parent  ON comments(parent_id);
CREATE INDEX idx_comments_search  ON comments USING gin(search_vector);
CREATE INDEX idx_comments_thread  ON comments(post_id, created_at);

-- ── 5. Tags ──────────────────────────────────────
CREATE TABLE tags (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    slug        VARCHAR(120) NOT NULL UNIQUE,
    description TEXT,
    color       VARCHAR(7) DEFAULT '#3b82f6',
    usage_count INTEGER DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_tags_usage ON tags(usage_count DESC);

-- ── 6. Post Tags (M:N) ──────────────────────────
CREATE TABLE post_tags (
    post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    tag_id  INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (post_id, tag_id)
);
CREATE INDEX idx_pt_tag ON post_tags(tag_id);

-- ── 7. Post Reactions (polymorphic-like) ────────
CREATE TABLE post_reactions (
    id         BIGSERIAL PRIMARY KEY,
    post_id    INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reaction   reaction_type NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (post_id, user_id)
);
CREATE INDEX idx_reactions_post ON post_reactions(post_id);
CREATE INDEX idx_reactions_user ON post_reactions(user_id);

-- ── 8. Media / Attachments ───────────────────────
CREATE TABLE media (
    id           SERIAL PRIMARY KEY,
    user_id      INTEGER REFERENCES users(id) ON DELETE SET NULL,
    post_id      INTEGER REFERENCES posts(id) ON DELETE CASCADE,
    filename     VARCHAR(500) NOT NULL,
    mime_type    VARCHAR(100),
    size_bytes   BIGINT,
    width        INTEGER,
    height       INTEGER,
    url          VARCHAR(1000),
    metadata     JSONB DEFAULT '{}',
    created_at   TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_media_user ON media(user_id);
CREATE INDEX idx_media_post ON media(post_id);

-- ── 9. Organizations ─────────────────────────────
CREATE TABLE organizations (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(150) NOT NULL,
    slug            VARCHAR(150) NOT NULL UNIQUE,
    billing_email   VARCHAR(120),
    plan            VARCHAR(20) DEFAULT 'free',
    settings        JSONB DEFAULT '{}',
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_org_slug ON organizations(slug);

-- ── 10. Organization Members ─────────────────────
CREATE TABLE org_members (
    org_id    INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role      member_role DEFAULT 'member',
    joined_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (org_id, user_id)
);
CREATE INDEX idx_members_user ON org_members(user_id);

-- ── 11. Invoices ──────────────────────────────────
CREATE TABLE invoices (
    id              SERIAL PRIMARY KEY,
    org_id          INTEGER REFERENCES organizations(id),
    number          VARCHAR(50) NOT NULL UNIQUE,
    amount          NUMERIC(12,2) NOT NULL,
    currency        VARCHAR(3) DEFAULT 'USD',
    status          invoice_status DEFAULT 'pending',
    line_items      JSONB DEFAULT '[]',
    due_date        DATE NOT NULL,
    paid_at         TIMESTAMPTZ,
    valid_period    DATERANGE,
    created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_invoices_org    ON invoices(org_id);
CREATE INDEX idx_invoices_status ON invoices(status);
CREATE INDEX idx_invoices_due    ON invoices(due_date);
CREATE INDEX idx_invoices_range  ON invoices USING gist(valid_period);

-- ── 12. Notifications ────────────────────────────
CREATE TABLE notifications (
    id          BIGSERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type        VARCHAR(50) NOT NULL,
    title       VARCHAR(200) NOT NULL,
    body        TEXT,
    payload     JSONB DEFAULT '{}',
    is_read     BOOLEAN DEFAULT false,
    read_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_notif_user     ON notifications(user_id);
CREATE INDEX idx_notif_unread   ON notifications(user_id) WHERE NOT is_read;
CREATE INDEX idx_notif_created  ON notifications(user_id, created_at);

-- ── 13. API Keys ──────────────────────────────────
CREATE TABLE api_keys (
    id           SERIAL PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name         VARCHAR(100) NOT NULL,
    key_prefix   VARCHAR(12) NOT NULL,
    key_hash     VARCHAR(128) NOT NULL,
    permissions  TEXT[] DEFAULT '{}',
    last_used_at TIMESTAMPTZ,
    expires_at   TIMESTAMPTZ,
    created_at   TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_apikeys_user   ON api_keys(user_id);
CREATE INDEX idx_apikeys_hash   ON api_keys(key_hash);

-- ── 14. Rate Limits ───────────────────────────────
CREATE TABLE rate_limits (
    id         BIGSERIAL PRIMARY KEY,
    key        VARCHAR(200) NOT NULL,
    time_window INT4RANGE NOT NULL,
    max_reqs   INTEGER NOT NULL,
    current    INTEGER DEFAULT 0,
    reset_at   TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_rl_key   ON rate_limits(key);
CREATE INDEX idx_rl_reset ON rate_limits(reset_at);

-- ── 15. Feature Flags ──────────────────────────────
CREATE TABLE feature_flags (
    id           SERIAL PRIMARY KEY,
    name         VARCHAR(100) NOT NULL UNIQUE,
    description  TEXT,
    enabled      BOOLEAN DEFAULT false,
    rules        JSONB DEFAULT '{}',
    rollout_pct  INTEGER DEFAULT 0 CHECK (rollout_pct BETWEEN 0 AND 100),
    created_at   TIMESTAMPTZ DEFAULT now(),
    updated_at   TIMESTAMPTZ DEFAULT now()
);

-- ── 16. User Sessions ─────────────────────────────
CREATE TABLE user_sessions (
    id            UUID DEFAULT gen_random_uuid(),
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash    VARCHAR(128) NOT NULL,
    ip_address    INET,
    user_agent    TEXT,
    device_info   JSONB DEFAULT '{}',
    is_active     BOOLEAN DEFAULT true,
    expires_at    TIMESTAMPTZ NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- Create partitions for user_sessions
CREATE TABLE user_sessions_2025h1 PARTITION OF user_sessions
    FOR VALUES FROM ('2025-01-01') TO ('2025-07-01');
CREATE TABLE user_sessions_2025h2 PARTITION OF user_sessions
    FOR VALUES FROM ('2025-07-01') TO ('2026-01-01');
CREATE TABLE user_sessions_default PARTITION OF user_sessions DEFAULT;

CREATE INDEX idx_sessions_user   ON user_sessions(user_id);
CREATE INDEX idx_sessions_token  ON user_sessions(token_hash);
CREATE INDEX idx_sessions_expiry ON user_sessions(expires_at);

-- ── Materialized View ─────────────────────────────
CREATE MATERIALIZED VIEW mv_post_stats AS
SELECT 
    p.id AS post_id,
    p.title,
    p.view_count,
    COUNT(DISTINCT c.id)  AS comment_count,
    COUNT(DISTINCT r.id)  AS reaction_count
FROM posts p
LEFT JOIN comments c      ON c.post_id = p.id
LEFT JOIN post_reactions r ON r.post_id = p.id
GROUP BY p.id, p.title, p.view_count;

CREATE UNIQUE INDEX idx_mv_stats_post ON mv_post_stats(post_id);

-- ── Trigger: auto-update search_vector ────────────
CREATE OR REPLACE FUNCTION trg_posts_search_update()
RETURNS trigger AS $$
BEGIN
    NEW.search_vector := to_tsvector('english',
        COALESCE(NEW.title, '') || ' ' || COALESCE(NEW.content, '')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_posts_search
    BEFORE INSERT OR UPDATE ON posts
    FOR EACH ROW EXECUTE FUNCTION trg_posts_search_update();

-- Same for comments
CREATE OR REPLACE FUNCTION trg_comments_search_update()
RETURNS trigger AS $$
BEGIN
    NEW.search_vector := to_tsvector('english', COALESCE(NEW.body, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_comments_search
    BEFORE INSERT OR UPDATE ON comments
    FOR EACH ROW EXECUTE FUNCTION trg_comments_search_update();
