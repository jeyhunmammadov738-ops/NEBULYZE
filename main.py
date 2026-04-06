import os
import logging
import asyncio
import uuid
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from dotenv import load_dotenv
from app.engine import engine

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TEMP_DIR = "temp_uploads"

# Professional Logging for VPS
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 **Nebulyze v3: Zero-Resistance Edition**\n\n"
        "Send me any URL (YouTube, TikTok, etc.) or Video/Audio file.\n"
        "No complex logins. No Access Denied. Just select your quality."
    )

async def auth_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """v3 Interactive OAuth2 flow."""
    status_msg = await update.message.reply_text("📡 Initializing Nebula Terminal v3...")
    dummy_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    try:
        await engine.download(dummy_url)
        await status_msg.edit_text("✅ Nebula Core is already authorized.")
    except Exception as e:
        error_text = str(e)
        logger.warning(f"Auth Prompt: {error_text}")
        await status_msg.edit_text(
            f"🔐 **Nebula v3 Activation Required**\n\n"
            f"YouTube says: `{error_text}`\n\n"
            "If you see a 'Device Code' above, enter it at:\n"
            "👉 [google.com/device](https://google.com/device)"
        )

def get_bitrate_keyboard(media_type: str, file_path: str):
    keyboard = [
        [
            InlineKeyboardButton("128k", callback_data=f"v3|128k|{media_type}|{file_path}"),
            InlineKeyboardButton("192k", callback_data=f"v3|192k|{media_type}|{file_path}"),
            InlineKeyboardButton("320k", callback_data=f"v3|320k|{media_type}|{file_path}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if not url.startswith("http"): return
    
    status_msg = await update.message.reply_text("🔗 Extracting URL via Nebula v3 Engine...")
    try:
        input_path, title = await engine.download(url)
        await status_msg.edit_text(
            f"🎬 **Found**: {title}\nSelect output quality:",
            reply_markup=get_bitrate_keyboard("url", input_path)
        )
    except Exception as e:
        logger.error(f"v3 Extraction failed: {e}")
        error_msg = str(e)
        if "device code" in error_msg.lower():
            await status_msg.edit_text(f"🔑 **Auth Required**: {error_msg}\n\nUse `/auth` to get a clickable link.")
        else:
            await status_msg.edit_text(f"❌ Nebula v3 Failed: {error_msg}")

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    video = message.video or message.document or message.audio
    if not video: return
    
    file_id = str(uuid.uuid4())
    ext = video.file_name.split('.')[-1] if hasattr(video, 'file_name') else "mp4"
    input_path = os.path.join(TEMP_DIR, f"{file_id}.{ext}")
    
    status_msg = await message.reply_text("📥 Downloading media to Nebula cluster...")
    try:
        new_file = await context.bot.get_file(video.file_id)
        await new_file.download_to_drive(input_path)
        await status_msg.edit_text(
            "✅ File Received!\nSelect output quality:",
            reply_markup=get_bitrate_keyboard("file", input_path)
        )
    except Exception as e:
        logger.error(f"Local download failed: {e}")
        await status_msg.edit_text(f"❌ Nebula download failed: {str(e)}")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    _, bitrate, media_type, input_path = query.data.split('|')
    await query.edit_message_text(f"⚡ **Converting to {bitrate} MP3**...")
    
    output_path = f"{input_path}_final.mp3"
    try:
        # Direct conversion in main thread (fine for low volume)
        final_file = await asyncio.to_thread(engine.convert_to_mp3, input_path, output_path, bitrate)
        
        await query.message.reply_audio(
            audio=open(final_file, 'rb'),
            title=os.path.basename(input_path)
        )
        await query.edit_message_text("✅ Processing Complete!")
    except Exception as e:
        logger.error(f"v3 Conversion error: {e}")
        await query.edit_message_text(f"❌ Conversion failed: {str(e)}")
    finally:
        # Async cleanup task (non-blocking)
        asyncio.create_task(cleanup_files(input_path, output_path))

async def cleanup_files(*files):
    """Delayed cleanup for OCI optimization."""
    await asyncio.sleep(1800) # 30 minute retention
    for f in files:
        if os.path.exists(f):
            try: os.remove(f)
            except: pass

def main():
    if not TOKEN:
        print("❌ Error: TELEGRAM_BOT_TOKEN not found in .env")
        return

    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("auth", auth_command))
    app.add_handler(CallbackQueryHandler(handle_callback, pattern="^v3\|"))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.ALL | filters.AUDIO, handle_media))
    
    logger.info("Nebulyze v3 cluster is ONLINE")
    app.run_polling()

if __name__ == "__main__":
    main()
