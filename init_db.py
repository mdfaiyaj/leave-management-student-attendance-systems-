import sqlite3

conn = sqlite3.connect("leave.db")
cur = conn.cursor()

# USERS TABLE
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL,
    department TEXT,
    roll_no TEXT,
    parent_phone TEXT,
    parent_email TEXT
);
""")

# LEAVES TABLE
cur.execute("""
CREATE TABLE IF NOT EXISTS leaves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER,
    reason TEXT,
    from_date TEXT,
    to_date TEXT,
    status TEXT DEFAULT 'Pending',
    decision_reason TEXT,
    applied_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(student_id) REFERENCES users(id)
);
""")

# SUPPORT CHAT TABLE
cur.execute("""
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_user_id INTEGER,
    to_user_id INTEGER,
    content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

conn.commit()
conn.close()

print("Database initialized successfully!")
