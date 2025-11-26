import aiosqlite
from database import DB_PATH  # твой путь к БД

# ======= Services =======
async def add_service(name, price=""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO services(name, price) VALUES(?,?)", (name, price))
        await db.commit()

async def list_services():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT name, price FROM services ORDER BY name")
        return await cur.fetchall()

async def get_services():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id, name, price FROM services ORDER BY name")
        return await cur.fetchall()

async def remove_service(service_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM services WHERE id=?", (service_id,))
        await db.commit()