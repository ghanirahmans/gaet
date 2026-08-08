-- ═══════════════════════════════════════════════════════════════
-- 03-ultra-complex-343mb-data.sql
-- Dataset untuk benchmark ultra-complex (16 tables + partitions + MV)
--
-- Usage:
--   createdb gaetlocaltest
--   psql -d gaetlocaltest -f 03-ultra-complex-343mb-schema.sql
--   psql -d gaetlocaltest -f 03-ultra-complex-343mb-data.sql
--   psql -d gaetlocaltest -c "REFRESH MATERIALIZED VIEW mv_post_stats;"
-- ═══════════════════════════════════════════════════════════════

-- ── 1. Users: 2,000 (tsvector + JSONB + INET + CHECK constraint) ──
INSERT INTO users (username, email, password_hash, full_name, bio, metadata, preferences, search_vector, is_active, last_login_ip, created_at)
SELECT 'u'||i, 'u'||i||'@co.io', '$2b$12$x', initcap('user '||i),
    'Senior engineer '||(i%10+5)||'y in '||CASE i%5 WHEN 0 THEN 'distributed systems.' WHEN 1 THEN 'full-stack.' WHEN 2 THEN 'data engineering.' WHEN 3 THEN 'ML infra.' ELSE 'security.' END,
    jsonb_build_object('role',CASE i%6 WHEN 0 THEN 'admin' WHEN 1 THEN 'moderator' ELSE 'user' END,'plan',CASE i%3 WHEN 0 THEN 'pro' WHEN 1 THEN 'team' ELSE 'free' END),
    jsonb_build_object('theme',CASE i%2 WHEN 0 THEN 'dark' ELSE 'light' END,'lang',CASE i%3 WHEN 0 THEN 'en' WHEN 1 THEN 'id' ELSE 'ja' END),
    to_tsvector('english',initcap('user '||i)),
    i%20<>0,
    ('192.168.'||(i%255+1)::text||'.'||(i%255+1)::text)::inet,
    now()-random()*interval '365d'
FROM generate_series(1,2000) s(i);

-- ── 2. Categories: 50 (self-referencing hierarchy, array path) ──
INSERT INTO categories (parent_id, name, slug, description, path, depth, sort_order)
SELECT CASE WHEN i<=5 THEN NULL WHEN i<=15 THEN ((i-6)%5+1) WHEN i<=30 THEN ((i-16)%10+6) ELSE ((i-31)%15+16) END,
    CASE i WHEN 1 THEN 'Technology' WHEN 2 THEN 'Business' WHEN 3 THEN 'Design' WHEN 4 THEN 'Science' WHEN 5 THEN 'Lifestyle' ELSE 'Subcat '||i END,
    CASE i WHEN 1 THEN 'tech' WHEN 2 THEN 'biz' WHEN 3 THEN 'design' WHEN 4 THEN 'science' WHEN 5 THEN 'life' ELSE 'subcat-'||i END,
    'Category '||i,
    CASE WHEN i<=5 THEN ARRAY[i] WHEN i<=15 THEN ARRAY[((i-6)%5+1),i] ELSE ARRAY[((i-16)%10+6),i] END,
    CASE WHEN i<=5 THEN 1 WHEN i<=15 THEN 2 ELSE 3 END, i
FROM generate_series(1,50) s(i);

