from aiogram import types, F, Router, Bot
from aiogram.filters import Command
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import aiosqlite
from datetime import datetime, timedelta
from handlers.booking import is_slot_available, is_valid_phone, parse_manual_input, router as booking_router, begin_booking

from database import (
    get_setting, DB_PATH, create_appointment_db,
    list_appointments_db, add_master, remove_master,
    get_dates_window, set_master_days, set_master_slots, get_all_masters, WEEKDAYS
)
from utils.config import OWNER_ID
from utils.utils import userflow, validate_phone_format, phone_belongs_to_country
import re
from utils.keyboard import main_menu_kb, admin_menu_kb, settings_kb
import json
import os 

router = Router()
MASTERS_FILE = "database/masters.json"

flow = {"start_time": "08:00", "end_time": "17:00"}  # Example initialization of flow

start_time = datetime.strptime(flow["start_time"], "%H:%M")  # введённое админом
end_time = datetime.strptime(flow["end_time"], "%H:%M")
service_duration = 1  # в часах или минутах

router.include_router(booking_router)

# =================== InlineKeyboard для конкретного мастера ===================
def get_master_inline_kb(master: dict):
    kb = InlineKeyboardBuilder()
    if master["status"] == "работает":
        kb.button(text="🌴 Отправить в отпуск", callback_data=f"vacation:{master['name']}")
    else:
        kb.button(text="🔙 Отменить отпуск", callback_data=f"cancel_vac:{master['name']}")
    kb.button(text="🗓 Настроить дни/часы", callback_data=f"set_schedule:{master['name']}")
    kb.button(text="💇 Настроить услуги", callback_data=f"set_services:{master['name']}")
    kb.button(text="❌ Удалить", callback_data=f"del_master:{master['name']}")
    kb.button(text="⬅️ Назад", callback_data="back_masters")
    kb.adjust(1)
    return kb.as_markup()

# =================== СТАРТ ===================
@router.message(Command("start"))
async def cmd_start(msg: types.Message):
    if msg.from_user.id == OWNER_ID:
        await msg.answer("👑 Добро пожаловать, админ!", reply_markup=admin_menu_kb())
    else:
        await msg.answer("👋 Добро пожаловать! Нажмите «📅 Записаться», чтобы выбрать услугу.",
                         reply_markup=main_menu_kb())

# =================== АДМИН ===================
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

# Кнопка добавления мастера
@router.message(F.text == "➕ Добавить мастера")
async def admin_add_master(msg: types.Message):
    userflow[msg.from_user.id] = {"next": "add_master"}
    await msg.answer("Введите имя нового мастера:")   

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
    userflow[msg.from_user.id] = {"next": "delete_master"}  # <- обязательно
    await msg.answer("Выберите мастера для удаления:", reply_markup=kb)

@router.message(F.text == "🧾 Просмотр заявок")
async def admin_requests(msg: types.Message):
    if msg.from_user.id != OWNER_ID:
        return
    await msg.answer("📋 Заявки пока не реализованы.")
    
# Главное меню
@router.message(F.text == "🏠 Главное меню")
async def back_to_main_menu(msg: types.Message):
    if msg.from_user.id == OWNER_ID:
        await msg.answer("🏠 Возврат в главное меню.", reply_markup=main_menu_kb(is_owner=True))
    else:
        await msg.answer("🏠 Возврат в главное меню.", reply_markup=main_menu_kb())

# Админ-меню
@router.message(F.text == "🏠 Админ-меню")
async def open_admin_menu(msg: types.Message):
    if msg.from_user.id == OWNER_ID:
        await msg.answer("⚙️ Админ-панель открыта.", reply_markup=admin_menu_kb())
    else:
        await msg.answer("⛔ У вас нет доступа к админ-панели.")

# =================== ГЛАВНОЕ МЕНЮ ===================
@router.message(F.text == "🏢 О нас")
async def about(m: Message):
    await m.answer("💖 Салон красоты — запись через бота. Для вопросов используйте Контакты.")

