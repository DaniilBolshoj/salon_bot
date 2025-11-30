import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from utils.config_loader import BOT_TOKEN
from database import init_db
from database.db import service_db

# Новые маршрутизаторы
from handlers.users.start import router as start_router
from handlers.users.menu import router as menu_router
from handlers.users.booking import router as booking_router
from handlers.users.contacts import router as contacts_router
from handlers.users.reviews import router as feedback_router

from handlers.admin.admin_menu import router as admin_menu_router
from handlers.admin.masters import router as admin_masters_router
from handlers.admin.schedule import router as admin_schedule_router
from handlers.admin.services import router as admin_services_router

from flows.universal_router import router as universal_router


# Инициализация бота
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

async def on_startup():
    print("🔄 Инициализация базы данных...")
    await init_db()
    await service_db()
    print("✅ База данных готова.")

    print("🔗 Подключение роутеров...")

    # USER роутеры
    dp.include_router(start_router)
    dp.include_router(menu_router)
    dp.include_router(booking_router)
    dp.include_router(contacts_router)
    dp.include_router(feedback_router)

    # ADMIN роутеры
    dp.include_router(admin_menu_router)
    dp.include_router(admin_masters_router)
    dp.include_router(admin_schedule_router)
    dp.include_router(admin_services_router)

    # UNIVERSAL FLOW router (замена universal_input_handler)
    dp.include_router(universal_router)

    print("✅ Все хэндлеры успешно подключены.")


async def bot_run():
    await on_startup()
    print("🤖 Бот запущен и ждёт сообщения...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(bot_run())
    except (KeyboardInterrupt, SystemExit):
        print("🛑 Бот остановлен.")