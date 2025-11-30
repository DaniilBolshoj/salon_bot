import aiosqlite
from database import DB_PATH

async def create_reviews_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                service TEXT,
                master TEXT,
                rating INTEGER,
                review_text TEXT
            )
        """)
        await db.commit()

async def add_review(user_id, service, master, rating, text):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO reviews (user_id, service, master, rating, review_text)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, service, master, rating, text))
        await db.commit()


async def get_last_reviews(limit=5):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT service, master, rating, review_text FROM reviews ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        return await cursor.fetchall()