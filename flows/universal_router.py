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

router = Router()

# ====== Выбор услуги для мастера ======
@router.callback_query(lambda c: c.data.startswith("adm_set_service:"))
async def adm_set_service_cb(c: types.CallbackQuery):
    user_id = c.from_user.id
    flow = userflow.get(user_id)
    if not flow or flow.get("next") != "choose_services":
        await c.answer("❌ Ошибка состояния")
        return

    service_id = int(c.data.split(":")[1])
    if service_id not in flow["selected_services"]:
        flow["selected_services"].append(service_id)
        await c.answer("✅ Услуга выбрана")
    else:
        flow["selected_services"].remove(service_id)
        await c.answer("❌ Услуга убрана")

@router.callback_query(lambda c: c.data == "adm_finish_services")
async def adm_finish_services_cb(c: types.CallbackQuery):
    user_id = c.from_user.id
    flow = userflow.get(user_id)
    if not flow or flow.get("next") != "choose_services":
        await c.answer("❌ Ошибка состояния")
        return

    if not flow["selected_services"]:
        await c.answer("❌ Выберите хотя бы одну услугу")
        return

    # Сохраняем выбранные услуги в БД (если нужно)
    # await update_master_services(flow["master_id"], flow["selected_services"])

    # Меняем следующий шаг flow на настройку слотов
    flow["next"] = "ask_start_time"

    await c.message.edit_text(
        f"✅ Мастер {flow['master_name']} добавлен!\n"
        f"Выбранные услуги: {', '.join(map(str, flow['selected_services']))}\n\n"
        f"Введите начало рабочего дня (например 09:00):"
    )

    await c.answer()  # убирает "часики" на кнопке

# ===================== УНИВЕРСАЛЬНЫЙ ХЕНДЛЕР ВВОДА =====================
@router.message(F.text & ~F.text.startswith("/"))
async def universal_input_handler(msg: types.Message):
    user_id = msg.from_user.id
    flow = userflow.get(user_id)
    if not flow:
        return  # Нет текущего потока

    text = msg.text.strip()

    # ====== Добавление мастера ======
    if flow.get("next") == "add_master":
        if text == "⬅️ Назад":
            userflow.pop(user_id, None)
            await msg.answer("Отмена добавления мастера.", reply_markup=admin_menu_kb())
            return

        # Создаём мастера
        master_id = await add_master(text, [])
        userflow[user_id] = {
            "master_id": master_id,
            "master_name": text,
            "selected_services": [],
            "next": "choose_services"
        }

        services = await get_services()
        if not services:
            await msg.answer("❌ Нет услуг, добавьте хотя бы одну.")
            return

        # Кнопки для выбора услуг
        kb = InlineKeyboardBuilder()
        for s_id, s_name, _ in services:
            kb.button(text=s_name, callback_data=f"adm_set_service:{s_id}")
        kb.button(text="✅ Готово", callback_data="adm_finish_services")
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

        success = await remove_master_by_name(text)
        if success:
            userflow.pop(user_id, None)
            await msg.answer(f"🗑 Мастер {text} удалён.", reply_markup=admin_menu_kb())
        else:
            await msg.answer("❌ Мастер с таким именем не найден.")
        return


    # ====== Настройка рабочего времени и слотов ======
    if flow.get("next") in ["ask_start_time", "ask_end_time", "ask_slot_duration"]:
        if flow["next"] == "ask_start_time":
            try:
                flow["start_time"] = datetime.strptime(text, "%H:%M").time()
                flow["next"] = "ask_end_time"
                await msg.answer(f"Начало рабочего дня установлено: {text}\nВведите конец рабочего дня (например 17:00):")
            except ValueError:
                await msg.answer("❌ Неверный формат времени! Используйте ЧЧ:ММ.")
            return

        if flow["next"] == "ask_end_time":
            try:
                end_time = datetime.strptime(text, "%H:%M").time()
                if end_time <= flow["start_time"]:
                    await msg.answer("❌ Конец дня должен быть позже начала!")
                    return
                flow["end_time"] = end_time
                flow["next"] = "ask_slot_duration"
                await msg.answer("Введите длительность слота в часах (например 1):")
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

                # Генерация слотов
                start_dt = datetime.combine(datetime.today(), flow["start_time"])
                end_dt = datetime.combine(datetime.today(), flow["end_time"])
                slots = []
                current = start_dt
                while current < end_dt:
                    slots.append(current.strftime("%H:%M"))
                    current += timedelta(hours=duration)
                flow["selected_slots"] = slots

                # Сохраняем в БД
                await set_master_slots(
                    master_name=flow["master_name"],
                    start_time=flow["start_time"].strftime("%H:%M"),
                    end_time=flow["end_time"].strftime("%H:%M"),
                    selected_days=flow.get("selected_days", []),
                    slot_duration_hours=duration
                )

                await msg.answer(
                    f"✅ Настройка завершена для {flow['master_name']}!\n"
                    f"Дни: {', '.join(flow.get('selected_days', []))}\n"
                    f"Слоты: {', '.join(slots)}"
                )
                userflow.pop(user_id, None)
            except ValueError:
                await msg.answer("❌ Введите число для длительности слота.")
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