-- ── 3. Posts: 45,000 (tsvector trigger, GIN, BRIN, CHECK) ──
INSERT INTO posts (user_id, category_id, title, slug, content, excerpt, tags_array, metadata, status, view_count, reading_time, published_at, created_at)
SELECT (random()*1999+1)::int, (random()*49+1)::int,
    'Post '||i||' — '||CASE i%10 WHEN 0 THEN 'PostgreSQL Query Planner Deep Dive' WHEN 1 THEN 'Event-Driven Systems at Scale' WHEN 2 THEN 'Database Indexing Complete Guide' WHEN 3 THEN 'Kubernetes Stateful Workloads' WHEN 4 THEN 'Clean Architecture in Go' WHEN 5 THEN 'Understanding WAL Internals' WHEN 6 THEN 'Rust Memory Model Explained' WHEN 7 THEN 'Observability: Logs to Traces' WHEN 8 THEN 'API Design Best Practices 2025' ELSE 'Scaling Postgres to 10M QPS' END,
    'p'||i||'-'||md5(i::text),
    repeat('Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum. ', CASE i%4 WHEN 0 THEN 6 WHEN 1 THEN 4 WHEN 2 THEN 8 ELSE 5 END),
    'Excerpt for post '||i,
    ARRAY['tag_'||((i%100)+1)::text,'tag_'||(((i+17)%100)+1)::text,'tag_'||(((i+53)%100)+1)::text],
    jsonb_build_object('read_time',(random()*15+3)::int,'format',CASE i%4 WHEN 0 THEN 'article' WHEN 1 THEN 'tutorial' WHEN 2 THEN 'guide' ELSE 'essay' END),
    CASE i%10 WHEN 0 THEN 'draft'::post_status WHEN 1 THEN 'archived'::post_status WHEN 2 THEN 'deleted'::post_status WHEN 3 THEN 'scheduled'::post_status ELSE 'published'::post_status END,
    (random()*50000)::int, (random()*20+2)::int, now()-random()*interval '730d', now()-random()*interval '730d'
FROM generate_series(1,20000) s(i);

INSERT INTO posts (user_id, category_id, title, slug, content, excerpt, tags_array, metadata, status, view_count, reading_time, published_at, created_at)
SELECT (random()*1999+1)::int, (random()*49+1)::int,
    'Extra Post '||i||' — '||CASE i%10 WHEN 0 THEN 'Advanced PostgreSQL Replication Setup' WHEN 1 THEN 'Microservices Anti-Patterns to Avoid' WHEN 2 THEN 'GraphQL vs REST Performance' WHEN 3 THEN 'Terraform Best Practices 2026' WHEN 4 THEN 'Monitoring Distributed Systems' WHEN 5 THEN 'Database Sharding Strategies' WHEN 6 THEN 'WebAssembly in Production' WHEN 7 THEN 'CI/CD Pipeline Optimization' WHEN 8 THEN 'Service Mesh Deep Dive' ELSE 'Zero-Trust Architecture' END,
    'xp'||i||'-'||md5(i::text),
    repeat('Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium doloremque laudantium, totam rem aperiam, eaque ipsa quae ab illo inventore veritatis et quasi architecto beatae vitae dicta sunt explicabo. Nemo enim ipsam voluptatem quia voluptas sit aspernatur aut odit aut fugit, sed quia consequuntur magni dolores eos qui ratione voluptatem sequi nesciunt. ', CASE i%4 WHEN 0 THEN 6 WHEN 1 THEN 4 WHEN 2 THEN 8 ELSE 5 END),
    'Extra excerpt '||i,
    ARRAY['tag_'||((i%100)+1)::text,'tag_'||(((i+31)%100)+1)::text,'tag_'||(((i+67)%100)+1)::text],
    jsonb_build_object('series',CASE i%3 WHEN 0 THEN 'advanced' WHEN 1 THEN 'intermediate' ELSE 'beginner' END),
    CASE i%10 WHEN 0 THEN 'draft'::post_status WHEN 1 THEN 'archived'::post_status ELSE 'published'::post_status END,
    (random()*30000)::int, (random()*18+2)::int, now()-random()*interval '730d', now()-random()*interval '730d'
FROM generate_series(1,25000) s(i);

-- ── 4. Tags: 100 ────────────────────────────────────────
INSERT INTO tags (name,slug,description,color,usage_count)
SELECT 'tag_'||i,'tag-'||i,'Desc '||i,
    CASE i%8 WHEN 0 THEN '#ef4444' WHEN 1 THEN '#f97316' WHEN 2 THEN '#eab308' WHEN 3 THEN '#22c55e'
             WHEN 4 THEN '#06b6d4' WHEN 5 THEN '#3b82f6' WHEN 6 THEN '#8b5cf6' ELSE '#ec4899' END,
    (random()*5000)::int
