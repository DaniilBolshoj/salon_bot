from aiogram import types, F, Bot, Router
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import (
    list_services,
    get_all_masters,
    get_master_days,
    get_master_slots,
    slot_taken,
    user_has_appointment_db,
    create_appointment_db,
    WEEKDAYS,
    get_master_slots_auto,
    get_masters_by_service
)
from utils.utils import userflow
from utils.config import BOT_TOKEN
import aiosqlite
import re
from datetime import datetime, timedelta
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from main import dp
from aiogram.types import CallbackQuery

router = Router()
bot = Bot(token=BOT_TOKEN)

def weekday_from_date(date_str: str):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    for k, v in WEEKDAYS.items():
        if v == dt.weekday():
            return k

# ===================== НАЧАЛО ЗАПИСИ =====================
async def begin_booking(m: types.Message):
    user_id = m.from_user.id
    if await user_has_appointment_db(user_id):
        await m.answer("❌ У вас уже есть активная запись. Для изменения свяжитесь с админом.")
        return
    rows = await list_services()
    builder = InlineKeyboardBuilder()
    for name, _ in rows:
        builder.button(text=name, callback_data=f"svc:{name}")
    builder.adjust(2)
    await m.answer("Выберите услугу:", reply_markup=builder.as_markup())

# ===================== ВЫБОР УСЛУГИ =====================
@router.callback_query(F.data.startswith("svc:"))
async def cb_service(callback: CallbackQuery):
    service = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id

    # Парсим услугу
    try:
        service = callback.data.split(":", 1)[1]
    except:
        await callback.answer("Ошибка callback формата!", show_alert=True)
        return

    # Сохраняем услугу в userflow
    userflow[user_id] = {
        "service": service,
        "step": "service_chosen"
    }

    # Получаем мастеров по услуге
    masters = await get_masters_by_service(service)

    if not masters:
        await callback.answer(f"❌ Нет мастеров для услуги: {service}", show_alert=True)
        await callback.answer()
        return

    # Генерация кнопок мастеров
    kb = InlineKeyboardBuilder()

    for m in masters:
        kb.button(text=m, callback_data=f"m:{m}")

    kb.adjust(1)

    await callback.message.edit_text(
        f"Вы выбрали услугу: <b>{service}</b>\nВыберите мастера:",
        reply_markup=kb.as_markup()
    )

# ===================== ВЫБОР МАСТЕРА =====================
@router.callback_query(F.data.startswith("m:"))
async def cb_master(callback: CallbackQuery):
    master = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id

    # Проверяем userflow
    flow = userflow.get(user_id)
    if not flow or "service" not in flow:
        await callback.answer("Сначала выберите услугу!", show_alert=True)
        return

    flow["master"] = master
    flow["step"] = "master_chosen"
    userflow[user_id] = flow

    # Получаем дни работы мастера
    master_days = await get_master_days(master)
    if not master_days:
        await callback.message.edit_text(
            f"❌ Мастер {master} не имеет рабочих дней."
        )
        return

    # Превращаем дни недели в реальные даты
    available_dates = await get_available_dates(master_days, days_ahead=14)

    kb = InlineKeyboardBuilder()
    for d in available_dates:
        kb.button(text=d, callback_data=f"day:{d}")
    kb.adjust(2)

    await callback.message.edit_text(
        f"📅 Доступные дни для мастера <b>{master}</b>:",
        reply_markup=kb.as_markup()
    )

