import time
from groq import Groq



def groq_define_topic(document: str, api_key: str) -> str:
    """
    Анализирует документ через GROQ API
    """
    client = Groq(api_key=api_key)
    
    answer = {}
    keys = ["topics", "summary"]
    prompts = {"topics":"Определи темы этого текста и перечисли их через запятые маленькими буквами, а в конце поставь точку",
               "summary":"Подготовь краткое summary текста длинной не более 100 слов"
               }

    for key in keys:
        try:    
            response = client.chat.completions.create(
                messages=[
                    {
                        "role": "user", 
                        "content": f"{prompts[key]}: {document}"
                    }
                ],
                model="llama-3.3-70b-versatile",
                max_tokens=300,
                temperature=0.3
            )
            answer[key] = response.choices[0].message.content.strip() 


            print(response.choices[0].message.content)
            answer[key] = response.choices[0].message.content.strip() 


        except Exception as e:
            print(f"Грок не ответил: {type(e).__name__}. Требуется VPN.")
            answer[key]=f"Грок не ответил по запросу {key}. Требуется VPN."
            continue
        time.sleep(1)
    answer = f"Тематика документа: {answer['topics']}\n\nСниппет:\n{answer['summary']}"
    return answer

