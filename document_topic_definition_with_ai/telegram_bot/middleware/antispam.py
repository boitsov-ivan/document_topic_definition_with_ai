from aiogram import BaseMiddleware
from aiogram.types import Update
from collections import defaultdict
import time
from typing import Dict, Any, Callable


class AntiSpamMiddleware(BaseMiddleware):
    def __init__(self, time_limit: float = 0.3, 
                 message_limit: int = 10,
                 time_window: int = 10):
        """
        Middleware для защиты от спама
        
        Args:
            time_limit: минимальное время между сообщениями (секунды)
            message_limit: максимальное количество сообщений в time_window
            time_window: временное окно для ограничения количества сообщений (секунды)
        """
        self.time_limit = time_limit
        self.message_limit = message_limit
        self.time_window = time_window
        
        self.user_last_message: Dict[int, float] = defaultdict(float)
        
        self.user_message_history: Dict[int, list] = defaultdict(list)
        
        self.exempt_users: set[int] = set()

    async def __call__(
        self,
        handler: Callable,
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        """
        Обработка входящего обновления
        """
        user_id = None
        message = None
        
        if event.message:
            user_id = event.message.from_user.id
            message = event.message
        elif event.callback_query:
            user_id = event.callback_query.from_user.id
            message = event.callback_query.message
        elif event.edited_message:
            user_id = event.edited_message.from_user.id
            message = event.edited_message
        else:
            return await handler(event, data)
        
        if user_id in self.exempt_users:
            return await handler(event, data)
        
        current_time = time.time()
        
        last_message_time = self.user_last_message.get(user_id, 0)
        
        if current_time - last_message_time < self.time_limit:
            time_left = self.time_limit - (current_time - last_message_time)
            
            if message:
                try:
                    await message.answer(
                        f"⏳ Слишком быстро! Подождите {time_left:.1f} сек."
                    )
                except:
                    pass
            
            return
        
        self.user_message_history[user_id] = [
            t for t in self.user_message_history[user_id]
            if current_time - t <= self.time_window
        ]
        
        if len(self.user_message_history[user_id]) >= self.message_limit:
            if message:
                try:
                    await message.answer(
                        f"🚫 Слишком много сообщений! "
                        f"Лимит: {self.message_limit} сообщений за {self.time_window} сек."
                    )
                except:
                    pass
            
            return
        
        self.user_last_message[user_id] = current_time
        self.user_message_history[user_id].append(current_time)
        
        return await handler(event, data)
    
    def add_exempt_user(self, user_id: int) -> None:
        """Добавить пользователя в исключения"""
        self.exempt_users.add(user_id)
    
    def remove_exempt_user(self, user_id: int) -> None:
        """Удалить пользователя из исключений"""
        self.exempt_users.discard(user_id)
    
    def clear_user_history(self, user_id: int) -> None:
        """Очистить историю сообщений пользователя"""
        if user_id in self.user_last_message:
            del self.user_last_message[user_id]
        if user_id in self.user_message_history:
            del self.user_message_history[user_id]
    
    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Получить статистику пользователя"""
        current_time = time.time()
        
        if user_id in self.user_message_history:
            self.user_message_history[user_id] = [
                t for t in self.user_message_history[user_id]
                if current_time - t <= self.time_window
            ]
        
        return {
            "last_message_time": self.user_last_message.get(user_id),
            "messages_in_window": len(self.user_message_history.get(user_id, [])),
            "time_since_last": current_time - self.user_last_message.get(user_id, 0) if self.user_last_message.get(user_id) else None,
            "is_exempt": user_id in self.exempt_users
        }