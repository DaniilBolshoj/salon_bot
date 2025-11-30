from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from states.reviews import ReviewStates
from database.reviews import add_review, get_last_reviews
from database.services import get_services
from database.masters import get_masters_by_service   # если нет – сделаем
from aiogram.types import KeyboardButton

router = Router()

@router.message(lambda m: m.text == "⭐ Отзывы")
async def reviews_menu_handler(m: types.Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="📝 Оставить отзыв", callback_data="leave_review_btn")
    kb.button(text="📄 Просмотреть отзывы", callback_data="view_reviews_btn")
    kb.adjust(1)

    await m.answer(
        "🌟 Ознакомьтесь с отзывами наших клиентов и оставьте свой!",
        reply_markup=kb.as_markup()
    )

# --- Начать оставление отзыва ---
@router.message(lambda m: m.text == "📝 Оставить отзыв")
async def leave_review(m: types.Message, state: FSMContext):
    services = await get_services()

    kb = InlineKeyboardBuilder()
    for sid, name, price in services:
        kb.button(text=name, callback_data=f"rev_service_{sid}")
    kb.adjust(1)

    await m.answer("🔧 Выберите услугу:", reply_markup=kb.as_markup())
    await state.set_state(ReviewStates.choosing_service)



# --- Выбор услуги ---
@router.callback_query(lambda c: c.data.startswith("rev_service_"))
async def choose_service(c: types.CallbackQuery, state: FSMContext):
    service_id = int(c.data.split("_")[2])  # ← вытаскиваем ID услуги

    await state.update_data(service_id=service_id)  # ← сохраняем!!

    # грузим мастеров по ID услуги
    masters = await get_masters_by_service(service_id)

    kb = InlineKeyboardBuilder()
    for master_name in masters:  # masters = ["Анна", "Мария"]
        kb.button(
            text=master_name,
            callback_data=f"rev_master_{master_name}"  # или ID, если хочешь
        )
    kb.adjust(1)

    await c.message.edit_text(
        "👤 Выберите мастера:",
        reply_markup=kb.as_markup()
    )

    await state.set_state(ReviewStates.choosing_master)



# --- Выбор мастера ---
@router.callback_query(lambda c: c.data.startswith("rev_master_"))
async def choose_master(c: types.CallbackQuery, state: FSMContext):
    master_id = int(c.data.split("_")[2])

    await state.update_data(master_id=master_id)

    kb = InlineKeyboardBuilder()

    # звезды 0.5 шага
    ratings = [0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5]

    for r in ratings:
        kb.button(text=f"{r} ⭐", callback_data=f"rev_rate_{r}")
    kb.adjust(3)

    await c.message.edit_text("⭐ Выберите рейтинг:", reply_markup=kb.as_markup())
    await state.set_state(ReviewStates.choosing_rating)



# --- Выбор рейтинга ---
@router.callback_query(lambda c: c.data.startswith("rev_rate_"))
async def choose_rating(c: types.CallbackQuery, state: FSMContext):
    rating = float(c.data.split("_")[2])

    await state.update_data(rating=rating)

    await c.message.edit_text("✍ Напишите текст отзыва:")
    await state.set_state(ReviewStates.writing_text)



# --- Получение текста и сохранение ---
@router.message(ReviewStates.writing_text)
async def write_text(m: types.Message, state: FSMContext):
    data = await state.get_data()

    from database.services import get_services
    from database.masters import get_masters

    # берём названия
    services = {s[0]: s[1] for s in await get_services()}
    masters = {m[0]: m[1] for m in await get_masters()}

    await add_review(
        user_id=m.from_user.id,
        service=services[data["service_id"]],
        master=masters[data["master_id"]],
        rating=data["rating"],
        text=m.text
    )

    await state.clear()
    await m.answer("✅ Спасибо! Ваш отзыв сохранён.")



# --- Просмотр отзывов ---
@router.message(lambda m: m.text == "📄 Просмотреть отзывы")
async def view_reviews(m: types.Message):
    reviews = await get_last_reviews()

    if not reviews:
        return await m.answer("📭 Пока нет отзывов.")

    text = "<b>📝 Последние отзывы:</b>\n\n"
    for s, master, r, t in reviews:
        text += f"🔧 <b>Сервис:</b> {s}\n"
        text += f"👤 <b>Мастер:</b> {master}\n"
        text += f"⭐ <b>Оценка:</b> {r}\n"
        text += f"💬 <b>Отзыв:</b> {t}\n\n"

    await m.answer(text)

@router.callback_query(lambda c: c.data == "leave_review_btn")
async def start_leave_review(c: types.CallbackQuery, state: FSMContext):
    await c.message.answer("Начинаем оформление отзыва...")
    await leave_review(c.message, state)
    await c.answer()

@router.callback_query(lambda c: c.data == "view_reviews_btn")
async def start_view_reviews(c: types.CallbackQuery):
    await view_reviews(c.message)
    await c.answer()