from aiogram.types import (
    KeyboardButton,
    ReplyKeyboardMarkup
)

# ---------- ГЛАВНОЕ МЕНЮ ----------
def main_menu_kb(is_owner=False):
    buttons = [
        [KeyboardButton(text="🏢 О нас"), KeyboardButton(text="💇 Услуги")],
        [KeyboardButton(text="📅 Записаться"), KeyboardButton(text="⭐ Отзывы")],
        [KeyboardButton(text="💬 Контакты"), KeyboardButton(text="🧠 AI-помощник")]
    ]
    if is_owner:
        buttons.append([KeyboardButton(text="🏠 Админ-меню")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)