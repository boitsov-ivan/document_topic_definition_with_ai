from routes import search
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import sys
from services.search_engine import SearchEngineManager
import os
from config import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

search_manager = None

def get_init_limit() -> int | None:
    """Получение лимита из переменной окружения"""
    limit_str = config.INIT_LIMIT
    if limit_str and limit_str.isdigit():
        limit = int(limit_str)
        logger.info(f"Установлен лимит документов: {limit}")
        return limit
    logger.info("Лимит не установлен, будут использованы все документы")
    return None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    global search_manager
    
    logger.info("Запуск Search API сервиса...")
    
    search_manager = SearchEngineManager()
    
    if search_manager._engines is not None:
        logger.info("Очищаем существующие движки для переинициализации...")
        search_manager._engines = None
    
    limit = get_init_limit()
    logger.info(f"Инициализация с лимитом: {limit}")
    
    try:
        if config.QDRANT_DIR.exists() and any(config.QDRANT_DIR.iterdir()):
            logger.info("Найдены существующие данные, загружаем...")
        else:
            logger.info("Данные не найдены, будут созданы новые...")
        
        search_manager.initialize(
            csv_path=str(config.CSV_DATA_PATH),
            limit=limit,
            force=True
        )
        
        engines = search_manager.get_available_engines()
        if engines:
            logger.info(f"Поисковые движки успешно инициализированы: {engines}")
        else:
            logger.warning("Не удалось инициализировать поисковые движки")
            
    except Exception as e:
        logger.error(f"Ошибка загрузки данных: {e}")
        import traceback
        traceback.print_exc()
        search_manager = None
    
    logger.info("API сервис готов к работе")
    
    yield
    
    logger.info("Остановка Search API сервиса...")



app = FastAPI(
    title="Search API",
    description="API для векторного поиска документов",
    version="1.0.0",
    lifespan=lifespan
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(search.router)


@app.get("/")
async def root():
    return {"message": "Search API is running"}


@app.get("/api/v1/search/health")
async def health_check():
    """Проверка статуса поискового движка"""
    if search_manager is None or search_manager._engines is None:
        return {
            "status": "unhealthy",
            "message": "Search engine not initialized",
            "engines": []
        }
    
    return {
        "status": "healthy",
        "message": "Search engine is ready",
        "engines": search_manager.get_available_engines()
    }