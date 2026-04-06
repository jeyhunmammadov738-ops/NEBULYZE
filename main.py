import os
import logging
import asyncio
import uuid
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from dotenv import load_dotenv
from app.engine import engine

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TEMP_DIR = "temp_uploads"

# Professional Logging for VPS
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 **Nebulyze v6: The API Bridge**\n\n"
        "Bana bir YouTube linki gonder, videoyu indireyim.\n"
        "Artik 'Sign-in' hatasi yok. Direkt extraction baslatildi.\n\n"
        "Format secin (Video veya Ses)."
    )

def get_options_keyboard(file_path: str):
    keyboard = [
        [
            InlineKeyboardButton("📥 Video (MP4)", callback_data=f"v6|mp4|{file_path}"),
            InlineKeyboardButton("🎵 Ses (MP3)", callback_data=f"v6|mp3|{file_path}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.startswith("http"): return
    
    # Mirroring the status feedback style from your local project
    status_msg = await update.message.reply_text("Indiriliyor ve isleniyor (V6 Bridge)...")
    
    try:
        # Step 1: External API extraction (Bypasses VPS block)
        input_path, title = await engine.extract_via_bridge(url)
        
        file_size_mb = os.path.getsize(input_path) / 1_048_576
        logger.info(f"V6 Bridged Download: {input_path} ({file_size_mb:.1f} MB)")
        
        await status_msg.edit_text(
             f"✅ **Bulundu**: {title}\n"
             f"Boyut: {file_size_mb:.1f} MB\n"
             "Format secin:",
            reply_markup=get_options_keyboard(input_path)
        )
    except Exception as e:
        logger.error(f"v6 Bridge extraction failed: {e}")
        await status_msg.edit_text(f"❌ Indirme basarisiz (V6 Error):\n{str(e)[:300]}")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    _, mode, file_path = query.data.split('|')
    
    if mode == "mp4":
        await query.edit_message_text("📤 Video yukleniyor...")
        try:
            with open(file_path, 'rb') as f:
                await query.message.reply_video(
                    video=f,
                    supports_streaming=True,
                    caption=f"Video indirildi! ({os.path.getsize(file_path)/1_048_576:.1f} MB)"
                )
            await query.edit_message_text("✅ Tamamlandi!")
        except Exception as e:
            await query.edit_message_text(f"❌ Video yukleme hatasi: {str(e)}")
            
    elif mode == "mp3":
        await query.edit_message_text("⚡ Ses donusturuluyor...")
        output_path = f"{file_path}.mp3"
        try:
            # Local conversion via FFmpeg
            final_file = await asyncio.to_thread(engine.convert_to_mp3, file_path, output_path)
            
            with open(final_file, 'rb') as f:
                await query.message.reply_audio(
                    audio=f,
                    title=os.path.basename(file_path),
                    caption=f"Ses indirildi! ({os.path.getsize(final_file)/1_048_576:.1f} MB)"
                )
            await query.edit_message_text("✅ Tamamlandi!")
        except Exception as e:
            await query.edit_message_text(f"❌ Ses donusturme hatasi: {str(e)}")
        finally:
            if os.path.exists(output_path):
                asyncio.create_task(delayed_cleanup(output_path))
    
    # Cleanup of original media file
    asyncio.create_task(delayed_cleanup(file_path))

async def delayed_cleanup(path: str):
    await asyncio.sleep(1800) # 30 min retention
    if os.path.exists(path):
        try: os.remove(path)
        except: pass

def main():
    if not TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN missing")
        return
    
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback, pattern="^v6\|"))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
    
    logger.info("Nebulyze v6 (API Bridge) is ONLINE")
    app.run_polling()

if __name__ == "__main__":
    main()
