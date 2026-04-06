import os
import asyncio
import logging
import yt_dlp
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CommandHandler

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to the YouTube to MP3 Downloader Bot!\n\n"
        "Simply send me a YouTube link, and I'll convert it to a high-quality MP3 file for you. 🎵"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "To use this bot, just paste a YouTube video link. I'll handle the rest!\n\n"
        "Supported platforms: YouTube, YouTube Music, and more (via yt-dlp)."
    )

def download_audio(url):
    """Downloads audio from YouTube and converts it to MP3 using yt-dlp."""
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        # yt-dlp changes the extension to .mp3 after post-processing
        mp3_filename = os.path.splitext(filename)[0] + ".mp3"
        return mp3_filename, info.get('title', 'audio')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if "youtube.com" not in url and "youtu.be" not in url:
        return

    status_message = await update.message.reply_text("📥 Processing your request... Please wait.")
    
    try:
        # Run download in a separate thread to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        mp3_path, title = await loop.run_in_executor(None, download_audio, url)

        await status_message.edit_text("📤 Uploading MP3... almost there!")

        # Send the file
        with open(mp3_path, 'rb') as audio:
            await update.message.reply_audio(
                audio=audio,
                title=title,
                filename=f"{title}.mp3"
            )

        # Cleanup
        if os.path.exists(mp3_path):
            os.remove(mp3_path)
        
        await status_message.delete()

    except Exception as e:
        logger.error(f"Error downloading {url}: {e}")
        await status_message.edit_text(f"❌ Sorry, an error occurred while processing your request: {str(e)}")

if __name__ == '__main__':
    if not os.path.exists('downloads'):
        os.makedirs('downloads')

    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    start_handler = CommandHandler('start', start)
    help_handler = CommandHandler('help', help_command)
    msg_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)

    application.add_handler(start_handler)
    application.add_handler(help_handler)
    application.add_handler(msg_handler)
    
    logger.info("Bot started successfully!")
    application.run_polling()
