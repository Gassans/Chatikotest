import os
import asyncio
import logging

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pytchat import LiveChat
from telegram import Bot

logging.basicConfig(level=logging.INFO)


TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = int(os.environ["TELEGRAM_CHAT_ID"])
YOUTUBE_API_KEY = os.environ["YOUTUBE_API_KEY"]
YOUTUBE_CHANNEL_ID = os.environ["YOUTUBE_CHANNEL_ID"]

bot = Bot(token=TELEGRAM_TOKEN)


async def send_message(text: str):
    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)
    except Exception as e:
        logging.error(f"Ошибка отправки в Telegram: {e}")


async def get_live_video_id(youtube, channel_id):
    try:
        request = youtube.search().list(
            part="id",
            channelId=channel_id,
            eventType="live",
            type="video",
            maxResults=1
        )
        response = request.execute()

        if response.get("items"):
            return response["items"][0]["id"]["videoId"]

    except HttpError as e:
        logging.error(f"Ошибка YouTube API при получении live video: {e}")
    except Exception as e:
        logging.error(f"Неожиданная ошибка YouTube API: {e}")

    return None


async def youtube_bot_loop():
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    seen_users = set()
    current_video_id = None

    while True:
        try:
           
            if not current_video_id:
                current_video_id = await get_live_video_id(youtube, YOUTUBE_CHANNEL_ID)

                if not current_video_id:
                    logging.info("Стрим не найден. Проверка через 5 минут.")
                    await asyncio.sleep(300)  # проверка каждые 5 минут
                    continue

                logging.info(f"Найден стрим/премьера: {current_video_id}")
                logging.info("Ждём 30 секунд, чтобы чат стабилизировался...")
                await asyncio.sleep(30)

            
            chat = None
            while not chat:
                try:
                    chat = LiveChat(video_id=current_video_id)
                    chat.renderer.channelId = YOUTUBE_CHANNEL_ID  
                    logging.info("Успешно подключились к чату")
                except Exception as e:
                    logging.error(f"pytchat не готов, повтор через 15 секунд: {e}")
                    await asyncio.sleep(15)

            
            while chat.is_alive():
                try:
                    for c in chat.get().sync_items():
                        author_id = c.author.channelId
                        if author_id not in seen_users:
                            seen_users.add(author_id)
                            user_name = c.author.name.lstrip('@').strip()
                            await send_message(f"Новый котэк на Ютубе❤️: {user_name}")
                    await asyncio.sleep(1)
                except Exception as e:
                    logging.error(f"Ошибка чтения чата: {e}")
                    await asyncio.sleep(5)

            
            logging.info("Чат завершён. Сбрасываем video_id.")
            current_video_id = None
            await asyncio.sleep(60)

        except Exception as e:
            logging.error(f"Глобальная ошибка цикла: {e}")
            await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(youtube_bot_loop())
