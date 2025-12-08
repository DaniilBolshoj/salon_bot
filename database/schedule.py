import aiosqlite
from datetime import datetime, timedelta, time as dt_time
from database import DB_PATH
from database.masters import WEEKDAYS
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

# ===== FSM =====
class MasterVacation(StatesGroup):
    waiting_for_name = State()

class SetMasterSchedule(StatesGroup):
    waiting_for_master = State()
    waiting_for_days = State()
    waiting_for_start_time = State()
    waiting_for_end_time = State()
    waiting_for_slot_duration = State()
    waiting_for_lunch_break = State()

# ===== Helpers =====
def str_to_time(t: str) -> dt_time:
    return datetime.strptime(t, "%H:%M").time()

def time_to_str(t: dt_time) -> str:
    return t.strftime("%H:%M")

def overlap(slot_start, slot_end, busy_start, busy_end):
    """Tikrina ar slotas sutampa su užimtu laiku"""
    return slot_start < busy_end and busy_start < slot_end

# ===== Master days =====
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

async def get_master_days(master_name):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT md.day FROM master_days md
            JOIN masters m ON m.id=md.master_id
            WHERE m.name=? ORDER BY md.day
        """, (master_name,))
        rows = await cur.fetchall()
        return [r[0] for r in rows]

# ===== Master slots =====
async def set_master_slots(master_name, start_time, end_time, selected_days, slot_duration_hours=1, lunch_break=None):
    """
    Genereuoja slotus pagal intervalą, pietų pertrauką ir pasirinktas dienas
    slot_duration_hours: pvz. 0.5 = 30 min
    lunch_break: tuple("HH:MM", "HH:MM")
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id FROM masters WHERE name=?", (master_name,))
        r = await cur.fetchone()
        if not r:
            return False
        master_id = r[0]

        # Ištriname senus slotus
        await db.execute("DELETE FROM master_slots WHERE master_id=?", (master_id,))

        start_dt = str_to_time(start_time)
        end_dt = str_to_time(end_time)
        slot_delta = timedelta(hours=slot_duration_hours)

        today = datetime.today()
        days_ahead = 14
        for day_offset in range(days_ahead):
            current_day = today + timedelta(days=day_offset)
            weekday_str = [k for k, v in WEEKDAYS.items() if v == current_day.weekday()][0]
            if weekday_str not in selected_days:
                continue

            slot_dt = datetime.combine(current_day.date(), start_dt)
            end_slot_dt = datetime.combine(current_day.date(), end_dt)

            while slot_dt + slot_delta <= end_slot_dt + timedelta(seconds=1):
                # Patikrinam pietų pertrauką
                if lunch_break:
                    lunch_start = datetime.combine(current_day.date(), str_to_time(lunch_break[0]))
                    lunch_end = datetime.combine(current_day.date(), str_to_time(lunch_break[1]))
                    if overlap(slot_dt, slot_dt + slot_delta, lunch_start, lunch_end):
                        slot_dt += slot_delta
                        continue

                # Įrašom slotą
                await db.execute(
                    "INSERT INTO master_slots(master_id, day, time) VALUES (?,?,?)",
                    (master_id, current_day.strftime("%Y-%m-%d"), slot_dt.strftime("%H:%M"))
                )
                slot_dt += slot_delta
        await db.commit()
        return True

async def get_master_slots_available(master_name, service_duration_hours=1, days_ahead=7):
    """
    Grąžina tik laisvus slotus
    service_duration_hours: intervalas pagal paslaugą
    """
    async with aiosqlite.connect(DB_PATH) as db:
        # gaunam master_id
        cur = await db.execute("SELECT id FROM masters WHERE name=?", (master_name,))
        r = await cur.fetchone()
        if not r:
            return []
        master_id = r[0]

        today = datetime.today().date()
        end_day = today + timedelta(days=days_ahead)

        cur = await db.execute(
            "SELECT day, time FROM master_slots WHERE master_id=? ORDER BY day, time",
            (master_id,)
        )
        all_slots = await cur.fetchall()

        # gaunam užimtus slotus
        cur = await db.execute(
            "SELECT day, time, service FROM appointments WHERE master=?",
            (master_name,)
        )
        busy = await cur.fetchall()

        available_slots = []
        for day_str, time_str in all_slots:
            slot_start = datetime.strptime(f"{day_str} {time_str}", "%Y-%m-%d %H:%M")
            slot_end = slot_start + timedelta(hours=service_duration_hours)

            # Patikrinam ar slotas užimtas
            is_busy = False
            for b_day, b_time, _ in busy:
                busy_start = datetime.strptime(f"{b_day} {b_time}", "%Y-%m-%d %H:%M")
                busy_end = busy_start + timedelta(hours=service_duration_hours)
                if overlap(slot_start, slot_end, busy_start, busy_end):
                    is_busy = True
                    break
            if not is_busy and today <= slot_start.date() <= end_day:
                available_slots.append(slot_start.strftime("%Y-%m-%d %H:%M"))

        return available_slots
    
async def slot_taken(master_name, day_str, time_str):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT COUNT(*) FROM appointments WHERE master=? AND day=? AND time=?",
            (master_name, day_str, time_str)
        )
        r = await cur.fetchone()
        return r[0] > 0
    
# ===== Auto slots for booking =====
async def get_master_slots_auto(master_name, days_ahead: int = 14):
    """
    Готовит слоты мастера в формате [(day, time), ...] для выбора пользователем.
    Берёт все слоты из таблицы master_slots, проверяет занятость.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        # Получаем master_id
        cur = await db.execute("SELECT id FROM masters WHERE name=?", (master_name,))
        r = await cur.fetchone()
        if not r:
            return []
        master_id = r[0]

        today = datetime.today().date()
        end_day = today + timedelta(days=days_ahead)

        # Получаем все слоты мастера
        cur = await db.execute(
            "SELECT day, time FROM master_slots WHERE master_id=? ORDER BY day, time",
            (master_id,)
        )
        all_slots = await cur.fetchall()

        # Получаем занятые слоты
        cur = await db.execute(
            "SELECT day, time FROM appointments WHERE master=?",
            (master_name,)
        )
        busy_slots = set(await cur.fetchall())

        # Фильтруем только доступные слоты
        available_slots = []
        for day_str, time_str in all_slots:
            slot_date = datetime.strptime(day_str, "%Y-%m-%d").date()
            if slot_date < today or slot_date > end_day:
                continue
            if (day_str, time_str) in busy_slots:
                continue
            available_slots.append((day_str, time_str))

        return available_slots

# ===== Vacation =====
async def set_master_vacation(master_name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE masters SET status=? WHERE name=?", ("в отпуске", master_name))
        await db.commit()

# ===== FSM =====
async def vacation_set(msg, state: FSMContext):
    master_name = msg.text.strip()
    await set_master_vacation(master_name)
    await msg.answer(f"🌴 Мастер {master_name} отправлен в отпуск.")
    await state.clear()