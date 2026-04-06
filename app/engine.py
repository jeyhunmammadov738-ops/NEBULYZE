import os
import logging
import asyncio
import yt_dlp
import uuid
import subprocess
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)

class NebulaV3Engine:
    """
    Nebulyze v3: Zero-Resistance Hybrid Engine
    Combines local yt-dlp power with resilient client cycling.
    """
    
    TEMP_DIR = "temp_uploads"
    
    CLIENTS = [
        {'player_client': ['android', 'ios'], 'player_skip': ['webpage', 'configs']}, # Resilient Mobile
        {'player_client': ['tv', 'web'], 'player_skip': ['configs']},                 # Traditional
        {'player_client': ['mweb', 'android_embedded']},                               # Deep Fallback
    ]

    def __init__(self):
        os.makedirs(self.TEMP_DIR, exist_ok=True)

    def get_ydl_opts(self, client_config: Optional[Dict] = None) -> Dict[str, Any]:
        file_id = str(uuid.uuid4())
        opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': os.path.join(self.TEMP_DIR, f"{file_id}.%(ext)s"),
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'geo_bypass': True,
            # Production-grade headers
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://www.google.com/'
            },
            # Built-in OAuth2 support for v3
            'username': 'oauth2'
        }
        
        if client_config:
            opts['extractor_args'] = {'youtube': client_config}
            
        return opts

    async def download(self, url: str) -> Tuple[str, str]:
        """Download URL with automatic client cycling."""
        last_error = None
        
        for client in self.CLIENTS:
            try:
                opts = self.get_ydl_opts(client)
                logger.info(f"V3 Attempting extraction with client: {client.get('player_client')}")
                
                def _sync_download():
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                        return ydl.prepare_filename(info), info.get('title', 'Nebula Media')

                input_path, title = await asyncio.to_thread(_sync_download)
                
                # Check for standard extension mapping
                if not input_path.endswith('.mp4') and os.path.exists(os.path.splitext(input_path)[0] + '.mp4'):
                    input_path = os.path.splitext(input_path)[0] + '.mp4'
                
                return input_path, title
            except Exception as e:
                last_error = e
                logger.warning(f"Client {client.get('player_client')} failed: {str(e)}")
                continue

        raise Exception(f"All V3 extraction paths failed: {str(last_error)}")

    def convert_to_mp3(self, input_path: str, output_path: str, bitrate: str = "192k") -> str:
        """Standard MP3 conversion via direct FFmpeg for VPS efficiency."""
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vn", "-ar", "44100", "-ac", "2",
            "-b:a", bitrate, output_path
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return output_path
        except Exception as e:
            logger.error(f"FFmpeg conversion failed: {e}")
            raise

engine = NebulaV3Engine()
