import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'vatools-secret-key-2026'
    
    UPLOAD_DIR = str(BASE_DIR / 'uploads')
    WORKSPACE_DIR = str(BASE_DIR / 'workspace')
    LOG_DIR = str(BASE_DIR / 'logs')
    
    MAX_FILE_SIZE = 512 * 1024 * 1024  # 512MB
    
    LOG_LEVEL = 'INFO'
    LOG_MAX_SIZE = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT = 5
    LOG_RETENTION_DAYS = 30
    
    DEFAULT_AUDIO_FORMAT = 'mp3'
    DEFAULT_BITRATE = '192k'
    DEFAULT_SAMPLE_RATE = 44100
    
    SEPARATION_MODEL = 'demucs'  # 默认使用 Demucs（Spleeter不支持Python 3.13）
    ACCELERATION_TYPE = 'auto'  # 'auto', 'mps', 'mlx', 'cpu'
    SEPARATION_OUTPUT_FORMAT = 'wav'
    
    # UVR模型默认路径（macOS）
    UVR_MODEL_DIR = '/Applications/Ultimate Vocal Remover.app/Contents/Resources/models'
    SEPARATION_MODEL_DIR = UVR_MODEL_DIR
    
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{BASE_DIR / "vatooldb.db"}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    @staticmethod
    def init_app():
        Path(Config.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
        Path(Config.WORKSPACE_DIR).mkdir(parents=True, exist_ok=True)
        Path(Config.LOG_DIR).mkdir(parents=True, exist_ok=True)
        (Path(Config.WORKSPACE_DIR) / 'audio').mkdir(exist_ok=True)
        (Path(Config.WORKSPACE_DIR) / 'separated').mkdir(exist_ok=True)
        (Path(Config.WORKSPACE_DIR) / 'edited').mkdir(exist_ok=True)
