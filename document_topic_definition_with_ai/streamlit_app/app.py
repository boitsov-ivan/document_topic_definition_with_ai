import streamlit as st
import time
import requests
from typing import List, Dict, Optional
from config import config


st.set_page_config(page_title="Поиск документов", layout="wide")


if 'available_hubs' not in st.session_state:
    st.session_state.available_hubs = set()
if 'available_tags' not in st.session_state:
    st.session_state.available_tags = set()
if 'selected_hubs' not in st.session_state:
    st.session_state.selected_hubs = []
if 'selected_tags' not in st.session_state:
    st.session_state.selected_tags = []
if 'current_query' not in st.session_state:
    st.session_state.current_query = ""
if 'summary_result' not in st.session_state:
    st.session_state.summary_result = None
if 'detected_hubs' not in st.session_state:
    st.session_state.detected_hubs = []
if 'detected_tags' not in st.session_state:
    st.session_state.detected_tags = []
if 'filter_update_counter' not in st.session_state:
    st.session_state.filter_update_counter = 0


if 'use_queue' not in st.session_state:
    st.session_state.use_queue = True

st.title("Поиск похожих документов в векторной базе")


class QueueSearchClient:
    """Клиент для поиска через очередь RabbitMQ"""
    
    def __init__(self, gateway_url: str):
        self.gateway_url = gateway_url
        self.timeout = 60
    
    def search(self, payload: Dict) -> Dict:
        """Поиск через очередь с ожиданием результата"""
        try:
            response = requests.post(
                f"{self.gateway_url}/api/v1/search",
                json=payload,
                timeout=5
            )
            response.raise_for_status()
            task_id = response.json()["task_id"]
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            start_time = time.time()
            
            while time.time() - start_time < self.timeout:
                result_response = requests.get(
                    f"{self.gateway_url}/api/v1/search/result/{task_id}",
                    timeout=2
                )
                
                if result_response.status_code == 200:
                    result_data = result_response.json()
                    elapsed = int(time.time() - start_time)
                    progress_bar.progress(min(elapsed / self.timeout, 0.95))
                    status_text.text(f"Поиск... {elapsed} сек")
                    
                    if "results" in result_data:
                        progress_bar.progress(1.0)
                        status_text.empty()
                        return result_data
                    
                    if result_data.get("status") == "failed":
                        progress_bar.empty()
                        status_text.empty()
                        return {"error": result_data.get("message", "Unknown error"), "results": []}
                
                time.sleep(0.5)
            
            progress_bar.empty()
            status_text.empty()
            return {"error": "Превышено время ожидания", "results": []}
            
        except requests.exceptions.RequestException as e:
            return {"error": f"Ошибка очереди: {e}", "results": []}
    
    def health_check(self) -> bool:
        """Проверка доступности gateway"""
        try:
            response = requests.get(f"{self.gateway_url}/api/v1/search/health", timeout=2)
            return response.status_code == 200
        except:
            return False


if 'queue_client' not in st.session_state:
    gateway_url = config.API_URL
    st.session_state.queue_client = QueueSearchClient(gateway_url)

def call_ml_classification(text: str, task: str) -> Optional[Dict]:
    """
    Вызов ML API для классификации или суммаризации
    """
    try:
        if task == "hubs":
            response = requests.post(
                f"{config.ML_API_URL}/classify/hubs",
                json={"text": text, "top_k": 10},
                timeout=30
            )
        elif task == "tags":
            response = requests.post(
                f"{config.ML_API_URL}/classify/tags",
                json={"text": text, "top_k": 15},
                timeout=30
            )
        elif task == "summarize":
            response = requests.post(
                f"{config.ML_API_URL}/summarize/",
                json={"text": text},
                timeout=30
            )
        else:
            return None
        
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Ошибка ML API: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Ошибка подключения к ML API: {e}")
        return None

def update_available_filters_from_query(hubs: List[str], tags: List[str]):
    """
    Обновление доступных опций фильтров на основе обнаруженных меток
    (без автоматической подстановки в выбранные фильтры)
    """
    updated = False
    if hubs:
        old_count = len(st.session_state.available_hubs)
        st.session_state.available_hubs.update(hubs)
        if len(st.session_state.available_hubs) != old_count:
            updated = True
    if tags:
        old_count = len(st.session_state.available_tags)
        st.session_state.available_tags.update(tags)
        if len(st.session_state.available_tags) != old_count:
            updated = True
    if updated:
        st.session_state.filter_update_counter += 1

