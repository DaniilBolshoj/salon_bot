import asyncio
import aiosqlite
import phonenumbers
from datetime import datetime, timedelta, date
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

# ========================
TOKEN = "8251523047:AAERjuRUJJQSewgORj58yRwxvkW9v7P0b2E"  # <- заменяй
OWNER_ID = 5395991590  # <- твой Telegram ID (int)
DB_PATH = "salon.db"
# ========================

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ======= утилиты дат/времени =======
def get_dates_window(days_ahead=7):
    today = date.today()
    return [(today + timedelta(days=i)).isoformat() for i in range(days_ahead)]

def now_iso(): return datetime.utcnow().isoformat(timespec='seconds')

# ======= SQL схемы =======
CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    price TEXT
);

CREATE TABLE IF NOT EXISTS masters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS master_days (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    master_id INTEGER NOT NULL,
    day TEXT NOT NULL,
    FOREIGN KEY(master_id) REFERENCES masters(id)
);

CREATE TABLE IF NOT EXISTS master_slots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    master_id INTEGER NOT NULL,
    time TEXT NOT NULL,
    FOREIGN KEY(master_id) REFERENCES masters(id)
);

CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT,
    phone TEXT,
    service TEXT,
    master TEXT,
    day TEXT,
    time TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    name TEXT,
    phone TEXT,
    desired_day TEXT,
    desired_time TEXT,
    note TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    service TEXT,
    master TEXT,
    rating INTEGER,
    text TEXT,
    created_at TEXT
);
"""

# ======= DB init =======
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        for stmt in CREATE_TABLES_SQL.strip().split(";"):
            sql = stmt.strip()
            if sql:
                await db.execute(sql + ";")
        # default settings
        cur = await db.execute("SELECT value FROM settings WHERE key='country_code'")
        if not await cur.fetchone():
            await db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES(?,?)", ("country_code", "+370"))
        cur = await db.execute("SELECT value FROM settings WHERE key='work_start'")
        if not await cur.fetchone():
            await db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES(?,?)", ("work_start", "09:00"))
            await db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES(?,?)", ("work_end", "18:00"))
        await db.commit()

# ======= DB helpers =======
async def get_setting(key):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = await cur.fetchone()
        return row[0] if row else None

async def set_setting(key, value):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES(?,?)", (key, value))
        await db.commit()

async def add_service(name, price=""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO services(name, price) VALUES(?,?)", (name, price))
        await db.commit()

async def list_services():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT name, price FROM services ORDER BY name")
        return await cur.fetchall()

async def add_master(name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO masters(name) VALUES(?)", (name,))
        await db.commit()

async def remove_master(name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM masters WHERE name=?", (name,))
        await db.commit()

async def get_all_masters():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT name FROM masters ORDER BY name")
        rows = await cur.fetchall()
        return [r[0] for r in rows]

async def set_master_days(master_name, days_list):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id FROM masters WHERE name=?", (master_name,))
        r = await cur.fetchone()
        if not r:
            return False
        master_id = r[0]
        await db.execute("DELETE FROM master_days WHERE master_id=?", (master_id,))
        for d in days_list:
            await db.execute("INSERT INTO master_days(master_id, day) VALUES(?,?)", (master_id, d))
        await db.commit()
        return True

async def set_master_slots(master_name, slots_list):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id FROM masters WHERE name=?", (master_name,))
        r = await cur.fetchone()
        if not r:
            return False
        master_id = r[0]
        await db.execute("DELETE FROM master_slots WHERE master_id=?", (master_id,))
        for s in slots_list:
            await db.execute("INSERT INTO master_slots(master_id, time) VALUES(?,?)", (master_id, s))
        await db.commit()
        return True

async def get_master_days(master_name):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""SELECT md.day FROM master_days md
                                  JOIN masters m ON m.id=md.master_id
                                  WHERE m.name=? ORDER BY md.day""", (master_name,))
        rows = await cur.fetchall()
        return [r[0] for r in rows]

