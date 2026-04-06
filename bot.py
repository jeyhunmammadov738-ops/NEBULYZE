import os
import logging
import asyncio
import uuid
import yt_dlp
from typing import Optional, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from dotenv import load_dotenv
import redis
import json

# Setup
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
TEMP_DIR = "temp_uploads"
os.makedirs(TEMP_DIR, exist_ok=True)

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger(__name__)

# Redis Client
r = redis.from_url(REDIS_URL)

# yt-dlp Client Registry (Fallback cycling)
CLIENT_CONFIGS = [
    {'player_client': ['android', 'ios'], 'player_skip': ['webpage', 'configs']}, # Preferred (Mobile)
    {'player_client': ['tv', 'web'], 'player_skip': ['configs']},                 # Secondary (TV/Web)
]

class NebulaExtractor:
    """Nebulyze v3 Zero-Resistance Extraction Engine"""
    @staticmethod
    async def extract(url: str) -> Tuple[str, str]:
        last_error = None
        for config in CLIENT_CONFIGS:
            file_id = str(uuid.uuid4())
            outtmpl = os.path.join(TEMP_DIR, f"{file_id}.%(ext)s")
            
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'outtmpl': outtmpl,
                'quiet': True,
                'no_warnings': True,
                'nocheckcertificate': True,
                'geo_bypass': True,
                'extractor_args': {'youtube': config},
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
                }
            }
            
            try:
                def _do():
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                        return ydl.prepare_filename(info), info.get('title', 'Unknown')
                
                return await asyncio.to_thread(_do)
            except Exception as e:
                last_error = e
                logger.warning(f"Extraction failed with client {config['player_client']}: {e}")
                continue
        
        raise Exception(f"All extraction clients failed: {str(last_error)}")

# Bot Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✨ **Nebulyze v3: Zero-Resistance Edition**\n"
        "Send me a YouTube link to convert it to MP3 instantly.\n\n"
        "No complex logins, no 'Access Denied'. Just URL -> MP3."
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if not url.startswith("http"): return
    
    status_msg = await update.message.reply_text("🛰️ **Nebula Core**: Extracting media...")
    
    try:
        input_path, title = await NebulaExtractor.extract(url)
        
        # Standardize for mp4
        if not input_path.endswith('.mp4') and os.path.exists(os.path.splitext(input_path)[0] + '.mp4'):
            input_path = os.path.splitext(input_path)[0] + '.mp4'
            
        # Queue for conversion
        task_data = {
            'input_path': input_path,
            'title': title,
            'chat_id': update.effective_chat.id,
            'message_id': status_msg.message_id
        }
        r.lpush("nebula_tasks", json.dumps(task_data))
        
        await status_msg.edit_text(f"🎬 **Found**: {title}\n⚙️ **Status**: Enqueued for conversion...")
        
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        await status_msg.edit_text(f"❌ **Nebula Error**: {str(e)}\n(This IP might be blocked by YouTube).")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
    
    logger.info("Nebulyze v3 Bot Starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
