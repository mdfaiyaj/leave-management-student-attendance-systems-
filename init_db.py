import sqlite3
import os

DB_PATH = "leave.db"

def create_tables():
    conn = sqlite3.connect("leave.db")
    c = conn.cursor()

    # USERS TABLE
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            password TEXT,
            role TEXT,
            branch TEXT,
            semester TEXT,
            roll_no TEXT,
            registration_no TEXT,
            parent_phone TEXT,
            parent_email TEXT,
            admin_branch TEXT,
            photo TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # LEAVES TABLE
    c.execute("""
        CREATE TABLE IF NOT EXISTS leaves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            reason TEXT,
            from_date TEXT,
            to_date TEXT,
            applied_on TEXT DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'Pending',
            decision_on TEXT,
            decision_reason TEXT,
            FOREIGN KEY(student_id) REFERENCES users(id)
        )
    """)

    # ATTENDANCE TABLE
    c.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            date TEXT,
            status TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(student_id) REFERENCES users(id)
        )
    """)

    # SUPPORT MESSAGES TABLE
    c.execute("""

CREATE TABLE IF NOT EXISTS support_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER,
    content TEXT,
    reply TEXT,
    seen INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(student_id) REFERENCES users(id)
   );

    """)

    conn.commit()
    conn.close()
