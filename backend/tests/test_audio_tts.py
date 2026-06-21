import pytest
import os
import json
import tempfile
import numpy as np
from pathlib import Path
from app import create_app, db
from app.models import File, Task


@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_analyze_emotion_default():
    from app.services.audio_tts import analyze_emotion
    result = analyze_emotion("今天天气不错。")
    assert len(result) == 1
    assert result[0]['sentence'] == '今天天气不错。'
    assert '自然平和' in result[0]['instruct']


def test_analyze_emotion_exclamation():
    from app.services.audio_tts import analyze_emotion
    result = analyze_emotion("太好了！太棒了！")
    assert len(result) == 2
    assert '兴奋开心' in result[0]['instruct']
    assert '兴奋开心' in result[1]['instruct']


def test_analyze_emotion_question():
    from app.services.audio_tts import analyze_emotion
    result = analyze_emotion("为什么？怎么会这样？")
    assert len(result) == 2
    assert '疑问好奇' in result[0]['instruct']


def test_analyze_emotion_anger():
    from app.services.audio_tts import analyze_emotion
    result = analyze_emotion("滚！不要再来烦我！")
    assert len(result) >= 1
    assert any('愤怒' in s['instruct'] for s in result)


def test_analyze_emotion_sighing():
    from app.services.audio_tts import analyze_emotion
    result = analyze_emotion("唉，算了。")
    assert len(result) >= 1
    assert any('低沉无奈' in s['instruct'] for s in result)


def test_analyze_emotion_polite():
    from app.services.audio_tts import analyze_emotion
    result = analyze_emotion("谢谢你。请帮我一下。")
    assert len(result) >= 1
    assert any('礼貌温和' in s['instruct'] for s in result)


def test_analyze_emotion_multi_sentence():
    from app.services.audio_tts import analyze_emotion
    result = analyze_emotion("你好。今天怎么样？太好了！")
    assert len(result) == 3


def test_get_tts_status():
    from app.services.audio_tts import get_tts_status
    status = get_tts_status()
    assert 'model_dir' in status
    assert 'models' in status
    assert 'mlx_audio_available' in status
    assert 'default_custom_voice_model' in status
    assert 'default_base_model' in status


def test_get_supported_speakers():
    from app.services.audio_tts import get_supported_speakers
    speakers = get_supported_speakers()
    assert isinstance(speakers, list)
    assert len(speakers) > 0
    assert 'vivian' in speakers


def test_resolve_tts_model_path_nonexistent():
    from app.services.audio_tts import _resolve_tts_model_path
    result = _resolve_tts_model_path('nonexistent-model')
    assert result is None


def test_concatenate_audio():
    from app.services.audio_tts import _concatenate_audio
    # Create audio with some trailing silence
    a1 = np.concatenate([
        np.ones(20000, dtype=np.float32) * 0.8,  # speech
        np.zeros(4000, dtype=np.float32)           # trailing silence
    ])
    a2 = np.concatenate([
        np.ones(18000, dtype=np.float32) * 0.6,  # speech
        np.zeros(6000, dtype=np.float32)           # trailing silence
    ])
    
    # pause_durations should match audio_segments length
    result = _concatenate_audio([a1, a2], [0.5, 0.3], 24000)
    
    # After trimming:
    # a1: 20000 (speech) + 2400 (min silence) = 22400 samples
    # gap: 12000 samples (0.5s)
    # a2: 18000 (speech) + 2400 (min silence) = 20400 samples
    # Total: 22400 + 12000 + 20400 = 54800 samples
    assert len(result) < len(a1) + len(a2) + int(0.5 * 24000)  # Less than untrimmed
    assert len(result) > 50000  # But still substantial
    assert result[0] == 0.8  # First sample from a1


def test_trim_silence():
    from app.services.audio_tts import _trim_silence
    audio = np.concatenate([
        np.ones(1000, dtype=np.float32) * 0.5,
        np.zeros(5000, dtype=np.float32)
    ])
    trimmed = _trim_silence(audio, 24000, threshold=0.01, min_silence_duration=0.1)
    assert len(trimmed) < len(audio)
    assert len(trimmed) >= 1000


def test_get_pause_duration():
    from app.services.audio_tts import _get_pause_duration
    assert _get_pause_duration('你好。') == 0.5
    assert _get_pause_duration('真的吗？') == 0.6
    assert _get_pause_duration('太好了！') == 0.8
    assert _get_pause_duration('嗯...') == 1.2
    assert _get_pause_duration('继续') == 0.3


def test_start_tts_missing_text(app):
    with app.app_context():
        from app.services.audio_tts import start_tts
        task_id, error = start_tts({'text': '', 'mode': 'custom_voice'})
        assert task_id is None
        assert error is not None


def test_start_tts_creates_task(app):
    with app.app_context():
        from app.services.audio_tts import start_tts
        task_id, error = start_tts({
            'text': '你好世界',
            'mode': 'custom_voice',
            'speaker': 'vivian',
        })
        assert task_id is not None
        assert error is None

        task = db.session.get(Task, task_id)
        assert task.task_type == 'audio_tts'
        assert task.status == 'pending'
        params = task.get_params()
        assert params['text'] == '你好世界'
        assert params['mode'] == 'custom_voice'


def test_tts_api_missing_text(client):
    response = client.post('/api/audio/tts',
                          json={'mode': 'custom_voice'},
                          content_type='application/json')
    assert response.status_code == 400
    data = response.get_json()
    assert 'error' in data


def test_tts_api_success(client, app):
    response = client.post('/api/audio/tts',
                          json={'text': '你好世界', 'mode': 'custom_voice', 'speaker': 'vivian'},
                          content_type='application/json')
    assert response.status_code == 201
    data = response.get_json()
    assert 'task_id' in data


def test_tts_status_api(client):
    response = client.get('/api/audio/tts/status')
    assert response.status_code == 200
    data = response.get_json()
    assert 'models' in data
    assert 'speakers' in data


def test_tts_speakers_api(client):
    response = client.get('/api/audio/tts/speakers')
    assert response.status_code == 200
    data = response.get_json()
    assert 'speakers' in data
    assert isinstance(data['speakers'], list)


def test_tts_analyze_api(client):
    response = client.post('/api/audio/tts/analyze',
                          json={'text': '你好。太好了！'},
                          content_type='application/json')
    assert response.status_code == 200
    data = response.get_json()
    assert 'emotions' in data
    assert len(data['emotions']) == 2
