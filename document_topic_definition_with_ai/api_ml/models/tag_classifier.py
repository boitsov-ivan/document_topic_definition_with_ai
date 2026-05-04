import pickle
import joblib
import numpy as np
from pathlib import Path
from typing import Union, List
from catboost import CatBoostClassifier
import pandas as pd
from sklearn.metrics import f1_score


class MultiLabelTagClassifier:
    """
    Класс модели классификации тегов
    """

    def __init__(self, model_dir: Union[str, Path]):
        """
        Загрузка модели и компонентов из директории
        """
        self.model_dir = Path(model_dir)

        self.model = CatBoostClassifier()
        self.model.load_model(self.model_dir / "catboost_tags_model.cbm")

        self.vectorizer = joblib.load(self.model_dir / "vectorizer_tags.pkl")

        with open(self.model_dir / "mlb_tags_filtered.pkl", 'rb') as f:
            self.mlb = pickle.load(f)

        with open(self.model_dir / "threshold_tags_info.pkl", 'rb') as f:
            self.threshold_info = pickle.load(f)

        self.threshold = self.threshold_info['best_threshold']

        print(f"Модель тегов успешно загружена из {model_dir}")
        print(f"Количество тегов: {len(self.mlb.classes_)}")
        print(f"Используемый порог: {self.threshold}")
        print(f"Лучший F1-score при обучении: {self.threshold_info['best_f1_score']:.3f}")

    def predict_proba(self, texts: Union[str, List[str]]) -> np.ndarray:
        """
        Предсказание вероятностей для текстов
        """
        if isinstance(texts, str):
            texts = [texts]

        X = self.vectorizer.transform(texts)
        probabilities = self.model.predict_proba(X)
        return probabilities

    def predict(self, texts: Union[str, List[str]], threshold: float = None) -> np.ndarray:
        """
        Предсказание бинарных меток для текстов
        """
        if threshold is None:
            threshold = self.threshold

        probabilities = self.predict_proba(texts)
        predictions = (probabilities >= threshold).astype(int)
        return predictions

    def predict_tag_names(self, texts: Union[str, List[str]], threshold: float = None) -> List[List[str]]:
        """
        Предсказание названий тегов для текстов
        """
        if isinstance(texts, str):
            texts = [texts]

        predictions = self.predict(texts, threshold)

        tag_names = []
        for pred in predictions:
            names = self.mlb.inverse_transform(pred.reshape(1, -1))[0]
            tag_names.append(list(names))

        return tag_names

    def predict_with_confidence(self, text: str, top_k: int = 10) -> dict:
        """
        Детальное предсказание для одного текста с топ-k вероятностями
        """
        proba = self.predict_proba(text)[0]
        predictions = (proba >= self.threshold).astype(int)

        pred_tags = self.mlb.inverse_transform(predictions.reshape(1, -1))[0]

        top_indices = proba.argsort()[-top_k:][::-1]
        top_predictions = [
            {
                'tag': self.mlb.classes_[idx],
                'probability': float(proba[idx])
            }
            for idx in top_indices
        ]

        return {
            'text': text[:200] + "..." if len(text) > 200 else text,
            'predicted_tags': list(pred_tags),
            'top_predictions': top_predictions,
            'num_tags_predicted': len(pred_tags)
        }

    def evaluate_on_test(self, X_test_text: pd.Series, y_test: np.ndarray) -> dict:
        """
        Оценка модели на тестовых данных
        """
        y_pred = self.predict(X_test_text)

        metrics = {
            'f1_micro': f1_score(y_test, y_pred, average='micro', zero_division=0),
            'f1_macro': f1_score(y_test, y_pred, average='macro', zero_division=0),
            'f1_weighted': f1_score(y_test, y_pred, average='weighted', zero_division=0),
            'f1_samples': f1_score(y_test, y_pred, average='samples', zero_division=0),
            'exact_match': np.mean(np.all(y_test == y_pred, axis=1))
        }
        return metrics

    def get_tag_statistics(self, texts: Union[str, List[str]]) -> dict:
        """
        Получение статистики по предсказанным тегам
        """
        predictions = self.predict(texts)
        tag_names = self.predict_tag_names(texts)

        stats = {
            'total_documents': len(texts) if isinstance(texts, list) else 1,
            'total_predictions': sum(len(tags) for tags in tag_names),
            'avg_tags_per_doc': np.mean([len(tags) for tags in tag_names]) if tag_names else 0,
            'unique_tags_predicted': len(set([tag for tags in tag_names for tag in tags])) if tag_names else 0,
            'all_predicted_tags': tag_names
        }
        return stats