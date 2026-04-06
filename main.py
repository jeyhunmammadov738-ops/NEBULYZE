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
        "👋 Welcome! I am your streamlined yt-dlp YouTube to MP3 Bot.\n\n"
        "I am now using your personal cookies for 100% reliable downloads. Simply send me a link!"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "This bot uses the latest yt-dlp engine with cookie authentication.\n\n"
        "If you need to update your session, use /cookies for instructions."
    )

async def cookies_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    instructions = (
        "🛡 **How to update your session:**\n\n"
        "1. Install 'Get cookies.txt LOCALLY' extension.\n"
        "2. Export Netscape cookies from YouTube.com.\n"
        "3. Send the `cookies.txt` file to this bot."
    )
    await update.message.reply_text(instructions, parse_mode='Markdown')

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if doc.file_name == "cookies.txt":
        new_file = await context.bot.get_file(doc.file_id)
        await new_file.download_to_drive(COOKIE_FILE)
        await update.message.reply_text("✅ `cookies.txt` updated! Authenticated session is active.")
    else:
        await update.message.reply_text("⚠️ Please upload a Netscape-formatted `cookies.txt`.")

def download_audio_ytdlp(url):
    """Downloads audio from YouTube using yt-dlp with absolute cookie paths."""
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '320', # High quality 320kbps
        }],
        'outtmpl': os.path.join(DOWNLOADS_DIR, '%(title)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'noprogress': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
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

    status_message = await update.message.reply_text("📥 Processing your request using yt-dlp...")
    
    try:
        loop = asyncio.get_event_loop()
        # Direct yt-dlp execution (no more Cobalt rotation)
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
        logger.error(f"yt-dlp error for {url}: {e}")
        error_msg = str(e)
        if "Sign in" in error_msg or "account" in error_msg.lower():
            final_msg = "❌ **YouTube required a sign-in** (even with cookies). Please re-export your `cookies.txt` and send it to me again."
        else:
            final_msg = f"❌ Error: {error_msg}"
        
        await status_message.edit_text(final_msg, parse_mode='Markdown')

if __name__ == '__main__':
    if not os.path.exists(DOWNLOADS_DIR):
        os.makedirs(DOWNLOADS_DIR)

    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('cookies', cookies_command))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    logger.info("Bot started successfully (Exclusive yt-dlp Build)!")
    application.run_polling()
