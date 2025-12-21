from aiogram import Router, F, types
from keyboards.admin_keyboard import admin_menu_kb, settings_kb
from utils.userflow import userflow
from utils.config_loader import OWNER_ID
from database.appointments import list_appointments_db
from database.masters import get_all_masters
from aiogram.types import KeyboardButton

router = Router()

@router.message(F.text == "📅 Просмотр записей")
async def view_appointments(msg: types.Message):
    if msg.from_user.id != OWNER_ID:
        return

    data = await list_appointments_db()
    if not data:
        await msg.answer("📭 Записей пока нет.")
        return

    sorted_data = sorted(data, key=lambda x: (x[6], x[7]))
    text = "📅 <b>Список записей</b>\n\n"
    current_day = ""

    for _, name, phone, service, master, day, time_, _ in sorted_data:
        if day != current_day:
            current_day = day
            text += f"📆 <b>{day}</b>\n"
        text += f"⏰ {time_} — {service} у {master} (👤 {name}, 📞 {phone})\n"

    await msg.answer(text, parse_mode="HTML")

@router.message(F.text == "🧾 Просмотр заявок")
async def admin_requests(msg: types.Message):
    if msg.from_user.id != OWNER_ID:
        return
    await msg.answer("📋 Заявки пока не реализованы.")
    
@router.message(F.text == "⚙️ Настройки")
async def admin_settings(msg: types.Message):
    if msg.from_user.id != OWNER_ID:
        await msg.answer("⛔ У вас нет доступа к настройкам.")
        return
    await msg.answer("⚙️ Настройки мастеров:", reply_markup=settings_kb())
