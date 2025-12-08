import aiosqlite
from datetime import datetime, date, timedelta

DB_PATH = "database/salon.db" 

# ======= SQL схемы =======
CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS services (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT UNIQUE NOT NULL,
  price TEXT
);

CREATE TABLE IF NOT EXISTS masters (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  services TEXT, -- e.g. "Стрижка,Маникюр"
  status TEXT
);

CREATE TABLE IF NOT EXISTS master_days (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    master_id INTEGER NOT NULL,
    day TEXT NOT NULL,
    FOREIGN KEY(master_id) REFERENCES masters(id)
);

CREATE TABLE IF NOT EXISTS master_slots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    master_id INTEGER NOT NULL,
    day TEXT NOT NULL,
    time TEXT NOT NULL,
    FOREIGN KEY(master_id) REFERENCES masters(id)
);

CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT,
    phone TEXT,
    service TEXT,
    master TEXT,
    day TEXT,
    time TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    name TEXT,
    phone TEXT,
    desired_day TEXT,
    desired_time TEXT,
    note TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS reviews (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  service TEXT,
  master TEXT,
  rating REAL,
  review_text TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        for stmt in CREATE_TABLES_SQL.strip().split(";"):
            sql = stmt.strip()
            if sql:
                await db.execute(sql + ";")
        # default settings
        cur = await db.execute("SELECT value FROM settings WHERE key='country_code'")
        if not await cur.fetchone():
            await db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES(?,?)", ("country_code", "+370"))
        cur = await db.execute("SELECT value FROM settings WHERE key='work_start'")
        if not await cur.fetchone():
            await db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES(?,?)", ("work_start", "09:00"))
            await db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES(?,?)", ("work_end", "18:00"))
        await db.commit()

async def service_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                price INTEGER
            )
        """)
        await db.commit()

def now_iso():
    return datetime.utcnow().isoformat(timespec='seconds')

def get_dates_window(days_ahead=7):
    today = date.today()
    return [(today + timedelta(days=i)).isoformat() for i in range(days_ahead)]

# ======= Settings =======
async def get_setting(key):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = await cur.fetchone()
        return row[0] if row else None

async def set_setting(key, value):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES(?,?)", (key, value))
        await db.commit()