def analyze_query(query_text: str):
    """
    Анализ запроса: определение хабов и тегов (без автоматической фильтрации)
    """
    with st.spinner("🔍 Анализирую запрос..."):
        hubs_result = call_ml_classification(query_text, "hubs")
        tags_result = call_ml_classification(query_text, "tags")
        
        if hubs_result and hubs_result.get("success"):
            hubs_data = hubs_result.get("data", {})
            predicted_hubs = hubs_data.get("predicted_hubs", [])
            
            if not predicted_hubs and hubs_data.get("top_predictions"):
                predicted_hubs = [p["hub"] for p in hubs_data["top_predictions"][:3]]
            
            st.session_state.detected_hubs = predicted_hubs
            
            if predicted_hubs:
                st.success(f"🎯 **Определенные хабы:** {', '.join(predicted_hubs)}")
                if hubs_data.get("top_predictions"):
                    with st.expander("📊 Детализация по хабам"):
                        st.markdown("**Вероятности всех хабов:**")
                        for pred in hubs_data["top_predictions"][:5]:
                            st.markdown(f"- {pred['hub']}: {pred['probability']:.3f}")
            else:
                st.info("🤔 Хабы не определены")
            
            update_available_filters_from_query(predicted_hubs, [])
        else:
            st.error("Не удалось определить хабы")
        
        st.divider()
        
        if tags_result and tags_result.get("success"):
            tags_data = tags_result.get("data", {})
            predicted_tags = tags_data.get("predicted_tags", [])
            
            if not predicted_tags and tags_data.get("top_predictions"):
                predicted_tags = [p["tag"] for p in tags_data["top_predictions"][:5]]
            
            st.session_state.detected_tags = predicted_tags
            
            if predicted_tags:
                st.success(f"🔖 **Определенные теги:** {', '.join(predicted_tags[:15])}")
                if len(predicted_tags) > 15:
                    st.markdown(f"*и еще {len(predicted_tags) - 15} тегов*")
            
                if tags_data.get("top_predictions"):
                    with st.expander("📊 Детализация по тегам"):
                        st.markdown("**Топ-10 тегов с вероятностями:**")
                        for pred in tags_data["top_predictions"][:10]:
                            st.markdown(f"- {pred['tag']}: {pred['probability']:.3f}")
            else:
                st.info("🤔 Теги не определены")
            
            update_available_filters_from_query([], predicted_tags)
        else:
            st.error("Не удалось определить теги")

def get_summary(query_text: str):
    """
    Получение краткого пересказа запроса
    """
    with st.spinner("📝 Генерирую краткий пересказ..."):
        summary_result = call_ml_classification(query_text, "summarize")
        if summary_result and summary_result.get("success"):
            st.session_state.summary_result = summary_result.get("summary")
            return st.session_state.summary_result
        else:
            st.error("Не удалось получить пересказ")
            return None