@router.message(F.text == "💇 Услуги")
async def services_list(m: types.Message):
    text = (
        "💇 Наши услуги:\n"
        "• Стрижка — 20€\n"
        "• Окрашивание — 35€\n"
        "• Маникюр — 15€\n"
        "• Массаж — 40€"
    )
    await m.answer(text)

@router.message(F.text == "💬 Контакты")
async def contacts(m: Message):
    await m.answer("📞 Телефон: +370 XXX XXX\n📍 Адрес: Вильнюс\n"
                   "Нажмите «📅 Записаться» для выбора времени.")

@router.message(F.text == "🧠 AI-помощник")
async def ai_helper(m: Message):
    await m.answer("🤖 AI-помощник временно недоступен. Попробуйте позже.")

# =================== ЗАПИСЬ ===================
@router.message(F.text == "📅 Записаться") 
async def book_appointment(msg: types.Message): 
    # Показываем список услуг 
    services = ["Стрижка", "Окрашивание", "Маникюр", "Массаж"] 
    kb = InlineKeyboardBuilder() 
    for s in services: 
        kb.button(text=s, callback_data=f"svc:{s}") 
    kb.adjust(2) 
    await msg.answer("💇 Выберите услугу:", reply_markup=kb.as_markup())

# =================== НАСТРОЙКИ АДМИНА ===================  
# --- отдельные хендлеры для кнопок настроек ---
@router.message(F.text == "🌴 Отправить мастера в отпуск")
async def send_master_vacation(msg: types.Message):
    await msg.answer("Выберите мастера для отпуска... (пока заглушка)")

@router.message(F.text == "🗓 Настроить дни/часы")
async def set_master_schedule(msg: types.Message):
    await msg.answer("Настройка дней и часов работы мастеров... (пока заглушка)")

@router.message(F.text == "💇 Настроить услуги")
async def set_master_services(msg: types.Message):
    await msg.answer("Настройка услуг и цен... (пока заглушка)")

@router.message(F.text == "⬅️ Назад в меню")
async def back_to_admin_menu(msg: types.Message):
    await msg.answer("Возврат в админ-меню", reply_markup=admin_menu_kb())

