#!/bin/bash

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'


print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}


check_required_files() {
    print_info "Проверка наличия необходимых файлов..."
    
    local missing_files=()
    local required_files=(
        # CSV данные
        "docs_cleaned.csv"
        # Модели hub_classifier для api_ml
        "api_ml/models/hub_classifier/catboost_model.cbm"
        "api_ml/models/hub_classifier/mlb_filtered.pkl"
        "api_ml/models/hub_classifier/threshold_info.pkl"
        "api_ml/models/hub_classifier/vectorizer.pkl"
        # Модели tag_classifier для api_ml
        "api_ml/models/tag_classifier/catboost_tags_model.cbm"
        "api_ml/models/tag_classifier/mlb_tags_filtered.pkl"
        "api_ml/models/tag_classifier/threshold_tags_info.pkl"
        "api_ml/models/tag_classifier/vectorizer_tags.pkl"
        # Модели hub_classifier для api_ml_full
        "api_ml_full/models/hub_classifier/catboost_model.cbm"
        "api_ml_full/models/hub_classifier/mlb_filtered.pkl"
        "api_ml_full/models/hub_classifier/threshold_info.pkl"
        "api_ml_full/models/hub_classifier/vectorizer.pkl"
        # Модели tag_classifier для api_ml_full
        "api_ml_full/models/tag_classifier/catboost_tags_model.cbm"
        "api_ml_full/models/tag_classifier/mlb_tags_filtered.pkl"
        "api_ml_full/models/tag_classifier/threshold_tags_info.pkl"
        "api_ml_full/models/tag_classifier/vectorizer_tags.pkl"
        # LoRA vikhr_improved модель для api_ml_full
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
        print_warning "Обнаружены отсутствующие файлы:"
        for file in "${missing_files[@]}"; do
            echo "   ❌ $file"
        done
        
        echo ""
        print_info "Запускаю загрузку данных и моделей из Yandex Cloud..."
        echo ""
        
        if [ ! -f "./load_data_and_models.sh" ]; then
            print_error "Скрипт загрузки load_data_and_models.sh не найден!"
            exit 1
        fi
        
        chmod +x ./load_data_and_models.sh
        
        if ./load_data_and_models.sh; then
            print_success "Данные и модели успешно загружены!"
            
            echo ""
            print_info "Проверяю загруженные файлы..."
            local still_missing=()
            
            for file in "${required_files[@]}"; do
                if [ ! -f "$file" ]; then
                    still_missing+=("$file")
                fi
            done
            
            if [ ${#still_missing[@]} -gt 0 ]; then
                print_error "После загрузки всё ещё отсутствуют файлы:"
                for file in "${still_missing[@]}"; do
                    echo "   ❌ $file"
                done
                exit 1
            else
                print_success "Все необходимые файлы на месте!"
                show_files_info
            fi
        else
            print_error "Ошибка при загрузке данных и моделей!"
            exit 1
        fi
    else
        print_success "Все необходимые файлы присутствуют!"
        show_files_info
    fi
}


show_files_info() {
    echo ""
    print_info "📁 Статус файлов:"

    if [ -f "docs_cleaned.csv" ]; then
        local size=$(du -h docs_cleaned.csv | cut -f1)
        echo "   ✅ docs_cleaned.csv ($size)"
    fi
    
    echo ""
    echo "   🤖 Hub classifier models (api_ml):"
    if [ -d "api_ml/models/hub_classifier" ]; then
        ls -lh api_ml/models/hub_classifier/ 2>/dev/null | tail -n +2 | while read line; do
            echo "      $line"
        done
    else
        echo "      ❌ Папка не найдена"
    fi
    
    echo ""
    echo "   🏷️  Tag classifier models (api_ml):"
    if [ -d "api_ml/models/tag_classifier" ]; then
        ls -lh api_ml/models/tag_classifier/ 2>/dev/null | tail -n +2 | while read line; do
            echo "      $line"
        done
    else
        echo "      ❌ Папка не найдена"
    fi
    
    echo ""
    echo "   🤖 Hub classifier models (api_ml_full):"
    if [ -d "api_ml_full/models/hub_classifier" ]; then
        ls -lh api_ml_full/models/hub_classifier/ 2>/dev/null | tail -n +2 | while read line; do
            echo "      $line"
        done
    else
        echo "      ❌ Папка не найдена"
    fi
    
    echo ""
    echo "   🏷️  Tag classifier models (api_ml_full):"
    if [ -d "api_ml_full/models/tag_classifier" ]; then
        ls -lh api_ml_full/models/tag_classifier/ 2>/dev/null | tail -n +2 | while read line; do
            echo "      $line"
        done
    else
        echo "      ❌ Папка не найдена"
    fi
    
    echo ""
    echo "   🎯 LoRA vikhr_improved (api_ml_full):"
    if [ -d "api_ml_full/models/lora_vikhr_improved" ]; then
        ls -lh api_ml_full/models/lora_vikhr_improved/ 2>/dev/null | tail -n +2 | while read line; do
            echo "      $line"
        done
    else
        echo "      ❌ Папка не найдена"
    fi
    echo ""
}



check_collections_exist() {
    local collections=("hybrid_only" "rerank_only" "advanced")
    local existing=()
    local missing=()
    local has_data=false
    
    if ! docker-compose ps qdrant 2>/dev/null | grep -q "Up"; then
        docker-compose up -d qdrant
        sleep 5
    fi
    
    for col in "${collections[@]}"; do
        if curl -s "http://localhost:6333/collections/$col" 2>/dev/null | grep -q '"status":"green"'; then
            existing+=("$col")
            local points_count=$(curl -s "http://localhost:6333/collections/$col" 2>/dev/null | grep -o '"points_count":[0-9]*' | cut -d':' -f2)
            if [ -n "$points_count" ] && [ "$points_count" -gt 0 ]; then
                has_data=true
                print_info "Коллекция $col содержит $points_count точек"
            fi
        else
            missing+=("$col")
        fi
    done
    
    if [ ${#missing[@]} -eq 0 ] && [ "$has_data" = true ]; then
        print_success "Все необходимые коллекции существуют и содержат данные: ${existing[*]}"
        return 0
    elif [ ${#missing[@]} -eq 0 ] && [ "$has_data" = false ]; then
        print_warning "Коллекции существуют, но не содержат данных: ${existing[*]}"
        print_info "Требуется индексация документов (обычный запуск)"
        return 2
    else
        print_warning "Отсутствуют коллекции: ${missing[*]}"
        if [ ${#existing[@]} -gt 0 ]; then
            print_info "Существующие коллекции: ${existing[*]}"
        fi
        return 1
    fi
}


save_collections() {
    print_info "Сохранение информации о существующих коллекциях..."
    
    mkdir -p .collections_backup
    
    curl -s "http://localhost:6333/collections" > .collections_backup/collections_info.json
    
    local collections=$(curl -s "http://localhost:6333/collections" | grep -o '"name":"[^"]*"' | cut -d'"' -f4)
    for col in $collections; do
        curl -s "http://localhost:6333/collections/$col" > ".collections_backup/${col}_config.json"
    done
    
    print_success "Метаданные коллекций сохранены в .collections_backup/"
}


clean_qdrant() {
    print_warning "Очистка Qdrant..."
    
    if [[ "$BACKUP_COLLECTIONS" == true ]]; then
        save_collections
    fi
    

    print_info "Остановка search-api и ml-api..."
    docker-compose stop search-api ml-api 2>/dev/null || true
    
    print_info "Удаление volume qdrant_storage..."
    docker-compose down -v qdrant 2>/dev/null || true
    docker volume rm qdrant_storage 2>/dev/null || true
    
    print_success "Qdrant очищен"
}


clean_all() {
    print_warning "ПОЛНАЯ ОЧИСТКА (все volumes)..."
    
    if [[ "$BACKUP_COLLECTIONS" == true ]]; then
        save_collections
    fi
    
    docker-compose down -v
    
    docker volume rm qdrant_storage logs_data models_cache 2>/dev/null || true
    
    read -p "Очистить кэш Docker builder? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker builder prune -f
    fi
    
    print_success "Полная очистка завершена"
}


check_collections() {
    print_info "Проверка существующих коллекций в Qdrant..."
    
    if ! docker-compose ps qdrant 2>/dev/null | grep -q "Up"; then
        docker-compose up -d qdrant
        sleep 5
    fi
    
    local response=$(curl -s http://localhost:6333/collections 2>/dev/null)
    local collections=$(echo "$response" | grep -o '"name":"[^"]*"' | cut -d'"' -f4)
    
    if [ -n "$collections" ]; then
        print_success "Найдены коллекции в Qdrant:"
        echo "$collections" | while read -r col; do
            local col_info=$(curl -s "http://localhost:6333/collections/$col")
            local vectors_count=$(echo "$col_info" | grep -o '"vectors_count":[0-9]*' | cut -d':' -f2)
            local points_count=$(echo "$col_info" | grep -o '"points_count":[0-9]*' | cut -d':' -f2)
            
            if [ -n "$points_count" ] && [ "$points_count" -gt 0 ]; then
                echo "   ✅ $col: $points_count точек, $vectors_count векторов"
            else
                echo "   ⚠️  $col: пустая (нет данных)"
            fi
        done
        
        echo ""
        print_info "Детальная информация:"
        echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response" | jq '.' 2>/dev/null || echo "  Установите jq или python3 для детального просмотра"
    else
        print_warning "Нет существующих коллекций в Qdrant"
        
        if [ -d ".collections_backup" ]; then
            print_info "Найдены бэкапы коллекций в .collections_backup/"
            read -p "Восстановить метаданные коллекций из бэкапа? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                restore_collections_backup
            fi
        fi
    fi
}

restore_collections_backup() {
    print_info "Восстановление метаданных коллекций из бэкапа..."
    
    if [ -f ".collections_backup/collections_info.json" ]; then
        local collections=$(grep -o '"name":"[^"]*"' .collections_backup/collections_info.json | cut -d'"' -f4)
        for col in $collections; do
            if [ -f ".collections_backup/${col}_config.json" ]; then
                print_info "Найден бэкап для коллекции: $col"
                cat ".collections_backup/${col}_config.json" | python3 -m json.tool 2>/dev/null
            fi
        done
        print_success "Информация о коллекциях восстановлена из бэкапа"
    else
        print_warning "Нет сохраненных бэкапов коллекций"
    fi
}

start_with_existing_collections() {
    print_info "Запуск с использованием существующих коллекций..."
    
    check_collections_exist
    local check_result=$?
    
    case $check_result in
        0)
            print_success "Все коллекции существуют и содержат данные, запускаем без создания новых"
            ;;
        2)
            print_warning "Коллекции существуют, но не содержат данных"
            echo ""
            echo "Доступные опции:"
            echo "  1) Продолжить запуск (попробовать использовать пустые коллекции)"
            echo "  2) Очистить Qdrant и выполнить индексацию (рекомендуется)"
            echo "  3) Отмена"
            echo ""
            read -p "Ваш выбор [1-3]: " -n 1 -r
            echo
            
            case $REPLY in
                1)
                    print_warning "Продолжаем с пустыми коллекциями - поиск не будет работать"
                    ;;
                2)
                    print_info "Будет выполнена очистка Qdrant и индексация"
                    clean_qdrant
                    export USE_EXISTING_COLLECTIONS=false
                    return
                    ;;
                3)
                    exit 0
                    ;;
                *)
                    print_error "Неверный выбор"
                    exit 1
                    ;;
            esac
            ;;
        1)
            print_warning "Некоторые коллекции отсутствуют"
            echo ""
            echo "Доступные опции:"
            echo "  1) Создать недостающие коллекции автоматически"
            echo "  2) Восстановить коллекции из бэкапа"
            echo "  3) Очистить Qdrant и создать новые коллекции"
            echo "  4) Отмена"
            echo ""
            read -p "Ваш выбор [1-4]: " -n 1 -r
            echo
            
            case $REPLY in
                1)
                    print_info "Продолжаем запуск. Недостающие коллекции будут созданы автоматически."
                    ;;
                2)
                    restore_collections_backup
                    ;;
                3)
                    print_warning "Будет выполнена очистка Qdrant"
                    clean_qdrant
                    ;;
                4)
                    exit 0
                    ;;
                *)
                    print_error "Неверный выбор"
                    exit 1
                    ;;
            esac
            ;;
    esac
    
    export USE_EXISTING_COLLECTIONS=true
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
    echo "3) 🗑️  Полная очистка (все volumes) + запуск"
    echo "4) 📋 Проверить существующие коллекции"
    echo "5) 💾 Запуск с существующими коллекциями (без повторной индексации)"
    echo "6) 🛑 Остановить все сервисы"
    echo "0) ❌ Выход"
    echo ""
    read -p "Ваш выбор [1-6]: " choice
    
    case $choice in
        1)
            echo ""
            print_info "Обычный запуск с индексацией..."
            USE_EXISTING_COLLECTIONS=false
            QDRANT_CLEAN=false
            FULL_CLEAN=false
            ;;
        2)
            echo ""
            print_warning "Будет выполнена очистка только Qdrant"
            read -p "Создать бэкап коллекций? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                BACKUP_COLLECTIONS=true
            else
                BACKUP_COLLECTIONS=false
            fi
            read -p "Продолжить? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                QDRANT_CLEAN=true
                FULL_CLEAN=false
                USE_EXISTING_COLLECTIONS=false
            else
                exit 0
            fi
            ;;
        3)
            echo ""
            print_warning "Будет выполнена ПОЛНАЯ очистка всех данных"
            read -p "Создать бэкап коллекций? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                BACKUP_COLLECTIONS=true
            else
                BACKUP_COLLECTIONS=false
            fi
            read -p "Вы уверены? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                FULL_CLEAN=true
                QDRANT_CLEAN=false
                USE_EXISTING_COLLECTIONS=false
            else
                exit 0
            fi
            ;;
        4)
            check_collections
            exit 0
            ;;
        5)
            echo ""
            start_with_existing_collections
            QDRANT_CLEAN=false
            FULL_CLEAN=false
            ;;
        6)
            echo ""
            print_info "Остановка всех сервисов..."
            docker-compose down
            print_success "Сервисы остановлены"
            exit 0
            ;;
        0)
            exit 0
            ;;
        *)
            print_error "Неверный выбор"
            exit 1
            ;;
    esac
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --clean-qdrant)
                QDRANT_CLEAN=true
                FULL_CLEAN=false
                USE_EXISTING_COLLECTIONS=false
                shift
                ;;
            --clean-all)
                FULL_CLEAN=true
                QDRANT_CLEAN=false
                USE_EXISTING_COLLECTIONS=false
                shift
                ;;
            --use-existing)
                USE_EXISTING_COLLECTIONS=true
                QDRANT_CLEAN=false
                FULL_CLEAN=false
                shift
                ;;
            --check)
                check_collections
                exit 0
                ;;
            --backup)
                BACKUP_COLLECTIONS=true
                shift
                ;;
            --skip-files-check)
                SKIP_FILES_CHECK=true
                shift
                ;;
            --help)
                echo "Использование: $0 [OPTIONS]"
                echo ""
                echo "Опции:"
                echo "  --clean-qdrant       Очистить только Qdrant перед запуском"
                echo "  --clean-all          Полная очистка всех volumes"
                echo "  --use-existing       Запуск с использованием существующих коллекций"
                echo "  --check              Проверить существующие коллекции"
                echo "  --backup             Создать бэкап коллекций перед очисткой"
                echo "  --skip-files-check   Пропустить проверку файлов данных и моделей"
                echo "  --help               Показать эту справку"
                echo ""
                echo "Примеры:"
                echo "  $0                           # Интерактивное меню"
                echo "  $0 --use-existing            # Запуск с существующими коллекциями"
                echo "  $0 --clean-qdrant --backup   # Очистка с бэкапом коллекций"
                echo "  $0 --check                   # Проверка коллекций"
                echo "  $0 --skip-files-check        # Запуск без проверки файлов"
                exit 0
                ;;
            *)
                print_error "Неизвестная опция: $1"
                echo "Используйте --help для справки"
                exit 1
                ;;
        esac
    done
}

