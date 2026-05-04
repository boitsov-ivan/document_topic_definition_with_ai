import httpx
import time
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest

from services.or_api import or_define_topic
from config import config

router = Router()
user_data_storage = {}


class QueueSearchClient:
    """Клиент для поиска через очередь RabbitMQ"""
    
    def __init__(self, gateway_url: str):
        self.gateway_url = gateway_url
        self.timeout = 60
    
    async def search(self, payload: dict) -> dict:
        """Поиск через очередь с ожиданием результата"""
        import asyncio
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.gateway_url}/api/v1/search",
                    json=payload,
                    timeout=5.0
                )
                response.raise_for_status()
                task_id = response.json()["task_id"]
                
                start_time = time.time()
                while time.time() - start_time < self.timeout:
                    result_response = await client.get(
                        f"{self.gateway_url}/api/v1/search/result/{task_id}",
                        timeout=2.0
                    )
                    
                    if result_response.status_code == 200:
                        result_data = result_response.json()
                        
                        if "results" in result_data:
                            return result_data
                        
                        if result_data.get("status") == "failed":
                            return {"error": result_data.get("message", "Unknown error"), "results": []}
                    
                    await asyncio.sleep(0.5)
                
                return {"error": "Превышено время ожидания", "results": []}
                
        except Exception as e:
            return {"error": f"Ошибка очереди: {e}", "results": []}
    
    async def health_check(self) -> bool:
        """Проверка доступности gateway"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.gateway_url}/api/v1/search/health", timeout=2.0)
                return response.status_code == 200
        except:
            return False


gateway_url = "http://search-gateway:8002"
queue_client = QueueSearchClient(gateway_url)

@router.message(Command("upload_doc"))
async def cmd_upload_doc(message: types.Message, or_api_key: str):
    await message.answer(
        "📄 Отправьте текст документа или TXT файл.\n"
        "Я проанализирую его, определю тематику и подготовлю краткий пересказ."
    )

@router.message(Command("search"))
async def cmd_search(message: types.Message):
    """Обработчик команды /search"""
    user_id = str(message.from_user.id)
    if user_id not in user_data_storage:
        user_data_storage[user_id] = {}
    user_data_storage[user_id]['awaiting_search'] = True
    
    await message.answer(
        "🔍 Введите ваш поисковый запрос и я найду похожие документы в базе:"
    )

async def analyze_document(message: types.Message, text: str, or_api_key: str):
    """Анализ документа: определение хабов и тегов"""
    result_message = ""
    
    async with httpx.AsyncClient() as client:
        hubs_response = await client.post(
            f"{config.ML_API_URL}/classify/hubs",
            json={"text": text, "top_k": 10},
            timeout=30.0
        )
        
        tags_response = await client.post(
            f"{config.ML_API_URL}/classify/tags",
            json={"text": text, "top_k": 15},
            timeout=30.0
        )
        
        result_message += "📊 *Результаты анализа документа:*\n\n"
        
        hubs = []
        if hubs_response.status_code == 200:
            hubs_data = hubs_response.json()
            if hubs_data.get("success"):
                hubs_data_content = hubs_data.get("data", {})
                predicted_hubs = hubs_data_content.get("predicted_hubs", [])
                
                if not predicted_hubs and hubs_data_content.get("top_predictions"):
                    predicted_hubs = [p["hub"] for p in hubs_data_content["top_predictions"][:3]]
                
                hubs = predicted_hubs
                
                if predicted_hubs:
                    result_message += f"🏷️ *Определённые хабы:*\n{', '.join(predicted_hubs)}\n\n"
                    
                    if hubs_data_content.get("top_predictions"):
                        result_message += "*Вероятности:*\n"
                        for pred in hubs_data_content["top_predictions"][:3]:
                            result_message += f"• {pred['hub']}: {pred['probability']:.3f}\n"
                        result_message += "\n"
                else:
                    result_message += "🤔 *Хабы не определены*\n\n"
        tags = []
        if tags_response.status_code == 200:
            tags_data = tags_response.json()
            if tags_data.get("success"):
                tags_data_content = tags_data.get("data", {})
                predicted_tags = tags_data_content.get("predicted_tags", [])
                
                if not predicted_tags and tags_data_content.get("top_predictions"):
                    predicted_tags = [p["tag"] for p in tags_data_content["top_predictions"][:5]]
                
                tags = predicted_tags
                
                if predicted_tags:
                    result_message += f"🔖 *Определённые теги:*\n{', '.join(predicted_tags[:15])}\n"
                    if len(predicted_tags) > 15:
                        result_message += f"\n*и еще {len(predicted_tags) - 15} тегов*\n"
                    result_message += "\n"
                    
                    if tags_data_content.get("top_predictions"):
                        result_message += "*Вероятности:*\n"
                        for pred in tags_data_content["top_predictions"][:5]:
                            result_message += f"• {pred['tag']}: {pred['probability']:.3f}\n"
                        result_message += "\n"
                else:
                    result_message += "🤔 *Теги не определены*\n\n"
        try:
            or_analysis = or_define_topic(text, or_api_key)
            if or_analysis:
                result_message += f"📋 *Дополнительный анализ:*\n{or_analysis}\n\n"
        except Exception as e:
            print(f"OR API error: {e}")
        
        await message.answer(result_message, parse_mode='Markdown')
        
        user_id = str(message.from_user.id)
        if user_id not in user_data_storage:
            user_data_storage[user_id] = {}
        
        user_data_storage[user_id]['last_analysis'] = {
            'hubs': hubs,
            'tags': tags,
            'text': text
        }
        
        if 'selected_hubs' not in user_data_storage[user_id]:
            user_data_storage[user_id]['selected_hubs'] = []
        if 'selected_tags' not in user_data_storage[user_id]:
            user_data_storage[user_id]['selected_tags'] = []
        
        await suggest_search(message, hubs, tags)

async def suggest_search(message: types.Message, hubs: list, tags: list):
    """Предложение выполнить поиск похожих документов"""
    keyboard_buttons = []
    
    if hubs:
        hub_buttons = []
        for hub in hubs[:3]:
            hub_buttons.append(InlineKeyboardButton(
                text=f"🏷️ {hub}", 
                callback_data=f"filter_hub_{hub}"
            ))
        if hub_buttons:
            keyboard_buttons.append(hub_buttons)
    
    if tags:
        tag_buttons = []
        for tag in tags[:5]:
            tag_buttons.append(InlineKeyboardButton(
                text=f"🔖 {tag}", 
                callback_data=f"filter_tag_{tag}"
            ))
        if tag_buttons:
            keyboard_buttons.append(tag_buttons[:3])
            if len(tag_buttons) > 3:
                keyboard_buttons.append(tag_buttons[3:5])
    
    action_buttons = [
        [
            InlineKeyboardButton(text="🔍 Поиск похожих документов", callback_data="search_similar")
        ],
        [
            InlineKeyboardButton(text="⚙️ Настройки поиска", callback_data="search_settings")
        ],
        [
            InlineKeyboardButton(text="🗑️ Сбросить фильтры", callback_data="reset_filters"),
            InlineKeyboardButton(text="📊 Показать выбранные фильтры", callback_data="show_filters")
        ]
    ]
    
    keyboard_buttons.extend(action_buttons)
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    user_id = str(message.from_user.id)
    selected_hubs = user_data_storage.get(user_id, {}).get('selected_hubs', [])
    selected_tags = user_data_storage.get(user_id, {}).get('selected_tags', [])
    
    filters_text = ""
    if selected_hubs or selected_tags:
        filters_text = "\n\n*Выбранные фильтры:*\n"
        if selected_hubs:
            filters_text += f"Хабы: {', '.join(selected_hubs)}\n"
        if selected_tags:
            filters_text += f"Теги: {', '.join(selected_tags[:10])}\n"
    else:
        filters_text = "\n\n*Фильтры не выбраны* (нажмите на хабы/теги выше для добавления)"
    
    await message.answer(
        f"🔎 *Что делать дальше?*\n"
        f"Вы можете выполнить поиск похожих документов.\n"
        f"Нажмите на тег или хаб для добавления в фильтры.{filters_text}",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

@router.callback_query(lambda c: c.data.startswith("filter_hub_"))
async def handle_filter_hub(callback_query: types.CallbackQuery):
    """Добавление хабов в фильтры"""
    hub = callback_query.data.replace("filter_hub_", "")
    user_id = str(callback_query.from_user.id)
    
    if user_id not in user_data_storage:
        user_data_storage[user_id] = {}
    if 'selected_hubs' not in user_data_storage[user_id]:
        user_data_storage[user_id]['selected_hubs'] = []
    
    if hub not in user_data_storage[user_id]['selected_hubs']:
        user_data_storage[user_id]['selected_hubs'].append(hub)
        await callback_query.answer(f"✅ Хаб '{hub}' добавлен в фильтры")
    else:
        user_data_storage[user_id]['selected_hubs'].remove(hub)
        await callback_query.answer(f"❌ Хаб '{hub}' удален из фильтров")
    
    user_data = user_data_storage.get(user_id, {})
    last_analysis = user_data.get('last_analysis', {})
    await suggest_search(callback_query.message, last_analysis.get('hubs', []), last_analysis.get('tags', []))
    await callback_query.message.delete()

@router.callback_query(lambda c: c.data.startswith("filter_tag_"))
async def handle_filter_tag(callback_query: types.CallbackQuery):
    """Добавление тегов в фильтры"""
    tag = callback_query.data.replace("filter_tag_", "")
    user_id = str(callback_query.from_user.id)
    
    if user_id not in user_data_storage:
        user_data_storage[user_id] = {}
    if 'selected_tags' not in user_data_storage[user_id]:
        user_data_storage[user_id]['selected_tags'] = []
    
    if tag not in user_data_storage[user_id]['selected_tags']:
        user_data_storage[user_id]['selected_tags'].append(tag)
        await callback_query.answer(f"✅ Тег '{tag}' добавлен в фильтры")
    else:
        user_data_storage[user_id]['selected_tags'].remove(tag)
        await callback_query.answer(f"❌ Тег '{tag}' удален из фильтров")
    
    user_data = user_data_storage.get(user_id, {})
    last_analysis = user_data.get('last_analysis', {})
    await suggest_search(callback_query.message, last_analysis.get('hubs', []), last_analysis.get('tags', []))
    await callback_query.message.delete()

@router.callback_query(lambda c: c.data == "reset_filters")
async def handle_reset_filters(callback_query: types.CallbackQuery):
    """Сброс всех фильтров"""
    user_id = str(callback_query.from_user.id)
    if user_id in user_data_storage:
        user_data_storage[user_id]['selected_hubs'] = []
        user_data_storage[user_id]['selected_tags'] = []
    
    await callback_query.answer("🗑️ Все фильтры сброшены")
    
    user_data = user_data_storage.get(user_id, {})
    last_analysis = user_data.get('last_analysis', {})
    await suggest_search(callback_query.message, last_analysis.get('hubs', []), last_analysis.get('tags', []))
    await callback_query.message.delete()

@router.callback_query(lambda c: c.data == "show_filters")
async def handle_show_filters(callback_query: types.CallbackQuery):
    """Показать выбранные фильтры"""
    user_id = str(callback_query.from_user.id)
    selected_hubs = user_data_storage.get(user_id, {}).get('selected_hubs', [])
    selected_tags = user_data_storage.get(user_id, {}).get('selected_tags', [])
    
    if not selected_hubs and not selected_tags:
        await callback_query.answer("Фильтры не выбраны", show_alert=True)
    else:
        message = "📊 *Текущие фильтры:*\n\n"
        if selected_hubs:
            message += f"🏷️ *Хабы:* {', '.join(selected_hubs)}\n"
        if selected_tags:
            message += f"🔖 *Теги:* {', '.join(selected_tags[:15])}\n"
            if len(selected_tags) > 15:
                message += f"\n*и еще {len(selected_tags) - 15} тегов*"
        
        await callback_query.answer(message, show_alert=True)
    
    await callback_query.answer()

@router.callback_query(lambda c: c.data == "search_similar")
async def handle_search_similar(callback_query: types.CallbackQuery):
    """Поиск похожих документов с выбранными фильтрами"""
    user_id = str(callback_query.from_user.id)
    
    selected_hubs = user_data_storage.get(user_id, {}).get('selected_hubs', [])
    selected_tags = user_data_storage.get(user_id, {}).get('selected_tags', [])
    
    if user_id not in user_data_storage or 'last_analysis' not in user_data_storage[user_id]:
        await callback_query.message.answer("❌ Сначала отправьте документ для анализа через /upload_doc")
        await callback_query.answer()
        return
    
    analysis_data = user_data_storage[user_id]['last_analysis']
    text = analysis_data.get('text', '')
    
    if not text:
        await callback_query.message.answer("❌ Текст документа не найден")
        await callback_query.answer()
        return
    
    search_config = user_data_storage[user_id].get('search_config', {})
    engine = search_config.get('engine', 'hybrid')
    top_k = search_config.get('top_k', 5)
    
    loading_msg = await callback_query.message.answer("🔍 Ищу похожие документы с выбранными фильтрами...")
    
    payload = {
        "query": text,
        "top_k": top_k,
        "engine": engine
    }
    
    if selected_hubs:
        payload["hubs"] = selected_hubs[:5]
    if selected_tags:
        payload["tags"] = selected_tags[:10]
    
    try:
        result = await queue_client.search(payload)
        
        if result.get("error"):
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{config.API_URL}/api/v1/search/",
                    json=payload,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                else:
                    await loading_msg.delete()
                    await callback_query.message.answer(f"❌ Ошибка поиска: {response.status_code}")
                    await callback_query.answer()
                    return
        else:
            data = result
        
        results = data.get('results', [])
        
        await loading_msg.delete()
        
        if not results:
            await callback_query.message.answer("😔 Похожих документов не найдено")
        else:
            applied_filters = []
            if selected_hubs:
                applied_filters.extend(selected_hubs[:3])
            if selected_tags:
                applied_filters.extend(selected_tags[:5])
            
            filters_msg = "🔍 *Поиск с выбранными фильтрами:* " + ", ".join(applied_filters)
            await callback_query.message.answer(filters_msg, parse_mode='Markdown')
            
            await callback_query.message.answer(
                f"✅ *Найдено {len(results)} похожих документов:*\n",
                parse_mode='Markdown'
            )
            
            for idx, result in enumerate(results[:5], 1):
                title = result.get('title', 'Без названия')
                score = result.get('score', 0)
                chunk_text = result.get('chunk_text', '')[:200]
                url = result.get('url', '#')
                
                message_text = f"*{idx}. {title}*\n"
                message_text += f"*Score:* {score:.3f}\n"
                
                if result.get('hubs'):
                    message_text += f"*Хабы:* {', '.join(result['hubs'][:2])}\n"
                if result.get('tags'):
                    message_text += f"*Теги:* {', '.join(result['tags'][:3])}\n"
                
                message_text += f"\n{chunk_text}...\n"
                message_text += f"\n[Читать далее]({url})"
                
                await callback_query.message.answer(
                    message_text,
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
    except Exception as e:
        await loading_msg.delete()
        await callback_query.message.answer(f"❌ Ошибка: {str(e)}")
    
    await callback_query.answer()

@router.callback_query(lambda c: c.data == "search_settings")
async def handle_search_settings(callback_query: types.CallbackQuery):
    """Настройки поиска: выбор движка, количества результатов"""
    user_id = str(callback_query.from_user.id)
    search_config = user_data_storage.get(user_id, {}).get('search_config', {})
    current_engine = search_config.get('engine', 'hybrid')
    current_topk = search_config.get('top_k', 5)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ hybrid" if current_engine == "hybrid" else "hybrid", callback_data="engine_hybrid"),
            InlineKeyboardButton(text="✅ dense" if current_engine == "dense" else "dense", callback_data="engine_dense")
        ],
        [
            InlineKeyboardButton(text="✅ rerank" if current_engine == "rerank" else "rerank", callback_data="engine_rerank"),
            InlineKeyboardButton(text="✅ full" if current_engine == "full" else "full", callback_data="engine_full")
        ],
        [
            InlineKeyboardButton(text="✅ 3" if current_topk == 3 else "3", callback_data="topk_3"),
            InlineKeyboardButton(text="✅ 5" if current_topk == 5 else "5", callback_data="topk_5"),
            InlineKeyboardButton(text="✅ 10" if current_topk == 10 else "10", callback_data="topk_10")
        ],
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")
        ]
    ])
    
    await callback_query.message.edit_text(
        "⚙️ *Настройки поиска:*\n\n"
        "Выберите движок поиска и количество результатов:\n"
        "• *hybrid* - комбинация векторного поиска и BM25\n"
        "• *dense* - только векторный поиск\n"
        "• *rerank* - векторный поиск с реранжированием результатов с помощью LLM\n"
        "• *full* - комбинация векторного поиска и BM25 с реранжированием",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )
    
    await callback_query.answer()

@router.callback_query(lambda c: c.data == "back_to_menu")
async def handle_back_to_menu(callback_query: types.CallbackQuery):
    """Возврат в главное меню"""
    user_id = str(callback_query.from_user.id)
    user_data = user_data_storage.get(user_id, {})
    last_analysis = user_data.get('last_analysis', {})
    await suggest_search(callback_query.message, last_analysis.get('hubs', []), last_analysis.get('tags', []))
    await callback_query.message.delete()
    await callback_query.answer()

@router.callback_query(lambda c: c.data.startswith("engine_"))
async def set_engine(callback_query: types.CallbackQuery):
    """Установка движка поиска"""
    engine = callback_query.data.split("_")[1]
    user_id = str(callback_query.from_user.id)
    
    if user_id not in user_data_storage:
        user_data_storage[user_id] = {}
    if 'search_config' not in user_data_storage[user_id]:
        user_data_storage[user_id]['search_config'] = {}
    
    user_data_storage[user_id]['search_config']['engine'] = engine
    await callback_query.answer(f"✅ Движок поиска установлен: {engine}")
    
    await handle_search_settings(callback_query)

@router.callback_query(lambda c: c.data.startswith("topk_"))
async def set_topk(callback_query: types.CallbackQuery):
    """Установка количества результатов"""
    top_k = int(callback_query.data.split("_")[1])
    user_id = str(callback_query.from_user.id)
    
    if user_id not in user_data_storage:
        user_data_storage[user_id] = {}
    if 'search_config' not in user_data_storage[user_id]:
        user_data_storage[user_id]['search_config'] = {}
    
    user_data_storage[user_id]['search_config']['top_k'] = top_k
    await callback_query.answer(f"✅ Количество результатов: {top_k}")
    
    await handle_search_settings(callback_query)

@router.message(F.text & ~F.text.startswith('/'))
async def handle_text(message: types.Message, or_api_key: str):
    """Обработка текстового сообщения"""
    user_id = str(message.from_user.id)
    
    if user_id in user_data_storage and user_data_storage[user_id].get('awaiting_search'):
        await perform_search_by_query(message, message.text)
        user_data_storage[user_id]['awaiting_search'] = False
        return
    
    text = message.text
    
    if len(text) < 50:
        await message.answer("⚠️ Пожалуйста, отправьте более содержательный текст (минимум 50 символов)")
        return
    
    loading_msg = await message.answer("🔄 Анализирую документ...")
    
    await analyze_document(message, text, or_api_key)
    
    try:
        await loading_msg.delete()
    except TelegramBadRequest:
        pass

async def perform_search_by_query(message: types.Message, query: str):
    """Выполнение поиска по текстовому запросу"""
    loading_msg = await message.answer("🔍 Поиск...")
    
    payload = {
        "query": query,
        "top_k": 5,
        "engine": "hybrid"
    }
    
    try:
        result = await queue_client.search(payload)
        
        if result.get("error"):
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{config.API_URL}/api/v1/search/",
                    json=payload,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                else:
                    await loading_msg.delete()
                    await message.answer(f"❌ Ошибка поиска: {response.status_code}")
                    return
        else:
            data = result
        
        results = data.get('results', [])
        
        await loading_msg.delete()
        
        if not results:
            await message.answer("😔 Ничего не найдено")
            return
        
        for idx, result in enumerate(results[:3], 1):
            title = result.get('title', 'Без названия')
            score = result.get('score', 0)
            chunk_text = result.get('chunk_text', '')[:300]
            url = result.get('url', '#')
            
            response_text = f"*{idx}. {title}*\n"
            response_text += f"*Score:* {score:.3f}\n\n"
            response_text += f"{chunk_text}...\n"
            response_text += f"\n[Читать далее]({url})"
            
            await message.answer(
                response_text,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
    except Exception as e:
        await loading_msg.delete()
        await message.answer(f"❌ Ошибка: {str(e)}")

@router.message(F.document & F.document.file_name.endswith('.txt'))
async def handle_txt_file(message: types.Message, bot, or_api_key: str):
    """Обработка TXT файла"""
    document = message.document
    
    loading_msg = await message.answer(f"📥 Загружаю файл {document.file_name}...")
    
    try:
        file_info = await bot.get_file(document.file_id)
        downloaded_file = await bot.download_file(file_info.file_path)
        text = downloaded_file.read().decode('utf-8', errors='ignore')
        
        if len(text) < 20:
            await loading_msg.edit_text("⚠️ Файл слишком короткий или пустой")
            return
        
        await loading_msg.edit_text("🔄 Анализирую документ...")
        
        await analyze_document(message, text, or_api_key)
        
        await loading_msg.delete()
    except Exception as e:
        await loading_msg.edit_text(f"❌ Ошибка при обработке файла: {str(e)}")

@router.message(F.document)
async def handle_unsupported_file(message: types.Message):
    """Обработка неподдерживаемых файлов"""
    await message.answer(
        "❌ Поддерживаются только TXT файлы.\n"
        "Отправьте текст напрямую или конвертируйте файл в TXT."
    )