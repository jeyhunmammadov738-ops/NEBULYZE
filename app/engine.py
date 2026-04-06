import os
import logging
import asyncio
import yt_dlp
import uuid
import subprocess
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)

class NebulaV5Stealth:
    """
    Nebulyze v5: Stealth Core (PO-Token & Mobile Client Logic)
    Bypasses "Sign in to confirm you're not a bot" on Oracle VPS.
    """
    
    TEMP_DIR = "temp_uploads"
    MAX_FILESIZE = 49 * 1024 * 1024 # 49 MB for Telegram
    
    # Mirror-Hybrid Format (yt-bot proven)
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

    def get_ydl_opts(self, player_client: str = "ios,android") -> Dict[str, Any]:
        file_id = str(uuid.uuid4())
        return {
            "format": self.YDL_FORMAT,
            "merge_output_format": "mp4",
            "outtmpl": os.path.join(self.TEMP_DIR, f"{file_id}.%(ext)s"),
            "max_filesize": self.MAX_FILESIZE,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "nocheckcertificate": True,
            # Stealth Extractor Args for 2026 Bypass
            'extractor_args': {
                'youtube': {
                    'player_client': player_client.split(','),
                    # Use the Deno po-token generator natively if available
                    'po_token': ['web+web_music:auto', 'ios:auto', 'android:auto'],
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
            }
        }

    async def extract_video(self, url: str) -> Tuple[str, str]:
        """Attempt extraction with Stealth PO-Token generation."""
        # Cycle through clients: Mobile -> TV -> Web (Stealth)
        clients = ["ios,android", "tv,web", "mweb"]
        last_error = None

        for client in clients:
            try:
                opts = self.get_ydl_opts(client)
                logger.info(f"V5 Attempting extraction (Client: {client})...")
                
                def _sync_extract():
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                        path = ydl.prepare_filename(info)
                        
                        if not os.path.exists(path):
                            base = os.path.splitext(path)[0]
                            for ext in (".mp4", ".mkv", ".webm"):
                                if os.path.exists(base + ext):
                                    path = base + ext
                                    break
                                    
                        return path, info.get('title', 'Nebula Media')

                return await asyncio.to_thread(_sync_extract)
            except Exception as e:
                last_error = e
                logger.warning(f"V5 Client {client} failed: {e}")
                continue

        raise Exception(f"All V5 stealth paths failed: {str(last_error)}")

    def convert_to_mp3(self, input_path: str, output_path: str) -> str:
        """Strip audio from the stealth-acquired media."""
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vn", "-ar", "44100", "-ac", "2", "-b:a", "192k",
            output_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return output_path

engine = NebulaV5Stealth()
