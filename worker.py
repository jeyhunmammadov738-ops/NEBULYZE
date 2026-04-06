import os
import time
import json
import redis
import logging
import subprocess
from telegram import Bot
from dotenv import load_dotenv

# Setup
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
TEMP_DIR = "temp_uploads"

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] Worker: %(message)s')
logger = logging.getLogger(__name__)

# Redis Client
r = redis.from_url(REDIS_URL)

# Bot Client
bot = Bot(token=TOKEN)

def convert_to_mp3(input_path: str, output_path: str) -> bool:
    """Fast FFmpeg conversion."""
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vn", "-ab", "192k", "-ar", "44100", "-y", output_path
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except Exception as e:
        logger.error(f"FFmpeg failed: {e}")
        return False

async def process_tasks():
    logger.info("Nebulyze v3 Worker Standing By...")
    while True:
        task = r.rpop("nebula_tasks")
        if not task:
            time.sleep(1)
            continue
            
        data = json.loads(task)
        input_path = data['input_path']
        output_path = input_path.rsplit('.', 1)[0] + ".mp3"
        title = data['title']
        chat_id = data['chat_id']
        message_id = data['message_id']
        
        logger.info(f"Processing: {title}")
        
        try:
            # Step 1: Convert
            if convert_to_mp3(input_path, output_path):
                # Step 2: Send to User
                with open(output_path, 'rb') as audio:
                    await bot.send_audio(
                        chat_id=chat_id,
                        audio=audio,
                        title=title,
                        caption=f"✅ **Nebulyze v3**: {title}"
                    )
                # Step 3: Delete status message
                try: await bot.delete_message(chat_id, message_id)
                except: pass
            else:
                await bot.send_message(chat_id, f"❌ **Nebula Error**: Conversion failed for {title}")
                
        except Exception as e:
            logger.error(f"Task processing error: {e}")
        finally:
            # Cleanup
            for p in [input_path, output_path]:
                if os.path.exists(p): os.remove(p)

if __name__ == "__main__":
    import asyncio
    asyncio.run(process_tasks())
