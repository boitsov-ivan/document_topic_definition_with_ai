from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import sys
from pathlib import Path
from api_ml.services.hub_classifier_service import classify_hubs
from api_ml.services.tag_classifier_service import classify_tags


sys.path.append(str(Path(__file__).parent.parent.parent))

router = APIRouter(prefix="/classify", tags=["classification"])


class TextRequest(BaseModel):
    text: str = Field(..., description="Текст для классификации", min_length=1)
    top_k: Optional[int] = Field(5, description="Количество топ-результатов", ge=1, le=20)


class HubResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None


class TagResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None


@router.post("/hubs", response_model=HubResponse, summary="Классификация хабов")
async def classify_hubs_endpoint(request: TextRequest):
    """
    Классифицирует текст по хабам.
    
    Возвращает предсказанные хабы и их вероятности.
    """
    result = classify_hubs(request.text, top_k=request.top_k)
    
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])
    
    return result


@router.post("/tags", response_model=TagResponse, summary="Классификация тегов")
async def classify_tags_endpoint(request: TextRequest):
    """
    Классифицирует текст по тегам.
    
    Возвращает предсказанные теги и их вероятности.
    """
    result = classify_tags(request.text, top_k=request.top_k)
    
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])
    
    return result