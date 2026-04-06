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
from app.core.downloader import downloader
from celery.result import AsyncResult

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger(__name__)

import uuid

TEMP_UPLOAD_DIR = "temp_uploads"
os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)

async def is_admin(update: Update):
    """Check if the user is an authorized admin."""
    user_id = update.effective_user.id
    if user_id in ADMIN_IDS:
        return True
    logger.warning(f"Unauthorized access attempt by user_id: {user_id}")
    await update.message.reply_text("⛔ **Access Denied**: Unauthorized Nebula terminal access.")
    return False

def get_bitrate_keyboard(media_type: str, file_path: str):
    """Generate inline keyboard for bitrate selection."""
    keyboard = [
        [
            InlineKeyboardButton("128k (Fast)", callback_data=f"conv|128k|{media_type}|{file_path}"),
            InlineKeyboardButton("192k (Standard)", callback_data=f"conv|192k|{media_type}|{file_path}"),
            InlineKeyboardButton("320k (Pro)", callback_data=f"conv|320k|{media_type}|{file_path}")
        ],
        [InlineKeyboardButton("🎤 Convert to Voice (OGG)", callback_data=f"conv|voice|{media_type}|{file_path}")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 **Nebulyze v2: Elite Production Bot**\n\n"
        "Send me a video or a URL (YouTube, TikTok, etc.) to begin conversion.\n"
        "Use `/auth` if you encounter a 'Sign in' error."
    )

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    video = message.video or message.document
    if not video: return
    
    file_id = str(uuid.uuid4())
    ext = video.file_name.split('.')[-1] if hasattr(video, 'file_name') else "mp4"
    input_path = os.path.join(TEMP_UPLOAD_DIR, f"{file_id}.{ext}")
    
    status_msg = await message.reply_text("📥 Downloading media to Nebula cluster...")
    
    try:
        new_file = await context.bot.get_file(video.file_id)
        await new_file.download_to_drive(input_path)
        
        await status_msg.edit_text(
            "✅ Downloaded!\nSelect desired output quality:",
            reply_markup=get_bitrate_keyboard("file", input_path)
        )
    except Exception as e:
        logger.error(f"Download failed: {e}")
        await status_msg.edit_text(f"❌ Nebula download failed: {str(e)}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if not url.startswith("http"):
        return
    
    message = update.message
    status_msg = await message.reply_text("🔗 Extracting URL via Nebula Core v2...")
    
    try:
        # Use new v2 resilient downloader
        input_path, title = await downloader.download(url)
            
        context.user_data[input_path] = title
        
        await status_msg.edit_text(
            f"🎬 **Found**: {title}\nSelect desired output quality:",
            reply_markup=get_bitrate_keyboard("url", input_path)
        )
                
    except Exception as e:
        logger.error(f"URL Extraction failed: {e}")
        error_text = str(e)
        if "device code" in error_text.lower() or "google.com/device" in error_text.lower():
            await status_msg.edit_text(f"🔑 **Auth Required**: {error_text}\n\nUse `/auth` for a manual link.")
        else:
            await status_msg.edit_text(f"❌ Nebula Core failed: {error_text}")

async def auth_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Trigger manual OAuth2 device flow."""
    if not await is_admin(update): return
    
    status_msg = await update.message.reply_text("📡 Requesting Nebula Auth Token...")
    
    # Run a dummy extraction to trigger the OAuth2 flow
    dummy_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    try:
        # We use a short timeout to let the log printer show the code
        await downloader.download(dummy_url)
        await status_msg.edit_text("✅ Nebula core is already authorized.")
    except Exception as e:
        # The exception may contain the code, or it might be in stdout
        logger.info(f"Auth info: {e}")
        await status_msg.edit_text(
            f"🔐 **Nebula Authorization Flow**\n\n"
            f"Check the bot server logs for the device code or try sending a video to see the prompt.\n"
            f"Visit: https://google.com/device"
        )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Format: conv|bitrate|type|path
    data = query.data.split('|')
    if len(data) < 4: return
    
    bitrate = data[1]
    media_type = data[2]
    input_path = data[3]
    
    fmt = "mp3" if bitrate != "voice" else "ogg"
    output_path = input_path.rsplit('.', 1)[0] + f"_final.{fmt}"
    
    await query.edit_message_text(f"🔄 Enqueuing {bitrate} conversion task...")
    
    # Enqueue task
    task = convert_media_task.delay(input_path, output_path, bitrate, fmt)
    
    # Safe non-blocking polling
    max_retries = 150 # ~5 mins
    for _ in range(max_retries):
        res = AsyncResult(task.id)
        if res.state == "SUCCESS":
            title = context.user_data.get(input_path, "Converted by Nebulyze")
            try:
                if bitrate == "voice":
                    await query.message.reply_voice(voice=open(output_path, 'rb'), caption=title)
                else:
                    await query.message.reply_audio(audio=open(output_path, 'rb'), title=title)
                await query.delete_message()
            except Exception as e:
                await query.message.reply_text(f"❌ Error sending file: {str(e)}")
            
            # Final cleanup
            if os.path.exists(output_path):
                os.remove(output_path)
            return
            
        elif res.state == "FAILURE":
            await query.edit_message_text("❌ Nebula process failed during conversion.")
            return
            
        await asyncio.sleep(2)
    
    await query.edit_message_text("⌛ Task timed out. Please try again later.")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update): return
    
    # Count files in temp_uploads
    files = os.listdir(TEMP_UPLOAD_DIR)
    total_size = sum(os.path.getsize(os.path.join(TEMP_UPLOAD_DIR, f)) for f in files) / (1024*1024)
    
    await update.message.reply_text(
        f"📊 **Nebulyze System Stats**\n\n"
        f"Cluster Status: ONLINE 🟢\n"
        f"Temp Files: {len(files)}\n"
        f"Disk Usage: {total_size:.2f} MB\n"
        f"Admin Count: {len(ADMIN_IDS)}"
    )

if __name__ == '__main__':
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN missing!")
        exit(1)

    app = ApplicationBuilder().token(TOKEN).read_timeout(60).write_timeout(60).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("auth", auth_command))
    app.add_handler(CallbackQueryHandler(handle_callback, pattern="^conv\|"))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.ALL, handle_media))
    
    logger.info("Nebulyze Bot starting...")
    app.run_polling()

