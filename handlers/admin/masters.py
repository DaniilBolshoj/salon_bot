from aiogram import Router, types, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from keyboards.admin_keyboard import admin_menu_kb
from database.masters import add_master, get_all_masters

router = Router()

@router.message(F.text == "Мастера")
async def show_masters(message: types.Message):
    masters = await get_all_masters()
    text = "Список мастеров:\n\n"
    for mid, name, spec in masters:
        text += f"{name} — {spec}\n"
    await message.answer(text, reply_markup=admin_menu_kb())

@router.message(F.text == "Добавить мастера")
async def add_master_start(message: types.Message, state: FSMContext):
    await message.answer("Введите имя мастера:")
    await state.set_state("add_master_name")


@router.message(State("add_master_name"))
async def add_master_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите специальность:")
    await state.set_state("add_master_spec")


@router.message(State("add_master_spec"))
async def add_master_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await add_master(data["name"], message.text)
    await message.answer("Мастер добавлен!")
    await state.clear()

@router.message(F.text == "⬅️ Назад в меню")
async def back_to_admin_menu(msg: types.Message, state: FSMContext):
    await msg.answer("Возврат в админ-меню", reply_markup=admin_menu_kb())
    await state.clear()