FROM generate_series(1,100) s(i);

-- ── 5. Post Tags (M:N) ────────────────────────────────────
INSERT INTO post_tags (post_id, tag_id)
SELECT p.id,t.id FROM posts p JOIN tags t ON t.id IN (((p.id%100)+1),(((p.id+17)%100)+1),(((p.id+53)%100)+1))
WHERE p.status='published';

-- ── 6. Comments: 250,000 (tsvector + self-ref FK + INET) ──
INSERT INTO comments (post_id, user_id, body, depth, ip_address, created_at)
SELECT (random()*19999+1)::int,
    CASE WHEN random()<0.08 THEN NULL ELSE (random()*1999+1)::int END,
    repeat(CASE (i%6) WHEN 0 THEN 'Excellent deep dive! Very helpful. ' WHEN 1 THEN 'Have you benchmarked against BRIN? ' WHEN 2 THEN 'This saved our deployment! ' WHEN 3 THEN 'Does this work with logical replication? ' WHEN 4 THEN '35% latency reduction — confirmed! ' ELSE 'Well researched piece. ' END,2),
    CASE WHEN random()<0.6 THEN 1 ELSE 2 END,
    ('10.0.'||(i%255+1)::text||'.'||(i%255+1)::text)::inet,
    now()-random()*interval '730d'
FROM generate_series(1,100000) s(i);

INSERT INTO comments (post_id, user_id, body, depth, ip_address, created_at)
SELECT (random()*44999+1)::int,
    CASE WHEN random()<0.08 THEN NULL ELSE (random()*1999+1)::int END,
    repeat(CASE (i%6) WHEN 0 THEN 'Great addition! Real clarifies edge cases. ' WHEN 1 THEN 'We saw similar benchmark results. ' WHEN 2 THEN 'Can you elaborate on partitioning? ' WHEN 3 THEN 'Required reading for every backend dev. ' WHEN 4 THEN 'One caveat with connection pooling. ' ELSE 'Bookmarked for architecture review. ' END,2),
    CASE WHEN random()<0.6 THEN 1 ELSE 2 END,
    ('10.0.'||(i%255+1)::text||'.'||(i%255+1)::text)::inet,
    now()-random()*interval '730d'
FROM generate_series(1,150000) s(i);

-- ── 7. Post Reactions: ~400,000 (enum + unique constraint) ──
INSERT INTO post_reactions (post_id, user_id, reaction, created_at)
SELECT (random()*19999+1)::int, (random()*1999+1)::int,
    CASE (i%6) WHEN 0 THEN 'like'::reaction_type WHEN 1 THEN 'love'::reaction_type WHEN 2 THEN 'laugh'::reaction_type WHEN 3 THEN 'surprise'::reaction_type WHEN 4 THEN 'sad'::reaction_type ELSE 'angry'::reaction_type END,
    now()-random()*interval '365d'
FROM generate_series(1,200000) s(i) ON CONFLICT DO NOTHING;

INSERT INTO post_reactions (post_id, user_id, reaction, created_at)
SELECT (random()*44999+1)::int, (random()*1999+1)::int,
    CASE (i%6) WHEN 0 THEN 'like'::reaction_type WHEN 1 THEN 'love'::reaction_type WHEN 2 THEN 'laugh'::reaction_type WHEN 3 THEN 'surprise'::reaction_type WHEN 4 THEN 'sad'::reaction_type ELSE 'angry'::reaction_type END,
    now()-random()*interval '365d'
FROM generate_series(1,200000) s(i) ON CONFLICT DO NOTHING;

