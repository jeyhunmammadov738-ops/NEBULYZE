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

# Absolute paths for VPS deployment
BASE_DIR = os.path.expanduser("~/nebulize-bot")
COOKIE_FILE = os.path.join(BASE_DIR, "cookies.txt")
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome! Your hardened YouTube to MP3 Bot is ready.\n\n"
        "I am now using your personal cookies and iOS client spoofing for maximum reliability. Send me a link!"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "This bot is hardened with iOS client spoofing and your personal session.\n\n"
        "If you encounter issues, try refreshing your cookies at google.com/device."
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if doc.file_name == "cookies.txt":
        new_file = await context.bot.get_file(doc.file_id)
        await new_file.download_to_drive(COOKIE_FILE)
        await update.message.reply_text("✅ `cookies.txt` updated! Hardened session active.")
    else:
        await update.message.reply_text("⚠️ Please upload a Netscape-formatted `cookies.txt`.")

def download_audio_ytdlp(url):
    """Downloads audio from YouTube using hardened yt-dlp config."""
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '320',
        }],
        'outtmpl': os.path.join(DOWNLOADS_DIR, '%(title)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'noprogress': True,
        'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
        # Hardened extractor args for iOS client spoofing
        'extractor_args': {
            'youtube': {
                'player_client': ['ios'],
                'skip': ['webpage', 'player_response'],
            }
        }
    }

    if os.path.exists(COOKIE_FILE):
        logger.info(f"Using absolute cookie path: {COOKIE_FILE}")
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

    status_message = await update.message.reply_text("📥 Processing your request using hardened yt-dlp...")
    
    try:
        loop = asyncio.get_event_loop()
        mp3_path, title = await loop.run_in_executor(None, download_audio_ytdlp, url)

        await status_message.edit_text("📤 Uploading high-quality MP3...")

        with open(mp3_path, 'rb') as audio:
            await update.message.reply_audio(
                audio=audio,
                title=title,
                performer="Nebulyze Bot",
                filename=f"{title}.mp3"
            )

        if os.path.exists(mp3_path):
            os.remove(mp3_path)
        
        await status_message.delete()

    except Exception as e:
        logger.error(f"yt-dlp hardened error for {url}: {e}")
        error_msg = str(e)
        if "Sign in" in error_msg or "account" in error_msg.lower():
            final_msg = "❌ **Hardened block detected.** Even with iOS spoofing, Google required a sign-in. Please visit [google.com/device](https://google.com/device) in your browser first to clear any security checks."
        else:
            final_msg = f"❌ Error: {error_msg}"
        
        await status_message.edit_text(final_msg, parse_mode='Markdown')

if __name__ == '__main__':
    if not os.path.exists(DOWNLOADS_DIR):
        os.makedirs(DOWNLOADS_DIR)

    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    logger.info("Bot started successfully (Hardened Exclusive Build)!")
    application.run_polling()
