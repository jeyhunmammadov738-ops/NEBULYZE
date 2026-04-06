import os
import logging
import asyncio
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
    CommandHandler,
    CallbackQueryHandler
)
from dotenv import load_dotenv

# Use shared components from app
from app.tasks.worker import convert_media_task
from celery.result import AsyncResult

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger(__name__)

import yt_dlp
import uuid

TEMP_UPLOAD_DIR = "temp_uploads"
os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 **Nebulyze: Elite Production Bot**\n\n"
        "Send me a video or a URL (YouTube, TikTok, etc.) to begin conversion.\n"
        "Your request will be processed by our Nebula-grade worker cluster."
    )

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    video = message.video or message.document
    if not video: return
    
    file_id = str(uuid.uuid4())
    ext = video.file_name.split('.')[-1] if hasattr(video, 'file_name') else "mp4"
    input_path = os.path.join(TEMP_UPLOAD_DIR, f"{file_id}.{ext}")
    output_path = os.path.join(TEMP_UPLOAD_DIR, f"{file_id}_final.mp3")
    
    status_msg = await message.reply_text("📥 Downloading media to Nebula cluster...")
    
    new_file = await context.bot.get_file(video.file_id)
    await new_file.download_to_drive(input_path)
    
    await status_msg.edit_text("🔄 Enqueuing for studio-grade conversion...")
    
    # Enqueue task
    task = convert_media_task.delay(input_path, output_path, "192k", "mp3")
    
    await status_msg.edit_text(
        f"✅ Task Enqueued!\n"
        f"Task ID: `{task.id}`\n\n"
        "I will send you the finished file shortly."
    )
    
    # Simple polling for completion (in production, use a callback/webhook)
    while True:
        res = AsyncResult(task.id)
        if res.state == "SUCCESS":
            await message.reply_audio(audio=open(output_path, 'rb'), title="Converted by Nebulyze")
            break
        elif res.state == "FAILURE":
            await message.reply_text("❌ Conversion failed during processing.")
            break
        await asyncio.sleep(2)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if not url.startswith("http"):
        return
    
    message = update.message
    status_msg = await message.reply_text("🔗 Extracting URL via Nebula Core...")
    
    file_id = str(uuid.uuid4())
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': os.path.join(TEMP_UPLOAD_DIR, f"{file_id}.%(ext)s"),
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'geo_bypass': True,
        'postprocessors': [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}],
        # Bypassing YouTube "Sign in to confirm you're not a bot"
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios'],
                'player_skip': ['configs', 'webpage']
            }
        }
    }
    
    # Use cookies if provided via cookies.txt in root
    cookies_path = os.path.join(os.getcwd(), "cookies.txt")
    if os.path.exists(cookies_path):
        ydl_opts['cookiefile'] = cookies_path
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            input_path = ydl.prepare_filename(info)
            if not input_path.endswith('.mp4'):
                input_path = os.path.splitext(input_path)[0] + '.mp4'
            
            output_path = os.path.join(TEMP_UPLOAD_DIR, f"{file_id}_final.mp3")
            
            await status_msg.edit_text("🔄 Enqueuing for studio-grade conversion...")
            task = convert_media_task.delay(input_path, output_path, "192k", "mp3")
            
            # Simple polling for completion
            while True:
                res = AsyncResult(task.id)
                if res.state == "SUCCESS":
                    await message.reply_audio(audio=open(output_path, 'rb'), title=info.get('title'))
                    break
                elif res.state == "FAILURE":
                    await status_msg.edit_text("❌ URL conversion failed.")
                    break
                await asyncio.sleep(2)
                
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {str(e)}")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 **Nebulyze System Stats**\n\nCluster Status: ONLINE 🟢")

if __name__ == '__main__':
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN missing!")
        exit(1)

    app = ApplicationBuilder().token(TOKEN).read_timeout(30).write_timeout(30).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.ALL, handle_media))
    
    logger.info("Nebulyze Bot starting...")
    app.run_polling()
