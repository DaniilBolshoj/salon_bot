from aiogram import Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime

from utils.userflow import userflow
from utils.config_loader import OWNER_ID
from keyboards.admin_keyboard import admin_menu_kb

from database.masters import add_master, remove_master_by_name, WEEKDAYS
from database.services import get_services
from database.schedule import set_master_slots, get_master_slots_auto, get_master_days

from flows.appointments_flow import (
    validate_phone,
    validate_slot,
    create_appointment,
    format_confirmation_message
)

router = Router()

# =========================================================
# ADMIN CALLBACKS (выбор услуг и дней)
# =========================================================

@router.callback_query(F.data.startswith("adm_set_service:"))
async def adm_set_service_cb(c: types.CallbackQuery):
    user_id = c.from_user.id
    flow = userflow.get(user_id)

    if not flow or flow.get("next") != "choose_services":
        return await c.answer("❌ Ошибка.")

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
        return await c.answer("❌ Выберите услуги.")

    flow["next"] = "choose_days"
    flow["selected_days"] = []

    await c.message.answer("Выберите рабочие дни мастера:")
    await send_days_keyboard(c.message, flow)
    await c.answer()


@router.callback_query(F.data.startswith("day_toggle:"))
async def day_toggle_cb(c: types.CallbackQuery):
    user_id = c.from_user.id
    flow = userflow.get(user_id)

    if not flow or flow.get("next") != "choose_days":
        return await c.answer("❌ Ошибка.")

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
        return await c.answer("❌ Выберите дни.")

    flow["next"] = "ask_start_time"
    await c.message.answer("Введите время начала работы (например 09:00):")
    await c.answer()


async def send_days_keyboard(message, flow):
    kb = InlineKeyboardBuilder()

    for d in WEEKDAYS:
        text = f"✓ {d}" if d in flow["selected_days"] else d
        kb.button(text=text, callback_data=f"day_toggle:{d}")

    kb.button(text="➡️ Далее", callback_data="finish_days")
    kb.adjust(3)

    await message.edit_reply_markup(reply_markup=kb.as_markup())


# =========================================================
# UNIVERSAL MESSAGE HANDLER (ADMIN + USER)
# =========================================================

@router.message(F.text & ~F.text.startswith("/"))
async def universal_input(msg: types.Message):
    user_id = msg.from_user.id
    text = msg.text.strip()
    flow = userflow.get(user_id)

    if not flow:
        return

    # ===================== ADD MASTER =====================
    if flow.get("next") == "add_master":
        if text == "⬅️ Назад":
            userflow.pop(user_id)
            await msg.answer("Отмена", reply_markup=admin_menu_kb())
            return

        master_id = await add_master(text)
        userflow[user_id] = {
            "next": "choose_services",
            "master_id": master_id,
            "master_name": text,
            "selected_services": []
        }

        services = await get_services()
        kb = InlineKeyboardBuilder()

        for sid, name, _ in services:
            kb.button(text=name, callback_data=f"adm_set_service:{sid}")

        kb.button(text="➡️ Далее", callback_data="adm_finish_services")
        kb.adjust(2)

        await msg.answer(
            f"Выберите услуги для мастера <b>{text}</b>:",
            reply_markup=kb.as_markup()
        )
        return

    # ===================== SCHEDULE =====================
    if flow.get("next") == "ask_start_time":
        try:
            flow["start_time"] = datetime.strptime(text, "%H:%M").time()
            flow["next"] = "ask_end_time"
            await msg.answer("Введите время окончания работы (например 18:00):")
        except ValueError:
            await msg.answer("❌ Формат ЧЧ:ММ")
        return

    if flow.get("next") == "ask_end_time":
        try:
            end = datetime.strptime(text, "%H:%M").time()
            if end <= flow["start_time"]:
                return await msg.answer("❌ Конец должен быть позже начала.")

            flow["end_time"] = end
            flow["next"] = "ask_slot_duration"
            await msg.answer("Введите длительность слота (например 1):")
        except ValueError:
            await msg.answer("❌ Формат ЧЧ:ММ")
        return

    if flow.get("next") == "ask_slot_duration":
        try:
            duration = float(text)
            await set_master_slots(
                master_name=flow["master_name"],
                start_time=flow["start_time"].strftime("%H:%M"),
                end_time=flow["end_time"].strftime("%H:%M"),
                selected_days=flow["selected_days"],
                slot_duration_hours=duration
            )

            userflow.pop(user_id)
            await msg.answer(
                f"🎉 Мастер <b>{flow['master_name']}</b> добавлен!",
                reply_markup=admin_menu_kb()
            )
        except:
            await msg.answer("❌ Введите число.")
        return

    # ===================== DELETE MASTER =====================
    if flow.get("next") == "delete_master":
        if text == "⬅️ Назад":
            userflow.pop(user_id)
            await msg.answer("Отмена", reply_markup=admin_menu_kb())
            return

        if await remove_master_by_name(text):
            await msg.answer(f"🗑 Мастер {text} удалён.", reply_markup=admin_menu_kb())
        else:
            await msg.answer("❌ Мастер не найден.")

        userflow.pop(user_id)
        return