#!/bin/bash

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }


if [ ! -f .env ]; then
    print_error "Файл .env не найден"
    exit 1
fi


print_info "Создание secret.yaml из .env..."


./generate-secret-k8s.sh



if [ -f k8s/secret.yaml ]; then
    print_success "secret.yaml успешно создан"
else
    print_error "secret.yaml не был создан"
    exit 1
fi



print_info "Остановка Minikube (если запущен)..."
minikube stop 2>/dev/null || true
sleep 3


print_info "Запуск Minikube..."
minikube start --cpus=4 --memory=4096 --disk-size=15g


print_info "Настройка Docker окружения..."
eval $(minikube docker-env)




print_info "Сборка Docker образов..."
docker build -f containers/Dockerfile.api_retrieval -t k8s-registry/search-api:latest . &
docker build -f containers/Dockerfile.gateway -t k8s-registry/gateway:latest . &
docker build -f containers/Dockerfile.queue_worker -t k8s-registry/worker:latest . &
docker build -f containers/Dockerfile.api_ml -t k8s-registry/ml-api:latest . &
docker build -f containers/Dockerfile.streamlit -t k8s-registry/streamlit:latest . &
docker build -f containers/Dockerfile.bot -t k8s-registry/telegram-bot:latest . &
wait
print_success "Все образы собраны"


print_info "Проверка образов в Minikube..."
docker images | grep k8s-registry || print_warning "Образы не найдены!"


print_info "Включение ingress..."
minikube addons enable ingress


# print_info "Удаление старого namespace (если есть)..."
# kubectl delete namespace document-analyzer --ignore-not-found
# sleep 5

print_info "Проверка существования namespace..."
if kubectl get namespace document-analyzer &>/dev/null; then
    print_warning "Namespace уже существует, данные сохраняются"
else
    kubectl create namespace document-analyzer
fi





print_info "Применение Kubernetes конфигураций..."
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
kubectl apply -f k8s/telegram-bot.yaml
kubectl apply -f k8s/ingress.yaml


print_info "Ожидание готовности подов..."
sleep 15
kubectl wait --for=condition=ready pod --all -n document-analyzer --timeout=300s 2>/dev/null || true


echo ""
echo "=== Статус подов ==="
kubectl get pods -n document-analyzer


echo ""
echo "=== Статус сервисов ==="
kubectl get svc -n document-analyzer



echo ""
print_info "Открытие доступа к Streamlit..."
minikube service streamlit -n document-analyzer --url
echo "Откройте вручную: http://192.168.49.2:30085"

echo ""
echo "===================================================="
print_success "Развёртывание завершено!"
echo "===================================================="
echo ""
print_info "Доступ к сервисам:"
echo "  • Streamlit UI:    minikube service streamlit -n document-analyzer"
echo "  • Gateway API:     minikube service search-gateway -n document-analyzer"
echo "  • RabbitMQ UI:     minikube service rabbitmq -n document-analyzer"
echo "  • Qdrant Console:  minikube service qdrant -n document-analyzer"
echo ""
print_info "Порт-форвардинг (альтернатива):"
echo "  • kubectl port-forward -n document-analyzer svc/streamlit 8501:8501"
echo "  • kubectl port-forward -n document-analyzer svc/search-gateway 8002:8002"
echo ""
print_info "Полезные команды:"
echo "  • Логи:     kubectl logs -n document-analyzer -f <pod-name>"
echo "  • Статус:   kubectl get all -n document-analyzer"
echo "  • Остановка: minikube stop"
echo "  • Удаление: minikube delete"
echo ""


echo ""
print_info "Ожидание полной инициализации search-api (индексация может занять несколько часов)..."
echo ""


wait_for_search_api() {
    local max_wait=6000000
    local wait_time=0
    local interval=10

    while [ $wait_time -lt $max_wait ]; do
        local pod_name=$(kubectl get pods -n document-analyzer -l app=search-api -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
        
        if [ -n "$pod_name" ]; then
            local logs=$(kubectl logs -n document-analyzer $pod_name --tail=50 2>/dev/null)
            
            if echo "$logs" | grep -q "Application startup complete"; then
                print_success "Search API полностью инициализирован и готов к работе!"
                return 0
            elif echo "$logs" | grep -q "Uvicorn running on"; then
                print_success "Search API запущен и готов!"
                return 0
            elif echo "$logs" | grep -q "Все поисковые движки успешно инициализированы"; then
                print_success "Search API готов с инициализированными поисковыми движками!"
                return 0
            fi
        fi
        
        sleep $interval
        wait_time=$((wait_time + interval))
        echo -n "."
    done
    
    print_warning "Search API не завершил инициализацию за отведенное время"
    return 1
}


print_info "Логи процесса инициализации search-api:"
echo ""


kubectl logs -n document-analyzer deployment/search-api -f 2>/dev/null &
LOG_PID=$!


wait_for_search_api


kill $LOG_PID 2>/dev/null || true

echo ""
print_info "Финальная проверка статуса сервисов:"
kubectl get pods -n document-analyzer

echo ""
print_info "Проверка здоровья API:"
kubectl port-forward -n document-analyzer svc/search-api 8000:8000 > /dev/null 2>&1 &
PF_PID=$!
sleep 3

HEALTH_STATUS=$(curl -s http://localhost:8000/api/v1/search/health 2>/dev/null || echo '{"status":"checking"}')
if echo "$HEALTH_STATUS" | grep -q "healthy"; then
    print_success "Search API health check: OK"
else
    print_warning "Search API health check: еще инициализируется"
fi

kill $PF_PID 2>/dev/null || true

echo ""
echo "===================================================="
print_success "Развёртывание завершено!"
echo "===================================================="



trap 'print_error "Прервано"; exit 1' INT TERM