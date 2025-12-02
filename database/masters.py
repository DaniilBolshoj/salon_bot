import aiosqlite
from database import DB_PATH  # твой путь к БД
from datetime import datetime, timedelta
from database import WEEKDAYS

# ======= Masters =======

async def add_master(name: str, service_ids: list[int]):
    """
    Добавляет мастера и список услуг, которые он оказывает.
    service_ids — список ID услуг, например [1, 3, 5]
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO masters(name, services) VALUES(?, ?)",
            (name, ",".join(map(str, service_ids)))
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


async def get_all_masters():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT name FROM masters ORDER BY name")
        rows = await cursor.fetchall()
        return [r[0] for r in rows]

async def remove_master(name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM masters WHERE name=?", (name,))
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
        #print("AUTO SLOTS:", rows)  # <- вот правильный print
        return rows 
    
async def update_master_status(master_name, status):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE masters SET status=? WHERE name=?",
            (status, master_name)
        )
        await db.commit()

