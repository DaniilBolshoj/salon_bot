from aiogram.types import (
    KeyboardButton,
    ReplyKeyboardMarkup
)

# ---------- МЕНЮ АДМИНА ----------
def admin_menu_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Просмотр записей"), KeyboardButton(text="⚙️ Настройки")],
            [KeyboardButton(text="➕ Добавить мастера"), KeyboardButton(text="➖ Удалить мастера")],
            [KeyboardButton(text="🧾 Просмотр заявок"), KeyboardButton(text="🏠 Главное меню")]
        ],
        resize_keyboard=True
    )
    
def settings_kb():
    buttons = [
        [KeyboardButton(text="🌴 Отправить мастера в отпуск"), KeyboardButton(text="🗓 Настроить дни/часы")],
        [KeyboardButton(text="💇 Настроить услуги"), KeyboardButton(text="Настроить обеденный перерыв")],
        [KeyboardButton(text="Мастера"), KeyboardButton(text="⬅️ Назад в меню")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
