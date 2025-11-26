import os
from dotenv import load_dotenv

load_dotenv(dotenv_path="c:/Users/Daniil/Desktop/salon_bot/api.env")

# Попробуем сначала загрузить из указанного пути, если не получится — из ./api.env
if os.path.exists("c:/Users/Daniil/Desktop/salon_bot/api.env"):
    load_dotenv("c:/Users/Daniil/Desktop/salon_bot/api.env")
    print("✅ .env файл загружен успешно.")
elif os.path.exists("./api.env"):
    load_dotenv("./api.env")
    print("⚠️ .env файл не найден по указанному пути, загружен ./api.env")
else:
    print("❌ .env файл не найден.")

BOT_TOKEN = os.getenv("TOKEN")
admin_id = os.getenv("ADMIN_ID")
if not admin_id:
    raise ValueError("ADMIN_ID не задан в .env файле")
OWNER_ID = int(admin_id)
DB_PATH = os.getenv("DB_PATH")
THRESHOLD = 10_000  # для генераторов слотов