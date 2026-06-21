import os
import re
import json
import threading
import numpy as np
from datetime import datetime, timezone
from pathlib import Path
from flask import current_app
from app import db, socketio
from app.models import Task, File
from app.config import Config
from loguru import logger
from sqlalchemy.orm import scoped_session, sessionmaker

_tts_model_cache = {}

_EMOTION_RULES = [
    (['哈哈', '太好了', '太棒了', 'wow', '太开心', '太高兴', '耶'], '用兴奋开心的语气说'),
    (['为什么', '怎么', '难道', '是不是', '什么', '哪里', '吗'], '用疑问好奇的语气说'),
    (['唉', '算了', '可惜', '哎', '遗憾', '没办法'], '用低沉无奈的语气说'),
    (['不要', '滚', '够了', '可恶', '混蛋', '烦死', '讨厌'], '用愤怒强烈的语气说'),
    (['请', '谢谢', '麻烦', '拜托', '感谢', '辛苦'], '用礼貌温和的语气说'),
]

_SENTENCE_SPLIT = re.compile(r'(?<=[。！？.!?])')

_DEFAULT_SPEAKERS = ['serena', 'vivian', 'uncle_fu', 'ryan', 'aiden', 'ono_anna', 'sohee', 'eric', 'dylan']


def analyze_emotion(text):
    parts = _SENTENCE_SPLIT.split(text)
    sentences = []
    for p in parts:
        p = p.strip()
        if p:
            sentences.append(p)

    if not sentences:
        return [{'sentence': text.strip(), 'instruct': '用自然平和的语气说'}]

    results = []
    for sentence in sentences:
        matched_instruct = None

        has_exclaim = '！' in sentence or '!' in sentence
        has_question = '？' in sentence or '?' in sentence

        for keywords, instruct in _EMOTION_RULES:
            if any(kw in sentence for kw in keywords):
                matched_instruct = instruct
                break

        if not matched_instruct:
            if has_exclaim:
                matched_instruct = '用兴奋开心的语气说'
            elif has_question:
                matched_instruct = '用疑问好奇的语气说'
            else:
                matched_instruct = '用自然平和的语气说'

        results.append({
            'sentence': sentence,
            'instruct': matched_instruct,
        })

    return results


def _get_tts_model_dir():
    try:
        from app.models import Config as ConfigModel
        config = ConfigModel.query.filter_by(key='tts_model_dir').first()
        if config and config.value:
            return config.value
    except Exception:
        pass
    return Config.TTS_MODEL_DIR


def _resolve_tts_model_path(model_name):
    model_dir = _get_tts_model_dir()
    model_path = Path(model_dir) / model_name
    if model_path.exists() and (model_path / 'config.json').exists():
        return str(model_path)
    return None


def _load_tts_model(model_name):
    model_path = _resolve_tts_model_path(model_name)
    if not model_path:
        raise Exception(f"未找到 TTS 模型: {model_name}\n请检查模型目录配置: {_get_tts_model_dir()}")

    if model_path in _tts_model_cache:
        return _tts_model_cache[model_path]

    from mlx_audio.tts.utils import load_model
    model = load_model(model_path)
    _tts_model_cache[model_path] = model
    return model


def get_supported_speakers():
    try:
        model = _load_tts_model(Config.TTS_CUSTOM_VOICE_MODEL)
        if hasattr(model, 'supported_speakers'):
            return model.supported_speakers
    except Exception:
        pass
    return _DEFAULT_SPEAKERS


def get_tts_status():
    model_dir = _get_tts_model_dir()
    model_path = Path(model_dir).expanduser()

    models = {}
    if model_path.exists():
        for entry in model_path.iterdir():
            if not entry.is_dir():
                continue
            if not (entry / 'config.json').exists():
                continue
            config_data = {}
            try:
                config_data = json.loads((entry / 'config.json').read_text())
            except (json.JSONDecodeError, OSError):
                pass
            model_type = config_data.get('model_type', '')
            if 'tts' in model_type.lower() or 'tts' in entry.name.lower():
                models[entry.name] = {'path': str(entry)}

    mlx_audio_available = False
    try:
        import mlx_audio
        mlx_audio_available = True
    except ImportError:
        pass

    return {
        'model_dir': model_dir,
        'models': models,
        'mlx_audio_available': mlx_audio_available,
        'default_custom_voice_model': Config.TTS_CUSTOM_VOICE_MODEL,
        'default_base_model': Config.TTS_BASE_MODEL,
        'speakers': get_supported_speakers(),
    }


def _concatenate_audio(audio_arrays, sample_rate, gap_seconds=0.3):
    gap_samples = int(gap_seconds * sample_rate)
    silence = np.zeros(gap_samples, dtype=np.float32)
    parts = []
    for i, arr in enumerate(audio_arrays):
        parts.append(arr)
        if i < len(audio_arrays) - 1:
            parts.append(silence)
    return np.concatenate(parts)


