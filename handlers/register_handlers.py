from aiogram.filters import Command
from aiogram import F, Router
from aiogram import Dispatcher
from handlers import start, booking, feedback

from handlers.start import cmd_start, admin_menu_kb, remove_master_cmd, universal_input_handler
from handlers.booking import begin_booking, cb_service, cb_master, cb_day, cb_time
from handlers.feedback import show_reviews

router = Router()

def register_all_handlers(dp: Dispatcher):
    # Команды
    dp.message.register(cmd_start, Command("start"))
    dp.message.register(admin_menu_kb, Command("admin"))
    dp.message.register(universal_input_handler, Command("add_master"))
    dp.message.register(remove_master_cmd, Command("delete_master"))

    # Пользовательские действия
    dp.message.register(begin_booking, F.text == "📅 Записаться")
    dp.callback_query.register(cb_service, F.data.startswith("svc:"))
    dp.callback_query.register(cb_master, F.data.startswith("m:"))
    dp.callback_query.register(cb_day, F.data.startswith("day:"))
    dp.callback_query.register(cb_time, F.data.startswith("slot:"))
    dp.message.register(show_reviews, F.text == "⭐ Отзывы")

    # Подключаем все роутеры
    dp.include_router(start.router)
    dp.include_router(booking.router)
    dp.include_router(feedback.router)