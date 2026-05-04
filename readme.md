# Аналитик документов
## Переменные окружения
Перед деплоем сервиса необходимо заполнить .env файл по образцу в .env.example

**cd document_topic_definition_with_ai**

заполням файл .env.example
и сохраняем его в .env

## Загрузка моделей и документов для информационного поиска
Перед деплоем сервиса необходимо загрузить модели и документы для векторного поиска похожих.

Запускаем скрипт:

**cd document_topic_definition_with_ai** (нужно запускать из этой папки)

**./load_data_and_models.sh**


## Режимы запуска сборки сервиса
Сервис можно деплоить двумя способами:
1) dockercompose
2) kubernetes

## Dockercompose сборка
### Конфигурация сервиса в docker-compose.yml

По умолчанию собираем сервис без инференса собственной модели саммаризации, а для саммаризации используем API LLM.

Используем Dockerfile.api_ml.


**docker-compose.yml** (по умолчанию):
```yaml
  ml-api:
    build:
      context: .
      dockerfile: containers/Dockerfile.api_ml
      #dockerfile: containers/Dockerfile.api_ml_full
```


Для сборки сервиса с инференсом собственной модели саммаризации (+4 гигабайта ГПУ + 2 гигабайта ОЗУ) используйте Dockerfile.api_ml_full.

**docker-compose.yml** (скорректировать по образцу ниже):
```yaml
  ml-api:
    build:
      context: .
      #dockerfile: containers/Dockerfile.api_ml
      dockerfile: containers/Dockerfile.api_ml_full
```

### Обычный запуск
**./start.sh**

Появится меню с выбором:

1) 🚀 Обычный запуск (с индексацией)
2) 🧹 Очистка Qdrant + запуск
3) 🗑️ Полная очистка (все volumes) + запуск
4) 💾 Запуск с существующими коллекциями
5) 📋 Проверить статус сервисов
6) 📊 Посмотреть логи
7) 🛑 Остановить все сервисы
0) ❌ Выход

### Очистка только Qdrant + запуск
**./start.sh --clean-qdrant**

### Полная очистка всех volumes + запуск
**./start.sh --clean-all**

### Только проверить коллекции
**./start.sh --check**

### Показать справку
**./start.sh --help**


