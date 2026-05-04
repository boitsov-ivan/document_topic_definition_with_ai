import sys
from pathlib import Path
from api_ml.models.tag_classifier import MultiLabelTagClassifier


sys.path.append(str(Path(__file__).parent.parent.parent))
MODEL_DIR_TAGS = Path(__file__).parent.parent / "models" / "tag_classifier"

loaded_tag_classifier = MultiLabelTagClassifier(MODEL_DIR_TAGS)

def classify_tags(text: str, top_k: int = 10) -> dict:
    """
    Классификация текста по тегам
    
    Args:
        text: текст для классификации
        top_k: количество топ-тегов для вывода
        
    Returns:
        словарь с результатами классификации
    """
    try:
        result = loaded_tag_classifier.predict_with_confidence(text, top_k=top_k)
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