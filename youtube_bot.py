import os
import asyncio
import logging
import yt_dlp
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

def download_chat(url, seen_users, loop):
    """Функция для работы с yt_dlp в синхронном режиме (внутри потока)"""
    
    # Обработчик каждого сообщения
    def comment_callback(comment):
        author_id = comment.get('author_id')
        if author_id and author_id not in seen_users:
            seen_users.add(author_id)
            raw_name = comment.get('author', 'User')
            user_name = raw_name.lstrip('@').strip()
            # Отправляем сообщение асинхронно из синхронной функции
            asyncio.run_coroutine_threadsafe(
                send_message(f"Новый котэк на Ютубе❤️: {user_name}"), 
                loop
            )

    ydl_opts = {
        'getcomments': True,
        'quiet': True,
        'live_from_start': False, # Берем только новые
        'comment_data_callback': comment_callback,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            ydl.download([url])
        except Exception as e:
            logger.error(f"yt_dlp завершил работу: {e}")

async def youtube_bot_loop():
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY, static_discovery=False)
    seen_users = set()
    loop = asyncio.get_running_loop()

    while True:
        try:
            video_id = await get_live_video_id(youtube)
            
            if not video_id:
                logger.info("Стрим не найден. Ждем 5 минут.")
                await asyncio.sleep(300)
                continue

            logger.info(f"Стрим найден: {video_id}. Запускаем безлимитный чат...")
            url = f"https://youtube.com{video_id}"

            # Запускаем блокирующую функцию yt_dlp в отдельном потоке, 
            # чтобы она не вешала весь бот
            await loop.run_in_executor(None, download_chat, url, seen_users, loop)

            logger.info("Переподключение через 30 секунд...")
            await asyncio.sleep(30)

        except Exception as e:
            logger.error(f"Глобальная ошибка: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(youtube_bot_loop())
