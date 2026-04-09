import os
import asyncio
import logging
import time
from chat_downloader import ChatDownloader
from googleapiclient.discovery import build
from telegram import Bot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = int(os.environ["TELEGRAM_CHAT_ID"])
YOUTUBE_API_KEY = os.environ["YOUTUBE_API_KEY"]
YOUTUBE_CHANNEL_ID = os.environ["YOUTUBE_CHANNEL_ID"]
COOKIES_FILE = "cookies.txt"  # Путь к cookies из браузера

bot = Bot(token=TELEGRAM_TOKEN)

async def send_message(text):
    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)
    except Exception as e:
        logger.error(f"Ошибка Telegram: {e}")


async def get_live_video_id(youtube):
    try:
        # Сначала live
        response = youtube.search().list(
            part='id',
            channelId=YOUTUBE_CHANNEL_ID,
            eventType='live',
            type='video',
            maxResults=1
        ).execute()

        if response.get('items'):
            return response['items'][0]['id']['videoId']

        # fallback — премьера
        response = youtube.search().list(
            part='id',
            channelId=YOUTUBE_CHANNEL_ID,
            eventType='upcoming',
            type='video',
            maxResults=1
        ).execute()

        if response.get('items'):
            return response['items'][0]['id']['videoId']

    except Exception as e:
        logger.error(f"Ошибка API: {e}")
    return None


def chat_worker(url, seen_users, loop):
    while True:
        try:
            logger.info("Пробуем подключиться к чату...")
            downloader = ChatDownloader(cookies=COOKIES_FILE)
            chat = downloader.get_chat(url, message_groups=["messages"])
            logger.info("✅ Подключились к чату")

            last_message_time = time.time()

            for message in chat:
                try:
                    last_message_time = time.time()
                    author_id = message.get("author_id")
                    if not author_id:
                        continue

                    if author_id not in seen_users:
                        seen_users.add(author_id)
                        name = message.get("author", {}).get("name", "User").lstrip("@").strip()
                        asyncio.run_coroutine_threadsafe(
                            send_message(f"Новый котэк на Ютубе❤️: {name}"), loop
                        )

                except Exception as e:
                    logger.error(f"Ошибка сообщения: {e}")

                if time.time() - last_message_time > 30:
                    logger.warning("⚠️ Нет сообщений 30 сек → реконнект")
                    break

            logger.warning("⚠️ Чат завершён → реконнект через 3 сек")
            time.sleep(3)

        except Exception as e:
            logger.error(f"Ошибка chat-downloader: {e}")
            logger.info("Повтор через 3 секунды...")
            time.sleep(3)


async def youtube_bot_loop():
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY, static_discovery=False)
    seen_users = set()
    loop = asyncio.get_running_loop()

    while True:
        try:
            video_id = await get_live_video_id(youtube)
            if not video_id:
                logger.info("Стрим не найден. Ждём 5 минут...")
                await asyncio.sleep(300)
                continue

            url = f"https://www.youtube.com/watch?v={video_id}"
            logger.info("===================================")
            logger.info(f"СТРИМ НАЙДЕН: {url}")
            logger.info("===================================")

            await asyncio.sleep(20)  # чат “созревает”

            # запускаем chat-downloader в отдельном потоке
            await loop.run_in_executor(None, chat_worker, url, seen_users, loop)

            logger.info("Чат завершён. Проверка через 5 минут...")
            await asyncio.sleep(300)

        except Exception as e:
            logger.error(f"Глобальная ошибка: {e}")
            await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(youtube_bot_loop())
