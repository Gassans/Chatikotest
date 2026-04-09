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

async def get_live_video_id(youtube, channel_id):
    try:
        # Ищем активный стрим
        request = youtube.search().list(
            part='id',
            channelId=channel_id,
            eventType='live',
            type='video'
        )
        response = request.execute()
        if response['items']:
            return response['items'][0]['id']['videoId']
        
        # Если стрима нет, ищем премьеры/предстоящие
        request_upcoming = youtube.search().list(
            part='id',
            channelId=channel_id,
            eventType='upcoming',
            type='video'
        )
        response_upcoming = request_upcoming.execute()
        if response_upcoming['items']:
            return response_upcoming['items'][0]['id']['videoId']
            
    except HttpError as e:
        logging.error(f"Ошибка YouTube API: {e}")
    except Exception as e:
        logging.error(f"Ошибка при поиске видео: {e}")
    return None

async def youtube_bot_loop():
    # static_discovery=False убирает ошибку кэширования в логах
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY, static_discovery=False)
    seen_users = set()

    while True:
        try:
            # 1. Находим ID видео
            video_id = await get_live_video_id(youtube, YOUTUBE_CHANNEL_ID)
            if not video_id:
                logging.info("Стрим/премьера не найдены. Следующая проверка через 5 минут.")
                await asyncio.sleep(300)
                continue

            logging.info(f"Найден стрим/премьера: {video_id}")
            await asyncio.sleep(5)

            # 2. Инициализация чата
            chat = None
            try:
                # Создаем объект напрямую
                chat = LiveChat(video_id=video_id)
                
                # ХАК ДЛЯ 0.5.5: Подменяем метод, который вызывает ошибку поиска channelId
                # Присваиваем ID канала напрямую внутреннему парсеру
                if hasattr(chat, '_parser'):
                    chat._parser._channel_id = YOUTUBE_CHANNEL_ID
                
                logging.info(f"Инициализировано прямое подключение к {video_id}")
            except Exception as e:
                logging.error(f"Не удалось инициализировать LiveChat: {e}")
                await asyncio.sleep(60)
                continue

            # 3. Читаем сообщения
            while chat.is_alive():
                try:
                    data = chat.get()
                    for c in data.sync_items():
                        author_id = c.author.channelId
                        if author_id not in seen_users:
                            seen_users.add(author_id)
                            user_name = c.author.name.lstrip('@').strip()
                            await send_message(f"Новый котэк на Ютубе❤️: {user_name}")
                    
                    # Даем асинхронности подышать
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logging.error(f"Ошибка при получении сообщений: {e}")
                    await asyncio.sleep(5)
                    if not chat.is_alive():
                        break

            logging.info("Стрим завершен или соединение разорвано. Ожидание 5 минут.")
            await asyncio.sleep(300)

        except Exception as e:
            logging.error(f"Глобальная ошибка в youtube_bot_loop: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(youtube_bot_loop())
