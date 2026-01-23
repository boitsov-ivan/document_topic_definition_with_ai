from aiogram import BaseMiddleware
from aiogram.types import Update, Message, CallbackQuery
import datetime

class LoggingMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Update, data: dict):
        """
        Обрабатывает все типы обновлений
        """
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if event.message:
            user = event.message.from_user
            content = event.message.text or f"[{event.message.content_type}]"
            update_type = "MESSAGE"
            
        elif event.callback_query:
            user = event.callback_query.from_user
            content = event.callback_query.data
            update_type = "CALLBACK"
            
        elif event.edited_message:
            user = event.edited_message.from_user
            content = event.edited_message.text or "[edited]"
            update_type = "EDITED"
            
        elif event.channel_post:
            user = "Channel"
            content = event.channel_post.text or "[channel_post]"
            update_type = "CHANNEL_POST"
            
        else:
            user = "Unknown"
            content = str(event.update_id)
            update_type = "OTHER"
        
        print(f"[{timestamp}] {update_type} from {user}: {content[:100]}")
        
        return await handler(event, data)