import time
import requests


def hf_define_topic(document: str, api_key: str) -> str:
    """
    Анализирует документ через Hugging Face Inference API
    Использует router.huggingface.co
    """
    answer = {}
    keys = ["topics", "summary"]
    
    prompts = {
        "topics": "Ты эксперт по анализу текстов. Прочитай следующий текст и определи его основные темы, перечисли 3-10 основных тем через запятые маленькими буквами, а в конце поставь точку",
        "summary": "Подготовь краткое summary текста длинной не более 100 слов"
    }

    for key in keys:
        try:
            print(f"Отправляю запрос '{key}' к Hugging Face API...")
            
            #API_URL = "https://router.huggingface.co/hf-inference/models"
            #API_URL = "https://router.huggingface.co/v1/models"
            #API_URL = "https://router.huggingface.co/models"
            
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            if key == "topics":
                # Используем модель для классификации
                # model = "facebook/bart-large-mnli"
                
                # payload = {
                #     "model": model,
                #     "inputs": document[:1000],
                #     "parameters": {
                #         "candidate_labels": [
                #             "технологии", "образование", "преступность", "спорт", 
                #             "авиамоделирование", "психология", "общество", "насилие"
                #         ]
                #     }
                # }

                #model = "mistralai/Mistral-7B-Instruct-v0.1"

                #model = "google/flan-t5-xxl"

                model = "google/flan-t5-xxl"  # или "microsoft/DialoGPT-medium"
                API_URL = f"https://api-inference.huggingface.co/models/{model}"


                prompt = f""" {prompts[key]}  Текст: {document}  Темы: """ 
    
                payload = {
                            #"model": model,
                            "inputs": prompt,
                            "parameters": {
                                "max_new_tokens": 300,
                                "temperature": 0.3,
                                "do_sample": False
                            }
                }            
            else:  # summary
                

                model = "facebook/bart-large-cnn"
                API_URL = f"https://api-inference.huggingface.co/models/{model}"
                

                prompt = f""" {prompts[key]}  Текст: {document}""" 

                
                payload = {
                    #"model": model,
                    "inputs": prompt,
                    "parameters": {
                        "max_length": 500,
                        "min_length": 30,
                        "do_sample": False
                    }
                }
            
            response = requests.post(
                API_URL, 
                headers=headers, 
                json=payload, 
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if key == "topics":
                    answer[key] = str(result[0])
                else:  # summary
                    if isinstance(result, list) and len(result) > 0:
                        if isinstance(result[0], dict) and "summary_text" in result[0]:
                            answer[key] = result[0]["summary_text"]
                        else:
                            answer[key] = str(result[0])
                    else:
                        answer[key] = "Краткое содержание не сгенерировано."
                
                print(f"Hugging Face ответил на '{key}'")
                
            else:
                print(f"HTTP {response.status_code}: {response.text[:200]}")
                answer[key] = "HF API не отвечает!"

        except Exception as e:
            print(f"Hugging Face не ответил: {type(e).__name__}")
            answer[key] = f"Hugging Face не ответил по запросу {key}."
            continue
        time.sleep(1)
    

    result = f"""
📊 **Анализ документа**

🎯 **Тематика документа:** {answer.get('topics', 'не определено')}

📝 **Сниппет:**
{answer.get('summary', 'не сгенерирован')}

🤖 *Анализ документа выполнен с помощью API Hugging Face AI*
"""
    return result

