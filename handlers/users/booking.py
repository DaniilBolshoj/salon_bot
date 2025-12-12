from aiogram import types, F, Bot, Router
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import CallbackQuery

# ====== Database ======
from database.masters import get_masters_by_service, WEEKDAYS
from database.schedule import get_master_slots_auto, get_master_days
from database.services import get_services

# ====== Utils ======
from utils.userflow import userflow
from utils.config_loader import BOT_TOKEN

# ====== Flow ======
from flows.appointments_flow import (
    validate_phone,
    validate_slot,
    create_appointment,
    format_confirmation_message
)

# ====== Standard libs ======
from datetime import datetime, timedelta

router = Router()
bot = Bot(token=BOT_TOKEN)


# Преобразование даты → weekday
def weekday_from_date(date_str: str):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    for k, v in WEEKDAYS.items():
        if v == dt.weekday():
            return k


# ======================= 1. Выбор услуги ===============================
@router.message(F.text == "📅 Записаться")
async def book_appointment(msg: types.Message):
    services = await get_services()
    if not services:
        await msg.answer("Пока нет доступных услуг.")
        return

    kb = InlineKeyboardBuilder()
    for s in services:
        kb.button(text=s, callback_data=f"svc:{s}")
    kb.adjust(2)

    await msg.answer("💇 Выберите услугу:", reply_markup=kb.as_markup())


# ======================= 2. Выбор мастера ==============================
@router.callback_query(F.data.startswith("svc:"))
async def cb_service(callback: CallbackQuery):
    service = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id

    userflow[user_id] = {
        "service": service,
        "step": "service_chosen"
    }

    masters = await get_masters_by_service(service)
    if not masters:
        await callback.answer(f"❌ Нет мастеров для услуги: {service}", show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    for m in masters:
        kb.button(text=m, callback_data=f"m:{m}")
    kb.adjust(1)

    await callback.message.edit_text(
        f"Вы выбрали услугу: <b>{service}</b>\nВыберите мастера:",
        reply_markup=kb.as_markup()
    )


# ======================= 3. Выбор даты ================================
@router.callback_query(F.data.startswith("m:"))
async def cb_master(callback: CallbackQuery):
    master = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id

    flow = userflow.get(user_id)
    if not flow or "service" not in flow:
        await callback.answer("Сначала выберите услугу!", show_alert=True)
        return

    flow["master"] = master
    flow["step"] = "master_chosen"
    userflow[user_id] = flow

    master_days = await get_master_days(master)
    if not master_days:
        await callback.message.edit_text(f"❌ Мастер {master} не имеет рабочих дней.")
        return

    available_dates = await get_available_dates(master_days, days_ahead=14)

    kb = InlineKeyboardBuilder()
    for d in available_dates:
        kb.button(text=d, callback_data=f"day:{d}")
    kb.adjust(2)

    await callback.message.edit_text(
        f"📅 Доступные дни для мастера <b>{master}</b>:",
        reply_markup=kb.as_markup()
    )


# ======================= 4. Выбор времени ================================
@router.callback_query(F.data.startswith("day:"))
async def cb_day(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in userflow or "master" not in userflow[user_id]:
        await callback.answer("Ошибка: выберите мастера сначала", show_alert=True)
        return

    selected_day = callback.data.split(":", 1)[1]
    await callback.answer()
    await callback.message.edit_text(f"📅 Вы выбрали дату: <b>{selected_day}</b>")

    userflow[user_id]["day"] = selected_day
    master_name = userflow[user_id]["master"]

    slots = await get_master_slots_auto(master_name)

    kb = InlineKeyboardBuilder()
    for day, time in slots:
        if day == selected_day:
            if await validate_slot(master_name, day, time):
                kb.button(text=time, callback_data=f"slot:{master_name}:{day}:{time}")

    kb.adjust(3)

    if not kb.buttons:
        await callback.answer(
            f"❌ На {selected_day} у мастера {master_name} нет свободных слотов.",
            show_alert=True
        )
        return

    await callback.message.edit_text(
        f"🕓 Доступное время для мастера <b>{master_name}</b> на {selected_day}:",
        reply_markup=kb.as_markup()
    )


# ======================= 5. Пользователь выбрал слот ======================
@router.callback_query(F.data.startswith("slot:"))
async def cb_time(callback: CallbackQuery):
    _, master, day, time = callback.data.split(":")

    user_id = callback.from_user.id
    flow = userflow.get(user_id, {})

    flow.update({
        "master": master,
        "day": day,
        "time": time,
        "step": "await_phone"
    })
    userflow[user_id] = flow

    await callback.message.edit_text(
        f"📋 <b>Подтверждение записи</b>\n\n"
        f"💇 Услуга: <b>{flow['service']}</b>\n"
        f"🧑‍🎨 Мастер: <b>{flow['master']}</b>\n"
        f"📅 День: <b>{flow['day']}</b>\n"
        f"⏰ Время: <b>{flow['time']}</b>\n\n"
        f"Отправьте свой номер телефона.\nПример: +37060000000",
        parse_mode="HTML"
    )

    await callback.answer()


# ======================= 6. Пользователь вводит телефон ====================
@router.message(F.text)
async def phone_input(msg: types.Message):
    user_id = msg.from_user.id
    flow = userflow.get(user_id)

    if not flow or flow.get("step") != "await_phone":
        return

    phone = msg.text.strip()
    if not validate_phone(phone):
        await msg.answer("❌ Неверный формат номера. Пример: +37060000000")
        return

    result = await create_appointment(flow, user_id, name=msg.from_user.full_name, phone=phone)

    if not result["ok"]:
        await msg.answer(f"❌ {result['error']}")
        return

    await msg.answer(result["message"], parse_mode="HTML")
    userflow.pop(user_id, None)


# ======================= Утилита получения дат ============================
async def get_available_dates(master_days: list, days_ahead=14):
    today = datetime.today()
    available_dates = []
    for i in range(days_ahead):
        day = today + timedelta(days=i)
        if day.weekday() in [WEEKDAYS[d] for d in master_days]:
            available_dates.append(day.strftime("%Y-%m-%d"))
    return available_dates