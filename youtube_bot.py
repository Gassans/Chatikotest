import os
import asyncio
import logging
import pytchat
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from telegram import Bot

logging.basicConfig(level=logging.INFO)

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


async def get_active_or_upcoming_stream(youtube, channel_id):
    """Ищем активный стрим или премьеру с liveChatId"""
    try:
        request = youtube.search().list(
            part="id",
            channelId=channel_id,
            type="video",
            order="date",
            maxResults=5
        )
        response = request.execute()

        for item in response.get("items", []):
            video_id = item["id"]["videoId"]

            # Проверяем детали стрима
            details_request = youtube.videos().list(
                part="liveStreamingDetails",
                id=video_id
            )
            details_response = details_request.execute()
            live_details = details_response["items"][0].get("liveStreamingDetails", {})

            live_chat_id = live_details.get("activeLiveChatId")
            if live_chat_id:
                return video_id, live_chat_id

    except HttpError as e:
        logging.error(f"Ошибка YouTube API: {e}")
    except Exception as e:
        logging.error(f"Ошибка при поиске стрима: {e}")

    return None, None


async def youtube_bot_loop():
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    seen_users = set()

    while True:
        try:
            video_id, live_chat_id = await get_active_or_upcoming_stream(
                youtube, YOUTUBE_CHANNEL_ID
            )

            if not video_id:
                logging.info("Стрим/премьера не найдены. Проверка через 2 минуты.")
                await asyncio.sleep(120)
                continue

            logging.info(f"Найден стрим/премьера: {video_id}, liveChatId: {live_chat_id}")

            # 🔁 Подключаем pytchat к liveChatId
            chat = None
            while not chat:
                try:
                    chat = pytchat.create(video_id=video_id, interruptable=True)
                    logging.info("Успешно подключились к чату")
                except Exception as e:
                    logging.error(f"pytchat не готов: {e}")
                    await asyncio.sleep(10)

            # 📖 Читаем чат
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

            # ❗ Если чат умер, сбрасываем
            logging.info("Чат завершён. Сбрасываем video_id.")
            await asyncio.sleep(30)

        except Exception as e:
            logging.error(f"Глобальная ошибка цикла: {e}")
            await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(youtube_bot_loop())
