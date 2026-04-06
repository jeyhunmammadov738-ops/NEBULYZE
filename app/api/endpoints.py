from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse
import shutil
import os
import uuid
from typing import Optional
from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict
from ..tasks.worker import convert_media_task
from celery.result import AsyncResult
from fastapi.responses import FileResponse
import yt_dlp
from typing import Tuple
import re

# Rate limiting
from slowapi import Limiter
from slowapi.util import get_remote_address

# Import validation schemas
from ..schemas import URLRequest

# Circuit breakers
from ..circuit_breakers import external_api_breaker

# Create limiter
limiter = Limiter(key_func=get_remote_address)

router = APIRouter()
TEMP_UPLOAD_DIR = "temp_uploads"
os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]

    async def send_personal_message(self, message: str, client_id: str):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_text(message)

manager = ConnectionManager()

@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(client_id, websocket)
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
            # Handle client heartbeats or messages if needed
    except WebSocketDisconnect:
        manager.disconnect(client_id)

def validate_url(url: str) -> bool:
    """
    Validate URL to prevent SSRF and other security issues
    """
    # Basic URL format validation
    if not re.match(r'^https?://', url):
        return False
    
    # Block potentially dangerous URLs
    blocked_patterns = [
        r'localhost',
        r'127\.0\.0\.1',
        r'192\.168\.',
        r'10\.',
        r'172\.(1[6-9]|2[0-9]|3[01])\.',
        r'internal',
        r'intranet',
        r'file://',
        r'data://'
    ]
    
    for pattern in blocked_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            return False
    
    return True

def validate_bitrate(bitrate: str) -> bool:
    """
    Validate bitrate format
    """
    valid_bitrates = ['96k', '128k', '192k', '256k', '320k']
    if bitrate in valid_bitrates:
        return True
    # Try to parse custom bitrate
    if bitrate.endswith('k') and bitrate[:-1].isdigit():
        bitrate_value = int(bitrate[:-1])
        return 96 <= bitrate_value <= 320
    return False

@router.post("/upload")
@limiter.limit("5/minute")
async def upload_file(request: Request, file: UploadFile = File(...), 
    bitrate: str = "192k", 
    fmt: str = "mp3", 
    trim: Optional[str] = None
):
    """
    Endpoint for direct file uploads.
    Saves file to disk and enqueues conversion task.
    """
    # Validate inputs
    if not validate_bitrate(bitrate):
        raise HTTPException(status_code=400, detail="Invalid bitrate format")
    
    if fmt not in ['mp3', 'ogg']:
        raise HTTPException(status_code=400, detail="Format must be either mp3 or ogg")
    
    file_id = str(uuid.uuid4())
    ext = file.filename.split('.')[-1] if '.' in file.filename else 'mp4'
    input_path = os.path.join(TEMP_UPLOAD_DIR, f"{file_id}.{ext}")
    
    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    output_ext = "mp3" if fmt == "mp3" else "ogg"
    output_path = os.path.join(TEMP_UPLOAD_DIR, f"{file_id}_final.{output_ext}")
    
    # Optional: Parse trim from string "MM:SS-MM:SS" if needed
    trim_params = None
    if trim:
        try:
            parts = trim.split('-')
            if len(parts) == 2:
                def parse_time(t): 
                    p = t.split(':')
                    return int(p[0]) * 60 + int(p[1]) if len(p) == 2 else 0
                start_time = parse_time(parts[0])
                end_time = parse_time(parts[1])
                if start_time >= end_time:
                    raise HTTPException(status_code=400, detail="End time must be greater than start time")
                trim_params = (start_time, end_time)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid trim format: {str(e)}")

    task = convert_media_task.delay(input_path, output_path, bitrate, fmt, trim_params)
    
    return {
        "task_id": task.id,
        "file_id": file_id,
        "status": "QUEUED"
    }

@router.get("/status/{task_id}")
@limiter.limit("30/minute")
async def get_status(request: Request, task_id: str):
    """
    Poll task status from Celery.
    Returns state and any metadata (e.g. progress percentage).
    """
    # Validate task_id format (should be UUID-like)
    if not re.match(r'^[a-zA-Z0-9\-]+$', task_id):
        raise HTTPException(status_code=400, detail="Invalid task ID format")
        
    res = AsyncResult(task_id)
    return {
        "status": res.state,
        "info": res.info # contains the metadata updated via self.update_state
    }

@router.get("/download/{task_id}")
@limiter.limit("20/minute")
async def download_result(request: Request, task_id: str):
    """
    Provide download link for finished files.
    """
    # Validate task_id format
    if not re.match(r'^[a-zA-Z0-9\-]+$', task_id):
        raise HTTPException(status_code=400, detail="Invalid task ID format")
        
    res = AsyncResult(task_id)
    if res.state == "SUCCESS":
        # Task info contains the output path returned by the worker
        result = res.result
        output_path = result.get("output_path") if isinstance(result, dict) else result
        
        if output_path and os.path.exists(output_path):
            filename = os.path.basename(output_path)
            return FileResponse(
                path=output_path,
                filename=filename,
                media_type="audio/mpeg" if filename.endswith(".mp3") else "audio/ogg",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "Access-Control-Expose-Headers": "Content-Disposition"
                }
            )
        else:
            raise HTTPException(status_code=404, detail="Converted file not found on server.")
    elif res.state == "PENDING" or res.state == "STARTED":
        raise HTTPException(status_code=202, detail="Task is still processing.")
    else:
        raise HTTPException(status_code=400, detail=f"Task failed or state is {res.state}.")

from ..core.downloader import downloader

@router.post("/url")
@limiter.limit("3/minute")
async def extract_url(request: Request, url_request: URLRequest):
    """
    Endpoint for URL-based extraction (YouTube, TikTok, etc.)
    Downloads file temporarily and enqueues conversion.
    """
    # Validate URL
    if not validate_url(str(url_request.url)):
        raise HTTPException(status_code=400, detail="Invalid or potentially dangerous URL")
    
    try:
        @external_api_breaker
        def extract_with_v2():
            # Use new v2 resilient downloader
            return asyncio.run(downloader.download(str(url_request.url)))
        
        input_path, title = extract_with_v2()
        
        file_id = os.path.basename(input_path).split('.')[0]
        output_ext = "mp3" if url_request.fmt == "mp3" else "ogg"
        output_path = os.path.join(TEMP_UPLOAD_DIR, f"{file_id}_final.{output_ext}")
        
        task = convert_media_task.delay(input_path, output_path, url_request.bitrate, url_request.fmt)
        
        return {
            "task_id": task.id,
            "title": title,
            "status": "QUEUED"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"URL Extraction Failed: {str(e)}")