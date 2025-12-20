from aiogram import Router, F, types
from keyboards.admin_keyboard import admin_menu_kb, settings_kb
from utils import userflow
from utils.config_loader import OWNER_ID
from database.appointments import list_appointments_db
from database.masters import get_all_masters, remove_master_by_name
from flows.admin_add_master_flow import start_add_master_flow
from collections import defaultdict
from aiogram.types import KeyboardButton

router = Router()

@router.message(F.text == "📅 Просмотр записей")
async def view_appointments(msg: types.Message):
    data = await list_appointments_db()
    if not data:
        await msg.answer("📭 Записей пока нет.")
        return

    # Surūšiuojame pagal dieną ir laiką
    sorted_data = sorted(data, key=lambda x: (x[6], x[7]))  # day, time

    text = "📅 <b>Список записей</b>\n\n"
    current_day = ""
    for _, name, phone, service, master, day, time_, _ in sorted_data:
        if day != current_day:
            current_day = day
            text += f"📆 <b>{day}</b>\n"
        text += f"⏰ {time_} — {service} у {master} (👤 {name}, 📞 {phone})\n"

    await msg.answer(text, parse_mode="HTML")

@router.message(F.text == "⚙️ Настройки")
async def admin_settings(msg: types.Message):
    if msg.from_user.id != OWNER_ID:
        await msg.answer("⛔ У вас нет доступа к настройкам.")
        return
    await msg.answer("⚙️ Настройки мастеров:", reply_markup=settings_kb())

@router.message(F.text == "➕ Добавить мастера")
async def admin_add_master(msg: types.Message):
    userflow[msg.from_user.id] = {"next": "add_master"}

    kb = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="⬅️ Назад")]],
        resize_keyboard=True
    )

    await msg.answer("Введите имя мастера:", reply_markup=kb)

@router.message(F.text == "➖ Удалить мастера")
async def remove_master_cmd(msg: types.Message):
    masters = await get_all_masters()
    if not masters:
        await msg.answer("❌ Нет мастеров для удаления.")
        return

    kb = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text=m[1])] for m in masters]
                 + [[types.KeyboardButton(text="⬅️ Назад")]],
        resize_keyboard=True
    )

    userflow[msg.from_user.id] = {"next": "delete_master"}
    await msg.answer("Выберите мастера для удаления:", reply_markup=kb)

@router.message(F.text == "🧾 Просмотр заявок")
async def admin_requests(msg: types.Message):
    if msg.from_user.id != OWNER_ID:
        return
    await msg.answer("📋 Заявки пока не реализованы.")