from aiogram import Router, F, types

router = Router()

@router.message(F.text == "🌴 Отправить мастера в отпуск")
async def send_master_vacation(msg: types.Message):
    await msg.answer("Выберите мастера для отпуска... (пока заглушка)")

@router.message(F.text == "🗓 Настроить дни/часы")
async def set_master_schedule(msg: types.Message):
    await msg.answer("Настройка дней и часов работы мастеров... (пока заглушка)")

@router.message(F.text == "💇 Настроить услуги")
async def set_master_services(msg: types.Message):
    await msg.answer("Настройка услуг и цен... (пока заглушка)")

@router.message(F.text == "⬅️ Назад в меню")
async def back_to_admin_menu(msg: types.Message):
    from keyboards.admin_keyboard import admin_menu_kb
    await msg.answer("Возврат в админ-меню", reply_markup=admin_menu_kb())