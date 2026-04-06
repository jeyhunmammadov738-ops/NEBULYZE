import os
import logging
import asyncio
import yt_dlp
import uuid
import subprocess
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)

class NebulaV4Mirror:
    """
    Nebulyze v4: Mirror Engine (Based on yt-bot)
    Prioritizes MP4 extraction to bypass audio-specific blocks.
    """
    
    TEMP_DIR = "temp_uploads"
    MAX_FILESIZE = 49 * 1024 * 1024 # 49 MB for Telegram
    
    # Exact format string from yt-bot
    YDL_FORMAT = (
        "bestvideo[ext=mp4][vcodec^=avc1][filesize<?49M]+"
        "bestaudio[ext=m4a][filesize<?49M]/"
        "bestvideo[ext=mp4][filesize<?49M]+bestaudio[filesize<?49M]/"
        "best[ext=mp4][filesize<?49M]/"
        "best[filesize<?49M]/"
        "best"
    )

    def __init__(self):
        os.makedirs(self.TEMP_DIR, exist_ok=True)

    def get_ydl_opts(self) -> Dict[str, Any]:
        file_id = str(uuid.uuid4())
        return {
            "format": self.YDL_FORMAT,
            "merge_output_format": "mp4",
            "outtmpl": os.path.join(self.TEMP_DIR, f"{file_id}.%(ext)s"),
            "max_filesize": self.MAX_FILESIZE,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            # Stealth headers
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            }
        }

    async def extract_video(self, url: str) -> Tuple[str, str]:
        """Mirror the yt-bot download_video method."""
        opts = self.get_ydl_opts()
        
        def _sync_extract():
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                path = ydl.prepare_filename(info)
                
                # Check for standard extension mapping if yt-dlp name is generic
                if not os.path.exists(path):
                    base = os.path.splitext(path)[0]
                    for ext in (".mp4", ".mkv", ".webm"):
                        if os.path.exists(base + ext):
                            path = base + ext
                            break
                            
                return path, info.get('title', 'Nebula Media')

        return await asyncio.to_thread(_sync_extract)

    def convert_to_mp3(self, input_path: str, output_path: str) -> str:
        """Strip audio from the mirrored MP4."""
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vn", "-ar", "44100", "-ac", "2", "-b:a", "192k",
            output_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return output_path

engine = NebulaV4Mirror()
