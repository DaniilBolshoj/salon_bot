from aiogram import Router
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from states.reviews import ReviewStates
from database.reviews import add_review, get_last_reviews
from database.services import get_services
from database.masters import get_all_masters, get_masters_by_service, get_master_by_id

router = Router()

# Меню отзывов (кнопки)
@router.message(lambda m: m.text == "⭐ Отзывы")
async def reviews_menu_handler(m: Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="📝 Оставить отзыв", callback_data="leave_review_btn")
    kb.button(text="📄 Просмотреть отзывы", callback_data="view_reviews_btn")
    kb.adjust(1)
    await m.answer("🌟 Ознакомьтесь с отзывами наших клиентов и оставьте свой!", reply_markup=kb.as_markup())

# Кнопки меню — обработчики callback
@router.callback_query(lambda c: c.data == "leave_review_btn")
async def cb_start_leave_review(c: CallbackQuery, state: FSMContext):
    await c.answer()
    # запускаем выбор услуги
    services = await get_services()
    if not services:
        await c.message.answer("Пока нет доступных услуг.")
        return
    kb = InlineKeyboardBuilder()
    for sid, name in services:
        kb.button(text=f"{name}", callback_data=f"rev_service_{sid}")
    kb.adjust(1)
    await c.message.answer("🔧 Выберите услугу:", reply_markup=kb.as_markup())
    await state.set_state(ReviewStates.choosing_service)

@router.callback_query(lambda c: c.data == "view_reviews_btn")
async def cb_view_reviews(c: CallbackQuery):
    await c.answer()
    await view_reviews(c.message)

# Выбор услуги (callback)
@router.callback_query(lambda c: c.data.startswith("rev_service_"))
async def choose_service(c: CallbackQuery, state: FSMContext):
    await c.answer()
    try:
        service_id = int(c.data.split("_")[2])
    except (IndexError, ValueError):
        await c.message.answer("Ошибка выбора услуги.")
        return

    await state.update_data(service_id=service_id)

    # получить мастеров по service_id
    masters = await get_masters_by_service(service_id)
    if not masters:
        await c.message.edit_text("❌ Для этой услуги пока нет мастеров.")
        await state.clear()
        return

    kb = InlineKeyboardBuilder()
    for mid, name in masters:
        # callback содержит id мастера
        kb.button(text=name, callback_data=f"rev_master_{mid}")
    kb.adjust(1)

    await c.message.edit_text("👤 Выберите мастера:", reply_markup=kb.as_markup())
    await state.set_state(ReviewStates.choosing_master)

# Выбор мастера (callback)
@router.callback_query(lambda c: c.data.startswith("rev_master_"))
async def choose_master(c: CallbackQuery, state: FSMContext):
    await c.answer()
    try:
        master_id = int(c.data.split("_")[2])
    except (IndexError, ValueError):
        await c.message.answer("Ошибка выбора мастера.")
        return

    await state.update_data(master_id=master_id)

    # Рейтинг — 0.5 шаги
    ratings = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
    kb = InlineKeyboardBuilder()
    for r in ratings:
        # format rating to show .0 as integer
        text = f"{int(r) if r.is_integer() else r} ⭐"
        kb.button(text=text, callback_data=f"rev_rate_{r}")
    kb.adjust(5)

    await c.message.edit_text("⭐ Выберите рейтинг:", reply_markup=kb.as_markup())
    await state.set_state(ReviewStates.choosing_rating)

# Выбор рейтинга (callback)
@router.callback_query(lambda c: c.data.startswith("rev_rate_"))
async def choose_rating(c: CallbackQuery, state: FSMContext):
    await c.answer()
    try:
        rating = float(c.data.split("_")[2])
    except (IndexError, ValueError):
        await c.message.answer("Ошибка выбора рейтинга.")
        return

    await state.update_data(rating=rating)
    await c.message.edit_text("✍ Напишите текст отзыва:")
    await state.set_state(ReviewStates.writing_text)

# Получаем текст отзыва и сохраняем
@router.message(ReviewStates.writing_text)
async def write_text(m: Message, state: FSMContext):
    data = await state.get_data()
    service_id = data.get("service_id")
    master_id = data.get("master_id")
    rating = data.get("rating")

    if not (service_id and master_id and rating):
        await m.answer("❌ Ошибка: не все данные были заполнены. Повторите попытку.")
        await state.clear()
        return

    # Получаем отображаемые имена (без лишних запросов — можно оптимизировать)
    # Получим service name
    from database.services import get_service_by_id  # реализуй (ниже дам SQL)
    service_row = await get_service_by_id(service_id)
    service_name = service_row[1] if service_row else str(service_id)

    masters_rows = await get_all_masters()  # может быть [(name1,), (name2,), ...]
    masters = [r[0] for r in masters_rows]  # теперь ['Иван', 'Мария', ...]

    # Сохраняем отзыв
    await add_review(
        user_id=m.from_user.id,
        service=service_name,
        master=masters,
        rating=rating,
        text=m.text
    )

    await m.answer("✅ Спасибо! Ваш отзыв сохранён.")
    await state.clear()

# Просмотр последних отзывов
@router.message(lambda m: m.text == "📄 Просмотреть отзывы")
async def view_reviews(m: Message):
    reviews = await get_last_reviews(limit=10)
    if not reviews:
        await m.answer("📭 Пока нет отзывов.")
        return

    text = "<b>📝 Последние отзывы:</b>\n\n"
    for service, master, rating, text_rev in reviews:
        text += f"🔧 <b>Сервис:</b> {service}\n"
        text += f"👤 <b>Мастер:</b> {master}\n"
        text += f"⭐ <b>Оценка:</b> {rating}\n"
        text += f"💬 <b>Отзыв:</b> {text_rev}\n\n"

    await m.answer(text, parse_mode="HTML")