import sys
import os
from pathlib import Path
import torch
import gc
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel
import re
import requests
import time
from config import config


sys.path.append(str(Path(__file__).parent.parent.parent))
MODEL_DIR_HUBS = Path(__file__).parent.parent / "models" / "lora_vikhr_improved"


def clear_memory():
    """Агрессивная очистка памяти GPU"""
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.reset_accumulated_memory_stats()


def or_define_topic(document: str, api_key: str) -> str:
    """
    Анализирует документ через Open Rputer API
    """
    url = "https://openrouter.ai/api/v1/chat/completions"
    #model="openai/gpt-3.5-turbo"
    model="meta-llama/llama-3.1-8b-instruct"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    
    answer = {}
    #keys = ["topics", "summary"]
    keys = ["summary"]
    
    prompts = {
        "topics": "Ты эксперт по анализу текстов. Прочитай следующий текст и определи его основные темы, перечисли 3-10 основных тем через запятые маленькими буквами, а в конце поставь точку. Не включай в ответ промпт.",
        "summary": "Подготовь краткое summary текста длинной не более 100 слов. Не включай в ответ промпт. Ответ должен начинаться сразу с пересказа."
    }

    for key in keys:
        prompt = f"{prompts[key]} Вот текст: {document}"
 
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

    result = f"{answer.get('summary', 'Краткий пересказ не сгенерирован!')}"
    return result


def load_model_4bit_optimized(model_id):
    """Загрузка модели в 4-бит с максимальной экономией памяти"""
    # очищаем память перед загрузкой
    #clear_memory()

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16
    )

    tokenizer = AutoTokenizer.from_pretrained(model_id)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        use_cache=True,
        low_cpu_mem_usage=True,
        torch_dtype=torch.bfloat16
    )

    return model, tokenizer

def generate_summary(model, tokenizer, text, max_new_tokens=150):
    """Генерация саммари с защитой от повторений"""
    if not isinstance(text, str) or len(text.strip()) == 0:
        return "Текст не предоставлен"

    try:
        if len(text) > 1500:
            text = text[:1500].rsplit(' ', 1)[0]

        prompt = f"""<bos><start_of_turn>user
Напиши краткое и информативное саммари текста.

Текст: {text}

Саммари:<end_of_turn>
<start_of_turn>model
"""

        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
        inputs = {k: v.to(model.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=0.7,
                top_p=0.9,
                top_k=50,
                do_sample=True,
                repetition_penalty=1.15,
                no_repeat_ngram_size=3,
                eos_token_id=tokenizer.eos_token_id,
                pad_token_id=tokenizer.pad_token_id,
                early_stopping=True
            )

        input_length = inputs['input_ids'].shape[1]
        generated_tokens = outputs[0][input_length:]
        summary = tokenizer.decode(generated_tokens, skip_special_tokens=True)

        summary = summary.strip()
        summary = re.sub(r'^\s*Саммари[:\s]*', '', summary, flags=re.IGNORECASE)
        summary = re.sub(r'(\w)\1{5,}', r'\1\1\1', summary)

        if len(summary) < 10 or len(set(summary)) < 3:
            return "Не удалось сгенерировать качественное саммари"

        return summary

    except Exception as e:
        print(f"Ошибка генерации: {e}")
        clear_memory()
        return "Ошибка при генерации"


def load_trained_model(lora_path=MODEL_DIR_HUBS):
    """Загрузка обученной модели с LoRA адаптером"""

    print("Начинаем загрузку модели...")
    #clear_memory()

    model_id = "Vikhrmodels/Vikhr-Gemma-2B-instruct"


    
    if not os.path.exists(lora_path):
        print(f"Папка {lora_path} не найдена!")
        print("Загружаем только базовую модель...")
        model, tokenizer = load_model_4bit_optimized(model_id)
        print("Базовая модель загружена")
        return model, tokenizer

    print("Загрузка базовой модели...")
    model, tokenizer = load_model_4bit_optimized(model_id)

    try:
        print(f"Загрузка LoRA адаптера из {lora_path}...")
        model = PeftModel.from_pretrained(model, lora_path)
        model.eval()
        print("LoRA адаптер успешно загружен!")

        print(f"Состояние: {model.active_adapters}")

    except Exception as e:
        print(f"Не удалось загрузить LoRA адаптер: {e}")
        print("Используем базовую модель без адаптера")

    model.config.use_cache = False

    print("Модель готова к работе!")
    return model, tokenizer

def quick_summary(text, model, tokenizer):
    """Быстрая генерация саммари"""
    if not text or len(text) < 10:
        return "Текст слишком короткий"

    summary = generate_summary(model, tokenizer, text)
    return summary




model_infer, tokenizer_infer = load_trained_model("./lora_vikhr_improved")




def create_summary(document: str) -> str:
    """
    Краткий пересказ текста
    
    Args:
        document: текст документа для пересказа
    Returns:
        краткий пересказ текста
    """
    try:
        result = generate_summary(model_infer, tokenizer_infer, document, max_new_tokens=150)
        return result
    except Exception as e:
        result = or_define_topic(document, config.OR_API_KEY)
        print(f"Ошибка генерации саммари: {str(e)}. Документ: {document}")
        return result
        