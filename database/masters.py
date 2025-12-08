import aiosqlite
from database import DB_PATH

WEEKDAYS = {"Пн":0,"Вт":1,"Ср":2,"Чт":3,"Пт":4,"Сб":5,"Вс":6}

# Добавить мастера: services — список строк (имён услуг)
async def add_master(name, services_list):
    async with aiosqlite.connect(DB_PATH) as db:
        # Проверяем, есть ли уже мастер с таким именем
        cur = await db.execute("SELECT id FROM masters WHERE name=?", (name,))
        existing = await cur.fetchone()
        if existing:
            return existing[0]  # возвращаем id существующего мастера

        # Если нет — создаём нового
        await db.execute(
            "INSERT INTO masters(name) VALUES(?)",
            (name,)
        )
        await db.commit()

        # Получаем id вновь добавленного мастера
        cur = await db.execute("SELECT id FROM masters WHERE name=?", (name,))
        r = await cur.fetchone()
        return r[0]

# Получить всех мастеров: возвращает [(id, name), ...]
async def get_all_masters():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id, name FROM masters ORDER BY name")
        rows = await cur.fetchall()
        return [(r[0], r[1]) for r in rows]

# Получить мастеров, которые выполняют услугу по service_id
# ИД услуги -> сначала получаем её имя, затем ищем по маске в поле services
async def get_masters_by_service(service_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        # получаем имя услуги по id
        cur = await db.execute("SELECT name FROM services WHERE id = ?", (service_id,))
        row = await cur.fetchone()
        if not row:
            return []  # услуга не найдена
        service_name = row[0]
        # ищем мастеров, у которых services LIKE %service_name%
        cur = await db.execute(
            "SELECT id, name FROM masters WHERE services LIKE ? ORDER BY name",
            (f"%{service_name}%",)
        )
        rows = await cur.fetchall()
        return [(r[0], r[1]) for r in rows]

# Получить мастера по id
async def get_master_by_id(master_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id, name, services FROM masters WHERE id = ?", (master_id,))
        row = await cur.fetchone()
        return row if row else None

# Удалить мастера по id
async def remove_master_by_name(master_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        # Сначала получаем id мастера
        cur = await db.execute("SELECT id FROM masters WHERE name = ?", (master_name,))
        row = await cur.fetchone()
        if not row:
            return False  # мастер не найден
        master_id = row[0]
        # Удаляем мастера
        await db.execute("DELETE FROM masters WHERE id = ?", (master_id,))
        await db.commit()
        return True

# Обновить services для мастера (services — список имён)
async def update_master_services(master_id: int, services: list[str]):
    services_str = ",".join(services)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE masters SET services = ? WHERE id = ?", (services_str, master_id))
        await db.commit()