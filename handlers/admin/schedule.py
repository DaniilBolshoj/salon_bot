from aiogram import Router, F, types
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from setuptools import Command
from database.masters import get_all_masters
from database.schedule import set_master_days, set_master_slots
#from handlers.admin.services import AddService
from handlers.users.contacts import services_menu
from database.services import get_services
from aiogram.utils.keyboard import InlineKeyboardBuilder

from keyboards.admin_keyboard import admin_menu_kb


router = Router()
from database.schedule import SetMasterSchedule

@router.message(F.text == "💇 Настроить услуги")
async def admin_services(msg: types.Message):
    # Siunčiam mygtuką su callback į centralų menu
    kb = InlineKeyboardBuilder()
    kb.button(text="Открыть меню услуг", callback_data="service_menu")
    kb.adjust(1)
    await msg.answer("Настройка услуг:", reply_markup=kb.as_markup())

@router.callback_query(lambda c: c.data == "🏠 В главное меню")
async def back_to_admin_menu(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Вы в главном меню администратора.",
        reply_markup=admin_menu_kb()
    )

# ====== Настройка расписания мастеров ======
@router.message(F.text == "🗓 Настроить дни/часы")
async def set_master_schedule(msg: types.Message):
    masters = await get_all_masters()
    if not masters:
        await msg.answer("Список мастеров пуст. Сначала добавьте мастеров.")
        return
    text = "Выберите мастера для настройки расписания:\n" + "\n".join(masters)
    await msg.answer(text)
    # Здесь можно добавить FSM для выбора мастера → дней → слотов


# ====== Отправка мастера в отпуск ======
@router.message(F.text == "🌴 Отправить мастера в отпуск")
async def send_master_vacation(msg: types.Message):
    masters = await get_all_masters()
    if not masters:
        await msg.answer("Список мастеров пуст. Сначала добавьте мастеров.")
        return
    text = "Выберите мастера для отпуска (напишите точное имя):\n" + "\n".join(masters)
    await msg.answer(text)
    await msg.answer("Введите имя мастера для отправки в отпуск:")

    # FSM для отпуска мастера
    state: FSMContext = msg.bot['state']
    await state.set_state("vacation_master")


# ====== Настройка дней и часов мастера ======
@router.message(F.text == "🗓 Настроить дни/часы")
async def set_master_schedule(msg: types.Message, state: FSMContext):
    masters = await get_all_masters()
    if not masters:
        await msg.answer("Список мастеров пуст. Сначала добавьте мастеров.")
        return

    text = "Выберите мастера для настройки расписания (напишите точное имя):\n" + "\n".join(masters)
    await msg.answer(text)
    await SetMasterSchedule.waiting_for_master.set()

# ====== Настройка обеденного перерыва ======
@router.message(F.text == "Настроить обеденный перерыв")
async def set_lunch_break(msg: types.Message):
    await msg.answer("Функция настройки обеденного перерыва пока не реализована.")
    
@router.message(SetMasterSchedule.waiting_for_master)
async def schedule_master_selected(msg: types.Message, state: FSMContext):
    master_name = msg.text.strip()
    masters = await get_all_masters()
    if master_name not in masters:
        await msg.answer("Ошибка: мастер не найден. Попробуйте снова.")
        return
    await state.update_data(master=master_name)
    await msg.answer("Введите рабочие дни мастера через запятую (например: Пн,Вт,Ср,Чт,Пт):")
    await SetMasterSchedule.waiting_for_days.set()


@router.message(SetMasterSchedule.waiting_for_days)
async def schedule_days_received(msg: types.Message, state: FSMContext):
    days = [d.strip() for d in msg.text.split(",")]
    await state.update_data(days=days)
    await msg.answer("Введите время начала работы (например: 09:00):")
    await SetMasterSchedule.waiting_for_start_time.set()


@router.message(SetMasterSchedule.waiting_for_start_time)
async def schedule_start_time_received(msg: types.Message, state: FSMContext):
    start_time = msg.text.strip()
    await state.update_data(start_time=start_time)
    await msg.answer("Введите время окончания работы (например: 18:00):")
    await SetMasterSchedule.waiting_for_end_time.set()


@router.message(SetMasterSchedule.waiting_for_end_time)
async def schedule_end_time_received(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    master_name = data["master"]
    days = data["days"]
    start_time = data["start_time"]
    end_time = msg.text.strip()

    # Сохраняем дни и слоты мастера в БД
    await set_master_days(master_name, days)
    await set_master_slots(master_name, start_time, end_time, days)

    await msg.answer(f"✅ Расписание мастера {master_name} обновлено.\nДни: {', '.join(days)}\nВремя: {start_time}–{end_time}")
    await state.clear()
