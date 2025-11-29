from aiogram import Router, types
from database import DB_PATH
import aiosqlite

router = Router()

@router.message(lambda m: m.text == "🏢 О нас")
async def about(m: types.Message):
    await m.answer("💖 Салон красоты — запись через бота. Для вопросов используйте Контакты.")

@router.message(lambda m: m.text == "💇 Услуги")
async def services_menu(m: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT name, price FROM services")
        rows = await cur.fetchall()
    
    if not rows:
        await m.answer("Пока нет доступных услуг.")
        return
    
    text = "💇 Наши услуги:\n"
    for name, price in rows:
        text += f"• {name} — {price}€\n"
    await m.answer(text)


@router.message(lambda m: m.text == "💬 Контакты")
async def contacts(m: types.Message):
    await m.answer("📞 Телефон: +370 XXX XXX\n📍 Адрес: Вильнюс\n"
                   "Нажмите «📅 Записаться» для выбора времени.")

@router.message(lambda m: m.text == "🧠 AI-помощник")
async def ai_helper(m: types.Message):
    await m.answer("🤖 AI-помощник временно недоступен. Попробуйте позже.")