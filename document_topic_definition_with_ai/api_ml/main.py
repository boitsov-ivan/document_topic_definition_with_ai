from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sys
from pathlib import Path

from api_ml.routes import classification, summarization

sys.path.append(str(Path(__file__).parent.parent))


app = FastAPI(
    title="ML API Service",
    description="API для классификации хабов, тегов и суммаризации текста",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)



app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



app.include_router(classification.router)
app.include_router(summarization.router)


@app.get("/", tags=["health"])
async def root():
    """Проверка работоспособности API"""
    return {
        "service": "ML API Service",
        "status": "running",
        "endpoints": [
            "/classify/hubs - классификация хабов",
            "/classify/tags - классификация тегов",
            "/summarize/ - суммаризация текста",
            "/docs - документация Swagger",
            "/redoc - документация ReDoc"
        ]
    }


@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}