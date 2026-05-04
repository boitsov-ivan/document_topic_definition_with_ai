#!/bin/bash

if [ -f .env ]; then
    echo "📄 Загружаю .env файл..."
    export $(cat .env | grep -v '^#' | xargs)
    echo "✅ .env загружен"
else
    echo "❌ .env файл не найден!"
    exit 1
fi

if [ -z "$YC_ACCESS_KEY" ] || [ -z "$YC_SECRET_KEY" ]; then
    echo "❌ В .env файле отсутствуют ключи для доступа к S3 хранилищу (YC_ACCESS_KEY или YC_SECRET_KEY)"
    exit 1
fi

BUCKET_NAME="mlops-hse-boitsov"

echo ""
echo "🔧 Настройки подключения:"
echo "Bucket: $BUCKET_NAME"
echo "Путь в бакете: topic_definition/"
echo ""


mkdir -p api_ml/models/hub_classifier
mkdir -p api_ml/models/tag_classifier

mkdir -p api_ml_full/models/hub_classifier
mkdir -p api_ml_full/models/tag_classifier
mkdir -p api_ml_full/models/lora_vikhr_improved

download_file() {
    local remote_file=$1
    local local_path=$2
    
    echo "⬇️  Загрузка: topic_definition/$remote_file -> $local_path"
    
    curl -# -o "$local_path" \
        --fail \
        --user "$YC_ACCESS_KEY:$YC_SECRET_KEY" \
        "https://$BUCKET_NAME.storage.yandexcloud.net/topic_definition/$remote_file"
    
    if [ $? -eq 0 ] && [ -f "$local_path" ]; then
        local size=$(du -h "$local_path" | cut -f1)
        echo "✅ Успешно: $local_path ($size)"
        return 0
    else
        echo "❌ Ошибка загрузки: topic_definition/$remote_file"
        return 1
    fi
}


download_directory() {
    local remote_dir=$1
    local local_dir=$2
    
    echo "📁 Загрузка всех файлов из директории: $remote_dir -> $local_dir"
    
    mkdir -p "$local_dir"
    
    local file_list=$(curl -s \
        --user "$YC_ACCESS_KEY:$YC_SECRET_KEY" \
        "https://$BUCKET_NAME.storage.yandexcloud.net/?prefix=topic_definition/$remote_dir/" \
        2>/dev/null | grep -oP '(?<=<Key>)[^<]+' | grep -v '/$')
    
    if [ -z "$file_list" ]; then
        echo "⚠️  Не удалось получить список файлов или директория пуста"
        return 1
    fi
    
    local success_count=0
    local fail_count=0
    
    while IFS= read -r file_key; do
        if [ -n "$file_key" ]; then
            local relative_path="${file_key#topic_definition/}"
            local filename=$(basename "$relative_path")
            local local_file_path="$local_dir/$filename"
            
            echo "⬇️  Загрузка: $file_key -> $local_file_path"
            
            curl -# -o "$local_file_path" \
                --fail \
                --user "$YC_ACCESS_KEY:$YC_SECRET_KEY" \
                "https://$BUCKET_NAME.storage.yandexcloud.net/$file_key"
            
            if [ $? -eq 0 ] && [ -f "$local_file_path" ]; then
                local size=$(du -h "$local_file_path" | cut -f1)
                echo "✅ Успешно: $filename ($size)"
                ((success_count++))
            else
                echo "❌ Ошибка загрузки: $filename"
                ((fail_count++))
            fi
        fi
    done <<< "$file_list"
    
    echo "📊 Загружено файлов: успешно - $success_count, ошибок - $fail_count"
    return 0
}

echo "📦 Начинаю загрузку из Yandex Cloud..."
echo ""

echo "📄 Загрузка данных..."
download_file "docs_cleaned.csv" "docs_cleaned.csv"
echo ""


download_models_to_both_paths() {
    local model_type=$1
    shift
    local files=("$@")
    
    echo "🤖 Загрузка моделей $model_type..."
    
    for file in "${files[@]}"; do
        download_file "$model_type/$file" "api_ml/models/$model_type/$file"
        download_file "$model_type/$file" "api_ml_full/models/$model_type/$file"
    done
    echo ""
}

hub_files=(
    "catboost_model.cbm"
    "mlb_filtered.pkl"
    "threshold_info.pkl"
    "vectorizer.pkl"
)


download_models_to_both_paths "hub_classifier" "${hub_files[@]}"

tag_files=(
    "catboost_tags_model.cbm"
    "mlb_tags_filtered.pkl"
    "threshold_tags_info.pkl"
    "vectorizer_tags.pkl"
)

download_models_to_both_paths "tag_classifier" "${tag_files[@]}"

echo "🎯 Загрузка LoRA модели vikhr_improved..."
download_directory "lora_vikhr_improved" "api_ml_full/models/lora_vikhr_improved"
echo ""

echo "🎉 Загрузка завершена!"
echo ""
echo "📁 Проверка загруженных файлов:"

if [ -f "docs_cleaned.csv" ]; then
    echo "✅ docs_cleaned.csv ($(du -h docs_cleaned.csv | cut -f1))"
else
    echo "❌ docs_cleaned.csv"
fi

echo ""
echo "Hub classifier models (api_ml/models/hub_classifier/):"
ls -lh api_ml/models/hub_classifier/ 2>/dev/null | tail -n +2 || echo "  ❌ Нет файлов"

echo ""
echo "Tag classifier models (api_ml/models/tag_classifier/):"
ls -lh api_ml/models/tag_classifier/ 2>/dev/null | tail -n +2 || echo "  ❌ Нет файлов"

echo ""
echo "Hub classifier models (api_ml_full/models/hub_classifier/):"
ls -lh api_ml_full/models/hub_classifier/ 2>/dev/null | tail -n +2 || echo "  ❌ Нет файлов"

echo ""
echo "Tag classifier models (api_ml_full/models/tag_classifier/):"
ls -lh api_ml_full/models/tag_classifier/ 2>/dev/null | tail -n +2 || echo "  ❌ Нет файлов"

echo ""
echo "LoRA vikhr_improved models (api_ml_full/models/lora_vikhr_improved/):"
ls -lh api_ml_full/models/lora_vikhr_improved/ 2>/dev/null | tail -n +2 || echo "  ❌ Нет файлов"

echo ""
echo "✨ Все файлы успешно загружены в оба проекта!"