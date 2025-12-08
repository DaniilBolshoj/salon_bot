import aiosqlite
from database import DB_PATH
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

# ======= Инициализация таблицы услуг, если не существует =======
async def init_services_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                price TEXT
            )
        """)
        await db.commit()

async def add_description_column():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("ALTER TABLE services ADD COLUMN description TEXT")
        await db.commit()

# ======= Добавить услугу =======
async def add_service(name, price=""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO services(name, price) VALUES(?,?)", (name, price))
        await db.commit()


# ======= Получить список услуг (id, name, price) =======
async def get_services():   # возвращает id, name, price
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id, name, price FROM services ORDER BY name")
        return await cur.fetchall()

# ======= Получить список услуг (name, price) ======= 
async def services_list():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT name, price FROM services ORDER BY name")
        return await cur.fetchall()

# ======= Найти услугу по названию =======
async def get_service_by_id(service_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id, name, price FROM services WHERE id = ?", (service_id,))
        return await cur.fetchone()

# ======= Удалить услугу по id =======
async def remove_service_by_id(service_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM services WHERE id=?", (service_id,))
        await db.commit()

# ======= Удалить услугу по названию =======
async def remove_service_by_name(name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM services WHERE name=?", (name,))
        await db.commit()

# ======= Обновить цену =======
async def update_service_price(service_id, price):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE services SET price = ? WHERE id = ?",
            (price, service_id)
        )
        await db.commit()