from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from database.services import services_list
from database.masters import get_masters_by_service
from database.schedule import slot_taken
from database.appointments import create_appointment_db
from datetime import datetime, timedelta
from database.schedule import get_master_slots_available

router = Router()

# ===== FSM states =====
class AppointmentFlow(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_service = State()
    waiting_for_master = State()
    waiting_for_day = State()
    waiting_for_time = State()

# ===== Start appointment =====
@router.message(F.text == "📝 Записаться")
async def start_appointment(msg: types.Message, state: FSMContext):
    await state.set_state(AppointmentFlow.waiting_for_name)
    await msg.answer("Введите ваше имя:")

# ===== Name =====
@router.message(AppointmentFlow.waiting_for_name)
async def get_name(msg: types.Message, state: FSMContext):
    await state.update_data(name=msg.text.strip())
    await state.set_state(AppointmentFlow.waiting_for_phone)
    await msg.answer("Введите ваш телефон:")

# ===== Phone =====
@router.message(AppointmentFlow.waiting_for_phone)
async def get_phone(msg: types.Message, state: FSMContext):
    phone = msg.text.strip()
    # Простая проверка номера
    if len(phone) < 6:
        await msg.answer("Введите корректный телефон!")
        return
    await state.update_data(phone=phone)
    services = await services_list()
    text = "Выберите услугу:\n" + "\n".join([f"{i+1}. {s[0]} — {s[1]}€" for i,s in enumerate(services)])
    await state.update_data(services=services)
    await state.set_state(AppointmentFlow.waiting_for_service)
    await msg.answer(text)

# ===== Service =====
@router.message(AppointmentFlow.waiting_for_service)
async def get_service(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    services = data["services"]
    try:
        choice = int(msg.text.strip()) - 1
        service_name, service_price = services[choice]
    except (ValueError, IndexError):
        await msg.answer("Выберите услугу корректно, указав номер из списка.")
        return
    await state.update_data(service=service_name, service_price=service_price)
    masters = await get_masters_by_service(service_name)
    if not masters:
        await msg.answer("Нет доступных мастеров для этой услуги.")
        await state.clear()
        return
    await state.update_data(masters=masters)
    text = "Выберите мастера:\n" + "\n".join([f"{i+1}. {m}" for i,m in enumerate(masters)])
    await state.set_state(AppointmentFlow.waiting_for_master)
    await msg.answer(text)

# ===== Master =====
@router.message(AppointmentFlow.waiting_for_master)
async def get_master(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    masters = data["masters"]
    try:
        choice = int(msg.text.strip()) - 1
        master_name = masters[choice]
    except (ValueError, IndexError):
        await msg.answer("Выберите мастера корректно.")
        return
    await state.update_data(master=master_name)

    # Получаем доступные слоты мастера (следующие 7 дней)
    slots = await get_master_slots_available(master_name, selected_weekdays=["Пн","Вт","Ср","Чт","Пт","Сб","Вс"],
                                   start_time="08:00", end_time="18:00", slot_duration_hours=0.5, days_ahead=7)
    # Отфильтруем занятые
    available_slots = []
    now = datetime.now()
    for day, time_ in slots:
        dt = datetime.strptime(f"{day} {time_}", "%Y-%m-%d %H:%M")
        if dt >= now and not await slot_taken(master_name, day, time_):
            available_slots.append((day, time_))
    if not available_slots:
        await msg.answer("Нет свободных слотов у выбранного мастера на ближайшие 7 дней.")
        await state.clear()
        return
    await state.update_data(slots=available_slots)
    # Составим список по дням
    text = "Доступные слоты:\n"
    day_dict = {}
    for day, time_ in available_slots:
        day_dict.setdefault(day, []).append(time_)
    for day in sorted(day_dict.keys()):
        text += f"{day}:\n"
        text += ", ".join(day_dict[day]) + "\n"
    await state.set_state(AppointmentFlow.waiting_for_day)
    await msg.answer("Введите дату из доступных (например: 2025-11-29):\n" + text)

# ===== Day =====
@router.message(AppointmentFlow.waiting_for_day)
async def get_day(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    day = msg.text.strip()
    slots = data["slots"]
    day_slots = [t for d,t in slots if d==day]
    if not day_slots:
        await msg.answer("Некорректная дата, выберите из доступных.")
        return
    await state.update_data(day=day, day_slots=day_slots)
    await msg.answer("Введите время из доступных (например: 09:00):\n" + ", ".join(day_slots))
    await state.set_state(AppointmentFlow.waiting_for_time)

# ===== Time =====
@router.message(AppointmentFlow.waiting_for_time)
async def get_time(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    time_ = msg.text.strip()
    if time_ not in data["day_slots"]:
        await msg.answer("Некорректное время, выберите из доступных.")
        return
    await state.update_data(time=time_)

    # Сохраняем в DB
    user_id = msg.from_user.id
    user_name = data["name"]
    phone = data["phone"]
    service_name = data["service"]
    master_name = data["master"]
    day_str = data["day"]
    time_str = data["time"]

    await create_appointment_db(user_id, user_name, phone, service_name, master_name, day_str, time_str)
    await msg.answer(f"✅ Запись создана:\n{day_str} {time_str}\nМастер: {master_name}\nУслуга: {service_name}")
    await state.clear()
