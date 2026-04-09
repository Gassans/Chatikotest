import os
import asyncio
import logging
import pytchat
from googleapiclient.discovery import build
from telegram import Bot

logging.basicConfig(level=logging.INFO)

# 🛠 Настройки
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = int(os.environ["TELEGRAM_CHAT_ID"])
YOUTUBE_API_KEY = os.environ["YOUTUBE_API_KEY"]
YOUTUBE_CHANNEL_ID = os.environ["YOUTUBE_CHANNEL_ID"]

bot = Bot(token=TELEGRAM_TOKEN)


async def send_message(text: str):
    """Отправка сообщения в Telegram"""
    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)
    except Exception as e:
        logging.error(f"Ошибка отправки в Telegram: {e}")


async def get_live_video_id(youtube, channel_id):
    """
    Поиск текущего live видео или премьеры на канале.
    ⚡ Квоты тратятся только здесь.
    """
    try:
        request = youtube.search().list(
            part='id',
            channelId=channel_id,
            eventType='live',  # live или upcoming
            type='video',
            order='date',
            maxResults=1
        )
        response = request.execute()
        items = response.get('items')
        if items:
            video_id = items[0]['id']['videoId']
            logging.info(f"Найден стрим / премьера: {video_id}")
            return video_id
    except Exception as e:
        logging.error(f"Ошибка YouTube API: {e}")
    return None


async def youtube_to_telegram_loop():
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    seen_users = set()
    current_video_id = None

    while True:
        try:
            if not current_video_id:
                current_video_id = await get_live_video_id(youtube, YOUTUBE_CHANNEL_ID)

                if not current_video_id:
                    logging.info("Стрим не найден. Проверка через 5 минут.")
                    await asyncio.sleep(300)
                    continue

          
            logging.info("Ждем готовности чата...")
            await asyncio.sleep(15)

          
            chat = None
            while not chat:
                try:
                    chat = pytchat.create(video_id=current_video_id)
                    logging.info("Успешно подключились к чату")
                except Exception as e:
                    logging.error(f"pytchat не готов: {e}")
                    await asyncio.sleep(15)

            # 📖 Читаем сообщения
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
            logging.error(f"Глобальная ошибка: {e}")
            await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(youtube_to_telegram_loop())
