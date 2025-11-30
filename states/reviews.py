from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.state import StatesGroup, State

class ReviewStates(StatesGroup):
    choosing_service = State()
    choosing_master = State()
    choosing_rating = State()
    writing_text = State()
    waiting_for_review = State()