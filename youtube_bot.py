import os
import asyncio
import logging
from googleapiclient.discovery import build
from telegram import Bot

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        logger.error(f"Ошибка ТГ: {e}")

async def get_live_info(youtube):
    """Находит стрим и ID чата. Тратит квоты только при вызове."""
    try:
        search = youtube.search().list(
            part='id', channelId=YOUTUBE_CHANNEL_ID, eventType='live', type='video'
        ).execute()
        
        if not search.get('items'):
            return None, None
        
        video_id = search['items'][0]['id']['videoId']
        
        video_details = youtube.videos().list(
            part='liveStreamingDetails', id=video_id
        ).execute()
        
        chat_id = video_details['items'][0].get('liveStreamingDetails', {}).get('activeLiveChatId')
        return video_id, chat_id
    except Exception as e:
        logger.error(f"Ошибка API при поиске: {e}")
        return None, None

async def youtube_bot_loop():
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY, static_discovery=False)
    seen_users = set()
    
    while True:
        try:
            #
            video_id, live_chat_id = await get_live_info(youtube)
            
            if not video_id or not live_chat_id:
                logger.info("Стрим не найден. Спим 5 минут...")
                await asyncio.sleep(300)
                continue

            logger.info(f"Подключено к API чату: {live_chat_id}")
            
            
            initial_req = youtube.liveChatMessages().list(
                liveChatId=live_chat_id, part='snippet'
            ).execute()
            next_page_token = initial_req.get('nextPageToken')

            
            while True:
                try:
                    request = youtube.liveChatMessages().list(
                        liveChatId=live_chat_id,
                        part='snippet,authorDetails',
                        pageToken=next_page_token
                    )
                    response = request.execute()
                    
                    for item in response.get('items', []):
                        author_id = item['authorDetails']['channelId']
                        if author_id not in seen_users:
                            seen_users.add(author_id)
                            # Очистка ника от @ и пробелов
                            raw_name = item['authorDetails'].get('displayName', 'User')
                            user_name = raw_name.lstrip('@').strip()
                            await send_message(f"Новый котэк на Ютубе❤️: {user_name}")

                    next_page_token = response.get('nextPageToken')
                    
                
                    await asyncio.sleep(10)

                except Exception as e:
                    logger.error(f"Ошибка чата (возможно, стрим окончен): {e}")
                    break 

        except Exception as e:
            logger.error(f"Глобальная ошибка: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(youtube_bot_loop())
