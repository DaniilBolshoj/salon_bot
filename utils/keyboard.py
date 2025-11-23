from aiogram.types import (
    KeyboardButton,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton
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
        [KeyboardButton(text="💇 Настроить услуги"), KeyboardButton(text="⬅️ Назад в меню")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# ---------- ИНЛАЙН ДЛЯ УСЛУГ ----------
def inline_services_kb(services: list[str]):
    buttons = []
    for s in services:
        buttons.append([InlineKeyboardButton(text=s, callback_data=f"svc:{s}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ---------- ИНЛАЙН ДЛЯ МАСТЕРОВ ----------
def inline_masters_kb(masters: list[str], service: str):
    buttons = []
    for m in masters:
        buttons.append([InlineKeyboardButton(text=m, callback_data=f"master:{service}:{m}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ---------- ИНЛАЙН ДЛЯ ДАТ ----------
def inline_days_kb(days: list[str], service: str, master: str):
    buttons = []
    for d in days:
        buttons.append([InlineKeyboardButton(text=d, callback_data=f"day:{service}:{master}:{d}")])
    buttons.append([InlineKeyboardButton(text="📅 Другая дата", callback_data=f"manual:{service}:{master}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ---------- ИНЛАЙН ДЛЯ ВРЕМЕНИ ----------
def inline_times_kb(times: list[str], service: str, master: str, day: str):
    buttons = []
    for t in times:
        buttons.append([InlineKeyboardButton(text=t, callback_data=f"time:{service}:{master}:{day}:{t}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)