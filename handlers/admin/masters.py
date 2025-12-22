from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime

from keyboards.admin_keyboard import admin_menu_kb
from utils.userflow import userflow
from utils.config_loader import OWNER_ID

from database.masters import add_master, get_all_masters, remove_master_by_name
from database.services import get_services
from database.schedule import set_master_slots

router = Router()

# =========================================================
# FSM STATES
# =========================================================

class AddMasterFSM(StatesGroup):
    waiting_for_name = State()
    waiting_for_start_time = State()
    waiting_for_end_time = State()
    waiting_for_slot_duration = State()


# =========================================================
# SHOW MASTERS
# =========================================================

@router.message(F.text == "Мастера")
async def show_masters(msg: types.Message):
    if msg.from_user.id != OWNER_ID:
        return

    masters = await get_all_masters()
    if not masters:
        await msg.answer("Мастеров пока нет.", reply_markup=admin_menu_kb())
        return

    text = "👨‍🎨 <b>Список мастеров:</b>\n\n"
    for _, name, spec in masters:
        text += f"• {name} — {spec}\n"

    await msg.answer(text, reply_markup=admin_menu_kb(), parse_mode="HTML")

# =========================================================
# ADD MASTER — STEP 1 (NAME)
# =========================================================
@router.message(F.text == "➕ Добавить мастера")
async def add_master_start(msg: types.Message, state: FSMContext):
    if msg.from_user.id != OWNER_ID:
        return

    await msg.answer(
        "Введите имя мастера:",
        reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[[types.KeyboardButton(text="⬅️ Назад")]],
            resize_keyboard=True
        )
    )
    await state.set_state(AddMasterFSM.waiting_for_name)

@router.message(AddMasterFSM.waiting_for_name)
async def add_master_name(msg: types.Message, state: FSMContext):
    if msg.text == "⬅️ Назад":
        await state.clear()
        await msg.answer("Отмена", reply_markup=admin_menu_kb())
        return

    master_name = msg.text.strip()

    userflow[msg.from_user.id] = {
    "next": "choose_services",
    "master_name": master_name,
    "selected_services": []
    }


    services = await get_services()
    kb = InlineKeyboardBuilder()

    for sid, name, _ in services:
        kb.button(text=name, callback_data=f"adm_set_service:{sid}")

    kb.button(text="➡️ Далее", callback_data="adm_finish_services")
    kb.adjust(2)

    await msg.answer(
        f"Выберите услуги для мастера <b>{master_name}</b>:",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

    await state.clear()

# =========================================================
# DELETE MASTER FLOWS
# =========================================================

@router.message(F.text == "➖ Удалить мастера")
async def delete_master(msg: types.Message):
    if msg.from_user.id != OWNER_ID:
        return

    masters = await get_all_masters()
    if not masters:
        await msg.answer("❌ Нет мастеров для удаления.")
        return

    kb = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text=m[1])] for m in masters]
                 + [[types.KeyboardButton(text="⬅️ Назад")]],
        resize_keyboard=True
    )

    userflow[msg.from_user.id] = {"next": "delete_master"}
    await msg.answer("Выберите мастера для удаления:", reply_markup=kb)

# =========================================================
# TIME INPUT (после callback’ов из universal_router)
# =========================================================

@router.message(F.text, lambda msg: userflow.get(msg.from_user.id, {}).get("next") in [
    "ask_start_time",
    "ask_end_time",
    "ask_slot_duration"
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
            await msg.answer("Введите время окончания работы (например 18:00):")
        except ValueError:
            await msg.answer("❌ Формат времени: ЧЧ:ММ")
        return

    # ===== END TIME =====
    if flow.get("next") == "ask_end_time":
        try:
            end_time = datetime.strptime(msg.text, "%H:%M").time()
            if end_time <= flow["start_time"]:
                await msg.answer("❌ Конец должен быть позже начала.")
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

            await set_master_slots(
                master_name=flow["master_name"],
                start_time=flow["start_time"].strftime("%H:%M"),
                end_time=flow["end_time"].strftime("%H:%M"),
                selected_days=flow["selected_days"],
                slot_duration_hours=duration
            )

            userflow.pop(user_id)
            await msg.answer(
                f"🎉 Мастер <b>{flow['master_name']}</b> успешно добавлен!",
                reply_markup=admin_menu_kb(),
                parse_mode="HTML"
            )
        except ValueError:
            await msg.answer("❌ Введите число.")
        return

@router.message(F.text, lambda msg: userflow.get(msg.from_user.id, {}).get("next") == "delete_master")
async def delete_master_confirm(msg: types.Message):
    user_id = msg.from_user.id
    flow = userflow.get(user_id)

    if msg.text == "⬅️ Назад":
        userflow.pop(user_id)
        await msg.answer("Отмена", reply_markup=admin_menu_kb())
        return

    if await remove_master_by_name(msg.text):
        await msg.answer(f"🗑 Мастер {msg.text} удалён.", reply_markup=admin_menu_kb())
    else:
        await msg.answer("❌ Мастер не найден.")

    userflow.pop(user_id)

