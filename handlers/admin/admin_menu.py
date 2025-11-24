from aiogram import Router, F, types
from keyboards.admin_keyboard import admin_menu_kb, settings_kb
from utils.config_loader import OWNER_ID
from database import list_appointments_db, get_all_masters, remove_master
from flows.admin_add_master_flow import start_add_master_flow

router = Router()

@router.message(F.text == "📅 Просмотр записей")
async def view_appointments(msg: types.Message):
    data = await list_appointments_db()
    if not data:
        await msg.answer("📭 Записей пока нет.")
    else:
        text = "\n\n".join([f"👤 {n} ({p})\n💇 {s} к {m}\n📅 {d} ⏰ {t}" for _, n, p, s, m, d, t, _ in data])
        await msg.answer(text)

@router.message(F.text == "⚙️ Настройки")
async def admin_settings(msg: types.Message):
    if msg.from_user.id != OWNER_ID:
        await msg.answer("⛔ У вас нет доступа к настройкам.")
        return
    await msg.answer("⚙️ Настройки мастеров:", reply_markup=settings_kb())

@router.message(F.text == "➕ Добавить мастера")
async def admin_add_master(msg: types.Message):
    await start_add_master_flow(msg)

@router.message(F.text == "➖ Удалить мастера")
async def remove_master_cmd(msg: types.Message):
    masters = await get_all_masters()
    if not masters:
        await msg.answer("❌ Нет мастеров для удаления.")
        return
    kb = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text=m)] for m in masters] + [[types.KeyboardButton(text="⬅️ Назад")]],
        resize_keyboard=True
    )
    from flows.universal_router import userflow
    userflow[msg.from_user.id] = {"next": "delete_master"}
    await msg.answer("Выберите мастера для удаления:", reply_markup=kb)

@router.message(F.text == "🧾 Просмотр заявок")
async def admin_requests(msg: types.Message):
    if msg.from_user.id != OWNER_ID:
        return
    await msg.answer("📋 Заявки пока не реализованы.")