-- ── 8. Media: 10,000 ───────────────────────────────────────
INSERT INTO media (user_id, post_id, filename, mime_type, size_bytes, width, height, metadata, created_at)
SELECT (random()*1999+1)::int, CASE WHEN random()<0.2 THEN NULL ELSE (random()*19999+1)::int END,
    'file_'||i||CASE i%3 WHEN 0 THEN '.jpg' WHEN 1 THEN '.png' ELSE '.mp4' END,
    CASE i%3 WHEN 0 THEN 'image/jpeg' WHEN 1 THEN 'image/png' ELSE 'video/mp4' END,
    (random()*5000000+10000)::bigint, (random()*4000+100)::int, (random()*3000+100)::int,
    jsonb_build_object('alt','Media '||i,'cdn','https://cdn.example.com/m/'||i),
    now()-random()*interval '365d'
FROM generate_series(1,10000) s(i);

-- ── 9. Organizations: 50 ───────────────────────────────────
INSERT INTO organizations (name, slug, billing_email, plan, settings, is_active, created_at)
SELECT 'Org '||initcap(CASE i%12 WHEN 0 THEN 'acme' WHEN 1 THEN 'globex' WHEN 2 THEN 'initech' WHEN 3 THEN 'umbrella' WHEN 4 THEN 'stark' WHEN 5 THEN 'wayne' WHEN 6 THEN 'cyberdyne' WHEN 7 THEN 'massive' WHEN 8 THEN 'hooli' WHEN 9 THEN 'piedpiper' WHEN 10 THEN 'raviga' ELSE 'tesla' END)||' '||i,
    'org-'||i, 'b'||i||'@org.io',
    CASE i%3 WHEN 0 THEN 'enterprise' WHEN 1 THEN 'pro' ELSE 'free' END,
    jsonb_build_object('seats',(i%5+1)*10), i%10<>0, now()-random()*interval '730d'
FROM generate_series(1,50) s(i);

-- ── 10. Org Members: 5,000 ─────────────────────────────────
INSERT INTO org_members (org_id, user_id, role, joined_at)
SELECT (random()*49+1)::int, (random()*1999+1)::int,
    CASE (i%5) WHEN 0 THEN 'owner'::member_role WHEN 1 THEN 'admin'::member_role WHEN 2 THEN 'member'::member_role WHEN 3 THEN 'viewer'::member_role ELSE 'billing'::member_role END,
    now()-random()*interval '365d'
FROM generate_series(1,5000) s(i) ON CONFLICT DO NOTHING;

-- ── 11. Invoices: 10,000 (NUMERIC, DATERANGE, GiST) ────────
INSERT INTO invoices (org_id, number, amount, currency, status, line_items, due_date, valid_period, created_at)
SELECT (random()*49+1)::int, 'INV-'||to_char(now()-random()*interval '365d','YYYYMMDD')||'-'||lpad(i::text,6,'0'),
    (random()*10000+50)::numeric(12,2),
    CASE i%4 WHEN 0 THEN 'USD' WHEN 1 THEN 'EUR' WHEN 2 THEN 'IDR' ELSE 'GBP' END,
    CASE i%10 WHEN 0 THEN 'pending'::invoice_status WHEN 1 THEN 'paid'::invoice_status WHEN 2 THEN 'overdue'::invoice_status WHEN 3 THEN 'cancelled'::invoice_status ELSE 'paid'::invoice_status END,
    jsonb_build_array(jsonb_build_object('desc','Seat','qty',i%5+1,'price',random()*100+10)),
    (now()-random()*interval '365d')::date,
    daterange((now()-random()*interval '365d')::date, (now()+random()*interval '365d')::date),
    now()-random()*interval '365d'
FROM generate_series(1,10000) s(i);

