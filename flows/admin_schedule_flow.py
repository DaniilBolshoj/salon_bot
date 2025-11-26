# Здесь будут callback-хендлеры для start_time, end_time, slot_duration
from aiogram import Router, F
from aiogram import types
router = Router()

@router.message(F.text == "🕒 Настроить время работы")
async def set_working_hours(msg: types.Message):
    await msg.answer("Настройка времени работы... (пока заглушка)")

@router.message(F.text == "⬅️ Назад в меню")
async def back_to_admin_menu(msg: types.Message):
    from keyboards.admin_keyboard import admin_menu_kb
    await msg.answer("Возврат в админ-меню", reply_markup=admin_menu_kb())