with st.sidebar:
    st.header("⚙️ Настройки поиска")
    
    # use_queue = st.toggle("🔁 Использовать очередь (RabbitMQ)", value=st.session_state.use_queue, 
    #                       help="Включите для асинхронной обработки через очередь")
    use_queue = True
    st.session_state.use_queue = use_queue
    
    default_engines = ["dense", "hybrid", "rerank", "full"]
    engines = default_engines.copy()
    
    try:
        response = requests.get(f"{config.SEARCH_API_URL}/api/v1/search/engines", timeout=5)
        if response.status_code == 200:
            data = response.json()
            engines = data.get("engines", default_engines)
            if len(engines) == 0:
                engines = default_engines.copy()
        else:
            st.warning(f"Не удалось загрузить движки, используем стандартные")
    except Exception as e:
        st.warning(f"Не удалось подключиться к API: {e}")
    
    engine_index = 0
    if "hybrid" in engines:
        engine_index = engines.index("hybrid")
    engine = st.selectbox("Движок поиска", engines, index=engine_index)
    
    top_k = st.slider("Количество результатов", 1, 20, 5)
    
    st.header("🏷️ Обнаруженные метки")
    
    if st.session_state.detected_hubs:
        st.markdown("**Обнаруженные хабы:**")
        for hub in st.session_state.detected_hubs:
            st.markdown(f"- {hub}")
    
    if st.session_state.detected_tags:
        st.markdown("**Обнаруженные теги:**")
        for tag in st.session_state.detected_tags[:10]:
            st.markdown(f"- {tag}")
        if len(st.session_state.detected_tags) > 10:
            st.markdown(f"*и еще {len(st.session_state.detected_tags) - 10}*")
    
    if not st.session_state.detected_hubs and not st.session_state.detected_tags:
        st.info("💡 Нажмите 'Определение тематики' для анализа запроса")
    
    st.divider()
    
    st.header("🔍 Фильтры поиска")
    st.caption("Выберите метки для фильтрации результатов поиска")
    
    hubs_list = sorted(list(st.session_state.available_hubs))
    tags_list = sorted(list(st.session_state.available_tags))
    
    selected_hubs = st.multiselect(
        "Фильтр по хабам", 
        hubs_list,
        default=st.session_state.selected_hubs,
        key=f"hubs_multiselect_{st.session_state.filter_update_counter}",
        help="Выберите хабы для фильтрации результатов поиска"
    )
    
    selected_tags = st.multiselect(
        "Фильтр по тегам", 
        tags_list,
        default=st.session_state.selected_tags,
        key=f"tags_multiselect_{st.session_state.filter_update_counter}",
        help="Выберите теги для фильтрации результатов поиска"
    )
    
    st.session_state.selected_hubs = selected_hubs
    st.session_state.selected_tags = selected_tags
    
    if not hubs_list and not tags_list:
        st.info("💡 Введите запрос и нажмите 'Определение тематики', чтобы появились доступные фильтры")
    
    if st.session_state.detected_hubs and st.button("➕ Добавить все обнаруженные хабы", use_container_width=True):
        current_hubs = set(st.session_state.selected_hubs)
        current_hubs.update(st.session_state.detected_hubs)
        st.session_state.selected_hubs = list(current_hubs)
        st.rerun()
    
    if st.session_state.detected_tags and st.button("➕ Добавить все обнаруженные теги", use_container_width=True):
        current_tags = set(st.session_state.selected_tags)
        current_tags.update(st.session_state.detected_tags[:15])
        st.session_state.selected_tags = list(current_tags)
        st.rerun()
    
    if st.button("🗑️ Сбросить все", use_container_width=True):
        st.session_state.available_hubs.clear()
        st.session_state.available_tags.clear()
        st.session_state.selected_hubs = []
        st.session_state.selected_tags = []
        st.session_state.detected_hubs = []
        st.session_state.detected_tags = []
        st.session_state.summary_result = None
        st.session_state.current_query = ""
        st.session_state.filter_update_counter += 1
        st.rerun()

st.header("🔍 Введите ваш запрос")

query = st.text_area(
    "Поисковый запрос:", 
    height=100, 
    placeholder="Например: как настроить VPN?",
    key="query_input"
)


col1, col2, col3 = st.columns([1, 1, 2])

with col1:
    analyze_button = st.button(
        "🏷️ Определение тематики", 
        type="secondary", 
        use_container_width=True,
        help="Определить хабы и теги запроса (доступные фильтры обновятся)"
    )

with col2:
    summarize_button = st.button(
        "📝 Краткий пересказ", 
        type="secondary", 
        use_container_width=True,
        help="Сделать краткий пересказ запроса"
    )

with col3:
    search_button = st.button(
        "🔍 Поиск", 
        type="primary", 
        use_container_width=True,
        help="Искать документы с учетом выбранных фильтров"
    )

if analyze_button and query:
    st.session_state.current_query = query
    analyze_query(query)
    st.rerun()
    
elif analyze_button and not query:
    st.warning("⚠️ Введите поисковый запрос для анализа")

if summarize_button and query:
    st.session_state.current_query = query
    summary = get_summary(query)
    if summary:
        st.success("📖 **Краткий пересказ запроса:**")
        st.markdown(summary)
        
elif summarize_button and not query:
    st.warning("⚠️ Введите поисковый запрос для пересказа")

if st.session_state.summary_result and st.session_state.current_query == query and not summarize_button:
    st.info("📖 **Краткий пересказ запроса:**")
    st.markdown(st.session_state.summary_result)


if st.session_state.detected_hubs or st.session_state.detected_tags:
    with st.expander("🏷️ Текущие метки запроса", expanded=False):
        if st.session_state.detected_hubs:
            st.markdown(f"**Хабы:** {', '.join(st.session_state.detected_hubs)}")
        if st.session_state.detected_tags:
            st.markdown(f"**Теги:** {', '.join(st.session_state.detected_tags[:15])}")
            if len(st.session_state.detected_tags) > 15:
                st.markdown(f"*и еще {len(st.session_state.detected_tags) - 15} тегов*")

st.divider()

