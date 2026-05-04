from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import sys
from pathlib import Path
from api_ml.services.summarize import create_summary
from config import config


sys.path.append(str(Path(__file__).parent.parent.parent))

router = APIRouter(prefix="/summarize", tags=["summarization"])


class SummarizeRequest(BaseModel):
    text: str = Field(..., description="Текст для суммаризации", min_length=1)


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

        result = create_summary(request.text)
        
        return {
            "success": True,
            "summary": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))