-- ── 12. Notifications: 100,000 ─────────────────────────────
INSERT INTO notifications (user_id, type, title, body, payload, is_read, created_at)
SELECT (random()*1999+1)::int,
    CASE i%6 WHEN 0 THEN 'comment' WHEN 1 THEN 'reaction' WHEN 2 THEN 'mention' WHEN 3 THEN 'invite' WHEN 4 THEN 'billing' ELSE 'system' END,
    CASE i%6 WHEN 0 THEN 'New comment' WHEN 1 THEN 'New reaction' WHEN 2 THEN 'Mentioned' WHEN 3 THEN 'Team invite' WHEN 4 THEN 'Invoice' ELSE 'System update' END,
    'Body '||i, jsonb_build_object('link','/p/'||(i%20000+1)), random()<0.3, now()-random()*interval '180d'
FROM generate_series(1,100000) s(i);

-- ── 13. API Keys: 5,000 ────────────────────────────────────
INSERT INTO api_keys (user_id, name, key_prefix, key_hash, permissions, last_used_at, expires_at, created_at)
SELECT (random()*1999+1)::int, 'key_'||i, 'gaet_'||lpad(i::text,6,'0'), md5(i::text||random()::text),
    ARRAY['read','write',CASE WHEN i%3=0 THEN 'admin' ELSE NULL END, CASE WHEN i%5=0 THEN 'export' ELSE NULL END],
    CASE WHEN random()<0.3 THEN NULL ELSE now()-random()*interval '90d' END,
    now()+random()*interval '365d', now()-random()*interval '180d'
FROM generate_series(1,5000) s(i);

-- ── 14. Rate Limits: 5,000 (INT4RANGE) ─────────────────────
INSERT INTO rate_limits (key, time_window, max_reqs, current, reset_at, created_at)
SELECT 'ip:'||CASE i%5 WHEN 0 THEN '8.8.8.'||(i%255)::text WHEN 1 THEN '1.1.1.'||(i%255)::text WHEN 2 THEN '192.168.1.'||(i%255)::text WHEN 3 THEN '10.0.0.'||(i%255)::text ELSE '172.16.0.'||(i%255)::text END,
    int4range(0,(i%100+100)), (i%50+10)*10, (random()*100)::int, now()+random()*interval '1h', now()-random()*interval '7d'
FROM generate_series(1,5000) s(i);

-- ── 15. Feature Flags: 50 ──────────────────────────────────
INSERT INTO feature_flags (name, description, enabled, rules, rollout_pct, created_at)
SELECT 'feat_'||CASE i%8 WHEN 0 THEN 'dark_mode' WHEN 1 THEN 'new_editor' WHEN 2 THEN 'beta_search' WHEN 3 THEN 'export_csv' WHEN 4 THEN 'api_v2' WHEN 5 THEN 'real_time' WHEN 6 THEN 'ai_assistant' ELSE 'sso_login' END||'_'||i,
    'Desc '||i, i%3<>0,
    jsonb_build_object('target',CASE i%2 WHEN 0 THEN 'all' ELSE 'premium' END),
    (i%5)*20, now()-random()*interval '180d'
FROM generate_series(1,50) s(i);

-- ── 16. User Sessions: 80,000 (PARTITIONED table!) ─────────
INSERT INTO user_sessions (user_id, token_hash, ip_address, user_agent, device_info, is_active, expires_at, created_at)
SELECT (random()*1999+1)::int, md5('s'||i||random()::text),
    ('192.168.'||(i%255+1)::text||'.'||(i%255+1)::text)::inet,
    'Mozilla/5.0 Chrome/'||(110+i%20)::text,
    jsonb_build_object('device',CASE i%3 WHEN 0 THEN 'desktop' WHEN 1 THEN 'mobile' ELSE 'tablet' END),
    random()<0.6, now()+random()*interval '30d', now()-random()*interval '365d'
FROM generate_series(1,80000) s(i);

-- ── Final size check ───────────────────────────────────────
REFRESH MATERIALIZED VIEW mv_post_stats;
SELECT 'ULTRACOMPLEX DATASET READY' AS info;
SELECT pg_size_pretty(pg_database_size(current_database())) AS total;