def start_tts(params):
    text = params.get('text', '').strip()
    if not text:
        return None, "文本内容不能为空"

    mode = params.get('mode', 'custom_voice')
    if mode not in ('custom_voice', 'voice_clone'):
        return None, "无效的模式，支持: custom_voice, voice_clone"

    if mode == 'voice_clone' and not params.get('ref_audio_id'):
        return None, "声音克隆模式需要上传参考音频"

    task = Task(
        task_type='audio_tts',
        status='pending',
        input_file='tts_input'
    )
    task.set_params(params)

    db.session.add(task)
    db.session.commit()

    app = current_app._get_current_object()
    thread = threading.Thread(target=process_tts, args=(task.id, app))
    thread.daemon = True
    thread.start()

    return task.id, None


def process_tts(task_id, app):
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
            text = params['text']
            mode = params.get('mode', 'custom_voice')
            speaker = params.get('speaker', 'vivian')
            speed = params.get('speed', 1.0)
            temperature = params.get('temperature', 0.9)
            emotions = params.get('emotions')
            language = params.get('language', 'auto')

            socketio.emit('task_progress', {
                'task_id': task.id,
                'progress': 5,
                'status': '加载模型...'
            }, namespace='/')

            if mode == 'custom_voice':
                model_name = Config.TTS_CUSTOM_VOICE_MODEL
            else:
                model_name = Config.TTS_BASE_MODEL

            model = _load_tts_model(model_name)

            socketio.emit('task_progress', {
                'task_id': task.id,
                'progress': 20,
                'status': '分析文本情感...'
            }, namespace='/')

            if emotions:
                sentence_emotions = emotions
            else:
                sentence_emotions = analyze_emotion(text)

            total = len(sentence_emotions)
            audio_segments = []

            ref_audio_path = None
            ref_text = None
            if mode == 'voice_clone':
                ref_audio_id = params.get('ref_audio_id')
                ref_audio_file = session.query(File).filter_by(id=ref_audio_id).first()
                if ref_audio_file and os.path.exists(ref_audio_file.file_path):
                    ref_audio_path = ref_audio_file.file_path
                ref_text = params.get('ref_text')

            for i, se in enumerate(sentence_emotions):
                sentence = se['sentence']
                instruct = se.get('instruct', '用自然平和的语气说')

                progress = 20 + int(60 * (i / total))
                socketio.emit('task_progress', {
                    'task_id': task.id,
                    'progress': progress,
                    'status': f'生成第 {i+1}/{total} 句...'
                }, namespace='/')

                gen_kwargs = {
                    'text': sentence,
                    'temperature': temperature,
                    'speed': speed,
                    'lang_code': language,
                    'verbose': False,
                }

                if mode == 'custom_voice':
                    gen_kwargs['voice'] = speaker
                    gen_kwargs['instruct'] = instruct
                elif mode == 'voice_clone':
                    if ref_audio_path:
                        gen_kwargs['ref_audio'] = ref_audio_path
                    if ref_text:
                        gen_kwargs['ref_text'] = ref_text

                results = list(model.generate(**gen_kwargs))

                for result in results:
                    if hasattr(result, 'audio') and result.audio is not None:
                        audio_segments.append(np.array(result.audio, dtype=np.float32))

            socketio.emit('task_progress', {
                'task_id': task.id,
                'progress': 85,
                'status': '拼接音频...'
            }, namespace='/')

            if not audio_segments:
                raise Exception("未生成任何音频")

            sample_rate = model.sample_rate
            final_audio = _concatenate_audio(audio_segments, sample_rate, gap_seconds=0.3)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_dir = os.path.join(Config.WORKSPACE_DIR, 'tts')
            os.makedirs(output_dir, exist_ok=True)
            output_filename = f'{timestamp}_tts.wav'
            output_path = os.path.join(output_dir, output_filename)

            import soundfile as sf
            sf.write(output_path, final_audio, sample_rate)

            file_size = os.path.getsize(output_path)
            output_file = File(
                filename=output_filename,
                file_path=output_path,
                file_type='audio',
                file_size=file_size,
                duration=len(final_audio) / sample_rate,
            )
            session.add(output_file)
            session.flush()

            task.output_file = output_path
            task.status = 'completed'
            task.progress = 100
            task.completed_at = datetime.now(timezone.utc)
            session.commit()

            socketio.emit('task_completed', {
                'task_id': task.id,
                'output_file': output_path,
                'file_id': output_file.id,
            }, namespace='/')

            logger.info(f"TTS task {task_id} completed: {len(audio_segments)} segments, {len(final_audio)/sample_rate:.1f}s")

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

                logger.error(f"TTS task {task_id} failed: {str(e)}")
        finally:
            session.remove()
