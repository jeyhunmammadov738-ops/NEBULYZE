import os
import logging
import asyncio
import yt_dlp
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)

class MediaDownloader:
    """
    Nebulyze v2 Resilient Media Downloader
    Handles YouTube bot detection via OAuth2, Deno-based signing, and Client Fallbacks.
    """
    
    DEFAULT_YDL_OPTS = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'geo_bypass': True,
        # Enhanced bypass headers
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.google.com/'
        }
    }

    CLIENT_REGISTRY = [
        {'player_client': ['android', 'ios'], 'player_skip': ['webpage', 'configs']}, # Preferred (Mobile)
        {'player_client': ['tv', 'web'], 'player_skip': ['configs']},                 # Secondary (TV/Web)
        {'player_client': ['mweb', 'android_embedded']},                               # Fallback
    ]

    def __init__(self, download_dir: str = "temp_uploads", use_oauth2: bool = True):
        self.download_dir = download_dir
        self.use_oauth2 = use_oauth2
        os.makedirs(self.download_dir, exist_ok=True)

    def _get_opts(self, client_config: Optional[Dict] = None) -> Dict[str, Any]:
        opts = self.DEFAULT_YDL_OPTS.copy()
        
        # Apply client configuration if provided
        if client_config:
            opts['extractor_args'] = {'youtube': client_config}
        
        # Enable OAuth2 if requested
        if self.use_oauth2:
            opts['username'] = 'oauth2'
            # Note: Token will be cached in /root/.cache/yt-dlp (mapped via Docker volume)
        
        return opts

    async def download(self, url: str) -> Tuple[str, str]:
        """
        Download media with automatic client cycling on failure.
        Returns: (file_path, title)
        """
        last_error = None
        
        # Cycle through clients in the registry
        for config in self.CLIENT_REGISTRY:
            try:
                opts = self._get_opts(config)
                # Ensure unique filename
                import uuid
                file_id = str(uuid.uuid4())
                opts['outtmpl'] = os.path.join(self.download_dir, f"{file_id}.%(ext)s")
                
                logger.info(f"Attempting extraction with client: {config.get('player_client')}")
                
                def _do_download():
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                        return ydl.prepare_filename(info), info.get('title', 'Unknown Title')

                input_path, title = await asyncio.to_thread(_do_download)
                
                # Standardize extension logic (mp4 focus)
                if not input_path.endswith('.mp4') and os.path.exists(os.path.splitext(input_path)[0] + '.mp4'):
                    input_path = os.path.splitext(input_path)[0] + '.mp4'
                
                logger.info(f"Successfully downloaded: {title}")
                return input_path, title

            except Exception as e:
                last_error = e
                error_msg = str(e).lower()
                
                if "sign in to confirm you're not a bot" in error_msg:
                    logger.warning(f"Bot detection triggered for client {config.get('player_client')}. Cycling...")
                elif "confirm you are not a robot" in error_msg:
                    logger.warning(f"Robot verification required. Cycling...")
                else:
                    logger.error(f"Extraction error with client {config.get('player_client')}: {e}")
                
                # If we are failing even with OAuth2, we might need a manual auth trigger (handled by bot)
                continue

        # If all clients in registry fail
        logger.error(f"All extraction clients failed for URL: {url}")
        raise Exception(f"Nebula v2 Extraction Failed: {str(last_error)}")

# Singleton instance
downloader = MediaDownloader()
