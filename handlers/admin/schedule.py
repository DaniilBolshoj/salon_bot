from aiogram import Router, F, types
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from setuptools import Command
from database.masters import get_all_masters
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
@router.message(F.text == "🍽 Настроить обеденный перерыв")
async def set_lunch_break(msg: types.Message):
    await msg.answer("Функция настройки обеденного перерыва пока не реализована.")

# ====== Возврат в админ меню ======
# Для текстового сообщения
@router.message(F.text == "⬅️ Назад в меню")
async def back_to_admin_menu_msg(msg: Message):
    await msg.answer(
        "Вы в главном меню администратора.",
        reply_markup=admin_menu_kb()
    )

# Для inline-кнопки с callback_data
@router.callback_query(lambda c: c.data == "back_to_admin_menu")
async def back_to_admin_menu_cb(callback: CallbackQuery):
    await callback.message.edit_text(
        "Вы в главном меню администратора.",
        reply_markup=admin_menu_kb()
    )
    await callback.answer()  # закрываем "часики" на кнопке