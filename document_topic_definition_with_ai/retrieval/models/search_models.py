from pydantic import BaseModel, Field
from typing import List, Optional

class SearchRequest(BaseModel):
    query: str = Field(..., description="Поисковый запрос")
    top_k: int = Field(5, ge=1, le=20, description="Количество результатов")
    engine: str = Field("hybrid", description="Тип поиска: dense, hybrid, rerank, full")
    hubs: Optional[List[str]] = Field(None, description="Фильтр по хабам")
    tags: Optional[List[str]] = Field(None, description="Фильтр по тегам")

class SearchResult(BaseModel):
    doc_id: int
    title: str
    text: str
    url: str
    score: Optional[float]
    chunk_text: str
    hubs: Optional[List[str]] = []
    tags: Optional[List[str]] = []

class SearchResponse(BaseModel):
    success: bool
    query: str
    results: List[SearchResult]
    total: int
    engine_used: str