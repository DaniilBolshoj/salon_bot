from aiogram import Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils.userflow import userflow
from database.masters import WEEKDAYS

router = Router()

# =========================================================
# ADMIN CALLBACKS (paslaugų ir dienų pasirinkimas)
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

    flow["next"] = "ask_start_time"
    await c.message.answer("Введите время начала работы (например 09:00):")
    await c.answer()


# =========================================================
# KEYBOARD BUILDER
# =========================================================

async def send_days_keyboard(message: types.Message, flow: dict):
    kb = InlineKeyboardBuilder()

    for d in WEEKDAYS:
        text = f"✓ {d}" if d in flow["selected_days"] else d
        kb.button(text=text, callback_data=f"day_toggle:{d}")

    kb.button(text="➡️ Далее", callback_data="finish_days")
    kb.adjust(3)

    await message.edit_reply_markup(reply_markup=kb.as_markup())
