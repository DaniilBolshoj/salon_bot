from aiogram import F, types, Router
import aiosqlite
from utils.userflow import userflow
from database import DB_PATH
from database.appointments import create_appointment_db
from database.masters import get_all_masters, remove_master
from handlers.users.booking import is_slot_available, is_valid_phone, parse_manual_input
from keyboards.admin_keyboard import admin_menu_kb
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta
from database.schedule import set_master_slots
from utils.config_loader import OWNER_ID

router = Router()

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