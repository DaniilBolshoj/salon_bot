import os
from dotenv import load_dotenv

load_dotenv(dotenv_path="c:/Users/Daniil/Desktop/salon_bot/api.env")

BOT_TOKEN = os.getenv("TOKEN")
OWNER_ID = int(os.getenv("ADMIN_ID"))
DB_PATH = os.getenv("DB_PATH")
THRESHOLD = 10_000  # для генераторов слотов