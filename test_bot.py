import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

TOKEN = "8251523047:AAERjuRUJJQSewgORj58yRwxvkW9v7P0b2E"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# === Главное меню ===
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🏢 О компании"), KeyboardButton(text="📋 Услуги")],
        [KeyboardButton(text="📅 Записаться"), KeyboardButton(text="⭐ Отзывы")],
        [KeyboardButton(text="💬 Контакты"), KeyboardButton(text="🧠 AI-помощник")]
    ],
    resize_keyboard=True
)

# === Команда /start ===
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "👋 Привет! Я AI-бот для бизнеса.\nВыберите действие из меню ниже 👇",
        reply_markup=main_menu
    )

# === Обработчики кнопок ===
@dp.message(lambda m: m.text == "🏢 О компании")
async def about(message: types.Message):
    await message.answer(
        "Мы создаём умных AI-ботов, которые помогают бизнесу продавать, экономить и расти 💼"
    )

@dp.message(lambda m: m.text == "📋 Услуги")
async def services(message: types.Message):
    await message.answer(
        "Наши услуги:\n• Создание Telegram-ботов\n• Автоматизация заявок\n• AI-чат-помощники\n• Подключение оплат 💳"
    )

@dp.message(lambda m: m.text == "📅 Записаться")
async def booking(message: types.Message):
    await message.answer("Чтобы записаться, просто напиши удобное время и контакт 👇")

@dp.message(lambda m: m.text == "⭐ Отзывы")
async def reviews(message: types.Message):
    await message.answer(
        "📢 Клиенты говорят:\n⭐ «Бот увеличил поток заказов на 40%!», — Анна\n⭐ «Теперь всё работает автоматически!», — Иван"
    )

@dp.message(lambda m: m.text == "💬 Контакты")
async def contacts(message: types.Message):
    await message.answer(
        "📞 Контакты:\nTelegram: @твойник\nInstagram: instagram.com/твойпроект\nСайт: www.твойдомен.lt"
    )

@dp.message(lambda m: m.text == "🧠 AI-помощник")
async def ai_helper(message: types.Message):
    await message.answer("Я могу ответить на частые вопросы — просто задай их 💬")

# === Команда /admin ===
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if str(message.from_user.id) == "ТВОЙ_TELEGRAM_ID":  # замени на свой ID
        await message.answer("🔐 Панель администратора:\n1. Рассылка\n2. Статистика\n3. Изменение текстов")
    else:
        await message.answer("❌ У тебя нет доступа к админ-панели.")

# === Запуск бота ===
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())