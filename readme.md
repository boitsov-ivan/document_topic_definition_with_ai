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

### Запуск вручную docker-compose

#### Сборка образов и запуск контейнеров

**docker-compose up -d --build**

#### Остановить все контейнеры

**docker-compose down**


## Кубернетес. Запуск в Minikube
### Создать secret.yaml из .env

**./generate-secret-k8s.sh**

### Сборка и запуск в Minikube скриптом

откройте **k8s-deploy.sh**

При наличии возможности увеличьте ресурсы:

```
print_info "Запуск Minikube..."
minikube start --cpus=2 --memory=3096 --disk-size=10g
```
запустите скрипт:

**./k8s-deploy.sh**


### Сборка образов для Minikube вручную

### Запустить Minikube
```
minikube start --cpus=2 --memory=3192 --disk-size=10g
```
#### Настроить окружение на Docker Minikube
```
eval $(minikube docker-env)
```
#### Собрать образы
```
docker build -f containers/Dockerfile.api_retrieval -t k8s-registry/search-api:latest .
docker build -f containers/Dockerfile.gateway -t k8s-registry/gateway:latest .
docker build -f containers/Dockerfile.queue_worker -t k8s-registry/worker:latest .
docker build -f containers/Dockerfile.api_ml -t k8s-registry/ml-api:latest .
docker build -f containers/Dockerfile.streamlit -t k8s-registry/streamlit:latest .
docker build -f containers/Dockerfile.bot -t k8s-registry/telegram-bot:latest .
```

### Включить ingress

minikube addons enable ingress

### Применить все конфиги
```
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/pvc.yaml
kubectl apply -f k8s/qdrant.yaml
kubectl apply -f k8s/rabbitmq.yaml
kubectl apply -f k8s/redis.yaml
kubectl apply -f k8s/ml-api.yaml
kubectl apply -f k8s/search-api.yaml
kubectl apply -f k8s/gateway.yaml
kubectl apply -f k8s/worker.yaml
kubectl apply -f k8s/streamlit.yaml
kubectl apply -f k8s/ingress.yaml
```
### Проверить статус

kubectl get all -n document-analyzer

### Открыть доступ

minikube service streamlit -n document-analyzer


#### Отркыть доступ через порт-форвардинг

kubectl port-forward -n document-analyzer svc/streamlit 8501:8501


### Остановка миникуб

minikube stop


### Удаление

minikube delete