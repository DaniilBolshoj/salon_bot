import phonenumbers
from database import get_dates_window

userflow = {}  # user_id: {"service": str, "master": str, "day": str, "time": str, "step": str}

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
