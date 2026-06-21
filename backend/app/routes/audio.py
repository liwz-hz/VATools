from flask import Blueprint, request, jsonify
from app.services.audio_extractor import start_audio_extraction
from app.services.audio_editor import start_audio_clip
from app.services.audio_separator import start_audio_separation, get_separation_status
from app.utils.ffmpeg_utils import validate_audio_format
from loguru import logger

bp = Blueprint('audio', __name__, url_prefix='/api/audio')

@bp.route('/separation/status', methods=['GET'])
def separation_status():
    """获取音源分离功能状态和模型信息"""
    status = get_separation_status()
    return jsonify(status)

@bp.route('/extract', methods=['POST'])
def extract():
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body is required'}), 400
    
    video_file_id = data.get('video_file_id')
    output_format = data.get('output_format', 'mp3')
    bitrate = data.get('bitrate', '192k')
    
    if not video_file_id:
        return jsonify({'error': 'video_file_id is required'}), 400
    
    try:
        video_file_id = int(video_file_id)
    except (ValueError, TypeError):
        return jsonify({'error': 'video_file_id must be a valid integer'}), 400
    
    format_valid, error = validate_audio_format(output_format)
    if not format_valid:
        return jsonify({'error': error}), 400
    
    valid_bitrates = ['128k', '192k', '256k', '320k']
    if bitrate not in valid_bitrates:
        return jsonify({'error': f'Invalid bitrate. Supported values: {", ".join(valid_bitrates)}'}), 400
    
    task_id, error = start_audio_extraction(video_file_id, output_format, bitrate)
    
    if error:
        return jsonify({'error': error}), 400
    
    logger.info(f"Audio extraction task created: {task_id}")
    
    return jsonify({'task_id': task_id, 'status': 'pending'}), 201

@bp.route('/clip', methods=['POST'])
def clip():
    data = request.get_json()
    
    audio_file_id = data.get('audio_file_id')
    operation = data.get('operation')
    start_time = data.get('start_time')
    end_time = data.get('end_time')
    output_format = data.get('output_format', 'mp3')
    
    if not all([audio_file_id, operation, start_time is not None, end_time is not None]):
        return jsonify({'error': 'Missing required parameters'}), 400
    
    if operation not in ['extract', 'delete']:
        return jsonify({'error': 'Invalid operation. Use "extract" or "delete"'}), 400
    
    format_valid, error = validate_audio_format(output_format)
    if not format_valid:
        return jsonify({'error': error}), 400
    
    task_id, error = start_audio_clip(audio_file_id, operation, start_time, end_time, output_format)
    
    if error:
        return jsonify({'error': error}), 400
    
    return jsonify({'task_id': task_id}), 201

@bp.route('/separate', methods=['POST'])
def separate():
    data = request.get_json()
    
    audio_file_id = data.get('audio_file_id')
    stems = data.get('stems', ['vocals', 'drums', 'bass', 'other'])
    engine = data.get('engine', 'demucs')  # 默认使用 Demucs
    model = data.get('model', 'htdemucs_ft')  # 默认使用 htdemucs_ft
    
    if not audio_file_id:
        return jsonify({'error': 'audio_file_id is required'}), 400
    
    task_id, error = start_audio_separation(audio_file_id, stems, engine, model)
    
    if error:
        return jsonify({'error': error}), 400
    
    return jsonify({'task_id': task_id}), 201
