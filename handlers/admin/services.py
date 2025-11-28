from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.services import (
    add_service,
    get_services,
    get_service_by_name,
    remove_service_by_id,
    update_service_price
)

router = Router()


# FSM состояния
class AddService(StatesGroup):
    waiting_for_name = State()
    waiting_for_price = State()


class EditServicePrice(StatesGroup):
    waiting_for_service = State()
    waiting_for_new_price = State()


class RemoveServiceFSM(StatesGroup):
    waiting_for_service = State()


# ====== Добавление услуги ======
@router.message(AddService.waiting_for_name)
async def service_name_received(msg: types.Message, state: FSMContext):
    await state.update_data(name=msg.text.strip())
    await msg.answer("Введите цену услуги:")
    await AddService.waiting_for_price.set()


@router.message(AddService.waiting_for_price)
async def service_price_received(msg: types.Message, state: FSMContext):
    price_text = msg.text.replace(",", ".").strip()

    try:
        price = float(price_text)
    except ValueError:
        await msg.answer("Введите корректную цену!")
        return

    data = await state.get_data()
    name = data.get("name")

    await add_service(name, price)
    await state.clear()
    await msg.answer(f"✅ Услуга добавлена:\n{name} — {price}€")


# ====== Просмотр списка услуг ======
@router.message(F.text == "Список услуг")
async def list_services_menu(msg: types.Message):
    services = await get_services()
    if not services:
        await msg.answer("Список услуг пуст.")
        return
    
    text = "📋 Услуги:\n\n"
    for sid, name, price in services:
        text += f"• {name} — {price}€\n"

    await msg.answer(text)


# ====== Редактирование цены ======
@router.message(F.text == "Редактировать цену услуги")
async def edit_service_start(msg: types.Message, state: FSMContext):
    services = await get_services()
    if not services:
        await msg.answer("Нет услуг для редактирования.")
        return

    text = "Напишите название услуги:\n"
    text += "\n".join([name for _, name, _ in services])
    await msg.answer(text)

    await EditServicePrice.waiting_for_service.set()


@router.message(EditServicePrice.waiting_for_service)
async def edit_service_get_name(msg: types.Message, state: FSMContext):
    service = await get_service_by_name(msg.text.strip())
    if not service:
        await msg.answer("Такой услуги нет. Попробуйте ещё раз.")
        return

    service_id, name, price = service
    await state.update_data(service_id=service_id)
    await msg.answer(f"Текущая цена: {price}€. Введите новую цену:")

    await EditServicePrice.waiting_for_new_price.set()


@router.message(EditServicePrice.waiting_for_new_price)
async def edit_service_set_price(msg: types.Message, state: FSMContext):
    price_text = msg.text.replace(",", ".").strip()

    try:
        price = float(price_text)
    except ValueError:
        await msg.answer("Введите нормальную цену.")
        return

    data = await state.get_data()
    service_id = data.get("service_id")

    await update_service_price(service_id, price)
    await state.clear()

    await msg.answer("✅ Цена обновлена!")


# ====== Удаление услуги ======
@router.message(F.text == "Удалить услугу")
async def remove_service_start(msg: types.Message, state: FSMContext):
    services = await get_services()
    if not services:
        await msg.answer("Нет услуг для удаления.")
        return

    text = "Введите название услуги:\n"
    text += "\n".join([name for _, name, _ in services])

    await msg.answer(text)
    await RemoveServiceFSM.waiting_for_service.set()


@router.message(RemoveServiceFSM.waiting_for_service)
async def remove_service_confirm(msg: types.Message, state: FSMContext):
    service = await get_service_by_name(msg.text.strip())
    if not service:
        await msg.answer("Такой услуги нет.")
        return

    service_id, name, price = service

    await remove_service_by_id(service_id)
    await state.clear()

    await msg.answer(f"❌ Услуга '{name}' удалена.")