from fastapi import APIRouter, HTTPException
from models.search_models import SearchRequest, SearchResponse, SearchResult
from services.search_service import SearchService

router = APIRouter(prefix="/api/v1/search", tags=["search"])
search_service = SearchService()

@router.post("/", response_model=SearchResponse)
async def search(request: SearchRequest):
    """Основной поиск"""
    try:
        results = await search_service.search(
            query=request.query,
            top_k=request.top_k,
            engine=request.engine,
            hubs=request.hubs,
            tags=request.tags
        )
        
        return SearchResponse(
            success=True,
            query=request.query,
            results=[SearchResult(**r) for r in results],
            total=len(results),
            engine_used=request.engine
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/engines")
async def get_engines():
    """Получение доступных поисковых движков"""
    engines = await search_service.get_available_engines()
    return {"engines": engines}

@router.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    return {"status": "healthy", "service": "search-api"}