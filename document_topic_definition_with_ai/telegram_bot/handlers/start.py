from aiogram import Router, types
from aiogram.filters import Command
from config import config


router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message, users: dict):
    """
    Обработчик команды /start
    """
    welcome_text = (
        "🤖 *Добро пожаловать! Я ваш интеллектуальный аналитик документов.*\n\n"
        f"Ваш ID: `{message.from_user.id}`\n\n"
        "*Доступные команды:*\n"
        "• [/start](command:start) - начать работу\n"
        "• [/upload_doc](command:upload_doc) - отправить документ для анализа и поиска похожих\n"
        "• [/search](command:search) - поиск документов по запросу\n\n"
        "*Как это работает:*\n"
        "1️⃣ Отправьте документ (текст или TXT файл)\n"
        "2️⃣ Я проанализирую его, определю тематику (хабы/теги) и подготовлю краткий пересказ документа\n"
        "3️⃣ Вы сможете найти похожие документы в базе данных\n"
        "4️⃣ Вы сможете использовать фильтры (определённые хабы и теги вашего документа) для поиска только среди документов с избранными метками\n\n"
        "*Возможности:*\n"
        "• 🏷️ Определение хабов и тегов документа\n"
        "• 📝 Краткий пересказ (суммаризация)\n"
        "• 🔍 Поиск похожих документов\n"
        "• ⚙️ Настройка движков поиска\n\n"
        "Отправьте документ прямо сейчас или используйте [/upload_doc](command:upload_doc)"
    )
    
    await message.reply(welcome_text, parse_mode='Markdown')

@router.message(lambda message: message.text and message.text.startswith('/'))
async def handle_command_links(message: types.Message):
    """
    Обработчик прямых команд из текста (кликабельные ссылки)
    """
    command = message.text.lower()
    
    if command == '/start':
        await cmd_start(message, {})
    elif command == '/upload_doc':
        from handlers.upload_doc import cmd_upload_doc
        await cmd_upload_doc(message, config.OR_API_KEY)
    elif command == '/search':
        from handlers.upload_doc import cmd_search
        await cmd_search(message)
    else:
        pass