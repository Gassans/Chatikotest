import os
import asyncio
import logging
from chat_downloader import ChatDownloader
from googleapiclient.discovery import build
from telegram import Bot

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = int(os.environ["TELEGRAM_CHAT_ID"])
YOUTUBE_API_KEY = os.environ["YOUTUBE_API_KEY"]
YOUTUBE_CHANNEL_ID = os.environ["YOUTUBE_CHANNEL_ID"]

bot = Bot(token=TELEGRAM_TOKEN)

async def send_message(text):
    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)
        logger.info(f"ТГ сообщение: {text}")
    except Exception as e:
        logger.error(f"Ошибка ТГ: {e}")

async def get_live_video_id(youtube, channel_id):
    """Ищет активный стрим. Тратит квоты."""
    try:
        request = youtube.search().list(
            part='id',
            channelId=channel_id,
            eventType='live',
            type='video'
        )
        response = request.execute()
        if response.get('items'):
            return response['items'][0]['id']['videoId']
        
        # Проверка премьер
        request_up = youtube.search().list(
            part='id',
            channelId=channel_id,
            eventType='upcoming',
            type='video'
        )
        response_up = request_up.execute()
        if response_up.get('items'):
            return response_up['items'][0]['id']['videoId']
    except Exception as e:
        logger.error(f"Ошибка поиска через API: {e}")
    return None

async def youtube_bot_loop():
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY, static_discovery=False)
    seen_users = set()
    downloader = ChatDownloader()
    
    current_video_id = None # Храним ID здесь, чтобы не тратить квоты зря

    while True:
        try:
            # 1. Ищем ID видео, только если мы его еще не знаем
            if not current_video_id:
                logger.info("Поиск активного стрима (трата квоты)...")
                current_video_id = await get_live_video_id(youtube, YOUTUBE_CHANNEL_ID)
                
                if not current_video_id:
                    logger.info("Стрим не найден. Спим 5 минут.")
                    await asyncio.sleep(300) # Строго 5 минут до следующей траты квоты
                    continue

            logger.info(f"Работаем со стримом: {current_video_id}")

            # 2. Читаем чат (бесплатно)
            try:
                # В твоей версии downloader.get_chat(id) — самый безопасный вызов
                chat = downloader.get_chat(current_video_id)
                
                for message in chat:
                    author = message.get('author', {})
                    author_id = author.get('id')
                    
                    if author_id and author_id not in seen_users:
                        seen_users.add(author_id)
                        user_name = author.get('name', 'User').lstrip('@').strip()
                        await send_message(f"Новый котэк на Ютубе❤️: {user_name}")
                    
                    await asyncio.sleep(0.1)

                # Если итератор закончился сам (стрим завершен)
                logger.info("Чат завершился сам. Сбрасываем ID видео.")
                current_video_id = None 
                await asyncio.sleep(60)

            except Exception as e:
                # Если произошла ошибка парсинга или разрыв соединения
                logger.error(f"Разрыв связи с чатом: {e}")
                # МЫ НЕ ОБНУЛЯЕМ current_video_id, чтобы не тратить квоту на поиск
                # Просто пробуем переподключиться к тому же ID через 30 секунд
                await asyncio.sleep(30)
                continue

        except Exception as e:
            logger.error(f"Глобальная ошибка: {e}")
            current_video_id = None
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(youtube_bot_loop())
