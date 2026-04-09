import os
import asyncio
import logging
import json
from googleapiclient.discovery import build
from telegram import Bot

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Окружение
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = int(os.environ["TELEGRAM_CHAT_ID"])
YOUTUBE_API_KEY = os.environ["YOUTUBE_API_KEY"]
YOUTUBE_CHANNEL_ID = os.environ["YOUTUBE_CHANNEL_ID"]

bot = Bot(token=TELEGRAM_TOKEN)

async def send_message(text):
    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)
    except Exception as e:
        logger.error(f"Ошибка ТГ: {e}")

async def get_live_video_id(youtube):
    """Один запрос поиска (100 юнитов)"""
    try:
        response = youtube.search().list(
            part='id',
            channelId=YOUTUBE_CHANNEL_ID,
            eventType='live',
            type='video',
            maxResults=1
        ).execute()
        if response.get('items'):
            return response['items'][0]['id']['videoId']
    except Exception as e:
        logger.error(f"Ошибка API при поиске: {e}")
    return None

async def youtube_bot_loop():
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY, static_discovery=False)
    seen_users = set()

    while True:
        try:
            # 1. Находим видео (100 юнитов)
            video_id = await get_live_video_id(youtube)
            
            if not video_id:
                logger.info("Стрим не найден. Ждем 5 минут.")
                await asyncio.sleep(300)
                continue

            logger.info(f"Стрим найден: {video_id}. Запускаем безлимитное чтение чата...")
            url = f"https://youtube.com{video_id}"

            # 2. Запускаем yt-dlp. 
            # --live-from-start может тянуть старые коменты, 
            # поэтому мы просто читаем текущий поток.
            process = await asyncio.create_subprocess_exec(
                'yt-dlp', 
                '--get-comments', 
                '--comment-sort', 'newness', # берем новые
                '--print', 'comment', 
                '--quiet', 
                url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Читаем вывод в реальном времени
            while True:
                line = await process.stdout.readline()
                if not line:
                    break # Если вывод кончился, значит процесс завершен
                
                try:
                    data = json.loads(line.decode().strip())
                    author_id = data.get('author_id')
                    
                    if author_id and author_id not in seen_users:
                        seen_users.add(author_id)
                        raw_name = data.get('author', 'User')
                        user_name = raw_name.lstrip('@').strip()
                        await send_message(f"Новый котэк на Ютубе❤️: {user_name}")
                except Exception:
                    continue

            logger.info("Чат завершен. Перепроверка через 60 секунд.")
            await asyncio.sleep(60)

        except Exception as e:
            logger.error(f"Глобальная ошибка: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(youtube_bot_loop())
