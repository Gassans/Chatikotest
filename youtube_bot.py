import os
import asyncio
import logging
import pytchat
from pytchat import LiveChat
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

async def youtube_bot_loop():
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    seen_users = set()

    while True:
        try:
            # 1. Находим live видео или премьеры
            video_id = await get_live_video_id(youtube, YOUTUBE_CHANNEL_ID)
            if not video_id:
                logging.info("Стрим/премьера не найдены. Следующая проверка через 5 минут.")
                await asyncio.sleep(300)
                continue

            logging.info(f"Найден стрим/премьера: {video_id}")
            
            # 2. Подождём, пока чат стабилизируется (особенно для премьеры)
            await asyncio.sleep(10)

            chat = None
            # 3. Постоянная проверка подключения к чату (LiveChat)
            while True:
                try:
                    chat = LiveChat(video_id=video_id)
                    if chat.is_alive():
                        logging.info(f"Успешное подключение к чату видео {video_id}")
                        break
                except Exception as e:
                    logging.error(f"Чат пока недоступен, повтор через 5 секунд: {e}")
                await asyncio.sleep(5)

            # 4. Читаем чат
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
                    logging.error(f"Ошибка в чтении чата: {e}")
                    await asyncio.sleep(5)

            logging.info("Чат завершён. Проверка нового стрима через 5 минут.")
            await asyncio.sleep(300)

        except Exception as e:
            logging.error(f"Глобальная ошибка цикла: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(youtube_bot_loop())
