-- ═══════════════════════════════════════════════════════════════
-- 02-complex-404mb-data.sql
-- Dataset untuk benchmark kompleks (7 tables, ~750K rows, 404 MB)
--
-- Usage:
--   createdb gaetlocaltest
--   psql -d gaetlocaltest -f 02-complex-404mb-schema.sql
--   psql -d gaetlocaltest -f 02-complex-404mb-data.sql
-- ═══════════════════════════════════════════════════════════════

-- ── 1. Users: 5,000 ─────────────────────────────────────
INSERT INTO users (username, email, password, full_name, bio, metadata, is_admin, login_count, last_login, created_at)
SELECT 'u_'||i, 'u'||i||'@c.io', '$2b$12$'||repeat('x',53),
    initcap('user '||i),
    'Bio user '||i||' — senior engineer with distributed systems expertise. ',
    jsonb_build_object('role',CASE i%6 WHEN 0 THEN 'admin' WHEN 1 THEN 'moderator' ELSE 'user' END,
        'plan', CASE i%3 WHEN 0 THEN 'pro' WHEN 1 THEN 'team' ELSE 'free' END,
        'prefs', jsonb_build_object('tz', CASE i%4 WHEN 0 THEN 'Asia/Jakarta' WHEN 1 THEN 'America/NYC' WHEN 2 THEN 'Europe/London' ELSE 'Asia/Tokyo' END,
            'lang', CASE i%3 WHEN 0 THEN 'en' WHEN 1 THEN 'id' ELSE 'ja' END)),
    i%30=0, (random()*500)::int, now()-random()*interval '365d', now()-random()*interval '365d'
FROM generate_series(1,5000) s(i);

-- ── 2. Tags: 100 ────────────────────────────────────────
INSERT INTO tags (name, slug, description, color, usage_count)
SELECT 'tag_'||i, 'tag-'||i, 'Description for tag '||i,
    CASE i%8 WHEN 0 THEN '#ef4444' WHEN 1 THEN '#f97316' WHEN 2 THEN '#eab308' WHEN 3 THEN '#22c55e'
             WHEN 4 THEN '#06b6d4' WHEN 5 THEN '#3b82f6' WHEN 6 THEN '#8b5cf6' ELSE '#ec4899' END,
    (random()*5000)::int
FROM generate_series(1,100) s(i);

-- ── 3. Posts: 50,000 (heavy text content) ───────────────
INSERT INTO posts (user_id, title, slug, content, excerpt, tags_array, metadata, status, view_count, like_count, published_at, created_at)
SELECT (random()*4999+1)::int,
    'Post '||i||' — '||CASE i%10 WHEN 0 THEN 'Comprehensive Guide to PostgreSQL Performance Tuning'
                                  WHEN 1 THEN 'Building Scalable Microservices with gRPC'
                                  WHEN 2 THEN 'Database Indexing Deep Dive: B-Trees to BRIN'
                                  WHEN 3 THEN 'Kubernetes Production Patterns Every Team Needs'
                                  WHEN 4 THEN 'Art of Code Review: Feedback That Builds Teams'
                                  WHEN 5 THEN 'Rust vs Go vs Zig: Systems Programming Showdown'
                                  WHEN 6 THEN 'Event-Driven Architecture in 2025'
                                  WHEN 7 THEN 'Zero-Downtime Database Migrations Guide'
                                  WHEN 8 THEN 'Observability Stack: Metrics Logs Traces'
                                  ELSE 'Clean Code for Data-Intensive Applications' END,
    'p'||i||'-'||md5(i::text),
    repeat('Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum. ',
        CASE i%4 WHEN 0 THEN 10 WHEN 1 THEN 7 WHEN 2 THEN 12 ELSE 8 END),
    'Excerpt for post '||i||' covering key concepts.',
    ARRAY['tag_'||((i%100)+1)::text, 'tag_'||(((i+17)%100)+1)::text, 'tag_'||(((i+53)%100)+1)::text],
    jsonb_build_object('read_time',(random()*20+3)::int,'word_count',(random()*8000+1000)::int,
        'format', CASE i%4 WHEN 0 THEN 'article' WHEN 1 THEN 'tutorial' WHEN 2 THEN 'guide' ELSE 'essay' END),
    CASE i%10 WHEN 0 THEN 'draft'::post_status WHEN 1 THEN 'archived'::post_status WHEN 2 THEN 'deleted'::post_status ELSE 'published'::post_status END,
    (random()*100000)::int, (random()*5000)::int, now()-random()*interval '730d', now()-random()*interval '730d'
FROM generate_series(1,50000) s(i);

-- ── 4. Post Tags (M:N) ─────────────────────────────────
INSERT INTO post_tags (post_id, tag_id)
SELECT p.id, t.id FROM posts p JOIN tags t ON t.id IN (((p.id%100)+1), (((p.id+17)%100)+1), (((p.id+53)%100)+1))
WHERE p.status='published';

-- ── 5. Comments: 250,000 ───────────────────────────────
INSERT INTO comments (post_id, user_id, body, depth, created_at)
SELECT (random()*49999+1)::int,
    CASE WHEN random()<0.1 THEN NULL ELSE (random()*4999+1)::int END,
    repeat(CASE (i%6) WHEN 0 THEN 'Excellent write-up! The indexing section cleared up months of confusion. '
                        WHEN 1 THEN 'Interesting perspective. Have you benchmarked this against BRIN indexes? '
                        WHEN 2 THEN 'This literally saved our deployment. The WAL section was the missing piece. '
                        WHEN 3 THEN 'Quick question — does this approach work with logical replication enabled? '
                        WHEN 4 THEN 'We implemented this and saw 40% improvement in query latency. '
                        ELSE 'I respectfully disagree on one point, but excellent overall. ' END, 2),
    CASE WHEN random()<0.6 THEN 1 ELSE CASE WHEN random()<0.7 THEN 2 ELSE 3 END END,
    now()-random()*interval '730d'
