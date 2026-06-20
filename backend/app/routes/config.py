from flask import Blueprint, jsonify, request
from app import db
from app.models import Config
from app.config import Config as AppConfig

bp = Blueprint('config', __name__, url_prefix='/api/config')

DEFAULT_CONFIG = {
    'upload_dir': AppConfig.UPLOAD_DIR,
    'workspace_dir': AppConfig.WORKSPACE_DIR,
    'max_file_size': str(AppConfig.MAX_FILE_SIZE),
    'log_dir': AppConfig.LOG_DIR,
    'log_level': AppConfig.LOG_LEVEL,
    'log_max_size': str(AppConfig.LOG_MAX_SIZE),
    'log_retention_days': str(AppConfig.LOG_RETENTION_DAYS),
    'default_audio_format': AppConfig.DEFAULT_AUDIO_FORMAT,
    'default_bitrate': AppConfig.DEFAULT_BITRATE,
    'default_sample_rate': str(AppConfig.DEFAULT_SAMPLE_RATE),
    'separation_model': AppConfig.SEPARATION_MODEL,
    'acceleration_type': AppConfig.ACCELERATION_TYPE,
    'separation_output_format': AppConfig.SEPARATION_OUTPUT_FORMAT
}

@bp.route('', methods=['GET'])
def get_config():
    configs = Config.query.all()
    config_dict = {c.key: c.value for c in configs}
    
    for key, value in DEFAULT_CONFIG.items():
        if key not in config_dict:
            config_dict[key] = value
    
    return jsonify(config_dict)

@bp.route('', methods=['PUT'])
def update_config():
    data = request.get_json()
    
    for key, value in data.items():
        if key in DEFAULT_CONFIG:
            config = Config.query.filter_by(key=key).first()
            if config:
                config.value = str(value)
            else:
                config = Config(key=key, value=str(value))
                db.session.add(config)
    
    db.session.commit()
    return jsonify({'message': 'Config updated successfully'})

@bp.route('/reset', methods=['POST'])
def reset_config():
    Config.query.delete()
    db.session.commit()
    return jsonify(DEFAULT_CONFIG)
