import phonenumbers
from database import get_dates_window

# Глобальное хранилище flow
userflow: dict[int, dict] = {}


def init_admin_master_flow(user_id: int, master_name: str):
    userflow[user_id] = {
        "master_name": master_name,
        "selected_services": [],
        "selected_days": [],
        "next": "choose_services"
    }

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
