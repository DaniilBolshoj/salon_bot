from aiogram import types, F, Router
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import CallbackQuery
from datetime import datetime, timedelta

from utils.userflow import userflow

# ===== Database =====
from database.masters import get_masters_by_service, WEEKDAYS
from database.schedule import get_master_slots_auto, get_master_days
from database.services import get_services, get_service_by_id

# ===== Flow =====
from flows.appointments_flow import (
    validate_phone,
    validate_slot,
    create_appointment
)

router = Router()

# ======================= 1. Выбор услуги ===============================
@router.message(F.text == "📅 Записаться")
async def book_appointment(msg: types.Message):
    services = await get_services()
    if not services:
        await msg.answer("Пока нет доступных услуг.")
        return

    kb = InlineKeyboardBuilder()
    for service_id, name, _ in services:
        kb.button(text=name, callback_data=f"svc:{service_id}")
    kb.adjust(2)

    await msg.answer("💇 Выберите услугу:", reply_markup=kb.as_markup())


# ======================= 2. Выбор мастера ==============================
@router.callback_query(F.data.startswith("svc:"))
async def cb_service(callback: CallbackQuery):
    service_id = int(callback.data.split(":")[1])
    service = await get_service_by_id(service_id)
    service_name = service[1]
    user_id = callback.from_user.id

    userflow[user_id] = {
        "service_id": service_id,
        "service_name": service_name,
        "step": "service_chosen"
    }

    masters = await get_masters_by_service(service_id)
    if not masters:
        await callback.answer("❌ Нет мастеров для этой услуги", show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    for master_id, master_name in masters:
        kb.button(text=master_name, callback_data=f"m:{master_id}")
    kb.adjust(1)

    await callback.message.edit_text(
        f"Вы выбрали услугу: <b>{service_name}</b>\nВыберите мастера:",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )


# ======================= 3. Выбор даты ================================
@router.callback_query(F.data.startswith("m:"))
async def cb_master(callback: CallbackQuery):
    master_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    flow = userflow.get(user_id)
    if not flow:
        await callback.answer("Сначала выберите услугу", show_alert=True)
        return

    flow["master_id"] = master_id
    flow["step"] = "master_chosen"

    master_days = await get_master_days(master_id)
    if not master_days:
        await callback.message.edit_text("❌ У мастера нет рабочих дней.")
        return

    dates = await get_available_dates(master_days)

    kb = InlineKeyboardBuilder()
    for d in dates:
        kb.button(text=d, callback_data=f"day:{d}")
    kb.adjust(2)

    await callback.message.edit_text(
        "📅 Выберите дату:",
        reply_markup=kb.as_markup()
    )


# ======================= 4. Выбор времени ================================
@router.callback_query(F.data.startswith("day:"))
async def cb_day(callback: CallbackQuery):
    user_id = callback.from_user.id
    flow = userflow.get(user_id)

    if not flow or "master_id" not in flow:
        await callback.answer("Ошибка", show_alert=True)
        return

    day = callback.data.split(":")[1]
    flow["day"] = day

    slots = await get_master_slots_auto(flow["master_id"])

    kb = InlineKeyboardBuilder()
    for d, t in slots:
        if d == day and await validate_slot(flow["master_id"], d, t):
            kb.button(text=t, callback_data=f"slot:{t}")

    kb.adjust(3)

    if not kb.buttons:
        await callback.answer("❌ Нет свободных слотов", show_alert=True)
        return

    await callback.message.edit_text(
        "🕓 Выберите время:",
        reply_markup=kb.as_markup()
    )


# ======================= 5. Выбор слота ======================
@router.callback_query(F.data.startswith("slot:"))
async def cb_time(callback: CallbackQuery):
    time = callback.data.split(":")[1]
    user_id = callback.from_user.id

    flow = userflow[user_id]
    flow["time"] = time
    flow["step"] = "await_phone"

    await callback.message.edit_text(
        f"📋 <b>Подтверждение</b>\n\n"
        f"💇 Услуга: <b>{flow['service_name']}</b>\n"
        f"📅 День: <b>{flow['day']}</b>\n"
        f"⏰ Время: <b>{time}</b>\n\n"
        f"Отправьте номер телефона (+370...)",
        parse_mode="HTML"
    )


# ======================= 6. Телефон ====================
@router.message(F.text & (F.text.startswith("+")))
async def phone_input(msg: types.Message):
    user_id = msg.from_user.id
    flow = userflow.get(user_id)

    if not flow or flow.get("step") != "await_phone":
        return

    if not validate_phone(msg.text):
        await msg.answer("❌ Неверный формат номера")
        return

    result = await create_appointment(
        flow=flow,
        user_id=user_id,
        name=msg.from_user.full_name,
        phone=msg.text
    )

    if not result["ok"]:
        await msg.answer(f"❌ {result['error']}")
        return

    await msg.answer(result["message"], parse_mode="HTML")
    userflow.pop(user_id)


# ======================= UTILS ============================
async def get_available_dates(master_days, days_ahead=14):
    today = datetime.today()
    result = []

    for i in range(days_ahead):
        day = today + timedelta(days=i)
        if day.weekday() in [WEEKDAYS[d] for d in master_days]:
            result.append(day.strftime("%Y-%m-%d"))

    return result