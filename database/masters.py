import aiosqlite
from database import DB_PATH  # твой путь к БД
from datetime import datetime, timedelta
from database import WEEKDAYS

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

async def get_all_masters():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT name FROM masters ORDER BY name")
        rows = await cur.fetchall()
        return [r[0] for r in rows]  
          
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
    
async def update_master_status(master_name, status):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE masters SET status=? WHERE name=?",
            (status, master_name)
        )
        await db.commit()