if search_button and query:
    with st.spinner("Поиск документов..."):
        payload = {
            "query": query,
            "top_k": top_k,
            "engine": str(engine) if engine else "hybrid"
        }
        
        if st.session_state.selected_hubs:
            payload["hubs"] = st.session_state.selected_hubs
        if st.session_state.selected_tags:
            payload["tags"] = st.session_state.selected_tags
        
        if st.session_state.selected_hubs or st.session_state.selected_tags:
            applied_filters = []
            if st.session_state.selected_hubs:
                applied_filters.extend(st.session_state.selected_hubs)
            if st.session_state.selected_tags:
                applied_filters.extend(st.session_state.selected_tags)
            st.info(f"🔍 Поиск с примененными фильтрами: {', '.join(applied_filters)}")
        else:
            st.info("🔍 Поиск без фильтров (используются все документы)")
        
        try:
            if st.session_state.use_queue:
                result = st.session_state.queue_client.search(payload)
                
                if result.get("error"):
                    st.warning(f"⚠️ Очередь недоступна: {result['error']}")
                    st.info("🔄 Пробуем прямой запрос к API...")
                    response = requests.post(
                        f"{config.SEARCH_API_URL}/api/v1/search/",
                        json=payload,
                        headers={"Content-Type": "application/json"},
                        timeout=30
                    )
                    response.raise_for_status()
                    data = response.json()
                else:
                    data = result
            else:
                response = requests.post(
                    f"{config.SEARCH_API_URL}/api/v1/search/",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )
                response.raise_for_status()
                data = response.json()
            
            results = data.get("results", [])
            total = data.get("total", len(results))
            
            st.success(f"✅ Найдено {total} результатов")
            
            if not results:
                st.info("По вашему запросу ничего не найдено. Попробуйте изменить запрос или настройки поиска.")
            
            for idx, result in enumerate(results, 1):
                with st.container():
                    st.markdown(f"### {idx}. {result.get('title', 'Без названия')}")
                    
                    score = result.get('score')
                    if score is not None:
                        st.markdown(f"**Score:** {score:.4f}" if isinstance(score, float) else f"**Score:** {score}")
                    
                    url = result.get('url')
                    if url:
                        st.markdown(f"**URL:** {url}")
                        st.markdown(f"[🔗 Открыть документ]({url})")
                    
                    if result.get('hubs'):
                        st.markdown(f"**Хабы:** {', '.join(result['hubs'][:3])}")
                    if result.get('tags'):
                        st.markdown(f"**Теги:** {', '.join(result['tags'][:5])}")
                    
                    full_text = result.get('text', '')
                    if full_text:
                        with st.expander("📄 Показать ближайший по смыслу фрагмент документа", expanded=False):
                            st.text_area(
                                "Ближайший по смыслу фрагмент документа:",
                                value=full_text,
                                height=200,
                                key=f"full_text_{idx}_{result.get('id', idx)}",
                                disabled=True,
                                label_visibility="collapsed"
                            )
                    
                    st.divider()
                    
        except requests.exceptions.ConnectionError:
            st.error(f"❌ Не удалось подключиться к API серверу ({config.SEARCH_API_URL})")
            st.info("Убедитесь, что search-api сервис запущен и доступен")
        except requests.exceptions.Timeout:
            st.error("❌ Превышено время ожидания ответа от сервера")
        except Exception as e:
            st.error(f"❌ Ошибка подключения: {e}")

elif search_button and not query:
    st.warning("⚠️ Введите поисковый запрос")

with st.expander("ℹ️ Информация"):
    st.markdown("""
    ### О сервисе
    - **Dense поиск** - только векторный поиск
    - **Hybrid поиск** - комбинация векторного поиска и BM25
    - **Rerank поиск** - посик с реранжированием результатов
    - **Full поиск** - полная версия с гибридным поиском и реранжированием
    
    ### Как использовать
    1. **Введите поисковый запрос**
    2. **Определение тематики** - автоматически определит хабы и теги запроса (доступные фильтры обновятся)
    3. **Краткий пересказ** - подготовит краткий пересказ введённого документа
    4. **Выберите фильтры** в боковой панели (хабы/теги), которые хотите применить для фильтрации документов в поисковой базе данных
    5. **Поиск** - найдет документы с учетом выбранных фильтров
    
    ### API Endpoints
    - `POST /api/v1/search/` - поиск документов
    - `POST /classify/hubs` - классификация по хабам
    - `POST /classify/tags` - классификация тегам
    - `POST /summarize/` - суммаризация текста
    """)