# ===================== УНИВЕРСАЛЬНЫЙ ХЕНДЛЕР ВВОДА =====================
@router.message(F.text & ~F.text.startswith("/"))
async def universal_input_handler(msg: types.Message):
    user_id = msg.from_user.id
    flow = userflow.get(user_id)
    if not flow:
        return  # Нет текущего потока, игнорируем

    text = msg.text.strip()

    # === После добавления мастера в universal_input_handler ===
    if flow.get("next") == "add_master":
        if text == "⬅️ Назад":
            userflow.pop(user_id, None)
            await msg.answer("Отмена добавления мастера.", reply_markup=admin_menu_kb())
            return

        # Добавляем мастера в БД
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR IGNORE INTO masters (name) VALUES (?)", (text,))
            await db.commit()

        # ВАЖНО! создаём временный flow
        userflow[user_id] = {
            "master_name": text,
            "selected_services": [],
            "next": "choose_services"
        }

        # Показываем кнопки выбора услуг
        kb = InlineKeyboardBuilder()
        services = ["Стрижка", "Окрашивание", "Маникюр", "Массаж"]
        for s in services:
            kb.button(text=s, callback_data=f"adm_set_service:{text}:{s}")
        kb.button(text="✅ Готово", callback_data=f"adm_finish_services:{text}")
        kb.adjust(2)

        await msg.answer(
            f"Выберите услуги для мастера {text}:",
            reply_markup=kb.as_markup()
        )
        return

    if flow.get("next") == "delete_master":
        if text == "⬅️ Назад":
            userflow.pop(user_id, None)
            await msg.answer("Возврат в меню.", reply_markup=admin_menu_kb())
            return
        masters = await get_all_masters()
        if text in masters:
            await remove_master(text)
            userflow.pop(user_id, None)
            await msg.answer(f"🗑 Мастер {text} удалён.", reply_markup=admin_menu_kb())
        else:
            await msg.answer("❌ Выберите мастера из списка.")
        return

    # --- Ввод часов работы мастера ---
    if flow.get("next") in ["ask_start_time", "ask_end_time", "ask_slot_duration"]:
        if flow["next"] == "ask_start_time":
            try:
                flow["start_time"] = datetime.strptime(text, "%H:%M").time()
                flow["next"] = "ask_end_time"
                await msg.answer(f"Начало рабочего дня установлено: {text}\nТеперь введите конец рабочего дня (например 17:00):")
            except ValueError:
                await msg.answer("❌ Неверный формат времени! Используйте ЧЧ:ММ.")
            return

        if flow["next"] == "ask_end_time":
            try:
                end_time = datetime.strptime(text, "%H:%M").time()
                if end_time <= flow["start_time"]:
                    await msg.answer("❌ Конец рабочего дня должен быть позже начала!")
                    return
                flow["end_time"] = end_time
                flow["next"] = "ask_slot_duration"
                await msg.answer("Теперь введите длительность одного слота в часах (например 1):")
            except ValueError:
                await msg.answer("❌ Неверный формат времени! Используйте ЧЧ:ММ.")
            return

        if flow["next"] == "ask_slot_duration":
            try:
                duration = float(text)
                if duration <= 0:
                    await msg.answer("❌ Длительность должна быть положительной!")
                    return
                flow["slot_duration"] = duration

                # Генерируем слоты в flow (для показа админу)
                start_dt = datetime.combine(datetime.today(), flow["start_time"])
                end_dt = datetime.combine(datetime.today(), flow["end_time"])
                slots = []
                current = start_dt
                while current < end_dt:
                    slots.append(current.strftime("%H:%M"))
                    current += timedelta(hours=duration)

                flow["selected_slots"] = slots

                # ================== ВАЖНО ==================
                # Записываем слоты в БД для выбранных дней
                await set_master_slots(
                    master_name=flow["master_name"],
                    start_time=flow["start_time"].strftime("%H:%M"),
                    end_time=flow["end_time"].strftime("%H:%M"),
                    selected_days=flow["selected_days"],
                    slot_duration_hours=duration
                )
                # ==========================================

                await msg.answer(
                    f"✅ Настройка завершена для {flow['master_name']}!\n"
                    f"Дни: {', '.join(flow.get('selected_days', []))}\n"
                    f"Слоты: {', '.join(slots)}"
                )
                userflow.pop(user_id, None)
            except ValueError:
                await msg.answer("❌ Введите число для длительности слота.")
            return

    # --- Ввод имени и телефона пользователя ---
    if flow.get("next") in ["ask_name", "ask_phone", "manual_input"]:
        # Ввод имени
        if flow.get("next") == "ask_name":
            flow["tmp_name"] = text
            flow["next"] = "ask_phone"
            await msg.answer("Спасибо! Теперь введите телефон в международном формате, пример +370 XXX XXX XX")
            return

        # Ввод телефона
        if flow.get("next") == "ask_phone":
            phone = text
            if not await is_valid_phone(phone):
                await msg.answer("❌ Неверный формат номера или код страны должен быть +370.")
                return

            master = flow["master"]
            day = flow["day"]
            time_ = flow["time"]

            if not await is_slot_available(master, day, time_):
                await msg.answer("❌ Выбранный слот занят или недоступен.")
                return

            name = flow.get("tmp_name", "Не указано")
            await create_appointment_db(user_id, name, phone, flow["service"], master, day, time_)
            userflow.pop(user_id, None)

            await msg.answer(
                f"✅ Запись подтверждена!\n\n"
                f"<b>Услуга:</b> {flow['service']}\n"
                f"<b>Мастер:</b> {master}\n"
                f"<b>Дата:</b> {day}\n"
                f"<b>Время:</b> {time_}\n"
                f"<b>Имя:</b> {name}\n"
                f"<b>Телефон:</b> {phone}"
            )

            try:
                bot = msg.bot
                await bot.send_message(
                    OWNER_ID,
                    f"📩 Новая запись:\n{flow['service']} | {master} | {day} {time_}\nИмя: {name}\nТелефон: {phone}"
                )
            except Exception:
                pass
            return

        # Ручной ввод даты/времени/телефона
        if flow.get("next") == "manual_input":
            day, time_, phone = await parse_manual_input(text)
            if not day or not time_ or not phone:
                await msg.answer("❌ Неверный формат! Используйте `YYYY-MM-DD, HH:MM, +370XXXXXXX`")
                return
            if not await is_valid_phone(phone):
                await msg.answer("❌ Неверный формат телефона или код страны должен быть +370.")
                return

            master = flow["master"]
            if not await is_slot_available(master, day, time_):
                await msg.answer("❌ Выбранный слот занят или недоступен.")
                return

            name = "Не указано"
            await create_appointment_db(user_id, name, phone, flow["service"], master, day, time_)
            userflow.pop(user_id, None)

            await msg.answer(
                f"✅ Запись подтверждена!\n\n"
                f"<b>Услуга:</b> {flow['service']}\n"
                f"<b>Мастер:</b> {master}\n"
                f"<b>Дата:</b> {day}\n"
                f"<b>Время:</b> {time_}\n"
                f"<b>Телефон:</b> {phone}"
            )

            try:
                bot = msg.bot
                await bot.send_message(
                    OWNER_ID,
                    f"📩 Новая запись:\n{flow['service']} | {master} | {day} {time_}\nТелефон: {phone}"
                )
            except Exception:
                pass
            return

