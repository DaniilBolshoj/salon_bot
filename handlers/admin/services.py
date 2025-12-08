from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder
import aiosqlite
from aiogram import Router, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.masters import add_master
from database.services import get_services
from flows.universal_router import userflow

from database.services import (
    add_service,
    get_services,
    get_service_by_id,
    remove_service_by_id,
    update_service_price
)

router = Router()


# ===== FSM States =====
class AddService(StatesGroup):
    waiting_for_name = State()
    waiting_for_price = State()


class EditService(StatesGroup):
    waiting_for_field = State()  # choice: name or price
    waiting_for_new_value = State()


class RemoveService(StatesGroup):
    waiting_for_confirm = State()

class AddMasterStates(StatesGroup):
    waiting_for_name = State()
    choose_services = State()
    choose_workdays = State()
    choose_slots = State()


@router.callback_query(lambda c: c.data == "service_menu")
async def service_menu(callback: types.CallbackQuery):
    services = await get_services()
    kb = InlineKeyboardBuilder()

    if not services:
        kb.button(text="➕ Добавить услугу", callback_data="service_add")
        await callback.message.edit_text(
            "Список услуг пуст.",
            reply_markup=kb.as_markup()
        )
        return

    for s_id, name, price in services:
        kb.button(
            text=f"{name} — {price}€",
            callback_data=f"service_item:{s_id}"
        )

    kb.button(text="➕ Добавить услугу", callback_data="service_add")
    kb.adjust(1)

    await callback.message.edit_text(
        "Список услуг:",
        reply_markup=kb.as_markup()
    )


# ====== Add new service ======
@router.callback_query(lambda c: c.data == "service_add")
async def add_service_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddService.waiting_for_name)
    await callback.message.edit_text("Введите название новой услуги:")


@router.message(AddService.waiting_for_name)
async def add_service_name(msg: types.Message, state: FSMContext):
    await state.update_data(name=msg.text.strip())
    await state.set_state(AddService.waiting_for_price)
    await msg.answer("Введите цену услуги:")


@router.message(AddService.waiting_for_price)
async def add_service_price(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    name = data.get("name")
    try:
        price = float(msg.text.replace(",", ".").strip())
    except ValueError:
        await msg.answer("Введите корректную цену!")
        return

    await add_service(name, price)
    await state.clear()
    await msg.answer(f"✅ Услуга добавлена:\n{name} — {price}€")


# ====== Select service to edit/remove ======
@router.callback_query(lambda c: c.data.startswith("service_item:"))
async def service_item(callback: types.CallbackQuery, state: FSMContext):
    service_id = int(callback.data.split(":")[1])
    service = await get_service_by_id(service_id)
    if not service:
        await callback.message.answer("Услуга не найдена.")
        return

    _, name, price = service
    await state.update_data(service_id=service_id)

    kb = InlineKeyboardBuilder()
    kb.button(text="Редактировать название", callback_data="edit_name")
    kb.button(text="Редактировать цену", callback_data="edit_price")
    kb.button(text="Удалить услугу", callback_data="remove_service")
    kb.button(text="⬅ Назад", callback_data="service_menu")
    kb.adjust(1)

    await callback.message.edit_text(
        f"Вы выбрали услугу:\n{name} — {price}€",
        reply_markup=kb.as_markup()
    )


# ====== Edit name ======
@router.callback_query(lambda c: c.data == "edit_name")
async def edit_service_name(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(EditService.waiting_for_new_value)
    await state.update_data(field="name")
    await callback.message.edit_text("Введите новое название услуги:")


# ====== Edit price ======
@router.callback_query(lambda c: c.data == "edit_price")
async def edit_service_price_cb(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(EditService.waiting_for_new_value)
    await state.update_data(field="price")
    await callback.message.edit_text("Введите новую цену услуги:")


# ====== Handle new value ======
@router.message(EditService.waiting_for_new_value)
async def edit_service_new_value(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    service_id = data.get("service_id")
    field = data.get("field")

    if field == "name":
        new_name = msg.text.strip()
        async with aiosqlite.connect("database.db") as db:
            await db.execute("UPDATE services SET name=? WHERE id=?", (new_name, service_id))
            await db.commit()
        await msg.answer(f"✅ Название обновлено на: {new_name}")
    elif field == "price":
        try:
            new_price = float(msg.text.replace(",", ".").strip())
        except ValueError:
            await msg.answer("Введите корректную цену!")
            return
        await update_service_price(service_id, new_price)
        await msg.answer(f"✅ Цена обновлена на: {new_price}€")

    await state.clear()


# ====== Remove service ======
@router.callback_query(lambda c: c.data == "remove_service")
async def remove_service_start(callback: types.CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    kb.button(text="Да, удалить", callback_data="confirm_remove")
    kb.button(text="Отмена", callback_data="service_menu")
    kb.adjust(1)
    await state.set_state(RemoveService.waiting_for_confirm)
    await callback.message.edit_text("Вы уверены, что хотите удалить эту услугу?", reply_markup=kb.as_markup())


@router.callback_query(lambda c: c.data == "confirm_remove")
async def remove_service_confirm(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    service_id = data.get("service_id")
    service = await get_service_by_id(service_id)
    if service:
        _, name, _ = service
        await remove_service_by_id(service_id)
        await callback.message.edit_text(f"❌ Услуга '{name}' удалена.")
    await state.clear()


# ====== Helper ======
async def get_service_name_by_id(service_id):
    services = await get_services()
    print(services)
    for s_id, name, _ in services:
        if s_id == service_id:
            return name
    return None