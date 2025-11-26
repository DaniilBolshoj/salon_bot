from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.services import add_service, get_services, remove_service

router = Router()

# FSM состояния для добавления/редактирования услуги
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
    await msg.answer("Введите цену услуги в формате числа (например: 20.5):")
    await AddService.waiting_for_price.set()

@router.message(AddService.waiting_for_price)
async def service_price_received(msg: types.Message, state: FSMContext):
    price_text = msg.text.replace(",", ".").strip()
    try:
        price = float(price_text)
    except ValueError:
        await msg.answer("Ошибка: введите корректное число для цены.")
        return

    data = await state.get_data()
    name = data.get("name")

    await add_service(name, str(price))
    await msg.answer(f"✅ Услуга добавлена:\n{name} — {price}€")
    await state.clear()


# ====== Просмотр списка услуг ======
@router.message(F.text == "Список услуг")
async def list_services_menu(msg: types.Message):
    services = await get_services()
    if not services:
        await msg.answer("Список услуг пока пустой.")
        return
    text = "📋 Список услуг:\n\n"
    for sid, name, price in services:
        text += f"{name} — {price}€\n"
    await msg.answer(text)


# ====== Редактирование цены услуги ======
@router.message(F.text == "Редактировать цену услуги")
async def edit_service_start(msg: types.Message, state: FSMContext):
    services = await get_services()
    if not services:
        await msg.answer("Список услуг пуст, нечего редактировать.")
        return
    text = "Выберите услугу для редактирования (напишите точное название):\n"
    text += "\n".join([name for _, name, _ in services])
    await msg.answer(text)
    await EditServicePrice.waiting_for_service.set()

@router.message(EditServicePrice.waiting_for_service)
async def edit_service_get_name(msg: types.Message, state: FSMContext):
    await state.update_data(name=msg.text.strip())
    await msg.answer("Введите новую цену услуги:")
    await EditServicePrice.waiting_for_new_price.set()

@router.message(EditServicePrice.waiting_for_new_price)
async def edit_service_set_price(msg: types.Message, state: FSMContext):
    price_text = msg.text.replace(",", ".").strip()
    try:
        price = float(price_text)
    except ValueError:
        await msg.answer("Ошибка: введите корректное число для цены.")
        return

    data = await state.get_data()
    name = data.get("name")

    # Удаляем старую услугу и добавляем с новой ценой
    await remove_service(name)
    await add_service(name, str(price))

    await msg.answer(f"✅ Цена услуги {name} изменена на {price}€")
    await state.clear()


# ====== Удаление услуги ======
@router.message(F.text == "Удалить услугу")
async def remove_service_start(msg: types.Message, state: FSMContext):
    services = await get_services()
    if not services:
        await msg.answer("Список услуг пуст, нечего удалять.")
        return
    text = "Выберите услугу для удаления (напишите точное название):\n"
    text += "\n".join([name for _, name, _ in services])
    await msg.answer(text)
    await RemoveServiceFSM.waiting_for_service.set()

@router.message(RemoveServiceFSM.waiting_for_service)
async def remove_service_confirm(msg: types.Message, state: FSMContext):
    name = msg.text.strip()
    await remove_service(name)
    await msg.answer(f"❌ Услуга {name} удалена.")
    await state.clear()