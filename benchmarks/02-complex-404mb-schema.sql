-- ═══════════════════════════════════════════════════
-- gaet benchmark: complex realistic schema
-- ═══════════════════════════════════════════════════

-- Drop if exists (clean slate)
DROP TABLE IF EXISTS analytics_events CASCADE;
DROP TABLE IF EXISTS audit_logs CASCADE;
DROP TABLE IF EXISTS post_tags CASCADE;
DROP TABLE IF EXISTS tags CASCADE;
DROP TABLE IF EXISTS comments CASCADE;
DROP TABLE IF EXISTS posts CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TYPE IF EXISTS event_type CASCADE;
DROP TYPE IF EXISTS log_level CASCADE;
DROP TYPE IF EXISTS post_status CASCADE;

-- ── Enums ────────────────────────────────────────
CREATE TYPE post_status AS ENUM ('draft', 'published', 'archived', 'deleted');
CREATE TYPE log_level AS ENUM ('DEBUG', 'INFO', 'WARN', 'ERROR', 'FATAL');
CREATE TYPE event_type AS ENUM ('click', 'view', 'purchase', 'signup', 'login', 'logout', 'error');

-- ── Users ────────────────────────────────────────
CREATE TABLE users (
    id          SERIAL PRIMARY KEY,
    username    VARCHAR(50) NOT NULL UNIQUE,
    email       VARCHAR(120) NOT NULL UNIQUE,
    password    VARCHAR(256) NOT NULL,
    full_name   VARCHAR(150),
    bio         TEXT,
    avatar_url  VARCHAR(500),
    metadata    JSONB DEFAULT '{}'::jsonb,
    is_admin    BOOLEAN DEFAULT false,
    is_active   BOOLEAN DEFAULT true,
    last_login  TIMESTAMPTZ,
    login_count INTEGER DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_active ON users(is_active) WHERE is_active = true;
CREATE INDEX idx_users_metadata ON users USING gin(metadata);
CREATE INDEX idx_users_created ON users(created_at);

-- ── Posts ────────────────────────────────────────
CREATE TABLE posts (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    title           VARCHAR(300) NOT NULL,
    slug            VARCHAR(350) NOT NULL UNIQUE,
    content         TEXT,
    excerpt         VARCHAR(500),
    cover_image_url VARCHAR(500),
    tags_array      TEXT[] DEFAULT '{}',
    metadata        JSONB DEFAULT '{}'::jsonb,
    status          post_status DEFAULT 'published',
    view_count      INTEGER DEFAULT 0,
    like_count      INTEGER DEFAULT 0,
    published_at    TIMESTAMPTZ DEFAULT now(),
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_posts_user ON posts(user_id);
CREATE INDEX idx_posts_status ON posts(status);
CREATE INDEX idx_posts_published ON posts(published_at DESC);
CREATE INDEX idx_posts_slug ON posts(slug);
CREATE INDEX idx_posts_tags ON posts USING gin(tags_array);
CREATE INDEX idx_posts_metadata ON posts USING gin(metadata);

-- ── Comments ─────────────────────────────────────
CREATE TABLE comments (
    id          SERIAL PRIMARY KEY,
    post_id     INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    parent_id   INTEGER REFERENCES comments(id) ON DELETE CASCADE,
    body        TEXT NOT NULL,
    depth       INTEGER DEFAULT 0,
    path        INTEGER[] DEFAULT '{}',
    is_edited   BOOLEAN DEFAULT false,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_comments_post ON comments(post_id);
CREATE INDEX idx_comments_user ON comments(user_id);
CREATE INDEX idx_comments_parent ON comments(parent_id);
CREATE INDEX idx_comments_created ON comments(post_id, created_at);

-- ── Tags ─────────────────────────────────────────
CREATE TABLE tags (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    slug        VARCHAR(120) NOT NULL UNIQUE,
    description TEXT,
    color       VARCHAR(7) DEFAULT '#3b82f6',
    usage_count INTEGER DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_tags_slug ON tags(slug);
CREATE INDEX idx_tags_usage ON tags(usage_count DESC);

-- ── Post Tags (M:N) ─────────────────────────────
CREATE TABLE post_tags (
    post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    tag_id  INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (post_id, tag_id)
);

CREATE INDEX idx_post_tags_tag ON post_tags(tag_id);

-- ── Audit Logs ────────────────────────────────────
CREATE TABLE audit_logs (
    id          BIGSERIAL PRIMARY KEY,
    actor_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action      VARCHAR(100) NOT NULL,
    table_name  VARCHAR(100),
    record_id   INTEGER,
    old_data    JSONB,
    new_data    JSONB,
    ip_address  INET,
    user_agent  TEXT,
    level       log_level DEFAULT 'INFO',
    duration_ms INTEGER,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_audit_actor ON audit_logs(actor_id);
CREATE INDEX idx_audit_action ON audit_logs(action);
CREATE INDEX idx_audit_table ON audit_logs(table_name);
CREATE INDEX idx_audit_level ON audit_logs(level);
CREATE INDEX idx_audit_created ON audit_logs(created_at DESC);
CREATE INDEX idx_audit_old_data ON audit_logs USING gin(old_data);
CREATE INDEX idx_audit_new_data ON audit_logs USING gin(new_data);

-- ── Analytics Events ─────────────────────────────
CREATE TABLE analytics_events (
    id          BIGSERIAL PRIMARY KEY,
    user_id     INTEGER REFERENCES users(id) ON DELETE CASCADE,
    session_id  UUID DEFAULT gen_random_uuid(),
    event_type  event_type NOT NULL,
    page_url    VARCHAR(500),
    referrer    VARCHAR(500),
    ip_address  INET,
    country     VARCHAR(2),
    device      VARCHAR(50),
    browser     VARCHAR(100),
    os          VARCHAR(50),
    payload     JSONB DEFAULT '{}'::jsonb,
    duration_ms INTEGER,
    error_code  INTEGER,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_events_user ON analytics_events(user_id);
CREATE INDEX idx_events_type ON analytics_events(event_type);
CREATE INDEX idx_events_session ON analytics_events(session_id);
CREATE INDEX idx_events_created ON analytics_events(created_at DESC);
CREATE INDEX idx_events_country ON analytics_events(country);
CREATE INDEX idx_events_payload ON analytics_events USING gin(payload);
CREATE INDEX idx_events_composite ON analytics_events(user_id, event_type, created_at);