main() {
    QDRANT_CLEAN=false
    FULL_CLEAN=false
    USE_EXISTING_COLLECTIONS=false
    BACKUP_COLLECTIONS=false
    SKIP_FILES_CHECK=false
    
    parse_args "$@"
    
    if [[ "$SKIP_FILES_CHECK" != true ]]; then
        check_required_files
    else
        print_warning "Проверка файлов пропущена (--skip-files-check)"
    fi
    
    if [[ $# -eq 0 ]]; then
        show_menu
    fi

    if [[ "$FULL_CLEAN" == true ]]; then
        clean_all
    elif [[ "$QDRANT_CLEAN" == true ]]; then
        clean_qdrant
    fi
    
    export USE_EXISTING_COLLECTIONS
    
    echo ""
    print_info "Начинаю сборку и запуск..."
    echo ""
    
    if [[ "$FULL_CLEAN" == true ]]; then
        echo "🔨 Сборка образов (без кэша)..."
        docker-compose build --no-cache
    else
        echo "🔨 Сборка образов..."
        docker-compose build
    fi
    
    if [ $? -ne 0 ]; then
        print_error "Ошибка при сборке образов!"
        exit 1
    fi
    
    print_success "Сборка завершена успешно!"
    
    echo ""
    echo "🚀 Запуск сервисов..."
    
    if [[ "$USE_EXISTING_COLLECTIONS" == true ]]; then
        print_info "Режим: использование существующих коллекций"
        docker-compose up -d
    else
        print_info "Режим: полная индексация документов"
        docker-compose up -d
    fi
    
    echo ""
    echo -n "⏳ Ожидание Qdrant"
    while ! docker-compose logs qdrant 2>&1 | grep -q "Qdrant HTTP listening on 6333"; do
        sleep 2
        echo -n "."
    done
    print_success " Qdrant готов"
    
    echo -n "⏳ Ожидание Search API (может занять несколько часов для индексации документов коллекции)"
    while ! docker-compose logs search-api 2>&1 | grep -q "Application startup complete"; do
        sleep 2
        echo -n "."
    done
    print_success " Search API готов"
    
    echo -n "⏳ Ожидание ML API (классификация и суммаризация)"
    while ! docker-compose logs ml-api 2>&1 | grep -q "Application startup complete"; do
        sleep 2
        echo -n "."
    done
    print_success " ML API готов"
    
    echo -n "⏳ Ожидание Streamlit"
    while ! docker-compose logs streamlit 2>&1 | grep -q "You can now view your Streamlit app"; do
        sleep 2
        echo -n "."
    done
    print_success " Streamlit готов"
    
    if docker-compose ps telegram-bot 2>/dev/null | grep -q "Up"; then
        echo -n "⏳ Ожидание Telegram бота"
        timeout=60
        counter=0
        while ! docker-compose logs telegram-bot 2>&1 | grep -q "Бот запущен"; do
            sleep 2
            echo -n "."
            counter=$((counter + 2))
            if [ $counter -ge $timeout ]; then
                print_warning " Telegram бот не ответил (таймаут)"
                break
            fi
        done
        
        if [ $counter -lt $timeout ]; then
            print_success " Telegram бот готов"
        fi
    fi
    
    # Вывод информации о запущенных сервисах
    echo ""
    echo "===================================================="
    print_success "Все сервисы Аналитика документов запущены!"
    echo "===================================================="
    echo ""
    echo "📊 Доступные сервисы:"
    echo "   • Streamlit UI:    http://localhost:8501"
    echo "   • Search API:      http://localhost:8000/docs"
    echo "   • ML API:          http://localhost:8001/docs"
    echo "   • Qdrant Console:  http://localhost:6333/dashboard"
    
    if [[ "$USE_EXISTING_COLLECTIONS" == true ]]; then
        echo ""
        echo "💡 Текущий режим: Использование существующих коллекций"
        echo "   • Индексация новых документов не выполняется"
        echo "   • Поиск работает с уже загруженными данными"
    else
        echo ""
        echo "💡 Текущий режим: Полная индексация"
        echo "   • Выполняется индексация всех документов из docs_cleaned.csv"
        echo "   • Для повторного использования данных используйте режим 5"
    fi
    
    echo ""
    echo "📝 Полезные команды:"
    echo "   • Логи всех сервисов:     docker-compose logs -f"
    echo "   • Логи конкретного:       docker-compose logs -f search-api"
    echo "   • Остановка сервисов:     docker-compose down"
    echo "   • Перезапуск:             docker-compose restart"
    echo "   • Просмотр volumes:       docker volume ls | grep -E '(qdrant|logs|models)'"
    echo "   • Проверка коллекций:     $0 --check"
    echo ""
    
    # print_info "Последние логи:"
    # docker-compose logs --tail=10
}

trap 'print_error "Скрипт прерван"; exit 1' INT TERM

main "$@"