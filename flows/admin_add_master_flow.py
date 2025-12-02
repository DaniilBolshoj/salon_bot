from aiogram import types
from keyboards.admin_keyboard import admin_menu_kb
from flows.universal_router import userflow


async def start_add_master_flow(msg: types.Message):
    user_id = msg.from_user.id
    userflow[user_id] = {"next": "add_master"}
    kb = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="⬅️ Назад")]],
        resize_keyboard=True
    )
    await msg.answer("Введите имя нового мастера:", reply_markup=kb)