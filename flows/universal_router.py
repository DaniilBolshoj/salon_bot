from aiogram import F, types, Router
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta

from utils.userflow import userflow
from flows.appointments_flow import (
    validate_phone,
    validate_slot,
    parse_manual_input,
    create_appointment,
    format_confirmation_message
)
from utils.config_loader import OWNER_ID
from database.masters import (
    remove_master_by_name,
    add_master,
    WEEKDAYS
)
from database.services import get_services
from database.schedule import set_master_slots, get_master_slots_auto, get_master_days
from keyboards.admin_keyboard import admin_menu_kb

router = Router()

# ===================== АДМИН: выбор услуги =====================
@router.callback_query(lambda c: c.data.startswith("adm_set_service:"))
async def adm_set_service_cb(c: types.CallbackQuery):
    user_id = c.from_user.id
    flow = userflow.get(user_id)
    if not flow or flow.get("next") != "choose_services":
        await c.answer("❌ Ошибка.")
        return

    service_id = int(c.data.split(":")[1])
    if service_id not in flow["selected_services"]:
        flow["selected_services"].append(service_id)
        await c.answer("Добавлено")
    else:
        flow["selected_services"].remove(service_id)
        await c.answer("Убрано")


@router.callback_query(lambda c: c.data == "adm_finish_services")
async def adm_finish_services_cb(c: types.CallbackQuery):
    user_id = c.from_user.id
    flow = userflow.get(user_id)
    if not flow or flow.get("next") != "choose_services":
        return await c.answer("❌ Ошибка.")
    if not flow.get("selected_services"):
        return await c.answer("❌ Нужно выбрать хотя бы одну услугу.")

    flow["next"] = "choose_days"
    flow["selected_days"] = []
    bot_msg = await c.message.answer("Выберите дни работы мастера:")
    await send_days_keyboard(bot_msg, flow)
    await c.answer()


@router.callback_query(lambda c: c.data.startswith("day_toggle:"))
async def day_toggle_cb(c: types.CallbackQuery):
    user_id = c.from_user.id
    flow = userflow.get(user_id)
    if not flow or flow.get("next") != "choose_days":
        return await c.answer("❌ Ошибка.")

    day = c.data.split(":", 1)[1]
    flow.setdefault("selected_days", [])
    if day in flow["selected_days"]:
        flow["selected_days"].remove(day)
        await c.answer(f"Убрано: {day}")
    else:
        flow["selected_days"].append(day)
        await c.answer(f"Добавлено: {day}")

    await send_days_keyboard(c.message, flow)


async def send_days_keyboard(message, flow):
    kb = InlineKeyboardBuilder()
    for d in WEEKDAYS:
        text = f"✓ {d}" if d in flow.get("selected_days", []) else d
        kb.button(text=text, callback_data=f"day_toggle:{d}")
    if flow.get("selected_days"):
        kb.button(text="➡️ Далее", callback_data="finish_days")
    kb.adjust(3)
    await message.edit_reply_markup(reply_markup=kb.as_markup())


@router.callback_query(lambda c: c.data == "finish_days")
async def finish_days_cb(c: types.CallbackQuery):
    user_id = c.from_user.id
    flow = userflow.get(user_id)
    if not flow or flow.get("next") != "choose_days":
        return await c.answer("❌ Ошибка.")
    if not flow.get("selected_days"):
        return await c.answer("❌ Нужно выбрать хотя бы один день.")

    flow["next"] = "ask_start_time"
    await c.message.answer("Введите время начала рабочего дня (например 09:00):")
    await c.answer()

