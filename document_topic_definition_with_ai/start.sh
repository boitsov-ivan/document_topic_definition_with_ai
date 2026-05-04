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

check_required_files() {
    print_info "Проверка наличия необходимых файлов..."
    
    local missing_files=()
    local required_files=(
        "docs_cleaned.csv"
        "api_ml/models/hub_classifier/catboost_model.cbm"
        "api_ml/models/hub_classifier/mlb_filtered.pkl"
        "api_ml/models/hub_classifier/threshold_info.pkl"
        "api_ml/models/hub_classifier/vectorizer.pkl"
        "api_ml/models/tag_classifier/catboost_tags_model.cbm"
        "api_ml/models/tag_classifier/mlb_tags_filtered.pkl"
        "api_ml/models/tag_classifier/threshold_tags_info.pkl"
        "api_ml/models/tag_classifier/vectorizer_tags.pkl"
        "api_ml_full/models/hub_classifier/catboost_model.cbm"
        "api_ml_full/models/hub_classifier/mlb_filtered.pkl"
        "api_ml_full/models/hub_classifier/threshold_info.pkl"
        "api_ml_full/models/hub_classifier/vectorizer.pkl"
        "api_ml_full/models/tag_classifier/catboost_tags_model.cbm"
        "api_ml_full/models/tag_classifier/mlb_tags_filtered.pkl"
        "api_ml_full/models/tag_classifier/threshold_tags_info.pkl"
        "api_ml_full/models/tag_classifier/vectorizer_tags.pkl"
        "api_ml_full/models/lora_vikhr_improved/adapter_config.json"
        "api_ml_full/models/lora_vikhr_improved/adapter_model.safetensors"
        "api_ml_full/models/lora_vikhr_improved/chat_template.jinja"
        "api_ml_full/models/lora_vikhr_improved/README.md"
        "api_ml_full/models/lora_vikhr_improved/tokenizer_config.json"
        "api_ml_full/models/lora_vikhr_improved/tokenizer.json"
    )
    
    for file in "${required_files[@]}"; do
        if [ ! -f "$file" ]; then
            missing_files+=("$file")
        fi
    done
    
    if [ ${#missing_files[@]} -gt 0 ]; then
        print_warning "Отсутствуют файлы, запуск загрузки..."
        chmod +x ./load_data_and_models.sh && ./load_data_and_models.sh || exit 1
        print_success "Данные и модели загружены"
    else
        print_success "Все файлы присутствуют"
    fi
}

check_service_health() {
    local service=$1
    local url=$2
    local max_attempts=${3:-30}
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s -f "$url" > /dev/null 2>&1; then
            return 0
        fi
        sleep 2
        attempt=$((attempt + 1))
    done
    return 1
}

wait_for_service() {
    local service=$1
    local log_pattern=$2
    local timeout=${3:-300}
    local elapsed=0
    
    echo -n "⏳ Ожидание $service"
    while ! docker-compose logs $service 2>&1 | grep -q "$log_pattern"; do
        sleep 2
        elapsed=$((elapsed + 2))
        echo -n "."
        if [ $elapsed -ge $timeout ]; then
            print_error " Таймаут ожидания $service"
            docker-compose logs $service --tail=20
            return 1
        fi
    done
    print_success " $service готов"
    return 0
}

check_dependencies() {
    print_info "Проверка зависимостей..."
    
    local missing=0
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker не установлен"
        missing=1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose не установлен"
        missing=1
    fi
    
    if ! command -v curl &> /dev/null; then
        print_error "curl не установлен"
        missing=1
    fi
    
    if [ $missing -eq 1 ]; then
        exit 1
    fi
    
    print_success "Все зависимости установлены"
}

check_port() {
    local port=$1
    if lsof -i ":$port" > /dev/null 2>&1; then
        print_warning "Порт $port уже занят"
        return 1
    fi
    return 0
}

show_menu() {
    echo ""
    echo "========================================="
    echo "    Deploy сервиса \"Аналитик документов\""
    echo "========================================="
    echo ""
    echo "Выберите вариант запуска:"
    echo ""
    echo "1) 🚀 Обычный запуск (с индексацией)"
    echo "2) 🧹 Очистка Qdrant + запуск"
    echo "3) 🗑️ Полная очистка (все volumes) + запуск"
    echo "4) 💾 Запуск с существующими коллекциями"
    echo "5) 📋 Проверить статус сервисов"
    echo "6) 📊 Посмотреть логи"
    echo "7) 🛑 Остановить все сервисы"
    echo "0) ❌ Выход"
    echo ""
    read -p "Ваш выбор [0-7]: " choice
    
    case $choice in
        1) MODE="normal" ;;
        2) MODE="clean-qdrant" ;;
        3) MODE="clean-all" ;;
        4) MODE="existing" ;;
        5) show_status; exit 0 ;;
        6) show_logs; exit 0 ;;
        7) docker-compose down; print_success "Сервисы остановлены"; exit 0 ;;
        0) exit 0 ;;
        *) print_error "Неверный выбор"; exit 1 ;;
    esac
}

