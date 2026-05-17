import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "drop_pin.db")

def get_db_connection():
    # SQLite works well enough without thread check in this single-worker usecase,
    # but check_same_thread=False helps with Flask's routing context.
    conn = sqlite3.connect(DB_PATH, timeout=15, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    # Ensure data dir exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # Activity Log
    c.execute('''
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT,
            filename TEXT,
            board TEXT,
            status TEXT,
            title TEXT
        )
    ''')
    
    # Bot Settings (Key-Value)
    c.execute('''
        CREATE TABLE IF NOT EXISTS bot_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # Boards (for AI Context)
    c.execute('''
        CREATE TABLE IF NOT EXISTS boards (
            name TEXT PRIMARY KEY,
            description TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

# --- Helper Functions ---

def log_activity(filename, board, status, title, time_str):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO activity_log (time, filename, board, status, title) VALUES (?, ?, ?, ?, ?)",
        (time_str, filename, board, status, title)
    )
    # Keep only the last 1000 activities to build accurate stats over time
    c.execute(
        "DELETE FROM activity_log WHERE id NOT IN (SELECT id FROM activity_log ORDER BY id DESC LIMIT 1000)"
    )
    conn.commit()
    conn.close()

def get_stats():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as total FROM activity_log")
    total_posts = c.fetchone()['total']
    
    c.execute("SELECT COUNT(*) as success FROM activity_log WHERE status LIKE '%Success%'")
    success_posts = c.fetchone()['success']
    
    c.execute("SELECT board, COUNT(*) as count FROM activity_log GROUP BY board ORDER BY count DESC LIMIT 1")
    row = c.fetchone()
    top_board = row['board'] if row else "None"
    
    conn.close()
    
    return {
        "total_posts": total_posts,
        "success_posts": success_posts,
        "failed_posts": total_posts - success_posts,
        "top_board": top_board
    }

def get_recent_activity(limit=20):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM activity_log ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def set_setting(key, value):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def get_setting(key, default=None):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT value FROM bot_settings WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    return row['value'] if row else default

def set_board_description(name, description):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO boards (name, description) VALUES (?, ?)", (name, description))
    conn.commit()
    conn.close()

def get_board_description(name):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT description FROM boards WHERE name = ?", (name,))
    row = c.fetchone()
    conn.close()
    return row['description'] if row else ""

def get_all_boards():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM boards")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]



if __name__ == "__main__":
    init_db()
    print("Database initialized.")
