import os
import json
from flask import Blueprint, request, jsonify, send_file
from app.services.audio_extractor import start_audio_extraction
from app.services.audio_editor import start_audio_clip
from app.services.audio_separator import start_audio_separation, get_separation_status
from app.services.audio_subtitle import (
    start_audio_subtitle,
    get_asr_status,
    generate_subtitle_file,
)
from app.services.audio_tts import (
    start_tts,
    get_tts_status,
    get_supported_speakers,
    analyze_emotion,
)
from app.models import Task
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


@bp.route('/subtitle', methods=['POST'])
def subtitle():
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body is required'}), 400

    audio_file_id = data.get('audio_file_id')
    model = data.get('model')
    language = data.get('language', 'auto')

    if not audio_file_id:
        return jsonify({'error': 'audio_file_id is required'}), 400

    try:
        audio_file_id = int(audio_file_id)
    except (ValueError, TypeError):
        return jsonify({'error': 'audio_file_id must be a valid integer'}), 400

    task_id, error = start_audio_subtitle(audio_file_id, model, language)

    if error:
        return jsonify({'error': error}), 400

    return jsonify({'task_id': task_id, 'status': 'pending'}), 201


@bp.route('/subtitle/status', methods=['GET'])
def subtitle_status():
    status = get_asr_status()
    return jsonify(status)


@bp.route('/subtitle/<int:task_id>/result', methods=['GET'])
def subtitle_result(task_id):
    task = Task.query.get_or_404(task_id)

    if task.task_type != 'audio_subtitle':
        return jsonify({'error': 'Not a subtitle task'}), 400

    if task.status != 'completed' or not task.output_file:
        return jsonify({'error': 'Task not completed'}), 400

    if not os.path.exists(task.output_file):
        return jsonify({'error': 'Result file not found'}), 404

    with open(task.output_file, 'r', encoding='utf-8') as f:
        result = json.load(f)

    return jsonify(result)


@bp.route('/subtitle/<int:task_id>/export', methods=['POST'])
def subtitle_export(task_id):
    task = Task.query.get_or_404(task_id)

    if task.task_type != 'audio_subtitle':
        return jsonify({'error': 'Not a subtitle task'}), 400

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body is required'}), 400

    export_format = data.get('format', 'srt')
    if export_format not in ('srt', 'vtt', 'json'):
        return jsonify({'error': 'Invalid format. Use srt, vtt, or json'}), 400

    segments = data.get('segments')

    if not segments:
        if task.status == 'completed' and task.output_file and os.path.exists(task.output_file):
            with open(task.output_file, 'r', encoding='utf-8') as f:
                result_data = json.load(f)
            segments = result_data.get('segments', [])
        else:
            return jsonify({'error': 'No segments available'}), 400

    import tempfile
    suffix = f'.{export_format}'
    with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False) as f:
        temp_path = f.name

    generate_subtitle_file(segments, export_format, temp_path)

    mime_types = {
        'srt': 'text/plain',
        'vtt': 'text/vtt',
        'json': 'application/json',
    }

    return send_file(
        temp_path,
        mimetype=mime_types.get(export_format, 'text/plain'),
        as_attachment=True,
        download_name=f'subtitle.{export_format}'
    )


@bp.route('/tts', methods=['POST'])
def tts():
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body is required'}), 400

    text = data.get('text', '').strip()
    if not text:
        return jsonify({'error': 'text is required'}), 400

    mode = data.get('mode', 'custom_voice')
    speaker = data.get('speaker', 'vivian')
    ref_audio_id = data.get('ref_audio_id')
    ref_text = data.get('ref_text')
    emotions = data.get('emotions')
    speed = data.get('speed', 1.0)
    temperature = data.get('temperature', 0.9)
    language = data.get('language', 'auto')

    params = {
        'text': text,
        'mode': mode,
        'speaker': speaker,
        'ref_audio_id': ref_audio_id,
        'ref_text': ref_text,
        'emotions': emotions,
        'speed': speed,
        'temperature': temperature,
        'language': language,
    }

    task_id, error = start_tts(params)

    if error:
        return jsonify({'error': error}), 400

    return jsonify({'task_id': task_id, 'status': 'pending'}), 201


@bp.route('/tts/status', methods=['GET'])
def tts_status():
    status = get_tts_status()
    return jsonify(status)


@bp.route('/tts/speakers', methods=['GET'])
def tts_speakers():
    speakers = get_supported_speakers()
    return jsonify({'speakers': speakers})


@bp.route('/tts/analyze', methods=['POST'])
def tts_analyze():
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body is required'}), 400

    text = data.get('text', '').strip()
    if not text:
        return jsonify({'error': 'text is required'}), 400

    emotions = analyze_emotion(text)
    return jsonify({'emotions': emotions})