@router.callback_query(F.data.startswith("day:"))
async def cb_day(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in userflow or "master" not in userflow[user_id]:
        await callback.answer("Ошибка: выберите мастера сначала", show_alert=True)
        return

    try:
        selected_day = callback.data.split(":", 1)[1]
    except:
        await callback.answer("Ошибка формата даты!", show_alert=True)
        return
    
    await callback.answer()
    
    # Обновляем сообщение вместо отправки нового
    await callback.message.edit_text(
        f"📅 Вы выбрали дату: <b>{selected_day}</b>"
    )
    
    userflow[user_id]["day"] = selected_day
    master_name = userflow[user_id]["master"]

    try:
        # Получаем слоты
        slots = await get_master_slots_auto(master_name)

        # Фильтруем слоты только по выбранному дню
        kb = InlineKeyboardBuilder()
        for day, time in slots:
            if day == selected_day:
                kb.button(
                    text=time,
                    callback_data=f"slot_{day}_{time}_{master_name}"
                )
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

    except Exception as e:
        await callback.message.answer(f"Ошибка: {e}")

# ===================== ВЫБОР ВРЕМЕНИ =====================
@router.callback_query(F.data.startswith("slot_"))
async def cb_time(callback: CallbackQuery):
    # формат: slot_{day}_{time}_{master}
    try:
        _, day, time, master = callback.data.split("_", 3)
    except ValueError:
        await callback.answer("Ошибка формата слота.", show_alert=True)
        return

    user_id = callback.from_user.id
    flow = userflow.get(user_id)
    if not flow or "service" not in flow:
        await callback.answer("Сначала выберите услугу/мастера.", show_alert=True)
        return

    flow["time"] = time
    flow["day"] = day
    flow["master"] = master
    flow["step"] = "time_chosen"
    userflow[user_id] = flow

    await callback.message.answer(
        f"📋 Подтвердите запись:\n"
        f"Услуга: {flow['service']}\n"
        f"Мастер: {flow['master']}\n"
        f"День: {flow['day']}\n"
        f"Время: {flow['time']}\n\n"
        f"Отправьте свой номер телефона для завершения записи."
    )
    await callback.answer()

# ===================== ПОЛУЧЕНИЕ ТЕЛЕФОНА =====================
async def generic_text(m: types.Message):
    user_id = m.from_user.id
    flow = userflow.get(user_id)
    if not flow or flow.get("step") != "await_phone":
        return

    phone = m.text.strip()
    await create_appointment_db(
        user_id=user_id,
        name=m.from_user.full_name,
        phone=phone,
        service=flow["service"],
        master=flow["master"],
        day=flow["day"],
        time_=flow["time"]
    )

    await m.answer("✅ Вы успешно записаны! Мы вас ждём.")
    userflow.pop(user_id, None)

# ===================== РЕГИСТРАЦИЯ В РОУТЕРЕ =====================
router.message.register(begin_booking, F.text == "📅 Записаться")
router.callback_query.register(cb_service, F.data.startswith("svc:"))
router.callback_query.register(cb_master, F.data.startswith("m:"))
router.callback_query.register(cb_day, F.data.startswith("day:"))
router.callback_query.register(cb_time, F.data.startswith("time:"))
router.message.register(generic_text, F.text.regexp(r"^\+?\d{5,15}$"))

# ===================== УТИЛИТЫ =====================
async def is_valid_phone(phone: str, country_code: str = "+370") -> bool:
    pattern = r"^\+\d{7,15}$"
    return bool(re.match(pattern, phone)) and phone.startswith(country_code)

async def parse_manual_input(text: str):
    try:
        date_str, time_str, phone = map(str.strip, text.split(","))
        datetime.strptime(date_str, "%Y-%m-%d")
        datetime.strptime(time_str, "%H:%M")
        return date_str, time_str, phone
    except Exception:
        return None, None, None

async def get_available_days(days_count: int = 7):
    days = []
    for i in range(days_count):
        day = datetime.now() + timedelta(days=i)
        days.append(day.strftime("%Y-%m-%d"))
    return days

async def get_available_dates(master_days: list, days_ahead=14):
    today = datetime.today()
    available_dates = []
    for i in range(days_ahead):
        day = today + timedelta(days=i)
        if day.weekday() in [WEEKDAYS[d] for d in master_days]:
            available_dates.append(day.strftime("%Y-%m-%d"))
    return available_dates

async def is_slot_available(master: str, date_str: str, time_: str) -> bool:
    async with aiosqlite.connect("your_db_path_here.db") as db:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        weekday = dt.weekday()
        cur = await db.execute("""
            SELECT md.day FROM master_days md
            JOIN masters m ON m.id = md.master_id
            WHERE m.name=?
        """, (master,))
        master_days = [r[0] for r in await cur.fetchall()]
        if not master_days:
            return False
        allowed_weekdays = [WEEKDAYS[d] for d in master_days]
        if weekday not in allowed_weekdays:
            return False
        cur = await db.execute("""
            SELECT ms.time
            FROM master_slots ms
            JOIN masters m ON m.id = ms.master_id
            JOIN master_days md ON md.master_id = m.id
            WHERE m.name=? AND md.day=?
        """, (master, [d for d in master_days if WEEKDAYS[d]==weekday][0]))
        allowed_slots = [r[0] for r in await cur.fetchall()]
        if time_ not in allowed_slots:
            return False
        cur = await db.execute("SELECT 1 FROM appointments WHERE master=? AND day=? AND time=?", (master, date_str, time_))
        if await cur.fetchone():
            return False
        return True

async def generate_slots_buttons(master_name, selected_weekdays, start_time="08:00", end_time="17:00", slot_duration_hours=1, days_ahead=6):
    buttons = InlineKeyboardMarkup(row_width=2)
    today = datetime.today()
    added_dates = 0
    current_day = today

    while added_dates < days_ahead:
        weekday_str = [k for k,v in WEEKDAYS.items() if v == current_day.weekday()][0]
        if weekday_str in selected_weekdays:
            day_str = current_day.strftime("%Y-%m-%d")
            btn = InlineKeyboardButton(text=day_str, callback_data=f"book_{master_name}_{day_str}")
            buttons.add(btn)
            added_dates += 1
        current_day += timedelta(days=1)

    manual_btn = InlineKeyboardButton(text="Записаться вручную", callback_data=f"book_manual_{master_name}")
    buttons.add(manual_btn)

    return buttons