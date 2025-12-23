from aiogram import Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime

from utils.userflow import userflow
from database.masters import WEEKDAYS, add_master, assign_service_to_master
from database.schedule import set_master_days, set_master_slots

router = Router()


# =========================================================
# ADMIN CALLBACKS
# =========================================================

@router.callback_query(F.data.startswith("adm_set_service:"))
async def adm_set_service_cb(c: types.CallbackQuery):
    user_id = c.from_user.id
    flow = userflow.get(user_id)

    if not flow or flow.get("next") != "choose_services":
        await c.answer("❌ Ошибка.")
        return

    service_id = int(c.data.split(":")[1])

    if service_id in flow["selected_services"]:
        flow["selected_services"].remove(service_id)
        await c.answer("Убрано")
    else:
        flow["selected_services"].append(service_id)
        await c.answer("Добавлено")


@router.callback_query(F.data == "adm_finish_services")
async def adm_finish_services_cb(c: types.CallbackQuery):
    user_id = c.from_user.id
    flow = userflow.get(user_id)

    if not flow or not flow.get("selected_services"):
        await c.answer("❌ Выберите услуги.")
        return

    # 1️⃣ Создаём мастера
    master_id = await add_master(flow["master_name"])

    # 2️⃣ Назначаем услуги мастеру
    for service_id in flow["selected_services"]:
        await assign_service_to_master(master_id, service_id)

    # 3️⃣ Инициализируем дни
    flow["master_id"] = master_id
    flow["selected_days"] = []
    flow["next"] = "choose_days"

    await c.message.answer("Выберите рабочие дни мастера:")
    await send_days_keyboard(c.message, flow)
    await c.answer()


@router.callback_query(F.data.startswith("day_toggle:"))
async def day_toggle_cb(c: types.CallbackQuery):
    user_id = c.from_user.id
    flow = userflow.get(user_id)

    if not flow or flow.get("next") != "choose_days":
        await c.answer("❌ Ошибка.")
        return

    day = c.data.split(":")[1]

    if day in flow["selected_days"]:
        flow["selected_days"].remove(day)
    else:
        flow["selected_days"].append(day)

    await send_days_keyboard(c.message, flow)
    await c.answer()


@router.callback_query(F.data == "finish_days")
async def finish_days_cb(c: types.CallbackQuery):
    user_id = c.from_user.id
    flow = userflow.get(user_id)

    if not flow or not flow.get("selected_days"):
        await c.answer("❌ Выберите дни.")
        return

    # Сохраняем выбранные дни в БД
    await set_master_days(flow["master_name"], flow["selected_days"])

    flow["next"] = "ask_start_time"
    await c.message.answer("Введите время начала работы мастера (например 09:00):")
    await c.answer()


# =========================================================
# KEYBOARD BUILDER
# =========================================================

async def send_days_keyboard(message: types.Message, flow: dict):
    kb = InlineKeyboardBuilder()

    for d in WEEKDAYS:
        text = f"✓ {d}" if d in flow.get("selected_days", []) else d
        kb.button(text=text, callback_data=f"day_toggle:{d}")

    kb.button(text="➡️ Далее", callback_data="finish_days")
    kb.adjust(3)

    await message.edit_reply_markup(reply_markup=kb.as_markup())


# =========================================================
# TIME INPUT HANDLER (работает через FSM/userflow)
# =========================================================

@router.message(F.text, lambda msg: userflow.get(msg.from_user.id, {}).get("next") in [
    "ask_start_time", "ask_end_time", "ask_slot_duration"
])
async def master_schedule_input(msg: types.Message):
    user_id = msg.from_user.id
    flow = userflow.get(user_id)

    if not flow:
        return

    # ===== START TIME =====
    if flow.get("next") == "ask_start_time":
        try:
            flow["start_time"] = datetime.strptime(msg.text, "%H:%M").time()
            flow["next"] = "ask_end_time"
            await msg.answer("Введите время окончания работы мастера (например 18:00):")
        except ValueError:
            await msg.answer("❌ Формат времени: ЧЧ:ММ")
        return

    # ===== END TIME =====
    if flow.get("next") == "ask_end_time":
        try:
            end_time = datetime.strptime(msg.text, "%H:%M").time()
            if end_time <= flow["start_time"]:
                await msg.answer("❌ Время окончания должно быть позже начала.")
                return
            flow["end_time"] = end_time
            flow["next"] = "ask_slot_duration"
            await msg.answer("Введите длительность слота в часах (например 1):")
        except ValueError:
            await msg.answer("❌ Формат времени: ЧЧ:ММ")
        return

    # ===== SLOT DURATION =====
    if flow.get("next") == "ask_slot_duration":
        try:
            duration = float(msg.text)
            flow["slot_duration"] = duration

            # Сохраняем слоты в БД
            await set_master_slots(
                master_name=flow["master_name"],
                start_time=flow["start_time"].strftime("%H:%M"),
                end_time=flow["end_time"].strftime("%H:%M"),
                selected_days=flow["selected_days"],
                slot_duration_hours=duration
            )

            # Финализируем добавление мастера
            userflow.pop(user_id)
            await msg.answer(f"🎉 Мастер <b>{flow['master_name']}</b> успешно добавлен!",
                             parse_mode="HTML")
        except ValueError:
            await msg.answer("❌ Введите число (например 1).")
        return
