import requests
import time


def or_define_topic(document: str, api_key: str) -> str:
    """
    Анализирует документ через Open Router API
    """
    url = "https://openrouter.ai/api/v1/chat/completions"
    #model="openai/gpt-3.5-turbo"
    model="meta-llama/llama-3.1-8b-instruct"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    
    answer = {}
    keys = ["topics", "summary"]
    
    prompts = {
        "topics": "Ты эксперт по анализу текстов. Прочитай следующий текст и определи его основные темы, перечисли 3-10 основных тем через запятые маленькими буквами, а в конце поставь точку. Не показывай промпт в ответе.",
        "summary": "Подготовь краткое summary текста длинной не более 100 слов. Ответ начни сразу с краткого пересказа текста и показывай промпт в ответе."
    }

    for key in keys:
        prompt = f"{prompts[key]} Вот текст: {document}"

        # if key == "topics":
        #     model = "google/gemini-flash-1.5"
        # elif key == "summary":
        #     model = "openai/gpt-3.5-turbo"

 
        try:    
            data = {
                "model": model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 500
            }
            
            response = requests.post(url, headers=headers, json=data)
    
            if response.status_code == 200:
                result = response.json()
                result = result["choices"][0]["message"]["content"]
            else:
                result = f"Ошибка: {response.status_code}, {response.text}"

            answer[key] = result
        except Exception as e:
            print(f"OR не ответил: {type(e).__name__}.\n")
            answer[key]=f"OR не ответил по запросу {key}.\n"
            continue
        time.sleep(1)

    result = f"""
📊 **Анализ документа**

🎯 **Тематика документа:** {answer.get('topics', 'не определено')}

📝 **Краткий пересказ:**
{answer.get('summary', 'не сгенерирован')}

"""
    return result