show_status() {
    echo ""
    print_info "Статус сервисов:"
    echo ""
    docker-compose ps
    
    echo ""
    print_info "Проверка здоровья:"
    
    for service in search-api ml-api search-gateway; do
        local port=""
        case $service in
            search-api) port=8000 ;;
            ml-api) port=8001 ;;
            search-gateway) port=8002 ;;
        esac
        if curl -s "http://localhost:$port/health" > /dev/null 2>&1; then
            print_success "$service: healthy"
        else
            print_warning "$service: not responding"
        fi
    done
}

show_logs() {
    echo ""
    print_info "Последние логи (Ctrl+C для выхода):"
    echo ""
    docker-compose logs --tail=50 -f
}

clean_qdrant() {
    print_warning "Очистка Qdrant..."
    docker-compose stop search-api ml-api 2>/dev/null || true
    docker-compose down -v qdrant 2>/dev/null || true
    docker volume rm qdrant_storage 2>/dev/null || true
    print_success "Qdrant очищен"
}

clean_all() {
    print_warning "Полная очистка..."
    docker-compose down -v
    docker volume rm qdrant_storage logs_data models_cache rabbitmq_data redis_data 2>/dev/null || true
    print_success "Полная очистка завершена"
}

main() {
    MODE=""
    SKIP_FILES_CHECK=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --clean-qdrant) MODE="clean-qdrant"; shift ;;
            --clean-all) MODE="clean-all"; shift ;;
            --use-existing) MODE="existing"; shift ;;
            --skip-files-check) SKIP_FILES_CHECK=true; shift ;;
            --help) 
                echo "Использование: $0 [--clean-qdrant|--clean-all|--use-existing|--skip-files-check]"
                exit 0 ;;
            *) print_error "Неизвестная опция: $1"; exit 1 ;;
        esac
    done
    
    
    check_dependencies
    
    
    if [[ "$SKIP_FILES_CHECK" != true ]]; then
        check_required_files
    fi
    
    if [[ -z "$MODE" ]]; then
        show_menu
    fi
    
    case $MODE in
        clean-qdrant)
            clean_qdrant
            ;;
        clean-all)
            clean_all
            ;;
    esac
    
    print_info "Сборка образов..."
    docker-compose build
    
    print_info "Запуск сервисов..."
    if [[ "$MODE" == "existing" ]]; then
        print_info "Режим: использование существующих коллекций"
    fi
    docker-compose up -d
    
    echo ""
    print_info "Ожидание запуска сервисов..."
    echo ""
    
    wait_for_service "rabbitmq" "Server startup complete" 60 || true
    wait_for_service "redis" "Ready to accept connections" 30 || true
    wait_for_service "qdrant" "Qdrant HTTP listening on 6333" 60 || true
    wait_for_service "search-api" "Application startup complete" 120 || true
    wait_for_service "ml-api" "Application startup complete" 120 || true
    wait_for_service "streamlit" "You can now view your Streamlit app" 60 || true
    

    if docker-compose ps search-gateway 2>/dev/null | grep -q "Up"; then
        wait_for_service "search-gateway" "Application startup complete" 60 || true
        if check_service_health "search-gateway" "http://localhost:8002/health" 10; then
            print_success " Gateway API готов"
        else
            print_warning "Gateway API не отвечает (очередь может не работать)"
        fi
    fi
    
    if docker-compose ps search-queue-worker 2>/dev/null | grep -q "Up"; then
        print_success " Queue worker запущен"
    fi
    
    if docker-compose ps telegram-bot 2>/dev/null | grep -q "Up"; then
        if grep -q "BOT_TOKEN" .env 2>/dev/null; then
            print_success " Telegram бот запущен"
        else
            print_warning "Telegram бот запущен, но BOT_TOKEN не настроен"
        fi
    fi
    
    echo ""
    echo "===================================================="
    print_success "Сервисы запущены!"
    echo "===================================================="
    echo ""
    echo "📊 Доступные сервисы:"
    echo "   • Streamlit UI:    http://localhost:8501"
    echo "   • Search API:      http://localhost:8000/docs"
    echo "   • ML API:          http://localhost:8001/docs"
    echo "   • Gateway API:     http://localhost:8002"
    echo "   • RabbitMQ UI:     http://localhost:15672 (guest/guest)"
    echo "   • Qdrant Console:  http://localhost:6333/dashboard"
    echo ""
    echo "📝 Полезные команды:"
    echo "   • Логи:        docker-compose logs -f"
    echo "   • Статус:      docker-compose ps"
    echo "   • Остановка:   docker-compose down"
    echo "   • Перезапуск:  docker-compose restart"
    echo "   • Проверка:    $0 --check"
    echo ""
    

    if ! docker-compose ps search-gateway 2>/dev/null | grep -q "Up"; then
        echo "💡 Совет: Очередь (RabbitMQ) не запущена. Используйте прямой вызов API."
        echo "   В Streamlit отключите toggle 'Использовать очередь'"
    fi
    echo ""
}

trap 'print_error "Прервано"; exit 1' INT TERM

main "$@"