# ===================== Клиент: показать ещё дни =====================
@router.callback_query(lambda c: c.data == "show_more_days")
async def show_more_days_cb(c: types.CallbackQuery):
    user_id = c.from_user.id
    flow = userflow.get(user_id)
    if not flow or "master" not in flow:
        await c.answer("❌ Сначала выберите мастера и услугу.")
        return

    master_name = flow["master"]
    master_days = await get_master_days(master_name)
    if not master_days:
        await c.answer(f"❌ Мастер {master_name} не работает ближайшие дни.")
        return

    # Получаем слоты на следующие 20 дней
    slots = await get_master_slots_auto(master_name, days_ahead=20)
    day_slots = {}
    for day, time_ in slots:
        day_slots.setdefault(day, []).append(time_)

    if not day_slots:
        await c.answer("❌ Нет свободных дней для мастера.")
        return

    # Формируем сообщение
    msg_text = "📅 Ближайшие дни с доступными слотами:\n"
    for day in sorted(day_slots.keys()):
        msg_text += f"{day} — {len(day_slots[day])} свободных слотов\n"

    msg_text += "\nВведите дату, на которую хотите записаться (YYYY-MM-DD):"
    await c.message.answer(msg_text)
    flow["next"] = "manual_date"
    userflow[user_id] = flow
    await c.answer()


# ===================== Клиент: ручной ввод даты =====================
@router.message(F.text.regexp(r"^\d{4}-\d{2}-\d{2}$"))
async def manual_date_input(msg: types.Message):
    user_id = msg.from_user.id
    flow = userflow.get(user_id)
    if not flow or flow.get("next") != "manual_date":
        return

    chosen_date = msg.text.strip()
    master_name = flow["master"]
    master_days = await get_master_days(master_name)

    # Проверяем рабочий день мастера
    weekday_str = [k for k, v in WEEKDAYS.items() if v == datetime.strptime(chosen_date, "%Y-%m-%d").weekday()][0]
    if weekday_str not in master_days:
        await msg.answer(f"❌ Мастер {master_name} не работает в этот день ({weekday_str}).")
        return

    # Получаем слоты на этот день
    slots = await get_master_slots_auto(master_name, days_ahead=20)
    available_times = [time_ for day, time_ in slots if day == chosen_date]

    if not available_times:
        await msg.answer("❌ В этот день нет свободных слотов. Попробуйте другой день.")
        return

    # Сохраняем выбранную дату
    flow["day"] = chosen_date
    flow["next"] = "choose_slot_manual"
    userflow[user_id] = flow

    # Показ слотов инлайн
    kb = InlineKeyboardBuilder()
    for t in available_times:
        kb.button(text=t, callback_data=f"manual_slot:{chosen_date}_{t}")
    kb.adjust(3)
    await msg.answer(f"🕓 Доступные слоты на {chosen_date}:", reply_markup=kb.as_markup())


# ===================== Клиент: выбор слота из ручного ввода =====================
@router.callback_query(lambda c: c.data.startswith("manual_slot:"))
async def manual_slot_cb(c: types.CallbackQuery):
    user_id = c.from_user.id
    flow = userflow.get(user_id)
    if not flow or flow.get("next") != "choose_slot_manual":
        await c.answer("❌ Сначала выберите дату.")
        return

    _, day, time_ = c.data.split(":", 1)[1].split("_")
    flow["time"] = time_
    flow["day"] = day
    flow["next"] = "ask_phone"
    userflow[user_id] = flow

    await c.message.answer(f"Вы выбрали {day} {time_}.\n📋 Введите ваш номер телефона для записи (+370...):")
    await c.answer()


# ===================== Клиент: ввод телефона =====================
@router.message(F.text.regexp(r"^\+?\d{5,15}$"))
async def phone_input(msg: types.Message):
    user_id = msg.from_user.id
    flow = userflow.get(user_id)
    if not flow or flow.get("next") != "ask_phone":
        return

    phone = msg.text.strip()
    if not validate_phone(phone):
        await msg.answer("❌ Неверный номер. Используйте формат +370...")
        return

    flow["phone"] = phone

    # Проверяем слот
    if not await validate_slot(flow["master"], flow["day"], flow["time"]):
        await msg.answer("❌ Слот уже занят! Попробуйте другой день.")
        userflow.pop(user_id, None)
        return

    # Создаём запись
    app = await create_appointment(
        user_id=user_id,
        name=flow.get("tmp_name", msg.from_user.full_name),
        phone=phone,
        service=flow["service"],
        master=flow["master"],
        day=flow["day"],
        time_=flow["time"]
    )

    txt = format_confirmation_message(app)
    await msg.answer(txt)

    # Уведомление владельца
    try:
        await msg.bot.send_message(OWNER_ID, f"📩 Новая запись:\n{txt}")
    except:
        pass

    userflow.pop(user_id, None)