async def get_master_slots(master_name):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""SELECT ms.time FROM master_slots ms
                                  JOIN masters m ON m.id=ms.master_id
                                  WHERE m.name=? ORDER BY ms.time""", (master_name,))
        rows = await cur.fetchall()
        return [r[0] for r in rows]

async def slot_taken(master, day, time_):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT 1 FROM appointments WHERE master=? AND day=? AND time=?", (master, day, time_))
        return await cur.fetchone() is not None

async def user_has_appointment_db(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT 1 FROM appointments WHERE user_id=?", (user_id,))
        return await cur.fetchone() is not None

async def create_appointment_db(user_id, name, phone, service, master, day, time_):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""INSERT INTO appointments(user_id, name, phone, service, master, day, time, created_at)
                            VALUES(?,?,?,?,?,?,?,?)""", (user_id, name, phone, service, master, day, time_, now_iso()))
        await db.commit()

async def list_appointments_db():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id, name, phone, service, master, day, time, created_at FROM appointments ORDER BY day, time")
        return await cur.fetchall()

async def add_request_db(user_id, name, phone, desired_day, desired_time, note):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""INSERT INTO requests(user_id, name, phone, desired_day, desired_time, note, created_at)
                            VALUES(?,?,?,?,?,?,?)""", (user_id, name, phone, desired_day, desired_time, note, now_iso()))
        await db.commit()

# ======= defaults init =======
async def init_defaults():
    # default services
    await add_service("Стрижка", "20€")
    await add_service("Окрашивание", "35€")
    await add_service("Маникюр", "15€")
    await add_service("Массаж", "40€")
    # default masters
    await add_master("Ольга")
    await add_master("Анна")
    await add_master("Мария")
    await add_master("Ирина")
    # set days for next 7 days and default slots
    dates = get_dates_window(7)
    for m in await get_all_masters():
        await set_master_days(m, dates)
        await set_master_slots(m, ["09:00", "10:30", "12:00", "14:00", "15:30", "17:00"])

# ======= phone utils =======
def validate_phone_format(phone: str) -> bool:
    try:
        p = phonenumbers.parse(phone, None)
        return phonenumbers.is_possible_number(p) and phonenumbers.is_valid_number(p)
    except Exception:
        return False

def phone_belongs_to_country(phone: str, country_code_str: str) -> bool:
    try:
        p = phonenumbers.parse(phone, None)
        cc = f"+{p.country_code}"
        return cc == country_code_str
    except Exception:
        return False

# ======= main menu =======
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🏢 О нас"), KeyboardButton(text="💇 Услуги")],
        [KeyboardButton(text="📅 Записаться"), KeyboardButton(text="⭐ Отзывы")],
        [KeyboardButton(text="💬 Контакты"), KeyboardButton(text="🧠 AI-помощник")]
    ],
    resize_keyboard=True
)

# ======= user flow store =======
user_flow = {}  # user_id -> dict: service, master, day, time, step, tmp_name, tmp_phone

# ======= handlers (booking flow) =======
@dp.message(Command("start"))
async def cmd_start(msg: types.Message):
    await msg.answer("👋 Добро пожаловать! Нажмите «📅 Записаться», чтобы выбрать услугу.", reply_markup=main_menu)

@dp.message(lambda m: m.text == "🏢 О нас")
async def about(m: types.Message):
    await m.answer("💖 Салон красоты — запись через бота. Для вопросов используйте Контакты.")

@dp.message(lambda m: m.text == "💇 Услуги")
async def services_list(m: types.Message):
    rows = await list_services()
    text = "💇 Наши услуги:\n"
    for name, price in rows:
        text += f"• {name} — {price}\n"
    await m.answer(text)

@dp.message(lambda m: m.text == "💬 Контакты")
async def contacts(m: types.Message):
    cc = await get_setting("country_code")
    await m.answer(f"📞 Телефон: {cc} XXX XXX\n📍 Адрес: Вильнюс\nНажмите «📅 Записаться» для выбора времени.")

@dp.message(lambda m: m.text == "📅 Записаться")
async def begin_book(m: types.Message):
    user_id = m.from_user.id
    if await user_has_appointment_db(user_id):
        await m.answer("❌ У вас уже есть активная запись. Для изменения свяжитесь с админом (номер указан в контактах).")
        return
    rows = await list_services()
    if not rows:
        await m.answer("Пока нет доступных услуг. Свяжитесь с админом.")
        return
    builder = InlineKeyboardBuilder()
    for name, _price in rows:
        builder.button(text=name, callback_data=f"svc:{name}")
    builder.adjust(2)
    await m.answer("Выберите услугу:", reply_markup=builder.as_markup())

@dp.callback_query(lambda c: c.data.startswith("svc:"))
async def cb_service(c: types.CallbackQuery):
    service = c.data.split(":", 1)[1]
    user_id = c.from_user.id
    user_flow[user_id] = {"service": service, "step": "service_chosen"}
    masters = await get_all_masters()
    if not masters:
        await c.message.answer("Нет доступных мастеров. Админ должен добавить мастеров.")
        await c.answer()
        return
    builder = InlineKeyboardBuilder()
    for mname in masters:
        builder.button(text=mname, callback_data=f"m:{mname}")
    builder.adjust(2)
    await c.message.answer(f"Услуга: {service}. Выберите мастера:", reply_markup=builder.as_markup())
    await c.answer()

@dp.callback_query(lambda c: c.data.startswith("m:"))
async def cb_master(c: types.CallbackQuery):
    master = c.data.split(":", 1)[1]
    user_id = c.from_user.id
    if user_id not in user_flow:
        await c.message.answer("Ошибка. Начните заново через «📅 Записаться».")
        await c.answer()
        return
    user_flow[user_id]["master"] = master
    user_flow[user_id]["step"] = "master_chosen"
    days = await get_master_days(master)
    today_iso = date.today().isoformat()
    days_filtered = [d for d in days if d >= today_iso]
    wanted = set(get_dates_window(7))
    days_final = [d for d in days_filtered if d in wanted]
    builder = InlineKeyboardBuilder()
    any_available = False
    for d in days_final:
        slots = await get_master_slots(master)
        if not slots:
            continue
        some_free = any(not await slot_taken(master, d, s) for s in slots)
        if some_free:
            builder.button(text=d, callback_data=f"day:{d}")
            any_available = True
        else:
            builder.button(text=f"{d} ❌", callback_data="disabled")
    builder.adjust(2)
    if not any_available:
        builder2 = InlineKeyboardBuilder()
        builder2.button(text="Оставить запрос на другое время", callback_data="req:other")
        await c.message.answer("К сожалению, у этого мастера нет свободных слотов в ближайшие 7 дней.", reply_markup=builder2.as_markup())
        await c.answer()
        return
    await c.message.answer("Выберите день:", reply_markup=builder.as_markup())
    await c.answer()

@dp.callback_query(lambda c: c.data.startswith("day:"))
async def cb_day(c: types.CallbackQuery):
    d = c.data.split(":", 1)[1]
    user_id = c.from_user.id
    if user_id not in user_flow or "master" not in user_flow[user_id]:
        await c.message.answer("Ошибка. Начните заново через «📅 Записаться».")
        await c.answer()
        return
    user_flow[user_id]["day"] = d
    user_flow[user_id]["step"] = "day_chosen"
    master = user_flow[user_id]["master"]
    slots = await get_master_slots(master)
    builder = InlineKeyboardBuilder()
    any_free = False
    for s in slots:
        taken = await slot_taken(master, d, s)
        if taken:
            builder.button(text=f"{s} ❌", callback_data="disabled")
        else:
            any_free = True
            builder.button(text=s, callback_data=f"time:{s}")
    builder.adjust(3)
    if not any_free:
        builder2 = InlineKeyboardBuilder()
        builder2.button(text="Оставить запрос на другое время", callback_data="req:other")
        await c.message.answer("В этот день нет свободных слотов. Хотите оставить запрос?", reply_markup=builder2.as_markup())
        await c.answer()
        return
    await c.message.answer("Выберите время:", reply_markup=builder.as_markup())
    await c.answer()

@dp.callback_query(lambda c: c.data.startswith("time:"))
async def cb_time(c: types.CallbackQuery):
    t = c.data.split(":", 1)[1]
    user_id = c.from_user.id
    if user_id not in user_flow or "day" not in user_flow[user_id] or "master" not in user_flow[user_id]:
        await c.message.answer("Ошибка. Начните заново через «📅 Записаться».")
        await c.answer()
        return
    master = user_flow[user_id]["master"]
    day = user_flow[user_id]["day"]
    if await slot_taken(master, day, t):
        await c.message.answer("Слот только что заняли — выберите другой.")
        await c.answer()
        return
    user_flow[user_id]["time"] = t
    user_flow[user_id]["step"] = "time_chosen"
    user_flow[user_id]["next"] = "ask_name"
    await c.message.answer("Отлично! Теперь введите ваше имя (например: Иван):")
    await c.answer()

@dp.callback_query(lambda c: c.data.startswith("req:"))
async def cb_request(c: types.CallbackQuery):
    typ = c.data.split(":",1)[1]
    user_id = c.from_user.id
    if typ == "other":
        user_flow[user_id] = {"step":"request_start"}
        await c.message.answer("Напишите желаемый день (YYYY-MM-DD), время (HH:MM) и телефон через запятую. Пример:\n2025-11-01, 15:00, +37061234567")
        await c.answer()
        return
    await c.answer()

@dp.message()
async def generic_text(m: types.Message):
    user_id = m.from_user.id
    txt = m.text.strip()
    flow = user_flow.get(user_id)

    if flow and flow.get("next") == "ask_name":
        flow["tmp_name"] = txt
        flow["next"] = "ask_phone"
        await m.answer("Спасибо! Теперь введите телефон в международном формате, например +37061234567")
        return

    if flow and flow.get("next") == "ask_phone":
        phone = txt
        if not validate_phone_format(phone):
            await m.answer("Неверный формат номера. Пример: +37061234567")
            return
        salon_cc = await get_setting("country_code")
        if salon_cc and not phone_belongs_to_country(phone, salon_cc):
            await m.answer(f"Номер не совпадает с кодом страны салона ({salon_cc}). Если вы из другой страны — свяжитесь с админом.")
            return
        master = flow["master"]
        day = flow["day"]
        time_ = flow["time"]
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("SELECT 1 FROM appointments WHERE phone=? AND master=? AND day=? AND time=?", (phone, master, day, time_))
            if await cur.fetchone():
                await m.answer("Этот номер уже записан на этот слот. Свяжитесь с админом.")
                return
        name = flow.get("tmp_name", "Не указано")
        await create_appointment_db(user_id, name, phone, flow["service"], master, day, time_)
        user_flow.pop(user_id, None)
        await m.answer(f"✅ Запись подтверждена: {flow['service']} | {master} | {day} {time_}\nИмя: {name}\nТел: {phone}")
        try:
            await bot.send_message(OWNER_ID, f"Новая запись: {flow['service']} | {master} | {day} {time_}\nИмя: {name}\nТел: {phone}")
        except Exception:
            pass
        return

    if flow and flow.get("step") == "request_start":
        parts = [p.strip() for p in txt.split(",")]
        if len(parts) < 3:
            await m.answer("Неправильный формат. Введите: YYYY-MM-DD, HH:MM, +phone")
            return
        desired_day, desired_time, phone = parts[0], parts[1], parts[2]
        note = parts[3] if len(parts) > 3 else ""
        if not validate_phone_format(phone):
            await m.answer("Неверный формат номера.")
            return
        salon_cc = await get_setting("country_code")
        if salon_cc and not phone_belongs_to_country(phone, salon_cc):
            await m.answer(f"Номер не совпадает с кодом страны салона ({salon_cc}). Заявка сохранена, админ свяжется.")
        await add_request_db(user_id, None, phone, desired_day, desired_time, note)
        user_flow.pop(user_id, None)
        await m.answer("Заявка сохранена. Админ свяжется.")
        try:
            await bot.send_message(OWNER_ID, f"Новая ручная заявка: {phone} | {desired_day} {desired_time} | {note}")
        except Exception:
            pass
        return

    # Admin quick text commands handled elsewhere; default:
    await m.answer("Не понял. Чтобы записаться — нажмите «📅 Записаться».\nДля админа: /admin.")

# ======= reviews shortcut (simple) =======
@dp.message(lambda m: m.text == "⭐ Отзывы")
async def reviews_btn(m: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT service, master, rating, text, created_at FROM reviews ORDER BY created_at DESC LIMIT 5")
        rows = await cur.fetchall()
    if not rows:
        await m.answer("Пока нет отзывов. Для записи — контакты в разделе «Контакты».")
        return
    text = "Последние отзывы:\n"
    for svc, mstr, rating, txt, created in rows:
        text += f"• {svc} | {mstr} — {rating}⭐\n  «{txt}»\n"
    await m.answer(text)

# ======= Admin panel & commands incl. /set_days and /set_slots =======
@dp.message(Command("admin"))
async def admin_menu(m: types.Message):
    if m.from_user.id != OWNER_ID:
        await m.answer("Доступ запрещён.")
        return
    builder = ReplyKeyboardBuilder()
    builder.button(text="📅 Просмотр записей")
    builder.button(text="➕ Добавить мастера")
    builder.button(text="➖ Удалить мастера")
    builder.button(text="⚙️ Настройки (страна/часы)")
    builder.button(text="🧾 Просмотр заявок")
    builder.button(text="🏠 Главное меню")
    builder.adjust(2)
    await m.answer("Панель администратора:", reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(lambda m: m.text == "📅 Просмотр записей" and m.from_user.id == OWNER_ID)
async def admin_view_appointments(m: types.Message):
    rows = await list_appointments_db()
    if not rows:
        await m.answer("Нет записей.")
        return
    text = "Записи:\n"
    for user_id, name, phone, service, master, day, time_, created in rows:
        text += f"• {service} | {master} | {day} {time_}\n  {name} | {phone}\n"
    await m.answer(text)

@dp.message(Command("add_master"))
async def cmd_add_master(m: types.Message):
    if m.from_user.id != OWNER_ID:
        return
    parts = m.text.split(maxsplit=1)
    if len(parts) < 2:
        await m.answer("Использование: /add_master Имя")
        return
    name = parts[1].strip()
    await add_master(name)
    await set_master_days(name, get_dates_window(7))
    await set_master_slots(name, ["09:00", "11:00", "14:00", "16:00"])
    await m.answer(f"Мастер {name} добавлен с дефолтными днями/слотами.")

@dp.message(Command("remove_master"))
async def cmd_remove_master(m: types.Message):
    if m.from_user.id != OWNER_ID:
        return
    parts = m.text.split(maxsplit=1)
    if len(parts) < 2:
        await m.answer("Использование: /remove_master Имя")
        return
    name = parts[1].strip()
    await remove_master(name)
    await m.answer(f"Мастер {name} удалён (если был).")

@dp.message(Command("set_days"))
async def cmd_set_days(m: types.Message):
    """
    Usage: /set_days Имя YYYY-MM-DD,YYYY-MM-DD,YYYY-MM-DD
    Example: /set_days Ольга 2025-10-21,2025-10-22,2025-10-23
    """
    if m.from_user.id != OWNER_ID:
        return
    parts = m.text.split(maxsplit=2)
    if len(parts) < 3:
        await m.answer("Использование: /set_days Имя YYYY-MM-DD,YYYY-MM-DD,...")
        return
    name = parts[1].strip()
    days_csv = parts[2].strip()
    days = [d.strip() for d in days_csv.split(",") if d.strip()]
    # validate date format
    for d in days:
        try:
            date.fromisoformat(d)
        except Exception:
            await m.answer(f"Неверный формат даты: {d}. Используйте YYYY-MM-DD.")
            return
    ok = await set_master_days(name, days)
    if ok:
        await m.answer(f"Дни мастера {name} обновлены: {', '.join(days)}")
    else:
        await m.answer(f"Мастер {name} не найден. Сначала добавьте /add_master {name}")

@dp.message(Command("set_slots"))
async def cmd_set_slots(m: types.Message):
    """
    Usage: /set_slots Имя HH:MM,HH:MM,...
    Example: /set_slots Ольга 09:00,10:30,12:00
    """
    if m.from_user.id != OWNER_ID:
        return
    parts = m.text.split(maxsplit=2)
    if len(parts) < 3:
        await m.answer("Использование: /set_slots Имя HH:MM,HH:MM,...")
        return
    name = parts[1].strip()
    slots_csv = parts[2].strip()
    slots = [s.strip() for s in slots_csv.split(",") if s.strip()]
    # simple validation HH:MM
    for s in slots:
        try:
            datetime.strptime(s, "%H:%M")
        except Exception:
            await m.answer(f"Неверный формат времени: {s}. Используйте HH:MM.")
            return
    ok = await set_master_slots(name, slots)
    if ok:
        await m.answer(f"Слоты мастера {name} обновлены: {', '.join(slots)}")
    else:
        await m.answer(f"Мастер {name} не найден. Сначала добавьте /add_master {name}")

@dp.message(Command("set_country"))
async def cmd_set_country(m: types.Message):
    if m.from_user.id != OWNER_ID:
        return
    parts = m.text.split(maxsplit=1)
    if len(parts) < 2:
        await m.answer("Использование: /set_country +370")
        return
    cc = parts[1].strip()
    await set_setting("country_code", cc)
    await m.answer(f"Код страны салона установлен: {cc}")

@dp.message(Command("set_workhours"))
async def cmd_set_hours(m: types.Message):
    if m.from_user.id != OWNER_ID:
        return
    parts = m.text.split()
    if len(parts) < 3:
        await m.answer("Использование: /set_workhours HH:MM HH:MM")
        return
    await set_setting("work_start", parts[1])
    await set_setting("work_end", parts[2])
    await m.answer(f"Часы работы обновлены: {parts[1]} - {parts[2]}")

@dp.message(lambda message: message.text == "🧾 Просмотр заявок" and message.from_user.id == OWNER_ID)
async def admin_view_requests(message: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT name, phone, desired_day, desired_time, note, created_at FROM requests ORDER BY created_at DESC")
        rows = await cur.fetchall()
    if not rows:
        await message.answer("Нет ручных заявок.")
        return
    text = "Ручные заявки:\n"
    for name, phone, day, time_, note, created in rows:
        text += f"• {day} {time_} | {phone} | {note}\n"
    await message.answer(text)

# ===== background maintenance =====
async def daily_maintenance_task():
    while True:
        try:
            dates = get_dates_window(7)
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT id, name FROM masters")
                masters_rows = await cur.fetchall()
                today_iso = date.today().isoformat()
                for mid, mname in masters_rows:
                    await db.execute("DELETE FROM master_days WHERE master_id=? AND day<?", (mid, today_iso))
                    cur2 = await db.execute("SELECT day FROM master_days WHERE master_id=?", (mid,))
                    existing = {r[0] for r in await cur2.fetchall()}
                    for d in dates:
                        if d not in existing:
                            await db.execute("INSERT INTO master_days(master_id, day) VALUES(?,?)", (mid, d))
            await asyncio.sleep(24*3600)
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(60)

# ===== startup =====
async def on_startup():
    await init_db()
    await init_defaults()
    dp.loop.create_task(daily_maintenance_task())

# ===== run =====
if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(on_startup())
        loop.create_task(dp.start_polling(bot))
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        pass