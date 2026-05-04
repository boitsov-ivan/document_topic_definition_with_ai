from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import sys
from pathlib import Path
from api_ml.services.or_api import or_define_topic
from config import config


sys.path.append(str(Path(__file__).parent.parent.parent))

router = APIRouter(prefix="/summarize", tags=["summarization"])


class SummarizeRequest(BaseModel):
    text: str = Field(..., description="Текст для суммаризации", min_length=1)
    api_key: Optional[str] = Field(None, description="API ключ (опционально)")


class SummarizeResponse(BaseModel):
    success: bool
    summary: Optional[str] = None
    error: Optional[str] = None


@router.post("/", response_model=SummarizeResponse, summary="Суммаризация текста")
async def summarize_text(request: SummarizeRequest):
    """
    Анализирует текст через API.
    
    Возвращает краткое summary.
    """
    try:
        api_key = request.api_key if request.api_key else config.OR_API_KEY
        
        if not api_key:
            raise HTTPException(
                status_code=400, 
                detail="API ключ не предоставлен и не найден в конфигурации"
            )
        
        result = or_define_topic(request.text, api_key)
        
        return {
            "success": True,
            "summary": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))