-- Create schema and tables for gaet local testing
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    email VARCHAR(100) NOT NULL,
    bio TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS posts (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id),
    title VARCHAR(200) NOT NULL,
    content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Truncate existing data if any to ensure clean generation
TRUNCATE TABLE posts, users RESTART IDENTITY CASCADE;

-- Insert 10,000 users
INSERT INTO users (username, email, bio)
SELECT 
    'user_' || i, 
    'user_' || i || '@example.com',
    repeat('This is a biography for user ' || i || ' who is testing gaet. ', 5)
FROM generate_series(1, 10000) s(i);

-- Insert 100,000 posts with repeat text to achieve ~100MB of data
INSERT INTO posts (user_id, title, content)
SELECT 
    (random() * 9999 + 1)::int,
    'Post title ' || i,
    repeat('Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. ' || i || ' ', 8)
FROM generate_series(1, 100000) s(i);