# ===================== УНИВЕРСАЛЬНЫЙ ХЕНДЛЕР ВВОДА =====================
@router.message(F.text & ~F.text.startswith("/"))
async def universal_input_handler(msg: types.Message):
    user_id = msg.from_user.id
    flow = userflow.get(user_id)
    if not flow:
        return

    text = msg.text.strip()

    # ====== Добавление мастера ======
    if flow.get("next") == "add_master":
        if text == "⬅️ Назад":
            userflow.pop(user_id, None)
            await msg.answer("Отмена.", reply_markup=admin_menu_kb())
            return

        master_id = await add_master(text, [])
        userflow[user_id] = {
            "next": "choose_services",
            "master_id": master_id,
            "master_name": text,
            "selected_services": []
        }

        services = await get_services()
        if not services:
            await msg.answer("❌ Нет услуг. Добавьте услугу.")
            userflow.pop(user_id, None)
            return

        kb = InlineKeyboardBuilder()
        for s_id, s_name, _ in services:
            kb.button(text=s_name, callback_data=f"adm_set_service:{s_id}")
        kb.button(text="➡️ Далее", callback_data="adm_finish_services")
        kb.adjust(2)

        await msg.answer(
            f"Выберите услуги для мастера <b>{text}</b>:",
            reply_markup=kb.as_markup()
        )
        return

    # ====== Настройка расписания ======
    if flow.get("next") == "ask_start_time":
        try:
            flow["start_time"] = datetime.strptime(text, "%H:%M").time()
            flow["next"] = "ask_end_time"
            await msg.answer("Введите время окончания рабочего дня (например 17:00):")
        except ValueError:
            await msg.answer("❌ Неверный формат. Используйте ЧЧ:ММ.")
        return

    if flow.get("next") == "ask_end_time":
        try:
            end = datetime.strptime(text, "%H:%M").time()
            if end <= flow["start_time"]:
                await msg.answer("❌ Конец должен быть позже начала.")
                return
            flow["end_time"] = end
            flow["next"] = "ask_slot_duration"
            await msg.answer("Введите длительность слота в часах (например 1):")
        except ValueError:
            await msg.answer("❌ Неверный формат.")
        return

    if flow.get("next") == "ask_slot_duration":
        try:
            duration = float(text)
            if duration <= 0:
                await msg.answer("❌ Длительность должна быть положительной.")
                return
            flow["slot_duration"] = duration
            await set_master_slots(
                master_name=flow["master_name"],
                start_time=flow["start_time"].strftime("%H:%M"),
                end_time=flow["end_time"].strftime("%H:%M"),
                selected_days=flow["selected_days"],
                slot_duration_hours=duration
            )
            userflow.pop(user_id, None)
            await msg.answer(f"🎉 Мастер <b>{flow['master_name']}</b> успешно добавлен!\n"
                             f"Услуги: {', '.join(map(str, flow['selected_services']))}\n"
                             f"Дни: {', '.join(flow['selected_days'])}")
            await msg.answer("Главное меню администратора:", reply_markup=admin_menu_kb())
        except ValueError:
            await msg.answer("❌ Введите число.")
        return

    # ====== Удаление мастера ======
    if flow.get("next") == "delete_master":
        if text == "⬅️ Назад":
            userflow.pop(user_id, None)
            await msg.answer("Возврат в меню.", reply_markup=admin_menu_kb())
            return

        success = await remove_master_by_name(text)
        if success:
            userflow.pop(user_id, None)
            await msg.answer(f"🗑 Мастер {text} удалён.", reply_markup=admin_menu_kb())
        else:
            await msg.answer("❌ Мастер с таким именем не найден.")
        return