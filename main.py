import os
import asyncio
import logging
import yt_dlp
import requests
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

# List of high-uptime Cobalt API instances for rotation
COBALT_INSTANCES = [
    "https://api.cobalt.tools/",
    "https://capi.3kh0.net/",
    "https://cobalt-api.meowing.de/",
    "https://cobalt-backend.canine.tools/",
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome back! Your YouTube to MP3 Bot is ready for another round.\n\n"
        "Simply send me a link, and I'll use my high-resiliency API rotation to convert it for you. 🎵"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "This bot is now using a multi-API rotation system for maximum reliability.\n\n"
        "If one method is blocked, it automatically switches to another until your download succeeds."
    )

def download_audio_cobalt(url):
    """Downloads audio from YouTube using Cobalt API rotation."""
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    payload = {
        "url": url,
        "downloadMode": "audio",
        "audioFormat": "mp3",
        "audioBitrate": "320"
    }

    last_error = None
    for instance in COBALT_INSTANCES:
        try:
            logger.info(f"Attempting download via {instance}...")
            response = requests.post(instance, json=payload, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") in ["tunnel", "redirect"]:
                    download_url = data.get("url")
                    title = data.get("filename", "audio").replace(".mp3", "")
                    mp3_path = f"downloads/{title}.mp3"
                    
                    # Download the actual file from the Cobalt URL
                    file_response = requests.get(download_url, stream=True, timeout=30)
                    with open(mp3_path, 'wb') as f:
                        for chunk in file_response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    
                    logger.info(f"Successfully downloaded via {instance}")
                    return mp3_path, title
                else:
                    logger.warning(f"Instance {instance} returned non-success: {data}")
            else:
                logger.warning(f"Instance {instance} failed with status {response.status_code}")
        except Exception as e:
            logger.warning(f"Error with instance {instance}: {e}")
            last_error = e
            continue
            
    raise Exception(f"All Cobalt instances failed. Last error: {last_error}")

def download_audio_ytdlp(url):
    """Fallback: Downloads audio from YouTube using yt-dlp."""
    cookie_file = 'cookies.txt'
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
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }

    if os.path.exists(cookie_file):
        ydl_opts['cookiefile'] = cookie_file

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        mp3_filename = os.path.splitext(filename)[0] + ".mp3"
        return mp3_filename, info.get('title', 'audio')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if "http" not in url:
        return

    status_message = await update.message.reply_text("📥 Processing your request using API rotation...")
    
    try:
        loop = asyncio.get_event_loop()
        try:
            # Try Cobalt rotation first
            mp3_path, title = await loop.run_in_executor(None, download_audio_cobalt, url)
        except Exception as cobalt_e:
            logger.warning(f"All Cobalt instances failed: {cobalt_e}. Falling back to yt-dlp...")
            await status_message.edit_text("🔄 High-load detected. Switching to local processing engine...")
            mp3_path, title = await loop.run_in_executor(None, download_audio_ytdlp, url)

        await status_message.edit_text("📤 Uploading MP3... thank you for your patience!")

        with open(mp3_path, 'rb') as audio:
            await update.message.reply_audio(
                audio=audio,
                title=title,
                filename=f"{title}.mp3"
            )

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
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    logger.info("Bot started successfully (Definitive Build)!")
    application.run_polling()
