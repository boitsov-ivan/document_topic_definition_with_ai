from typing import List, Dict, Optional
from services.search_engine import SearchEngineManager

class SearchService:
    """Сервис для работы с поиском"""
    
    def __init__(self):
        self.manager = None
        self._initialized = False
    
    def _ensure_initialized(self):
        """Ленивая инициализация - только при первом использовании"""
        if not self._initialized:
            self.manager = SearchEngineManager()
            # НЕ вызываем initialize() здесь!
            # Инициализация будет выполнена в main.py при старте приложения
            self._initialized = True
    
    def is_ready(self) -> bool:
        """Проверка, готов ли поисковый движок"""
        return self.manager is not None and self.manager._engines is not None
    
    async def search(self, query: str, top_k: int = 5, 
                     engine: str = 'hybrid',
                     hubs: Optional[List[str]] = None,
                     tags: Optional[List[str]] = None) -> List[Dict]:
        """Поиск документов"""
        self._ensure_initialized()
        
        # Если движки не инициализированы, возвращаем пустой результат
        if not self.is_ready():
            print("Search engine not initialized yet")
            return []
        
        try:
            results = self.manager.search(
                query=query,
                engine_name=engine,
                top_k=top_k,
                hubs=hubs,
                tags=tags
            )
            return results
        except Exception as e:
            print(f"Search error: {e}")
            return []
    
    async def get_available_engines(self) -> List[str]:
        """Получение списка доступных движков"""
        if not self.is_ready():
            return []
        
        engines = self.manager._engines
        return list(engines.keys()) if engines else []