import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
HF_API_KEY = os.getenv("HF_API_KEY")
OR_API_KEY = os.getenv("OR_API_KEY")

if not TOKEN:
    raise  ValueError("Переменная окружения BOT_TOKEN не установлена!")


if not GROQ_API_KEY:
    raise  ValueError("Переменная окружения GROQ_API_KEY не установлена!")

if not HF_API_KEY:
    raise  ValueError("Переменная окружения HF_API_KEY не установлена!")


if not OR_API_KEY:
    raise  ValueError("Переменная окружения OR_API_KEY не установлена!")