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
        logger.info(f"ТГ сообщение отправлено: {text}")
    except Exception as e:
        logger.error(f"Ошибка отправки в Телеграм: {e}")

async def get_live_video_id(youtube, channel_id):
    """Ищет ID активного стрима. Тратит квоты YouTube API."""
    try:
        # 1. Ищем активный эфир
        request = youtube.search().list(
            part='id',
            channelId=channel_id,
            eventType='live',
            type='video'
        )
        response = request.execute()
        if response.get('items'):
            return response['items'][0]['id']['videoId']
        
        # 2. Ищем премьеру, если эфир не найден
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
        logger.error(f"Ошибка при запросе к YouTube API: {e}")
    return None

async def youtube_bot_loop():
    # static_discovery=False убирает лишние предупреждения в логах
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY, static_discovery=False)
    seen_users = set()
    downloader = ChatDownloader()

    while True:
        try:
            # Находим ID стрима (тратим квоту)
            video_id = await get_live_video_id(youtube, YOUTUBE_CHANNEL_ID)
            
            if not video_id:
                logger.info("Стрим не найден. Ждем 5 минут перед следующей проверкой.")
                await asyncio.sleep(300)
                continue

            logger.info(f"Стрим найден (ID: {video_id}). Подключаемся к чату...")

            try:
                # В твоей версии вызываем максимально просто, чтобы не было ошибок аргументов
                chat = downloader.get_chat(video_id)
                
                # Читаем сообщения
                for message in chat:
                    author = message.get('author', {})
                    author_id = author.get('id')
                    
                    if author_id and author_id not in seen_users:
                        seen_users.add(author_id)
                        # Чистим никнейм
                        user_name = author.get('name', 'User').lstrip('@').strip()
                        await send_message(f"Новый котэк на Ютубе❤️: {user_name}")
                    
                    # Пауза, чтобы не нагружать систему
                    await asyncio.sleep(0.1)

                logger.info("Поток сообщений завершился.")

            except Exception as e:
                # Если чат отвалился, логируем и пробуем снова через 10 сек
                logger.error(f"Ошибка при чтении чата: {e}")
                await asyncio.sleep(10)
                continue # Возврат к проверке того же видео без ожидания 5 минут

            # Если стрим реально закончился, ждем минуту перед поиском нового
            await asyncio.sleep(60)

        except Exception as e:
            logger.error(f"Глобальная ошибка в основном цикле: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    try:
        asyncio.run(youtube_bot_loop())
    except KeyboardInterrupt:
        logger.info("Бот остановлен вручную.")
