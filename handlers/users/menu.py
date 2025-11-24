from aiogram import Router, F, types
from keyboards.main_keyboard import main_menu_kb
from keyboards.admin_keyboard import admin_menu_kb
from utils.config_loader import OWNER_ID

router = Router()

@router.message(F.text == "🏠 Главное меню")
async def back_to_main_menu(msg: types.Message):
    if msg.from_user.id == OWNER_ID:
        await msg.answer("🏠 Возврат в главное меню.", reply_markup=main_menu_kb(is_owner=True))
    else:
        await msg.answer("🏠 Возврат в главное меню.", reply_markup=main_menu_kb())

@router.message(F.text == "🏠 Админ-меню")
async def open_admin_menu(msg: types.Message):
    if msg.from_user.id == OWNER_ID:
        await msg.answer("⚙️ Админ-панель открыта.", reply_markup=admin_menu_kb())
    else:
        await msg.answer("⛔ У вас нет доступа к админ-панели.")