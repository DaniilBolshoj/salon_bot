import re
from typing import Tuple, Dict, Any

from database import DB_PATH
from database.appointments import (
    create_appointment_db,
    user_has_appointment_db,
    slot_taken as db_slot_taken,
)
from database.schedule import get_master_slots_auto
from utils.config_loader import OWNER_ID  # для оповещения владельца (если нужно)
from aiogram import Bot
from utils.config_loader import BOT_TOKEN

bot = Bot(token=BOT_TOKEN)


async def validate_phone(phone: str, country_code: str = "+370") -> bool:
    """
    Простая валидация телефона: + и 7..15 цифр, и начинается с country_code.
    """
    if not isinstance(phone, str):
        return False
    pattern = r"^\+\d{7,15}$"
    if not re.match(pattern, phone):
        return False
    return phone.startswith(country_code)


async def validate_slot(master: str, day: str, time_: str) -> bool:
    """
    Проверяет, что слот существует в автогенерации и что он не занят.
    Использует get_master_slots_auto (возвращает [(day, time), ...]) и db_slot_taken.
    """
    # Получаем доступные слоты мастера
    slots = await get_master_slots_auto(master, days_ahead=30)
    # slots возвращает список кортежей (day_str, time_str)
    if (day, time_) not in slots:
        return False

    # Проверяем занятость в таблице appointments
    taken = await db_slot_taken(master, day, time_)
    return not taken

async def parse_manual_input(input_str: str) -> Tuple[bool, Dict[str, str]]:
    """
    Парсит ввод пользователя в формате:
    Услуга: <услуга>
    Мастер: <мастер>
    Дата: <год-месяц-день>
    Время: <часы:минуты>
    
    Возвращает (ok: bool, data: dict)
    Если ok == False, data содержит ключ "error" с описанием ошибки.
    Если ok == True, data содержит ключи "service", "master", "day", "time".
    """
    pattern = (
        r"Услуга:\s*(?P<service>.+?)\s*"
        r"Мастер:\s*(?P<master>.+?)\s*"
        r"Дата:\s*(?P<day>\d{4}-\d{2}-\d{2})\s*"
        r"Время:\s*(?P<time>\d{2}:\d{2})"
    )
    match = re.search(pattern, input_str, re.DOTALL)
    if not match:
        return False, {"error": "Неверный формат ввода. Пожалуйста, используйте указанный шаблон."}
    
    data = match.groupdict()
    return True, data


async def create_appointment(flow: dict, user_id: int, name: str, phone: str) -> Dict[str, Any]:
    """
    Унифицированная функция создания записи.
    Возвращает dict: {"ok": bool, "error": Optional[str], "message": Optional[str]}
    """
    # Базовые проверки
    if await user_has_appointment_db(user_id):
        return {"ok": False, "error": "У вас уже есть активная запись."}

    if not await validate_phone(phone):
        return {"ok": False, "error": "Неверный формат телефона. Пример: +37060000000"}

    # Читаем данные из flow
    service = flow.get("service")
    master = flow.get("master")
    day = flow.get("day")
    time_ = flow.get("time")

    if not all([service, master, day, time_]):
        return {"ok": False, "error": "Неполные данные для записи (услуга/мастер/дата/время)."}

    # Проверяем слот
    ok_slot = await validate_slot(master, day, time_)
    if not ok_slot:
        return {"ok": False, "error": "Слот недоступен или уже занят."}

    # Сохраняем
    try:
        await create_appointment_db(user_id, name, phone, service, master, day, time_)
    except Exception as e:
        return {"ok": False, "error": f"Ошибка при создании записи: {e}"}

    # Сформируем текст подтверждения
    text = format_confirmation_message(service, master, day, time_, name, phone)

    # Отправка нотификации владельцу (попытка; не критично)
    try:
        await bot.send_message(
            OWNER_ID,
            f"📩 Новая запись:\n{service} | {master} | {day} {time_}\nИмя: {name}\nТелефон: {phone}"
        )
    except Exception:
        # не фейлим при ошибке уведомления владельца
        pass

    return {"ok": True, "message": text}


def format_confirmation_message(service: str, master: str, day: str, time_: str, name: str, phone: str) -> str:
    """
    Формирует текст подтверждения для пользователя (HTML).
    """
    return (
        "✅ Ваша запись подтверждена!\n\n"
        f"<b>Услуга:</b> {service}\n"
        f"<b>Мастер:</b> {master}\n"
        f"<b>Дата:</b> {day}\n"
        f"<b>Время:</b> {time_}\n"
        f"<b>Имя:</b> {name}\n"
        f"<b>Телефон:</b> {phone}"
    )