# ===================== ВЫБОР УСЛУГ =====================
@router.callback_query(F.data.startswith("adm_set_service:"))
async def adm_set_master_services(callback: types.CallbackQuery):
    _, master_name, service = callback.data.split(":", 2)
    user_id = callback.from_user.id

    flow = userflow.get(user_id)
    if not flow:
        flow = userflow.setdefault(user_id, {"master_name": master_name, "selected_services": []})

    # Добавляем в список во временном userflow
    if service not in flow["selected_services"]:
        flow["selected_services"].append(service)

    # Добавляем сразу в БД
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT services FROM masters WHERE name=?", (master_name,))
        row = await cur.fetchone()
        existing = (row[0].split(",") if row and row[0] else [])
        if service not in existing:
            existing.append(service)
        await db.execute("UPDATE masters SET services=? WHERE name=?", (",".join(existing), master_name))
        await db.commit()

    await callback.answer(f"✅ Услуга {service} добавлена")

    # Обновляем клавиатуру
    kb = InlineKeyboardBuilder()
    services = ["Стрижка", "Окрашивание", "Маникюр", "Массаж"]
    for s in services:
        kb.button(text=s, callback_data=f"adm_set_service:{master_name}:{s}")
    kb.button(text="✅ Готово", callback_data=f"adm_finish_services:{master_name}")
    kb.adjust(2)

    await callback.message.edit_text(
        f"Услуга {service} добавлена мастеру {master_name}!\n"
        f"Вы можете добавить ещё или нажать «Готово».",
        reply_markup=kb.as_markup()
    )

#===================== ЗАВЕРШЕНИЕ ВЫБОРА УСЛУГ =====================    
@router.callback_query(F.data.startswith("adm_finish_services:"))
async def adm_finish_service_selection(callback: types.CallbackQuery):
    _, master_name = callback.data.split(":", 1)
    user_id = callback.from_user.id
    userflow[user_id] = {"master_name": master_name, "selected_days": [], "selected_slots": [], "next": "choose_days"}

    flow = userflow.get(user_id)
    if not flow:
        userflow[user_id] = {"master_name": master_name}

    userflow[user_id].update({
        "selected_days": [],
        "next": "choose_days"
    })

    # Показываем выбор дней
    kb = InlineKeyboardBuilder()
    days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    for d in days:
        kb.button(text=d, callback_data=f"set_day:{d}")
    kb.button(text="Готово", callback_data="days_done")
    kb.adjust(2)

    await callback.message.edit_text(
        f"Выберите рабочие дни для мастера {master_name}:",
        reply_markup=kb.as_markup()
    )

