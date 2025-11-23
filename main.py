import sys
import os
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from utils.config import BOT_TOKEN
from database.db_helpers import init_db
from handlers import register_handlers, start

# Добавляем текущую директорию в PATH
sys.path.append(os.path.dirname(__file__))

# Инициализация бота с HTML по умолчанию
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

async def on_startup():
    print("🔄 Инициализация базы данных...")
    await init_db()
    print("✅ База данных готова.")

    # Регистрируем все хэндлеры
    dp.include_router(start.router)
    print("✅ Хэндлеры успешно подключены.")

async def main_run():
    await on_startup()
    print("🤖 Бот запущен и ждёт сообщения...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main_run())
    except (KeyboardInterrupt, SystemExit):
        print("🛑 Бот остановлен.")