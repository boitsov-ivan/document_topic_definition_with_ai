from aiogram import BaseMiddleware
from aiogram.types import Update, Message
import datetime

class CleaningMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Update, data: dict):
        print("Проверка запроса.")
        

        if not event.message:
            return await handler(event, data)
        
        
        user = event.message.from_user
        username = user.username if user.username else f"user_{user.id}"
        text = event.message.text if event.message.text else "[no text]"
        
        print(f"[{datetime.datetime.now()}] Сообщение от {username}: {text[:50]}")
        return await handler(event, data)