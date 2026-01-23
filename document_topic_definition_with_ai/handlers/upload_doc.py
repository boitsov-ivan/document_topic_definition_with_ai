from aiogram import Router, types, F
from aiogram.filters import Command

from services.groq_api import groq_define_topic
from services.huggingface_api import hf_define_topic
from services.or_api import or_define_topic

router = Router()



@router.message(Command("upload_doc"))
async def cmd_upload_doc(message: types.Message, users: dict, groq_api_key: str, hf_api_key: str, or_api_key: str):
    await message.reply(
        "Отправьте текст документа или TXT файл.\n"
        "Я проанализирую его."
    )

@router.message(F.text & ~F.text.startswith('/'))
async def handle_text(message: types.Message, groq_api_key: str, hf_api_key: str, or_api_key: str):
    text = message.text
    #answer = groq_define_topic(text, groq_api_key)
    answer = or_define_topic(text, or_api_key)
    if answer:
        await message.reply(answer)
    else:
        await message.reply(f"Не могу проанализировать документ!")


@router.message(F.document & F.document.file_name.endswith('.txt'))
async def handle_txt_file(message: types.Message, bot, groq_api_key: str, hf_api_key: str, or_api_key: str):
    document = message.document
    
    file_info = await bot.get_file(document.file_id)
    downloaded_file = await bot.download_file(file_info.file_path)
    text = downloaded_file.read().decode('utf-8', errors='ignore')

    #answer = groq_define_topic(text, groq_api_key)
    answer = or_define_topic(text, or_api_key)
    if answer:
        await message.reply(answer)
    else:
        await message.reply(f"Не могу проанализировать документ!")

    
    # await message.reply(
    #     f"TXT файл получен!\n"
    #     f"Имя: {document.file_name}\n"
    #     f"Размер: {len(text)} символов\n"
    #     f"Предпросмотр: {text[:200]}..."
    # )

@router.message(F.document)
async def handle_unsupported_file(message: types.Message):
    await message.reply(
        "Поддерживаются только TXT файлы.\n"
        "Отправьте текст напрямую или конвертируйте файл в TXT."
    )


