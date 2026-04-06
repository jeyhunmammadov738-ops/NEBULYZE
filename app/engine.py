import os
import logging
import asyncio
import aiohttp
import uuid
import subprocess
from typing import Tuple, Dict, Any

logger = logging.getLogger(__name__)

class NebulaV6Bridge:
    """
    Nebulyze v3: API Bridge Engine
    Offloads extraction to external infrastructure to bypass the VPS IP block.
    """
    
    TEMP_DIR = "temp_uploads"
    # A public stable instance of the Cobalt API
    COBALT_API = "https://api.cobalt.tools/api/json"

    def __init__(self):
        os.makedirs(self.TEMP_DIR, exist_ok=True)

    async def extract_via_bridge(self, url: str) -> Tuple[str, str]:
        """Send URL to the external Bridge API to bypass VPS block."""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        data = {
            "url": url,
            "vQuality": "720",
            "aFormat": "mp3", # Request MP3 directly if possible
            "isAudioOnly": False, # Extract video first to ensure stability
        }

        async with aiohttp.ClientSession() as session:
            try:
                logger.info(f"V6 Bridging URL: {url}")
                async with session.post(self.COBALT_API, json=data, headers=headers) as resp:
                    if resp.status != 200:
                        error_data = await resp.text()
                        raise Exception(f"Bridge API returned {resp.status}: {error_data}")
                    
                    result = await resp.json()
                    status = result.get("status")
                    
                    if status == "error":
                        raise Exception(f"Bridge Error: {result.get('text', 'Unknown')}")
                    
                    stream_url = result.get("url")
                    filename = result.get("filename", "nebula_media")
                    
                    # Download the final media file to the VPS
                    input_path = os.path.join(self.TEMP_DIR, f"{str(uuid.uuid4())}_{filename}")
                    async with session.get(stream_url) as file_resp:
                        if file_resp.status != 200:
                            raise Exception(f"Failed to fetch media from Bridge: {file_resp.status}")
                        
                        with open(input_path, 'wb') as f:
                            f.write(await file_resp.read())
                    
                    return input_path, filename
                    
            except Exception as e:
                logger.error(f"V6 Bridge failed: {e}")
                raise Exception(f"Nebula v6 Alternative Engine failed: {str(e)}")

    def convert_to_mp3(self, input_path: str, output_path: str) -> str:
        """Standard MP3 conversion for local delivery."""
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vn", "-ar", "44100", "-ac", "2", "-b:a", "192k",
            output_path
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return output_path
        except Exception as e:
            logger.error(f"FFmpeg conversion failed: {e}")
            raise

engine = NebulaV6Bridge()