# ===================== МУЛЬТИВЫБОР ДНЕЙ =====================
@router.callback_query(F.data.startswith("set_day:"))
async def adm_select_master_days(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    day = callback.data.split(":")[1]

    flow = userflow.get(user_id)
    if not flow:
        await callback.answer("❌ Ошибка.")
        return

    selected_days = flow.setdefault("selected_days", [])

    # Добавляем или убираем день из выбранных
    if day in selected_days:
        selected_days.remove(day)
    else:
        selected_days.append(day)

    # Обновляем клавиатуру с отметкой выбранных дней
    days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    kb = InlineKeyboardBuilder()
    for d in days:
        text = f"✅ {d}" if d in selected_days else d
        kb.button(text=text, callback_data=f"set_day:{d}")
    kb.button(text="Готово", callback_data="days_done")
    kb.adjust(2)

    await callback.message.edit_text(
        f"Выберите рабочие дни для {flow.get('master_name', 'неизвестного мастера')}:",
        reply_markup=kb.as_markup()
    )
    await callback.answer()

# ===================== ЗАВЕРШЕНИЕ ВЫБОРА ДНЕЙ =====================
@router.callback_query(F.data == "days_done")
async def adm_finish_days_selection(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    flow = userflow.get(user_id)
    if not flow or not flow.get("selected_days"):
        await callback.answer("❌ Вы не выбрали ни одного дня.")
        return

    name = flow["master_name"]
    selected_days = flow["selected_days"]

    # Сохраняем выбранные дни в БД
    await set_master_days(name, selected_days)

    # Переходим к выбору начала и конца рабочего дня
    await callback.message.edit_text(
        f"Выберите начало рабочего дня для {name} (формат ЧЧ:ММ, например 08:00):"
    )
    flow["next"] = "ask_start_time"
    await callback.answer()
    
# ===================== ВЫБОР ВРЕМЕНИ РАБОЧЕГО ДНЯ МАСТЕРА =====================
@router.callback_query(F.data == "set_work_time")
async def adm_set_work_time(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    flow = userflow.get(user_id)

    if not flow:
        await callback.answer("❌ Ошибка, поток не найден.")
        return

    # Просим выбрать время начала
    kb = InlineKeyboardBuilder()
    # Диапазон времени можно сделать с 6 до 22 часов, шаг 1 час
    for hour in range(6, 23):
        time_str = f"{hour:02}:00"
        kb.button(text=time_str, callback_data=f"adm_start_time:{time_str}")
    kb.adjust(4)

    await callback.message.edit_text(
        f"Выберите время начала рабочего дня для {flow['master_name']}:",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


# ===================== ВЫБОР КОНЦА РАБОЧЕГО ДНЯ =====================
@router.callback_query(F.data.startswith("start_time:"))
async def adm_choose_start_time(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    flow = userflow.get(user_id)
    start_time = callback.data.split(":")[1]

    flow["start_time"] = start_time
    kb = InlineKeyboardBuilder()
    # Конец рабочего дня должен быть больше начала
    start_hour = int(start_time.split(":")[0])
    for hour in range(start_hour + 1, 24):
        time_str = f"{hour:02}:00"
        kb.button(text=time_str, callback_data=f"adm_end_time:{time_str}")
    kb.adjust(4)

    await callback.message.edit_text(
        f"Выберите время окончания рабочего дня для {flow['master_name']}:",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("end_time:"))
async def choose_end_time(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    flow = userflow.get(user_id)
    end_time = callback.data.split(":")[1]

    flow["end_time"] = end_time
    flow["next"] = "ask_slot_duration"

    await callback.message.edit_text(
        f"Рабочий день установлен: {flow['start_time']} - {flow['end_time']}\n"
        f"Теперь введите длительность одного слота в часах (например 1):"
    )
    await callback.answer()
    

async def generate_slots_buttons(master_name, selected_weekdays, start_time, end_time, slot_duration_hours=1, days_ahead=6):
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

    # Добавляем кнопку "Записаться вручную" в отдельный ряд
    manual_btn = InlineKeyboardButton(text="Записаться вручную", callback_data=f"book_manual_{master_name}")
    buttons.add(manual_btn)

    return buttons

router.message.register(universal_input_handler)