FROM generate_series(1,250000) s(i);

-- ── 6. Audit Logs: 100,000 ─────────────────────────────
INSERT INTO audit_logs (actor_id, action, table_name, record_id, old_data, new_data, ip_address, user_agent, level, duration_ms, created_at)
SELECT CASE WHEN random()<0.05 THEN NULL ELSE (random()*4999+1)::int END,
    CASE i%10 WHEN 0 THEN 'CREATE' WHEN 1 THEN 'UPDATE' WHEN 2 THEN 'DELETE' WHEN 3 THEN 'LOGIN' WHEN 4 THEN 'LOGOUT' WHEN 5 THEN 'EXPORT' WHEN 6 THEN 'IMPORT' WHEN 7 THEN 'PUBLISH' WHEN 8 THEN 'ARCHIVE' ELSE 'RESTORE' END,
    CASE i%7 WHEN 0 THEN 'users' WHEN 1 THEN 'posts' WHEN 2 THEN 'comments' WHEN 3 THEN 'tags' WHEN 4 THEN 'post_tags' WHEN 5 THEN 'audit_logs' ELSE 'analytics_events' END,
    (random()*50000)::int,
    CASE WHEN i%3=0 THEN jsonb_build_object('title','Old Title '||i,'status','draft') ELSE NULL END,
    jsonb_build_object('ts',now(),'by','user_'||((random()*4999+1)::int)::text,
        'changes',jsonb_build_array(jsonb_build_object('field','status','old','draft','new','published'))),
    CASE i%5 WHEN 0 THEN '192.168.1.1'::inet WHEN 1 THEN '10.0.0.1'::inet WHEN 2 THEN '172.16.0.1'::inet WHEN 3 THEN '203.0.113.42'::inet ELSE '198.51.100.7'::inet END,
    'Mozilla/5.0 Chrome/'||(110+i%20)::text,
    CASE i%20 WHEN 0 THEN 'DEBUG'::log_level WHEN 1 THEN 'WARN'::log_level WHEN 2 THEN 'ERROR'::log_level WHEN 3 THEN 'FATAL'::log_level ELSE 'INFO'::log_level END,
    (random()*5000)::int, now()-random()*interval '365d'
FROM generate_series(1,100000) s(i);

-- ── 7. Analytics Events: 240,000 ───────────────────────
INSERT INTO analytics_events (user_id, event_type, page_url, referrer, ip_address, country, device, browser, os, payload, duration_ms, error_code, created_at)
SELECT CASE WHEN random()<0.12 THEN NULL ELSE (random()*4999+1)::int END,
    CASE i%7 WHEN 0 THEN 'click'::event_type WHEN 1 THEN 'view'::event_type WHEN 2 THEN 'purchase'::event_type WHEN 3 THEN 'signup'::event_type WHEN 4 THEN 'login'::event_type WHEN 5 THEN 'logout'::event_type ELSE 'error'::event_type END,
    CASE i%12 WHEN 0 THEN '/home' WHEN 1 THEN '/dashboard' WHEN 2 THEN '/posts/'||(i%50000+1)::text WHEN 3 THEN '/profile' WHEN 4 THEN '/settings' WHEN 5 THEN '/search' WHEN 6 THEN '/api/v1/posts' WHEN 7 THEN '/api/v1/users' WHEN 8 THEN '/docs/getting-started' WHEN 9 THEN '/blog' WHEN 10 THEN '/pricing' ELSE '/about' END,
    CASE WHEN random()<0.4 THEN NULL ELSE 'https://google.com/search' END,
    CASE i%6 WHEN 0 THEN '8.8.8.8'::inet WHEN 1 THEN '1.1.1.1'::inet WHEN 2 THEN '208.67.222.222'::inet WHEN 3 THEN '9.9.9.9'::inet WHEN 4 THEN '185.125.190.58'::inet ELSE '91.189.91.39'::inet END,
    CASE i%10 WHEN 0 THEN 'US' WHEN 1 THEN 'ID' WHEN 2 THEN 'JP' WHEN 3 THEN 'GB' WHEN 4 THEN 'DE' WHEN 5 THEN 'BR' WHEN 6 THEN 'IN' WHEN 7 THEN 'SG' WHEN 8 THEN 'AU' ELSE 'NL' END,
    CASE i%3 WHEN 0 THEN 'desktop' WHEN 1 THEN 'mobile' ELSE 'tablet' END,
    CASE i%4 WHEN 0 THEN 'Chrome' WHEN 1 THEN 'Firefox' WHEN 2 THEN 'Safari' ELSE 'Edge' END,
    CASE i%4 WHEN 0 THEN 'Windows' WHEN 1 THEN 'macOS' WHEN 2 THEN 'Linux' ELSE 'iOS' END,
    jsonb_build_object('load_ms',(random()*3000+100)::int,'ttfb_ms',(random()*500+50)::int,
        'exp',jsonb_build_object('name','experiment_'||i%10,'variant',CASE i%3 WHEN 0 THEN 'A' WHEN 1 THEN 'B' ELSE 'control' END)),
    (random()*30000)::int,
    CASE WHEN i%7=6 THEN (random()*600+400)::int ELSE NULL END,
    now()-random()*interval '90d'
FROM generate_series(1,240000) s(i);

-- ── Final size check ───────────────────────────────────
SELECT 'COMPLEX DATASET READY' AS info;
SELECT pg_size_pretty(pg_database_size(current_database())) AS total;