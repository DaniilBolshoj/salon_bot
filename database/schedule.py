from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from database.masters import update_master_status
from aiogram import Router, F, types
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta
import aiosqlite
from database import DB_PATH, WEEKDAYS

router = Router()

class MasterVacation(StatesGroup):
    waiting_for_name = State()

class SetMasterSchedule(StatesGroup):
    waiting_for_master = State()
    waiting_for_days = State()
    waiting_for_start_time = State()
    waiting_for_end_time = State()

# ======= Master days & slots =======
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
        cur = await db.execute("""SELECT md.day FROM master_days md
                                  JOIN masters m ON m.id=md.master_id
                                  WHERE m.name=? ORDER BY md.day""", (master_name,))
        rows = await cur.fetchall()
        return [r[0] for r in rows]

async def set_master_slots(master_name, start_time, end_time, selected_days, slot_duration_hours=1):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id FROM masters WHERE name=?", (master_name,))
        r = await cur.fetchone()
        if not r:
            return False
        master_id = r[0]
        await db.execute("DELETE FROM master_slots WHERE master_id=?", (master_id,))

        start_dt = datetime.strptime(start_time, "%H:%M")
        end_dt = datetime.strptime(end_time, "%H:%M")

        today = datetime.today()
        for day_offset in range(14):  # например 2 недели вперёд
            current_day = today + timedelta(days=day_offset)
            weekday_str = [k for k,v in WEEKDAYS.items() if v == current_day.weekday()][0]
            if weekday_str in selected_days:
                slot_dt = datetime.combine(current_day, start_dt.time())
                end_slot_dt = datetime.combine(current_day, end_dt.time())
                while slot_dt + timedelta(hours=slot_duration_hours) <= end_slot_dt + timedelta(seconds=1):
                    await db.execute(
                        "INSERT INTO master_slots(master_id, day, time) VALUES (?,?,?)",
                        (master_id, current_day.strftime("%Y-%m-%d"), slot_dt.strftime("%H:%M"))
                    )
                    slot_dt += timedelta(hours=slot_duration_hours)
        await db.commit()
        return True

async def get_master_slots(master_name, selected_weekdays, start_time, end_time, slot_duration_hours=1, days_ahead=14):
    """
    selected_weekdays: ["Пн", "Ср", "Пт"]
    start_time, end_time: "08:30", "16:30"
    slot_duration_hours: 1
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id FROM masters WHERE name=?", (master_name,))
        r = await cur.fetchone()
        if not r:
            return False
        master_id = r[0]
        
        # Удаляем старые слоты
        await db.execute("DELETE FROM master_slots WHERE master_id=?", (master_id,))

        today = datetime.today()
        end_day = today + timedelta(days=days_ahead)
        start_dt = datetime.strptime(start_time, "%H:%M")
        end_dt = datetime.strptime(end_time, "%H:%M")

        current_day = today
        while current_day <= end_day:
            weekday_str = [k for k,v in WEEKDAYS.items() if v == current_day.weekday()][0]
            if weekday_str in selected_weekdays:
                slot_dt = datetime.combine(current_day, start_dt.time())
                end_slot_dt = datetime.combine(current_day, end_dt.time())
                while slot_dt + timedelta(hours=slot_duration_hours) <= end_slot_dt + timedelta(seconds=1):
                    await db.execute(
                        "INSERT INTO master_slots(master_id, day, time) VALUES (?,?,?)",
                        (master_id, current_day.strftime("%Y-%m-%d"), slot_dt.strftime("%H:%M"))
                    )
                    slot_dt += timedelta(hours=slot_duration_hours)
            current_day += timedelta(days=1)
        await db.commit()
    return True

@router.message(MasterVacation.waiting_for_name)
async def vacation_set(msg: types.Message, state: FSMContext):
    master_name = msg.text.strip()
    await update_master_status(master_name, "в отпуске")
    await msg.answer(f"🌴 Мастер {master_name} отправлен в отпуск.")
    await state.clear()