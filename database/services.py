import aiosqlite
from database import DB_PATH

async def add_description_column():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("ALTER TABLE services ADD COLUMN description TEXT")
        await db.commit()

# ======= Добавить услугу =======
async def add_service(name, price):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO services(name, price) VALUES (?, ?)",
            (name, price)
        )
        await db.commit()


# ======= Получить список услуг (id, name, price) =======
async def get_services():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id, name, price FROM services ORDER BY name")
        return await cur.fetchall()


# ======= Найти услугу по названию =======
async def get_service_by_name(name):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, name, price FROM services WHERE name = ?",
            (name,)
        )
        return await cur.fetchone()


# ======= Удалить услугу по id =======
async def remove_service_by_id(service_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM services WHERE id = ?", (service_id,))
        await db.commit()


# ======= Обновить цену =======
async def update_service_price(service_id, price):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE services SET price = ? WHERE id = ?",
            (price, service_id)
        )
        await db.commit()