import os
import asyncio
import logging
from chat_downloader import ChatDownloader
from googleapiclient.discovery import build
from telegram import Bot

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
    except Exception as e:
        logger.error(f"Ошибка Telegram: {e}")


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

        # fallback — ищем upcoming (премьеры)
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


def run_chat_downloader(url, seen_users, loop):
    downloader = ChatDownloader()

    try:
        chat = downloader.get_chat(
            url,
            message_groups=['messages'],  # только сообщения
        )

        for message in chat:
            try:
                author_id = message.get('author_id')
                if not author_id:
                    continue

                if author_id not in seen_users:
                    seen_users.add(author_id)

                    name = message.get('author', {}).get('name', 'User')
                    name = name.lstrip('@').strip()

                    asyncio.run_coroutine_threadsafe(
                        send_message(f"Новый котэк на Ютубе❤️: {name}"),
                        loop
                    )

            except Exception as e:
                logger.error(f"Ошибка обработки сообщения: {e}")

    except Exception as e:
        logger.error(f"chat-downloader упал: {e}")


async def youtube_bot_loop():
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY, static_discovery=False)
    seen_users = set()
    loop = asyncio.get_running_loop()

    while True:
        try:
            video_id = await get_live_video_id(youtube)

            if not video_id:
                logger.info("Стрим/премьера не найдены. Ждём 5 минут...")
                await asyncio.sleep(300)
                continue

            url = f"https://www.youtube.com/watch?v={video_id}"

            logger.info("===================================")
            logger.info(f"Подключаемся к: {url}")
            logger.info("===================================")

            # запускаем в отдельном потоке
            await loop.run_in_executor(
                None,
                run_chat_downloader,
                url,
                seen_users,
                loop
            )

            logger.info("Чат завершён. Проверка через 5 минут...")
            await asyncio.sleep(300)

        except Exception as e:
            logger.error(f"Глобальная ошибка: {e}")
            await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(youtube_bot_loop())
