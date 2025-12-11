from aiogram import F, types, Router
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta
import aiosqlite

from utils.userflow import userflow
from database.masters import remove_master_by_name
from database.masters import add_master, get_all_masters
from database.services import get_services
from database.schedule import set_master_slots
from database.appointments import create_appointment_db
from handlers.users.booking import is_slot_available, is_valid_phone, parse_manual_input
from utils.config_loader import OWNER_ID
from keyboards.admin_keyboard import admin_menu_kb
from database.masters import WEEKDAYS

router = Router()

# ====== Выбор услуги ======
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


# ====== После выбора услуг — ввод дней ======
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

    await send_days_keyboard(c.message, flow)
    await c.answer()


    # Сразу отправляем клавиатуру дней (вместо ожидания текстового сообщения)
    kb = InlineKeyboardBuilder()
    for d in WEEKDAYS:
        kb.button(text=d, callback_data=f"day_toggle:{d}")
    kb.button(text="➡️ Далее", callback_data="finish_days")
    kb.adjust(3)

    # Отправляем сообщение с клавиатурой
    await c.message.answer("Выберите дни работы мастера через кнопки:", reply_markup=kb.as_markup())

    # Закрываем всплывающее (или просто подтверждаем callback)
    await c.answer()

@router.callback_query(lambda c: c.data.startswith("day_toggle:"))
async def day_toggle_cb(c: types.CallbackQuery):
    user_id = c.from_user.id
    flow = userflow.get(user_id)

    if not flow or flow.get("next") != "choose_days":
        return await c.answer("❌ Ошибка.")

    day = c.data.split(":", 1)[1]

    if "selected_days" not in flow:
        flow["selected_days"] = []

    if day in flow["selected_days"]:
        flow["selected_days"].remove(day)
        await c.answer(f"Убрано: {day}")
    else:
        flow["selected_days"].append(day)
        await c.answer(f"Добавлено: {day}")

async def send_days_keyboard(message, flow):
    kb = InlineKeyboardBuilder()

    for d in WEEKDAYS:
        text = f"✓ {d}" if d in flow["selected_days"] else d
        kb.button(text=text, callback_data=f"day_toggle:{d}")

    if flow["selected_days"]:
        kb.button(text="➡️ Далее", callback_data="finish_days")

    kb.adjust(3)
    await message.edit_reply_markup(kb.as_markup())


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

# ===================== УНИВЕРСАЛЬНЫЙ ХЕНДЛЕР ВВОДА =====================
@router.message(F.text & ~F.text.startswith("/"))
async def universal_input_handler(msg: types.Message):
    user_id = msg.from_user.id
    flow = userflow.get(user_id)
    if not flow:
        return  # Нет текущего потока

    text = msg.text.strip()

    # ===================== ДОБАВЛЕНИЕ МАСТЕРА =====================
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

    # ===================== НАЧАЛО РАБОТЫ =====================
    if flow.get("next") == "ask_start_time":
        try:
            flow["start_time"] = datetime.strptime(text, "%H:%M").time()
            flow["next"] = "ask_end_time"
            await msg.answer("Введите время окончания рабочего дня (например 17:00):")
        except ValueError:
            await msg.answer("❌ Неверный формат. Используйте ЧЧ:ММ.")
        return


    # ===================== КОНЕЦ РАБОТЫ =====================
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


    # ===================== ДЛИТЕЛЬНОСТЬ СЛОТА =====================
    if flow.get("next") == "ask_slot_duration":
        try:
            duration = float(text)
            if duration <= 0:
                await msg.answer("❌ Длительность должна быть положительной.")
                return

            flow["slot_duration"] = duration

            # Генерация времени слотов
            start_dt = datetime.combine(datetime.today(), flow["start_time"])
            end_dt = datetime.combine(datetime.today(), flow["end_time"])
            slots = []
            current = start_dt
            while current < end_dt:
                slots.append(current.strftime("%H:%M"))
                current += timedelta(hours=duration)

            flow["generated_slots"] = slots

            # Сохранение в БД
            await set_master_slots(
                master_name=flow["master_name"],
                start_time=flow["start_time"].strftime("%H:%M"),
                end_time=flow["end_time"].strftime("%H:%M"),
                selected_days=flow["selected_days"],
                slot_duration_hours=duration
            )

            # Вывод результата
            await msg.answer(
                f"🎉 Мастер <b>{flow['master_name']}</b> успешно добавлен!\n\n"
                f"Услуги: {', '.join(map(str, flow['selected_services']))}\n"
                f"Дни: {', '.join(flow['selected_days'])}\n"
                f"Слоты: {', '.join(slots)}"
            )

            # Завершение flow
            userflow.pop(user_id, None)

            # Возврат в админ-меню
            await msg.answer("Главное меню администратора:", reply_markup=admin_menu_kb())

        except ValueError:
            await msg.answer("❌ Введите число.")
        return

    # ====== Создание записи клиента ======
    if flow.get("next") in ["ask_name", "ask_phone", "manual_input"]:
        # Ввод имени
        if flow["next"] == "ask_name":
            flow["tmp_name"] = text
            flow["next"] = "ask_phone"
            await msg.answer("Введите телефон в международном формате, например +370 XXX XXX XX")
            return

        # Ввод телефона
        if flow["next"] == "ask_phone":
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
                f"✅ Запись подтверждена!\n"
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

        # Ручной ввод
        if flow["next"] == "manual_input":
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
                f"✅ Запись подтверждена!\n"
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