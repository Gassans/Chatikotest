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
        logger.info(f"Сообщение отправлено: {text}")
    except Exception as e:
        logger.error(f"Ошибка отправки в Telegram: {e}")

async def get_live_video_id(youtube, channel_id):
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
        
        # Проверка предстоящих трансляций (премьер)
        request_upcoming = youtube.search().list(
            part='id',
            channelId=channel_id,
            eventType='upcoming',
            type='video'
        )
        response_upcoming = request_upcoming.execute()
        if response_upcoming.get('items'):
            return response_upcoming['items'][0]['id']['videoId']
            
    except HttpError as e:
        logger.error(f"YouTube API Error: {e}")
    except Exception as e:
        logger.error(f"Search Error: {e}")
    return None

async def youtube_bot_loop():
    # static_discovery=False убирает лишние ошибки в логах
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY, static_discovery=False)
    seen_users = set()
    downloader = ChatDownloader()

    while True:
        try:
            # 1. Получаем актуальный ID видео
            video_id = await get_live_video_id(youtube, YOUTUBE_CHANNEL_ID)
            
            if not video_id:
                logger.info("Стрим/премьера не найдены. Проверка через 5 минут...")
                await asyncio.sleep(300)
                continue

            logger.info(f"Подключение напрямую к чату ID: {video_id}")

            try:
                # Используем URL, но принудительно отключаем парсинг метаданных страницы
                # Это должно убрать ошибку "Unable to parse initial video data"
                url = f"https://youtube.com{video_id}"
                chat = downloader.get_chat(
                    url=url,
                    ignore_exceptions=['JSONDecodeError'] # Игнорируем ошибки кривого парсинга
                )
                
                for message in chat:
                    author = message.get('author', {})
                    author_id = author.get('id')
                    
                    if author_id and author_id not in seen_users:
                        seen_users.add(author_id)
                        user_name = author.get('name', 'User').lstrip('@').strip()
                        await send_message(f"Новый котэк на Ютубе❤️: {user_name}")
                    
                    await asyncio.sleep(0.1)

            except Exception as e:
                # Если ошибка 'Unable to parse', пробуем еще более простой метод
                logger.error(f"Ошибка при чтении чата: {e}")
                await asyncio.sleep(30)


            logger.info("Цикл чата прерван. Перепроверка через 5 минут...")
            await asyncio.sleep(300)

        except Exception as e:
            logger.error(f"Глобальная ошибка в youtube_bot_loop: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    try:
        asyncio.run(youtube_bot_loop())
    except KeyboardInterrupt:
        logger.info("Бот выключен пользователем")
