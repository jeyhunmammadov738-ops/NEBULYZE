# 🚀 Elite MP4 to MP3 Production Bot v2.0 (Zero-Leak)

A high-performance, asynchronous Telegram bot built for large-scale video-to-audio conversion with enterprise-grade stability.

## ✨ Production Features
- **🛡️ Zero-Error Tolerance**: Tiered exception handling and self-healing temporary file cleanup.
- **⚡ Adaptive Engine**: Refactored logic using `asyncio.to_thread` for non-blocking CPU-bound tasks.
- **📉 Dynamic Quality Scaling**: Automatically adjusts output bitrate to match source fidelity (avoids bloated files).
- **🎤 Audio-to-Voice**: Seamlessly convert any video or link to a native Telegram Voice Message (OGG/Opus).
- **🔗 Intelligent URL Handling**: Supports YouTube, Instagram, and TikTok links with metadata extraction (Artist/Title).
- **📊 Admin Control Center**: Real-time statistics, log extraction, and global broadcasting via `/admin`.
- **💾 Persistent Analytics**: Atomic database operations via `aiosqlite`.

## 🛠️ Rapid Setup

### 1. Environment Configuration
Create a `.env` file in the root directory:
```env
TELEGRAM_BOT_TOKEN=your_token_here
ADMIN_IDS=12345678,98765432
```

### 2. Local Deployment
```bash
pip install -r requirements.txt
python main.py
```

### 3. Docker Deployment (Recommended)
```bash
docker-compose up --build -d
```

## 🎮 How to Use
1. **Upload**: Send any MP4 or Video file.
2. **Configure**: Use the inline buttons to select bitrate (128k-320k) and format (MP3/Voice).
3. **Customize**: 
   - Reply with `00:00 - 00:30` to trim the clip.
   - Send text after uploading to override the metadata title.
4. **URL**: Send a link directly for instant processing.

## 🛡️ Production Security
- **Memory Integrity**: Explicit resource disposal for `moviepy` and `PIL` objects.
- **Concurrent Safety**: Global executor limits CPU spikes while maintaining responsiveness.
- **Sandboxed Execution**: Multi-stage Docker build for minimal attack surface.
