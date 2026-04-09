import os
import asyncio
import logging
from chat_downloader import ChatDownloader
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from telegram import Bot

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Переменные окружения
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
    """Ищет активный стрим или премьеру. Тратит квоты API."""
    try:
        # Проверка активного лайва
        request = youtube.search().list(
            part='id',
            channelId=channel_id,
            eventType='live',
            type='video'
        )
        response = request.execute()
        if response.get('items'):
            return response['items'][0]['id']['videoId']
        
        # Проверка предстоящих трансляций
        request_upcoming = youtube.search().list(
            part='id',
            channelId=channel_id,
            eventType='upcoming',
            type='video'
        )
        response_upcoming = request_upcoming.execute()
        if response_upcoming.get('items'):
            return response_upcoming['items'][0]['id']['videoId']
            
    except Exception as e:
        logger.error(f"Ошибка поиска YouTube API: {e}")
    return None

async def youtube_bot_loop():
    # static_discovery=False убирает лишние алерты кэша
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY, static_discovery=False)
    seen_users = set() # Список уникальных пользователей за сессию
    downloader = ChatDownloader()

    while True:
        try:
            # 1. Ищем ID видео (тратим квоту)
            video_id = await get_live_video_id(youtube, YOUTUBE_CHANNEL_ID)
            
            if not video_id:
                logger.info("Стрим не найден. Ждем 5 минут...")
                await asyncio.sleep(300)
                continue

            logger.info(f"Стрим найден! ID: {video_id}. Подключаемся...")

            # 2. Читаем чат (бесплатно, без квот API)
            try:
                # Параметры заставляют читалку ждать сообщения и пробовать реконнект
                chat = downloader.get_chat(
                    video_id, 
                    params={
                        'timeout': 3600,             # Держать сессию долго
                        'retry_attempts': 10,        # Пытаться переподключиться при обрыве
                        'continuation_fetch_sleep': 1 # Частота опроса чата в секундах
                    }
                )
                
                # Цикл будет работать, пока стрим идет
                for message in chat:
                    author = message.get('author', {})
                    author_id = author.get('id')
                    
                    if author_id and author_id not in seen_users:
                        seen_users.add(author_id)
                        user_name = author.get('name', 'User').lstrip('@').strip()
                        await send_message(f"Новый котэк на Ютубе❤️: {user_name}")
                    
                    # Минимальная пауза для асинхронности
                    await asyncio.sleep(0.1)

                # Если мы вышли из цикла for - значит стрим реально кончился
                logger.info("Чат пуст или завершен. Проверим статус стрима...")

            except Exception as e:
                logger.error(f"Ошибка внутри чата: {e}")
                await asyncio.sleep(10) # Короткая пауза при ошибке чата
                continue # Возврат к началу, чтобы снова проверить тот же video_id

            # Пауза перед следующей проверкой квот после завершения стрима
            await asyncio.sleep(60)

        except Exception as e:
            logger.error(f"Глобальная ошибка: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(youtube_bot_loop())
