import os
import asyncio
import logging
from chat_downloader import ChatDownloader
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from telegram import Bot

# Логирование
logging.basicConfig(level=logging.INFO)

# Переменные окружения
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = int(os.environ["TELEGRAM_CHAT_ID"])
YOUTUBE_API_KEY = os.environ["YOUTUBE_API_KEY"]
YOUTUBE_CHANNEL_ID = os.environ["YOUTUBE_CHANNEL_ID"]

bot = Bot(token=TELEGRAM_TOKEN)

async def send_message(text):
    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)
    except Exception as e:
        logging.error(f"Ошибка отправки в Telegram: {e}")

async def get_live_video_id(youtube, channel_id):
    try:
        request = youtube.search().list(
            part='id',
            channelId=channel_id,
            eventType='live',
            type='video'
        )
        response = request.execute()
        if response['items']:
            return response['items'][0]['id']['videoId']
        
        request_upcoming = youtube.search().list(
            part='id',
            channelId=channel_id,
            eventType='upcoming',
            type='video'
        )
        response_upcoming = request_upcoming.execute()
        if response_upcoming['items']:
            return response_upcoming['items'][0]['id']['videoId']
            
    except Exception as e:
        logging.error(f"Ошибка YouTube API: {e}")
    return None

async def youtube_bot_loop():
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY, static_discovery=False)
    seen_users = set()
    downloader = ChatDownloader()

    while True:
        try:
            video_id = await get_live_video_id(youtube, YOUTUBE_CHANNEL_ID)
            if not video_id:
                logging.info("Стрим не найден. Ждем 5 минут...")
                await asyncio.sleep(300)
                continue

            url = f"https://www.youtube.com/watch?v={video_id}"
            logging.info(f"Подключение к чату через chat-downloader: {url}")

            try:
                # Получаем итератор чата (работает асинхронно в потоке)
                chat = downloader.get_chat(url)
                
                for message in chat:
                    author_id = message.get('author', {}).get('id')
                    if author_id and author_id not in seen_users:
                        seen_users.add(author_id)
                        user_name = message['author']['name'].lstrip('@').strip()
                        await send_message(f"Новый котэк на Ютубе❤️: {user_name}")
                    
                    # Маленькая пауза, чтобы не забивать цикл
                    await asyncio.sleep(0.1)

            except Exception as e:
                logging.error(f"Ошибка при чтении чата: {e}")
                await asyncio.sleep(30)

            logging.info("Стрим завершен. Проверка через 5 минут.")
            await asyncio.sleep(300)

        except Exception as e:
            logging.error(f"Глобальная ошибка: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(youtube_bot_loop())
