import httpx
from telegram import Update
from telegram.ext import ContextTypes
from config import config


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /search"""
    await update.message.reply_text("Введите ваш поисковый запрос:")
    context.user_data['awaiting_search'] = True

async def handle_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка поискового запроса"""
    query = update.message.text
    
    search_config = context.user_data.get('search_config', {})
    hubs = search_config.get('hubs', [])
    tags = search_config.get('tags', [])
    engine = search_config.get('engine', 'hybrid')
    top_k = search_config.get('top_k', 5)
    
    await update.message.reply_text("Поиск... 🔍")
    
    async with httpx.AsyncClient() as client:
        # Формируем payload
        payload = {
            "query": query,
            "top_k": top_k,
            "engine": engine
        }
        
        if hubs:
            payload["hubs"] = hubs
        if tags:
            payload["tags"] = tags
        
        response = await client.post(
            f"{config.API_URL}/api/v1/search/",
            json=payload,
            timeout=30.0
        )
        
        if response.status_code == 200:
            data = response.json()
            results = data['results']
            
            if not results:
                await update.message.reply_text("😔 Ничего не найдено")
                return
            
            if hubs or tags:
                filters_msg = "🔍 Фильтры: " + ", ".join(hubs + tags)
                await update.message.reply_text(filters_msg)
            
            for idx, result in enumerate(results[:5], 1):
                message = f"*{idx}. {result.get('title', 'Без названия')}*\n"
                message += f"Score: {result.get('score', 0):.3f}\n"
                
                if result.get('hubs'):
                    message += f"Хабы: {', '.join(result['hubs'][:3])}\n"
                if result.get('tags'):
                    message += f"Теги: {', '.join(result['tags'][:5])}\n"
                
                chunk_text = result.get('chunk_text', '')
                if chunk_text:
                    if len(chunk_text) > 500:
                        chunk_text = chunk_text[:500] + "..."
                    message += f"\n{chunk_text}\n"
                
                if result.get('url'):
                    message += f"\n[Читать далее]({result['url']})"
                
                await update.message.reply_text(
                    message,
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
        else:
            await update.message.reply_text("❌ Ошибка поиска")
    
    context.user_data['awaiting_search'] = False
    context.user_data.pop('search_config', None)

async def search_with_filters(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, hubs: list = None, tags: list = None):
    """Поиск с фильтрацией по хабам и тегам"""
    if hubs is None:
        hubs = []
    if tags is None:
        tags = []
    
    await update.message.reply_text("🔍 Поиск похожих документов...")
    
    async with httpx.AsyncClient() as client:
        payload = {
            "query": text,
            "top_k": 5,
            "engine": "hybrid",
            "hubs": hubs,
            "tags": tags
        }
        
        response = await client.post(
            f"{config.API_URL}/api/v1/search/",
            json=payload,
            timeout=30.0
        )
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            
            if not results:
                await update.message.reply_text("😔 Похожих документов не найдено")
                return
            
            await update.message.reply_text(f"✅ Найдено {len(results)} похожих документов:\n")
            
            for idx, result in enumerate(results[:3], 1):
                message = f"*{idx}. {result.get('title', 'Без названия')}*\n"
                message += f"Score: {result.get('score', 0):.3f}\n\n"
                message += f"{result.get('chunk_text', '')[:300]}...\n"
                message += f"\n[Читать далее]({result.get('url', '#')})"
                
                await update.message.reply_text(
                    message,
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
        else:
            await update.message.reply_text("❌ Ошибка поиска похожих документов")
