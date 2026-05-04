import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

class Config:
    BASE_DIR = Path(__file__).parent

    # Telegram настройки
    TELEGRAM_TOKEN = os.getenv('BOT_TOKEN', '')
    if not TELEGRAM_TOKEN:
        raise  ValueError("Переменная окружения BOT_TOKEN для телеграм не установлена!")

    # ключи API LLM
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    HF_API_KEY = os.getenv("HF_API_KEY")
    OR_API_KEY = os.getenv("OR_API_KEY")

    if not GROQ_API_KEY:
        raise  ValueError("Переменная окружения GROQ_API_KEY не установлена!")

    if not HF_API_KEY:
        raise  ValueError("Переменная окружения HF_API_KEY не установлена!")


    if not OR_API_KEY:
        raise  ValueError("Переменная окружения OR_API_KEY не установлена!")


    # Директории данных
    DATA_DIR = Path(os.getenv('DATA_DIR', BASE_DIR / 'data'))
    QDRANT_DIR = Path(os.getenv('QDRANT_PATH', DATA_DIR / 'qdrant'))
    LOGS_DIR = Path(os.getenv('LOGS_PATH', DATA_DIR / 'logs'))
    MODELS_CACHE = Path(os.getenv('MODELS_CACHE', DATA_DIR / 'models_cache'))
    CSV_DATA_PATH = Path(os.getenv('CSV_DATA_PATH', BASE_DIR / 'docs_cleaned.csv'))
    
    # Создание директорий
    for dir_path in [DATA_DIR, QDRANT_DIR, LOGS_DIR, MODELS_CACHE]:
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"Warning: Could not create directory {dir_path}: {e}")
    
    # настройки API сервиса
    API_URL=os.getenv("API_URL")
    ML_API_URL=os.getenv("ML_API_URL")
    SEARCH_API_URL=os.getenv("SEARCH_API_URL")
    INIT_LIMIT=os.getenv('INIT_LIMIT')
    

config = Config()