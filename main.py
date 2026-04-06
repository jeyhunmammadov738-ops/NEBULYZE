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

COOKIE_FILE = 'cookies.txt'

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome! I am your resilient YouTube to MP3 Bot.\n\n"
        "If you encounter a 'Sign in to confirm you're not a bot' error, please use /cookies to learn how to authenticate the bot."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Commands:\n"
        "/start - Start the bot\n"
        "/cookies - How to fix 'Sign in' errors using cookies\n\n"
        "Simply send a YouTube link to download its MP3."
    )

async def cookies_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    instructions = (
        "🛡 **How to fix 'Sign in' / Bot Detection errors:**\n\n"
        "1. Install the **'Get cookies.txt LOCALLY'** extension in Chrome or Firefox.\n"
        "2. Log in to YouTube in your browser.\n"
        "3. Open the extension while on YouTube and export as 'Netscape' format.\n"
        "4. Rename the file to `cookies.txt`.\n"
        "5. **Send the file directly to this bot** as an attachment.\n\n"
        "Once uploaded, the bot will use your session to bypass all restrictions!"
    )
    await update.message.reply_text(instructions, parse_mode='Markdown')

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Saves the uploaded cookies.txt file."""
    doc = update.message.document
    if doc.file_name == "cookies.txt":
        new_file = await context.bot.get_file(doc.file_id)
        await new_file.download_to_drive(COOKIE_FILE)
        await update.message.reply_text("✅ `cookies.txt` updated! I will now use your session for downloads.")
    else:
        await update.message.reply_text("⚠️ Please only upload the `cookies.txt` file exported from the extension.")

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
            response = requests.post(instance, json=payload, headers=headers, timeout=20)
            
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
                    msg = data.get('text', 'Unknown Cobalt error')
                    logger.warning(f"Instance {instance} returned non-success: {msg}")
                    last_error = msg
            else:
                logger.warning(f"Instance {instance} failed with status {response.status_code}")
                last_error = f"HTTP {response.status_code}"
        except Exception as e:
            logger.warning(f"Error with instance {instance}: {e}")
            last_error = str(e)
            continue
            
    raise Exception(f"All API methods failed. Final error: {last_error}")

def download_audio_ytdlp(url):
    """Fallback: Downloads audio from YouTube using yt-dlp with cookie support."""
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

    if os.path.exists(COOKIE_FILE):
        logger.info("Using uploaded cookies.txt for yt-dlp...")
        ydl_opts['cookiefile'] = COOKIE_FILE

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
        error_msg = str(e)
        if "Sign in to confirm you're not a bot" in error_msg or "requires an account" in error_msg.lower():
            final_msg = (
                "❌ **YouTube Blocked this Video**\n\n"
                "Google requires a signed-in account to view this specific content.\n\n"
                "🛠 **Permanent Fix**: Use the /cookies command to learn how to securely authenticate this bot."
            )
        else:
            final_msg = f"❌ Sorry, an error occurred while processing your request: {error_msg}"
        
        await status_message.edit_text(final_msg, parse_mode='Markdown')

if __name__ == '__main__':
    if not os.path.exists('downloads'):
        os.makedirs('downloads')

    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('cookies', cookies_command))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    logger.info("Bot started successfully (Definitive Build v2)!")
    application.run_polling()
