import subprocess
import os
import shutil
from loguru import logger
from typing import Tuple, Optional

FFMPEG_NOT_FOUND_ERROR = "FFmpeg binary not found. Please install FFmpeg: brew install ffmpeg (macOS) or apt-get install ffmpeg (Linux)"

def check_ffmpeg_installed() -> Tuple[bool, Optional[str]]:
    if not shutil.which('ffmpeg'):
        return False, FFMPEG_NOT_FOUND_ERROR
    if not shutil.which('ffprobe'):
        return False, "FFprobe binary not found. Please install FFmpeg: brew install ffmpeg (macOS) or apt-get install ffmpeg (Linux)"
    return True, None

def validate_audio_format(output_format: str) -> Tuple[bool, Optional[str]]:
    valid_formats = ['mp3', 'wav', 'flac']
    if output_format.lower() not in valid_formats:
        return False, f"Invalid audio format: {output_format}. Supported formats: {', '.join(valid_formats)}"
    return True, None

def extract_audio(video_path: str, output_path: str, output_format: str = 'mp3', bitrate: str = '192k') -> Tuple[bool, Optional[str]]:
    ffmpeg_installed, error = check_ffmpeg_installed()
    if not ffmpeg_installed:
        return False, error
    
    format_valid, error = validate_audio_format(output_format)
    if not format_valid:
        return False, error
    
    try:
        codec_map = {
            'mp3': 'libmp3lame',
            'wav': 'pcm_s16le',
            'flac': 'flac'
        }
        
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-vn',
            '-acodec', codec_map[output_format.lower()],
            '-ab', bitrate,
            '-y',
            output_path
        ]
        
        logger.info(f"Running FFmpeg: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        logger.info(f"Audio extracted successfully: {output_path}")
        return True, None
    
    except FileNotFoundError:
        return False, FFMPEG_NOT_FOUND_ERROR
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else str(e)
        logger.error(f"FFmpeg error: {error_msg}")
        return False, error_msg
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return False, str(e)

def get_audio_duration(file_path: str) -> Optional[float]:
    ffmpeg_installed, _ = check_ffmpeg_installed()
    if not ffmpeg_installed:
        return None
    
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            file_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        duration = float(result.stdout.strip())
        return duration
    except FileNotFoundError:
        logger.error("FFprobe binary not found")
        return None
    except Exception as e:
        logger.error(f"Failed to get duration: {str(e)}")
        return None

def clip_audio(input_path: str, output_path: str, start_time: float, end_time: float, output_format: str = 'mp3') -> Tuple[bool, Optional[str]]:
    ffmpeg_installed, error = check_ffmpeg_installed()
    if not ffmpeg_installed:
        return False, error
    
    format_valid, error = validate_audio_format(output_format)
    if not format_valid:
        return False, error
    
    try:
        codec_map = {
            'mp3': 'libmp3lame',
            'wav': 'pcm_s16le',
            'flac': 'flac'
        }
        
        cmd = [
            'ffmpeg',
            '-i', input_path,
            '-ss', str(start_time),
            '-to', str(end_time),
            '-acodec', codec_map[output_format.lower()],
            '-y',
            output_path
        ]
        
        logger.info(f"Clipping audio: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        logger.info(f"Audio clipped successfully: {output_path}")
        return True, None
    
    except FileNotFoundError:
        return False, FFMPEG_NOT_FOUND_ERROR
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else str(e)
        logger.error(f"FFmpeg clip error: {error_msg}")
        return False, error_msg
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return False, str(e)
