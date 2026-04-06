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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to the YouTube to MP3 Downloader Bot!\n\n"
        "Simply send me a YouTube link, and I'll convert it to a high-quality MP3 file for you. 🎵"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "To use this bot, just paste a YouTube video link. I'll handle the rest!\n\n"
        "Supported platforms: YouTube, YouTube Music, and more (via Cobalt API / yt-dlp)."
    )

def download_audio_cobalt(url):
    """Downloads audio from YouTube using Cobalt API and converts it to MP3."""
    api_url = "https://api.cobalt.tools/"
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
    
    response = requests.post(api_url, json=payload, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        if data.get("status") in ["tunnel", "redirect"]:
            download_url = data.get("url")
            # Get the filename from headers or use title if available
            filename_response = requests.get(download_url, stream=True)
            title = data.get("filename", "audio").replace(".mp3", "")
            mp3_path = f"downloads/{title}.mp3"
            
            with open(mp3_path, 'wb') as f:
                for chunk in filename_response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return mp3_path, title
        else:
            raise Exception(f"Cobalt API error: {data.get('text', 'Unknown error')}")
    else:
        raise Exception(f"Cobalt API request failed with status {response.status_code}")

def download_audio_ytdlp(url):
    """Fallback: Downloads audio from YouTube and converts it to MP3 using yt-dlp."""
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
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
                'skip': ['webpage', 'hls', 'dash']
            }
        },
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

    status_message = await update.message.reply_text("📥 Processing your request via Cobalt API...")
    
    try:
        # Try Cobalt first
        loop = asyncio.get_event_loop()
        try:
            mp3_path, title = await loop.run_in_executor(None, download_audio_cobalt, url)
        except Exception as cobalt_e:
            logger.warning(f"Cobalt API failed: {cobalt_e}. Falling back to yt-dlp...")
            await status_message.edit_text("🔄 Cobalt API reached a limit. Falling back to local engine...")
            mp3_path, title = await loop.run_in_executor(None, download_audio_ytdlp, url)

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
