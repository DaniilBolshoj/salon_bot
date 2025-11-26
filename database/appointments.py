import aiosqlite
from database import DB_PATH  # твой путь к БД
from datetime import datetime
from database.db import now_iso

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