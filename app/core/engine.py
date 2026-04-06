import os
import logging
import subprocess
from typing import Optional, Tuple
from moviepy import VideoFileClip, AudioFileClip
from imageio_ffmpeg import get_ffmpeg_exe
import cv2

logger = logging.getLogger(__name__)
FFMPEG_PATH = get_ffmpeg_exe()

class ConversionError(Exception):
    pass

def validate_media(file_path: str) -> bool:
    """Validate if the media file is readable using OpenCV."""
    try:
        if not os.path.exists(file_path):
            return False
        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            return False
        ret, frame = cap.read()
        cap.release()
        return ret
    except Exception as e:
        logger.error(f"Media validation failed: {e}")
        return False

def preprocess_media(input_path: str) -> str:
    """
    Standardize incoming streams to MP4/M4A before conversion.
    Fixes 'failed to read first frame' by remuxing with FFmpeg.
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # Step 0: Check if already valid to skip redundant work (OCI Optimization)
    if validate_media(input_path) and input_path.lower().endswith('.mp4'):
        logger.info(f"Media already valid, skipping standardization: {input_path}")
        return input_path

    # Standardize to a fresh .mp4 container
    standard_path = input_path.rsplit('.', 1)[0] + "_std.mp4"
    logger.info(f"Standardizing media: {input_path} -> {standard_path}")
    
    # FFmpeg command to remux/repair without re-encoding
    cmd = [
        FFMPEG_PATH, "-y", "-i", input_path,
        "-c", "copy", "-map", "0", "-ignore_unknown",
        "-movflags", "faststart", standard_path
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        if validate_media(standard_path):
            return standard_path
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        logger.warning(f"Fast remux failed or timed out: {str(e)}. Attempting full re-encoding.")
        # Fallback: Full re-encoding for maximum compatibility
        repair_cmd = [
            FFMPEG_PATH, "-y", "-i", input_path,
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac", "-map", "0", standard_path
        ]
        try:
            subprocess.run(repair_cmd, check=True, capture_output=True, timeout=300)
            return standard_path
        except Exception as ex:
            logger.error(f"Media repair failed: {str(ex)}")
            raise ConversionError("Failed to repair/standardize media file.")
    
    return input_path

def convert_to_mp3(
    input_path: str, 
    output_path: str, 
    bitrate: str = "192k", 
    trim: Optional[Tuple[float, float]] = None,
    dynamic_quality: bool = True
) -> str:
    """
    Convert media to MP3 using MoviePy with enhanced resilience.
    """
    # 1. Pre-process / Repair if needed
    try:
        work_path = preprocess_media(input_path)
    except Exception as e:
        logger.error(f"Preprocessing failed: {e}")
        work_path = input_path

    clip = None
    try:
        is_video = work_path.lower().endswith(('.mp4', '.mkv', '.mov', '.avi', '.webm'))
        
        if is_video:
            clip = VideoFileClip(work_path)
            audio_source = clip.audio
        else:
            clip = AudioFileClip(work_path)
            audio_source = clip

        if not audio_source:
            raise ConversionError("No audio track found in the source file.")

        # Trimming
        if trim:
            start_t, end_t = trim
            duration = audio_source.duration or 0
            audio_source = audio_source.subclip(max(0, start_t), min(duration, end_t))

        audio_source.write_audiofile(
            output_path, 
            bitrate=bitrate, 
            codec='libmp3lame',
            ffmpeg_params=["-preset", "ultrafast", "-threads", "auto"],
            logger=None
        )
        return output_path
        
    except Exception as e:
        logger.error(f"Conversion engine failure: {e}")
        raise ConversionError(str(e))
    finally:
        if clip:
            clip.close()
            if hasattr(clip, 'audio') and clip.audio:
                clip.audio.close()
        # Clean up standardized temp file
        if work_path != input_path and os.path.exists(work_path):
            try:
                os.remove(work_path)
            except: pass

def convert_to_voice(
    input_path: str, 
    output_path: str, 
    trim: Optional[Tuple[float, float]] = None
) -> str:
    """
    Convert media to OGG/Opus for Telegram Voice simulation.
    Uses direct FFmpeg for memory efficiency on OCI VPS.
    """
    logger.info(f"Converting to Voice (OGG/Opus): {input_path}")
    
    cmd = [
        FFMPEG_PATH, "-y", "-i", input_path,
        "-c:a", "libopus", "-b:a", "32k", "-vbr", "on",
        "-compression_level", "10", output_path
    ]
    
    # Add trimming if specified
    if trim:
        start_t, end_t = trim
        cmd = [FFMPEG_PATH, "-y", "-ss", str(start_t), "-to", str(end_t), "-i", input_path] + cmd[4:]

    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
        return output_path
    except Exception as e:
        logger.error(f"Voice conversion failed: {str(e)}")
        raise ConversionError(f"Direct voice conversion failed: {str(e)}")

