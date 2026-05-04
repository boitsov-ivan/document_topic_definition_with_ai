import asyncio
from aiogram import Bot, Dispatcher

from config import config
from handlers import router

from middleware.logging import LoggingMiddleware
from middleware.cleaning import CleaningMiddleware
from middleware.antispam import AntiSpamMiddleware


bot = Bot(token=config.TELEGRAM_TOKEN)
dp = Dispatcher()
dp.include_router(router)

#dp.message.middleware(LoggingMiddleware())

dp.update.outer_middleware(LoggingMiddleware())
dp.update.outer_middleware(CleaningMiddleware())
dp.update.outer_middleware(AntiSpamMiddleware(time_limit=0.1))


dp['groq_api_key'] = config.GROQ_API_KEY
dp['hf_api_key'] = config.HF_API_KEY
dp['or_api_key'] = config.OR_API_KEY


async def main():
    print("Бот запущен!")
    await dp.start_polling(bot, users = dict())



if __name__ == "__main__":
    asyncio.run(main())