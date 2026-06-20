from flask import Blueprint, request, jsonify
from app.services.audio_extractor import start_audio_extraction
from app.utils.ffmpeg_utils import validate_audio_format
from loguru import logger

bp = Blueprint('audio', __name__, url_prefix='/api/audio')

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
