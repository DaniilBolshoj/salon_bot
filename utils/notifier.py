import sqlite3

DB_NAME = "bot_data.db"

def create_tables():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            service TEXT,
            date TEXT,
            time TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            message TEXT,
            date TEXT
        )
    """)

    conn.commit()
    conn.close()

def add_booking(user_id, name, service, date, time):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO bookings (user_id, name, service, date, time) VALUES (?, ?, ?, ?, ?)",
                   (user_id, name, service, date, time))
    conn.commit()
    conn.close()

def get_all_bookings():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bookings")
    data = cursor.fetchall()
    conn.close()
    return data

def add_feedback(user_id, username, message, date):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO feedback (user_id, username, message, date) VALUES (?, ?, ?, ?)",
                   (user_id, username, message, date))
    conn.commit()
    conn.close()

def get_all_feedback():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM feedback ORDER BY id DESC")
    data = cursor.fetchall()
    conn.close()
    return data