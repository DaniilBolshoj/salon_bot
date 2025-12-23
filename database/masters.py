import aiosqlite
from database import DB_PATH

WEEKDAYS = {"Пн": 0, "Вт": 1, "Ср": 2, "Чт": 3, "Пт": 4, "Сб": 5, "Вс": 6}

# ==================================================
# ИНИЦИАЛИЗАЦИЯ ТАБЛИЦ
# ==================================================

async def init_masters_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS masters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE
            )
        """)
        await db.commit()


async def init_master_services():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS master_services (
                master_id INTEGER,
                service_id INTEGER,
                UNIQUE(master_id, service_id)
            )
        """)
        await db.commit()

# ==================================================
# МАСТЕРА
# ==================================================

# Добавить мастера
async def add_master(name: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO masters(name) VALUES(?)",
            (name,)
        )
        await db.commit()

        cur = await db.execute(
            "SELECT id FROM masters WHERE name = ?",
            (name,)
        )
        row = await cur.fetchone()
        return row[0]


# Получить всех мастеров
async def get_all_masters():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, name FROM masters ORDER BY name"
        )
        return await cur.fetchall()


# Получить мастера по id
async def get_master_by_id(master_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, name FROM masters WHERE id = ?",
            (master_id,)
        )
        return await cur.fetchone()


# Удалить мастера по имени
async def remove_master_by_name(name: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id FROM masters WHERE name = ?",
            (name,)
        )
        row = await cur.fetchone()
        if not row:
            return False

        master_id = row[0]

        await db.execute(
            "DELETE FROM master_services WHERE master_id = ?",
            (master_id,)
        )
        await db.execute(
            "DELETE FROM masters WHERE id = ?",
            (master_id,)
        )
        await db.commit()
        return True

# ==================================================
# СВЯЗЬ МАСТЕР ↔ УСЛУГА
# ==================================================

# Назначить услугу мастеру
async def assign_service_to_master(master_id: int, service_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO master_services(master_id, service_id) VALUES (?, ?)",
            (master_id, service_id)
        )
        await db.commit()


# Удалить услугу у мастера
async def remove_service_from_master(master_id: int, service_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM master_services WHERE master_id = ? AND service_id = ?",
            (master_id, service_id)
        )
        await db.commit()


# Получить услуги мастера
async def get_services_by_master(master_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT s.id, s.name, s.price
            FROM services s
            JOIN master_services ms ON ms.service_id = s.id
            WHERE ms.master_id = ?
            ORDER BY s.name
        """, (master_id,))
        return await cur.fetchall()


# Получить мастеров по услуге
async def get_masters_by_service(service_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT m.id, m.name
            FROM masters m
            JOIN master_services ms ON ms.master_id = m.id
            WHERE ms.service_id = ?
            ORDER BY m.name
        """, (service_id,))
        return await cur.fetchall()
