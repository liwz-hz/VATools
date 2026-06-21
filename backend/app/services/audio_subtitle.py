import os
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from flask import current_app
from app import db, socketio
from app.models import Task, File
from app.config import Config
from loguru import logger
from sqlalchemy.orm import scoped_session, sessionmaker

_model_cache = {}


def scan_asr_models(model_dir=None):
    if model_dir is None:
        model_dir = _get_asr_model_dir()

    model_path = Path(model_dir).expanduser()
    if not model_path.exists():
        return {}

    models = {}
    for entry in model_path.iterdir():
        if not entry.is_dir():
            continue
        if not (entry / 'config.json').exists():
            continue
        has_model = (entry / 'model.safetensors').exists()
        has_index = (entry / 'model.safetensors.index.json').exists()
        if not (has_model or has_index):
            continue
        config_data = {}
        try:
            config_data = json.loads((entry / 'config.json').read_text())
        except (json.JSONDecodeError, OSError):
            pass
        model_type = config_data.get('model_type', '')
        if 'asr' in model_type.lower() or 'asr' in entry.name.lower():
            models[entry.name] = str(entry)

    return models


def _get_asr_model_dir():
    try:
        from app.models import Config as ConfigModel
        config = ConfigModel.query.filter_by(key='asr_model_dir').first()
        if config and config.value:
            return config.value
    except Exception:
        pass
    return Config.ASR_MODEL_DIR


def get_asr_status():
    model_dir = _get_asr_model_dir()
    models = scan_asr_models(model_dir)

    mlx_audio_available = False
    try:
        import mlx_audio
        mlx_audio_available = True
    except ImportError:
        pass

    return {
        'model_dir': model_dir,
        'models': {name: {'path': path} for name, path in models.items()},
        'mlx_audio_available': mlx_audio_available,
        'default_model': Config.ASR_DEFAULT_MODEL,
    }


def format_timestamp(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f'{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}'


def format_timestamp_vtt(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f'{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}'


def generate_subtitle_file(segments, format, output_path):
    with open(output_path, 'w', encoding='utf-8') as f:
        if format == 'srt':
            for i, seg in enumerate(segments, 1):
                f.write(f"{i}\n")
                f.write(f"{format_timestamp(seg['start'])} --> {format_timestamp(seg['end'])}\n")
                f.write(f"{seg['text']}\n\n")
        elif format == 'vtt':
            f.write("WEBVTT\n\n")
            for seg in segments:
                f.write(f"{format_timestamp_vtt(seg['start'])} --> {format_timestamp_vtt(seg['end'])}\n")
                f.write(f"{seg['text']}\n\n")
        elif format == 'json':
            json.dump({'segments': segments}, f, ensure_ascii=False, indent=2)


def start_audio_subtitle(audio_file_id, model=None, language='auto'):
    audio_file = db.session.get(File, audio_file_id)
    if not audio_file:
        return None, "音频文件未找到"

    if model is None:
        model = Config.ASR_DEFAULT_MODEL

    task = Task(
        task_type='audio_subtitle',
        status='pending',
        input_file=audio_file.file_path
    )
    task.set_params({
        'audio_file_id': audio_file_id,
        'model': model,
        'language': language,
    })

    db.session.add(task)
    db.session.commit()

    app = current_app._get_current_object()
    thread = threading.Thread(target=process_audio_subtitle, args=(task.id, app))
    thread.daemon = True
    thread.start()

    return task.id, None


def process_audio_subtitle(task_id, app):
    with app.app_context():
        session = scoped_session(sessionmaker(bind=db.engine))

        try:
            task = session.query(Task).filter_by(id=task_id).first()
            if not task:
                logger.error(f"Task {task_id} not found")
                return

            task.status = 'processing'
            session.commit()

            params = task.get_params()
            audio_file = session.query(File).filter_by(id=params['audio_file_id']).first()

            if not audio_file or not os.path.exists(audio_file.file_path):
                raise Exception(f"音频文件未找到: {task.input_file}")

            model_name = params.get('model', Config.ASR_DEFAULT_MODEL)

            socketio.emit('task_progress', {
                'task_id': task.id,
                'progress': 5,
                'status': '加载模型...'
            }, namespace='/')

            model_path = _resolve_model_path(model_name)
            if not model_path:
                raise Exception(
                    f"未找到 ASR 模型: {model_name}\n"
                    f"请检查模型目录配置: {_get_asr_model_dir()}"
                )

            model = _load_model(model_path)

            socketio.emit('task_progress', {
                'task_id': task.id,
                'progress': 30,
                'status': '开始转录...'
            }, namespace='/')

            from mlx_audio.stt.generate import generate_transcription

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_dir = os.path.join(Config.WORKSPACE_DIR, 'subtitles')
            os.makedirs(output_dir, exist_ok=True)
            json_output = os.path.join(output_dir, f'{timestamp}_result')

            result = generate_transcription(
                model=model,
                audio=audio_file.file_path,
                output_path=json_output,
                format='json',
                verbose=False,
            )

            socketio.emit('task_progress', {
                'task_id': task.id,
                'progress': 80,
                'status': '生成字幕文件...'
            }, namespace='/')

            segments = _parse_result(result)

            json_path = f'{json_output}.json'
            segments_data = {
                'text': result.text if hasattr(result, 'text') else '',
                'segments': segments,
                'language': result.language if hasattr(result, 'language') else 'unknown',
            }
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(segments_data, f, ensure_ascii=False, indent=2)

            task.output_file = json_path
            task.status = 'completed'
            task.progress = 100
            task.completed_at = datetime.now(timezone.utc)
            session.commit()

            socketio.emit('task_completed', {
                'task_id': task.id,
                'output_file': json_path,
            }, namespace='/')

            logger.info(f"Subtitle task {task_id} completed: {len(segments)} segments")

        except Exception as e:
            task = session.query(Task).filter_by(id=task_id).first()
            if task:
                task.status = 'failed'
                task.error_message = str(e)
                session.commit()

                socketio.emit('task_failed', {
                    'task_id': task.id,
                    'error': str(e)
                }, namespace='/')

                logger.error(f"Subtitle task {task_id} failed: {str(e)}")
        finally:
            session.remove()


def _resolve_model_path(model_name):
    model_dir = _get_asr_model_dir()
    model_path = Path(model_dir) / model_name
    if model_path.exists() and (model_path / 'config.json').exists():
        return str(model_path)

    models = scan_asr_models(model_dir)
    if model_name in models:
        return models[model_name]

    return None


def _load_model(model_path):
    if model_path in _model_cache:
        return _model_cache[model_path]

    from mlx_audio.stt.utils import load_model
    model = load_model(model_path)
    _model_cache[model_path] = model
    return model


def _parse_result(result):
    segments = []

    if hasattr(result, 'segments') and result.segments:
        for i, seg in enumerate(result.segments):
            if isinstance(seg, dict):
                segments.append({
                    'id': i + 1,
                    'start': seg.get('start', 0),
                    'end': seg.get('end', 0),
                    'text': seg.get('text', '').strip(),
                })
            else:
                segments.append({
                    'id': i + 1,
                    'start': getattr(seg, 'start', 0) or getattr(seg, 'start_time', 0) or 0,
                    'end': getattr(seg, 'end', 0) or getattr(seg, 'end_time', 0) or 0,
                    'text': (getattr(seg, 'text', '') or '').strip(),
                })
    elif hasattr(result, 'text'):
        segments.append({
            'id': 1,
            'start': 0,
            'end': 0,
            'text': result.text.strip(),
        })

    return segments
