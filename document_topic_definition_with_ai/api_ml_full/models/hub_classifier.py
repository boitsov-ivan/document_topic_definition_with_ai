import pickle
import joblib
import numpy as np
from pathlib import Path
from typing import Union, List
from catboost import CatBoostClassifier
import pandas as pd
from sklearn.metrics import f1_score


class MultiLabelHubClassifier:
    """
    Класс для инференса модели многометочной классификации хабов
    """

    def __init__(self, model_dir: Union[str, Path]):
        """
        Загрузка модели и компонентов

        Args:
            model_dir: путь к директории с сохранённой моделью
        """
        self.model_dir = Path(model_dir)

        self.model = CatBoostClassifier()
        self.model.load_model(self.model_dir / "catboost_model.cbm")

        self.vectorizer = joblib.load(self.model_dir / "vectorizer.pkl")

        with open(self.model_dir / "mlb_filtered.pkl", 'rb') as f:
            self.mlb = pickle.load(f)

        with open(self.model_dir / "threshold_info.pkl", 'rb') as f:
            self.threshold_info = pickle.load(f)

        self.threshold = self.threshold_info['best_threshold']

        print(f"Модель хабов успешно загружена из {model_dir}")
        print(f"Количество классов: {len(self.mlb.classes_)}")
        print(f"Используемый порог: {self.threshold}")

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

    def predict_hub_names(self, texts: Union[str, List[str]], threshold: float = None) -> List[List[str]]:
        """
        Предсказание названий хабов для текстов
        """
        if isinstance(texts, str):
            texts = [texts]

        predictions = self.predict(texts, threshold)

        hub_names = []
        for pred in predictions:
            names = self.mlb.inverse_transform(pred.reshape(1, -1))[0]
            hub_names.append(list(names))

        return hub_names

    def predict_with_confidence(self, text: str, top_k: int = 5) -> dict:
        """
        Детальное предсказание для одного текста с топ-k вероятностями
        """
        proba = self.predict_proba(text)[0]
        predictions = (proba >= self.threshold).astype(int)

        pred_hubs = self.mlb.inverse_transform(predictions.reshape(1, -1))[0]

        top_indices = proba.argsort()[-top_k:][::-1]
        top_predictions = [
            {
                'hub': self.mlb.classes_[idx],
                'probability': float(proba[idx])
            }
            for idx in top_indices
        ]

        return {
            'text': text[:200] + "..." if len(text) > 200 else text,
            'predicted_hubs': list(pred_hubs),
            'top_predictions': top_predictions,
            'all_probabilities': dict(zip(self.mlb.classes_, proba))
        }

    def evaluate_on_test(self, X_test_text: pd.Series, y_test: np.ndarray) -> dict:
        """
        Оценка модели на тестовых данных
        """
        y_pred = self.predict(X_test_text)

        metrics = {
            'f1_micro': f1_score(y_test, y_pred, average='micro'),
            'f1_macro': f1_score(y_test, y_pred, average='macro'),
            'f1_weighted': f1_score(y_test, y_pred, average='weighted'),
            'f1_samples': f1_score(y_test, y_pred, average='samples')
        }
        return metrics