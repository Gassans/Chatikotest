import os
import asyncio
import logging
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
        logger.error(f"Ошибка ТГ: {e}")

async def get_live_info(youtube):
    try:
        search = youtube.search().list(
            part='id', channelId=YOUTUBE_CHANNEL_ID, eventType='live', type='video'
        ).execute()
        if not search.get('items'): return None, None
        video_id = search['items'][0]['id']['videoId']
        
        video_details = youtube.videos().list(part='liveStreamingDetails', id=video_id).execute()
        if not video_details.get('items'): return video_id, None
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
            video_id, live_chat_id = await get_live_info(youtube)
            if not video_id or not live_chat_id:
                await asyncio.sleep(300)
                continue

            logger.info(f"Подключено к чату: {live_chat_id}")
            
            # --- ИСПРАВЛЕНИЕ: Пропускаем историю сообщений ---
            # Делаем один холостой запрос, чтобы получить актуальный токен будущего
            first_response = youtube.liveChatMessages().list(
                liveChatId=live_chat_id,
                part='snippet'
            ).execute()
            next_page_token = first_response.get('nextPageToken')
            logger.info("История чата пропущена, ждем новых сообщений...")
            # ------------------------------------------------

            while True:
                try:
                    request = youtube.liveChatMessages().list(
                        liveChatId=live_chat_id,
                        part='snippet,authorDetails',
                        pageToken=next_page_token
                    )
                    response = request.execute()
                    
                    # Обрабатываем сообщения (теперь здесь будут только новые)
                    for item in response.get('items', []):
                        author_id = item['authorDetails']['channelId']
                        if author_id not in seen_users:
                            seen_users.add(author_id)
                            user_name = item['authorDetails'].get('displayName', 'User').lstrip('@').strip()
                            await send_message(f"Новый котэк на Ютубе❤️: {user_name}")

                    next_page_token = response.get('nextPageToken')
                    
                    polling = response.get('pollingIntervalMillis', 10000) / 1000
                    await asyncio.sleep(max(polling, 15.0)) 

                except Exception as e:
                    if "rateLimitExceeded" in str(e):
                        logger.warning("YouTube просит снизить скорость. Ждем 30 секунд...")
                        await asyncio.sleep(30)
                        continue 
                    
                    logger.error(f"Ошибка чата: {e}")
                    break 

        except Exception as e:
            logger.error(f"Глобальная ошибка: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(youtube_bot_loop())
