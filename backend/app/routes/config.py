from flask import Blueprint, jsonify, request
from app import db
from app.models import Config
from app.config import Config as AppConfig
from app.services.audio_separator import get_separation_status, scan_for_models
from pathlib import Path

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
    'separation_output_format': AppConfig.SEPARATION_OUTPUT_FORMAT,
    'separation_model_dir': AppConfig.SEPARATION_MODEL_DIR or '',
    'asr_model_dir': AppConfig.ASR_MODEL_DIR,
    'asr_default_model': AppConfig.ASR_DEFAULT_MODEL,
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

@bp.route('/models/scan', methods=['GET'])
def scan_models():
    """扫描系统中的音源分离模型"""
    models = scan_for_models()
    return jsonify(models)

@bp.route('/models/status', methods=['GET'])
def models_status():
    """获取音源分离完整状态"""
    status = get_separation_status()
    return jsonify(status)

@bp.route('/models/validate', methods=['POST'])
def validate_model_dir():
    """验证模型目录是否有效"""
    data = request.get_json()
    model_dir = data.get('model_dir')
    
    if not model_dir:
        return jsonify({'valid': False, 'error': '未提供模型目录'}), 400
    
    model_path = Path(model_dir).expanduser()
    
    if not model_path.exists():
        return jsonify({'valid': False, 'error': f'目录不存在: {model_dir}'})
    
    if not model_path.is_dir():
        return jsonify({'valid': False, 'error': f'不是有效的目录: {model_dir}'}), 400
    
    # 检查是否包含模型文件
    has_models = False
    found_models = []
    
    # 检查 UVR Demucs 模型
    uvr_demucs_dir = model_path / 'Demucs_Models' / 'v3_v4_repo'
    if uvr_demucs_dir.exists():
        th_files = list(uvr_demucs_dir.glob('*.th'))
        if th_files:
            has_models = True
            for th_file in th_files[:5]:  # 只显示前5个
                found_models.append(f'demucs/{th_file.name}')
    
    # 检查 UVR MDX 模型
    mdx_dir = model_path / 'MDX_Net_Models'
    if mdx_dir.exists():
        onnx_files = list(mdx_dir.glob('*.onnx'))
        if onnx_files:
            has_models = True
            found_models.append(f'mdx-net ({len(onnx_files)} models)')
    
    # 检查 UVR VR 模型
    vr_dir = model_path / 'VR_Models'
    if vr_dir.exists():
        pth_files = list(vr_dir.glob('*.pth'))
        if pth_files:
            has_models = True
            found_models.append(f'vr-models ({len(pth_files)} models)')
    
    # 检查 Spleeter 模型
    for model_name in ['2stems', '4stems']:
        model_subdir = model_path / model_name
        if model_subdir.exists() and (model_subdir / 'model.meta').exists():
            has_models = True
            found_models.append(f'spleeter/{model_name}')
    
    # 检查普通 Demucs 模型
    for pattern in ['*.th', '*.pth']:
        th_files = list(model_path.glob(pattern))
        if th_files:
            has_models = True
            for th_file in th_files[:5]:
                found_models.append(f'demucs/{th_file.name}')
            break
    
    if has_models:
        return jsonify({
            'valid': True,
            'model_dir': str(model_path),
            'found_models': found_models
        })
    else:
        return jsonify({
            'valid': False,
            'error': '目录中未找到有效的音源分离模型',
            'expected': [
                'UVR: Demucs_Models/v3_v4_repo/*.th',
                'Spleeter: 2stems/, 4stems/ 目录',
                'Demucs: *.th 或 *.pth 文件'
            ]
        })
