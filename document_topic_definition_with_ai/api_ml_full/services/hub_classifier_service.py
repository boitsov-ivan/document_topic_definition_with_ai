import sys
from pathlib import Path
from api_ml.models.hub_classifier import MultiLabelHubClassifier

sys.path.append(str(Path(__file__).parent.parent.parent))
MODEL_DIR_HUBS = Path(__file__).parent.parent / "models" / "hub_classifier"

loaded_hub_classifier = MultiLabelHubClassifier(MODEL_DIR_HUBS)

def classify_hubs(text: str, top_k: int = 5) -> dict:
    """
    Классификация текста по хабам
    
    Args:
        text: текст для классификации
        top_k: количество топ-хабов для вывода
        
    Returns:
        словарь с результатами классификации
    """
    try:
        result = loaded_hub_classifier.predict_with_confidence(text, top_k=top_k)
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "data": None
        }