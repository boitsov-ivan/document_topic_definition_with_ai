from aiogram import Router, types
from aiogram.filters import Command

router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message, users: dict):
    """
    Обработчик команды /start
    """
    welcome_text = (
        "Добро пожаловать! Я ваш аналитик документов.\n"
        f"Ваш ID: {message.from_user.id}\n\n"
        "Доступные команды:\n"
        "/start - начать работу\n"
        "/load_doc - отправить документ для анализа\n"
    )
    
    await message.reply(welcome_text)