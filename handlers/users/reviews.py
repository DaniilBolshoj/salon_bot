from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from states.reviews import ReviewStates
from database.reviews import add_review, get_last_reviews
from database.services import get_services
from database.masters import get_all_masters  # если нет – сделаем
from aiogram.types import KeyboardButton
from database.masters import get_masters_by_service

router = Router()

# ------------------ МЕНЮ ОТЗЫВОВ ------------------
@router.message(lambda m: m.text == "⭐ Отзывы")
async def reviews_menu_handler(m: types.Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="📝 Оставить отзыв", callback_data="leave_review_btn")
    kb.button(text="📄 Просмотреть отзывы", callback_data="view_reviews_btn")
    kb.adjust(1)

    await m.answer("🌟 Что хотите сделать?", reply_markup=kb.as_markup())


# ------------------ НАЧАТЬ ОТЗЫВ ------------------
@router.callback_query(lambda c: c.data == "leave_review_btn")
async def start_leave_review(c: types.CallbackQuery, state: FSMContext):
    services = await get_services()

    kb = InlineKeyboardBuilder()
    for sid, name, price in services:
        kb.button(text=name, callback_data=f"rev_service_{sid}")
    kb.adjust(1)

    await c.message.edit_text("🔧 Выберите услугу:", reply_markup=kb.as_markup())
    await state.set_state(ReviewStates.choosing_service)    
    await c.answer()


# ------------------ ВЫБОР УСЛУГИ ------------------
@router.callback_query(lambda c: c.data.startswith("rev_service_"))
async def choose_service(c: types.CallbackQuery, state: FSMContext):
    service_name = c.data.split("_")[2]
    await state.update_data(service_name=service_name)

    masters = await get_masters_by_service(service_name)

    kb = InlineKeyboardBuilder()
    for mid, name in masters:
        kb.button(text=name, callback_data=f"rev_master_{mid}")
    kb.adjust(1)

    await c.message.edit_text("👤 Выберите мастера:", reply_markup=kb.as_markup())
    await state.set_state(ReviewStates.choosing_master)
    await c.answer()


# ------------------ ВЫБОР МАСТЕРА ------------------
@router.callback_query(lambda c: c.data.startswith("rev_master_"))
async def choose_master(c: types.CallbackQuery, state: FSMContext):
    master_id = int(c.data.split("_")[2])
    await state.update_data(master_id=master_id)

    kb = InlineKeyboardBuilder()
    ratings = [0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5]

    for r in ratings:
        kb.button(text=f"{r} ⭐", callback_data=f"rev_rate_{r}")
    kb.adjust(3)

    await c.message.edit_text("⭐ Выберите рейтинг:", reply_markup=kb.as_markup())
    await state.set_state(ReviewStates.choosing_rating)
    await c.answer()


# ------------------ ВЫБОР РЕЙТИНГА ------------------
@router.callback_query(lambda c: c.data.startswith("rev_rate_"))
async def choose_rating(c: types.CallbackQuery, state: FSMContext):
    rating = float(c.data.split("_")[2])
    await state.update_data(rating=rating)

    await c.message.edit_text("✍ Напишите текст отзыва:")
    await state.set_state(ReviewStates.writing_text)
    await c.answer()


# ------------------ ПОЛУЧЕНИЕ ТЕКСТА ------------------
@router.message(ReviewStates.writing_text)
async def write_text(m: types.Message, state: FSMContext):
    data = await state.get_data()

    services = {s[0]: s[1] for s in await get_services()}
    masters = {m[0]: m[1] for m in await get_all_masters()}

    await add_review(
        user_id=m.from_user.id,
        service=services[data["service_id"]],
        master=masters[data["master_id"]],
        rating=data["rating"],
        text=m.text
    )

    await state.clear()
    await m.answer("✅ Спасибо! Ваш отзыв сохранён.")


# ------------------ ПРОСМОТР ОТЗЫВОВ ------------------
@router.callback_query(lambda c: c.data == "view_reviews_btn")
async def start_view_reviews(c: types.CallbackQuery):
    await view_reviews(c.message)
    await c.answer()


@router.message(lambda m: m.text == "📄 Просмотреть отзывы")
async def view_reviews(m: types.Message):
    reviews = await get_last_reviews()

    if not reviews:
        return await m.answer("📭 Пока нет отзывов.")

    text = "<b>📝 Последние отзывы:</b>\n\n"
    for s, master, r, t in reviews:
        text += (
            f"🔧 <b>Сервис:</b> {s}\n"
            f"👤 <b>Мастер:</b> {master}\n"
            f"⭐ <b>Оценка:</b> {r}\n"
            f"💬 <b>Отзыв:</b> {t}\n\n"
        )

    await m.answer(text)

@router.callback_query(lambda c: c.data == "leave_review_btn")
async def start_leave_review(c: types.CallbackQuery, state: FSMContext):
    await c.message.answer("Начинаем оформление отзыва...")
    await start_leave_review(c.message, state)
    await c.answer()

@router.callback_query(lambda c: c.data == "view_reviews_btn")
async def start_view_reviews(c: types.CallbackQuery):
    await view_reviews(c.message)
    await c.answer()