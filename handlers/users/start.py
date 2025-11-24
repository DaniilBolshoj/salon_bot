from aiogram import Router, types, F
from aiogram.filters import Command
from keyboards.main_keyboard import main_menu_kb
from keyboards.admin_keyboard import admin_menu_kb
from utils.config_loader import OWNER_ID
from handlers.users.booking import router as booking_router

router = Router()

@router.message(Command("start"))
async def cmd_start(msg: types.Message):
    if msg.from_user.id == OWNER_ID:
        await msg.answer("👑 Добро пожаловать, админ!", reply_markup=admin_menu_kb())
    else:
        await msg.answer(
            "👋 Добро пожаловать! Нажмите «📅 Записаться», чтобы выбрать услугу.",
            reply_markup=main_menu_kb()
        )