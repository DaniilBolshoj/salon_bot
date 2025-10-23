import aiosqlite
from datetime import datetime


DB_PATH = "salon.db" 

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
    name TEXT UNIQUE NOT NULL
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
    rating INTEGER,
    text TEXT,
    created_at TEXT
);
"""

def now_iso():
    return datetime.now().isoformat()

# ======= DB init =======
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

# ======= DB helpers =======
async def get_setting(key):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = await cur.fetchone()
        return row[0] if row else None

async def set_setting(key, value):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES(?,?)", (key, value))
        await db.commit()

async def add_service(name, price=""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO services(name, price) VALUES(?,?)", (name, price))
        await db.commit()

async def list_services():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT name, price FROM services ORDER BY name")
        return await cur.fetchall()

async def add_master(name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO masters(name) VALUES(?)", (name,))
        await db.commit()

async def remove_master(name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM masters WHERE name=?", (name,))
        await db.commit()

async def get_all_masters():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT name FROM masters ORDER BY name")
        rows = await cur.fetchall()
        return [r[0] for r in rows]

async def set_master_days(master_name, days_list):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id FROM masters WHERE name=?", (master_name,))
        r = await cur.fetchone()
        if not r:
            return False
        master_id = r[0]
        await db.execute("DELETE FROM master_days WHERE master_id=?", (master_id,))
        for d in days_list:
            await db.execute("INSERT INTO master_days(master_id, day) VALUES(?,?)", (master_id, d))
        await db.commit()
        return True

async def set_master_slots(master_name, slots_list):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id FROM masters WHERE name=?", (master_name,))
        r = await cur.fetchone()
        if not r:
            return False
        master_id = r[0]
        await db.execute("DELETE FROM master_slots WHERE master_id=?", (master_id,))
        for s in slots_list:
            await db.execute("INSERT INTO master_slots(master_id, time) VALUES(?,?)", (master_id, s))
        await db.commit()
        return True

async def get_master_days(master_name):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""SELECT md.day FROM master_days md
                                  JOIN masters m ON m.id=md.master_id
                                  WHERE m.name=? ORDER BY md.day""", (master_name,))
        rows = await cur.fetchall()
        return [r[0] for r in rows]

async def get_master_slots(master_name):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""SELECT ms.time FROM master_slots ms
                                  JOIN masters m ON m.id=ms.master_id
                                  WHERE m.name=? ORDER BY ms.time""", (master_name,))
        rows = await cur.fetchall()
        return [r[0] for r in rows]

async def slot_taken(master, day, time_):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT 1 FROM appointments WHERE master=? AND day=? AND time=?", (master, day, time_))
        return await cur.fetchone() is not None

async def user_has_appointment_db(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT 1 FROM appointments WHERE user_id=?", (user_id,))
        return await cur.fetchone() is not None

async def create_appointment_db(user_id, name, phone, service, master, day, time_):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""INSERT INTO appointments(user_id, name, phone, service, master, day, time, created_at)
                            VALUES(?,?,?,?,?,?,?,?)""", (user_id, name, phone, service, master, day, time_, now_iso()))
        await db.commit()

async def list_appointments_db():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id, name, phone, service, master, day, time, created_at FROM appointments ORDER BY day, time")
        return await cur.fetchall()

async def add_request_db(user_id, name, phone, desired_day, desired_time, note):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""INSERT INTO requests(user_id, name, phone, desired_day, desired_time, note, created_at)
                            VALUES(?,?,?,?,?,?,?)""", (user_id, name, phone, desired_day, desired_time, note, now_iso()))
        await db.commit()