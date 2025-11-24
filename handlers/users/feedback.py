from aiogram import types, Router
from database import DB_PATH
import aiosqlite

router = Router()

async def show_reviews(m: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT service, master, rating, text, created_at FROM reviews ORDER BY created_at DESC LIMIT 5")
        rows = await cur.fetchall()
    if not rows:
        await m.answer("Пока нет отзывов. Для записи — контакты в разделе «Контакты».")
        return
    text = "Последние отзывы:\n"
    for svc, mstr, rating, txt, created in rows:
        text += f"• {svc} | {mstr} — {rating}⭐\n  «{txt}»\n"
    await m.answer(text)