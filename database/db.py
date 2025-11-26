import aiosqlite
from datetime import datetime, date, timedelta

WEEKDAYS = {"Пн":0,"Вт":1,"Ср":2,"Чт":3,"Пт":4,"Сб":5,"Вс":6}

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
    name TEXT UNIQUE,
    services TEXT,
    status TEXT DEFAULT 'работает'
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
    rating INTEGER,
    text TEXT,
    created_at TEXT
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

# ======= Services =======
async def add_service(name, price=""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO services(name, price) VALUES(?,?)", (name, price))
        await db.commit()

async def list_services():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT name, price FROM services ORDER BY name")
        return await cur.fetchall()

# ======= Masters =======
async def add_master(name, services):
    """
    Добавляет мастера и записывает, какие услуги он выполняет.
    services — это список строк, например ['Массаж', 'Стрижка'].
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO masters(name, services) VALUES(?, ?)",
            (name, ",".join(services))
        )
        await db.commit()
        
async def get_masters_by_service(service_name):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT name FROM masters WHERE services LIKE ?",
            (f"%{service_name}%",)
        )
        rows = await cur.fetchall()
        return [r[0] for r in rows]

async def remove_master(name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM masters WHERE name=?", (name,))
        await db.commit()

async def get_all_masters():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT name FROM masters ORDER BY name")
        rows = await cur.fetchall()
        return [r[0] for r in rows]

# ======= Master days & slots =======
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

async def get_master_days(master_name):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""SELECT md.day FROM master_days md
                                  JOIN masters m ON m.id=md.master_id
                                  WHERE m.name=? ORDER BY md.day""", (master_name,))
        rows = await cur.fetchall()
        return [r[0] for r in rows]

async def set_master_slots(master_name, start_time, end_time, selected_days, slot_duration_hours=1):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id FROM masters WHERE name=?", (master_name,))
        r = await cur.fetchone()
        if not r:
            return False
        master_id = r[0]
        await db.execute("DELETE FROM master_slots WHERE master_id=?", (master_id,))

        start_dt = datetime.strptime(start_time, "%H:%M")
        end_dt = datetime.strptime(end_time, "%H:%M")

        today = datetime.today()
        for day_offset in range(14):  # например 2 недели вперёд
            current_day = today + timedelta(days=day_offset)
            weekday_str = [k for k,v in WEEKDAYS.items() if v == current_day.weekday()][0]
            if weekday_str in selected_days:
                slot_dt = datetime.combine(current_day, start_dt.time())
                end_slot_dt = datetime.combine(current_day, end_dt.time())
                while slot_dt + timedelta(hours=slot_duration_hours) <= end_slot_dt + timedelta(seconds=1):
                    await db.execute(
                        "INSERT INTO master_slots(master_id, day, time) VALUES (?,?,?)",
                        (master_id, current_day.strftime("%Y-%m-%d"), slot_dt.strftime("%H:%M"))
                    )
                    slot_dt += timedelta(hours=slot_duration_hours)
        await db.commit()
        return True

async def get_master_slots(master_name, selected_weekdays, start_time, end_time, slot_duration_hours=1, days_ahead=14):
    """
    selected_weekdays: ["Пн", "Ср", "Пт"]
    start_time, end_time: "08:30", "16:30"
    slot_duration_hours: 1
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id FROM masters WHERE name=?", (master_name,))
        r = await cur.fetchone()
        if not r:
            return False
        master_id = r[0]
        
        # Удаляем старые слоты
        await db.execute("DELETE FROM master_slots WHERE master_id=?", (master_id,))

        today = datetime.today()
        end_day = today + timedelta(days=days_ahead)
        start_dt = datetime.strptime(start_time, "%H:%M")
        end_dt = datetime.strptime(end_time, "%H:%M")

        current_day = today
        while current_day <= end_day:
            weekday_str = [k for k,v in WEEKDAYS.items() if v == current_day.weekday()][0]
            if weekday_str in selected_weekdays:
                slot_dt = datetime.combine(current_day, start_dt.time())
                end_slot_dt = datetime.combine(current_day, end_dt.time())
                while slot_dt + timedelta(hours=slot_duration_hours) <= end_slot_dt + timedelta(seconds=1):
                    await db.execute(
                        "INSERT INTO master_slots(master_id, day, time) VALUES (?,?,?)",
                        (master_id, current_day.strftime("%Y-%m-%d"), slot_dt.strftime("%H:%M"))
                    )
                    slot_dt += timedelta(hours=slot_duration_hours)
            current_day += timedelta(days=1)
        await db.commit()
    return True

# ======= Appointments =======
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
        await db.execute(
            """INSERT INTO appointments 
               (user_id, name, phone, service, master, day, time, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, name, phone, service, master, day, time_, now_iso())
        )
        await db.commit()

async def list_appointments_db():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id, name, phone, service, master, day, time, created_at FROM appointments ORDER BY day, time")
        return await cur.fetchall()

# ======= Requests =======
async def add_request_db(user_id, name, phone, desired_day, desired_time, note):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""INSERT INTO requests(user_id, name, phone, desired_day, desired_time, note, created_at)
                            VALUES(?,?,?,?,?,?,?)""", (user_id, name, phone, desired_day, desired_time, note, now_iso()))
        await db.commit()
        
# ======= Упрощённая версия (автоматическая) =======
async def get_master_slots_auto(master_name):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """SELECT day, time FROM master_slots
               JOIN masters ON masters.id = master_slots.master_id
               WHERE masters.name=? ORDER BY day, time""",
            (master_name,)
        )
        rows = await cur.fetchall()
        print("AUTO SLOTS:", rows)  # <- вот правильный print
        return rows 
