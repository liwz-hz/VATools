import pytest
import os
import json
import tempfile
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


def test_scan_asr_models_finds_valid_models():
    with tempfile.TemporaryDirectory() as tmpdir:
        model_dir = Path(tmpdir) / 'Qwen3-ASR-1.7B-8bit'
        model_dir.mkdir()
        (model_dir / 'config.json').write_text('{"model_type": "qwen3_asr"}')
        (model_dir / 'model.safetensors').write_text('')

        from app.services.audio_subtitle import scan_asr_models
        result = scan_asr_models(tmpdir)

        assert 'Qwen3-ASR-1.7B-8bit' in result
        assert result['Qwen3-ASR-1.7B-8bit'] == str(model_dir)


def test_scan_asr_models_ignores_incomplete():
    with tempfile.TemporaryDirectory() as tmpdir:
        model_dir = Path(tmpdir) / 'incomplete-model'
        model_dir.mkdir()
        (model_dir / 'config.json').write_text('{"model_type": "asr"}')

        from app.services.audio_subtitle import scan_asr_models
        result = scan_asr_models(tmpdir)

        assert len(result) == 0


def test_scan_asr_models_nonexistent_dir():
    from app.services.audio_subtitle import scan_asr_models
    result = scan_asr_models('/nonexistent/path')
    assert result == {}


def test_format_timestamp():
    from app.services.audio_subtitle import format_timestamp
    assert format_timestamp(0) == '00:00:00,000'
    assert format_timestamp(1.5) == '00:00:01,500'
    assert format_timestamp(3661.123) == '01:01:01,123'


def test_generate_subtitle_file_srt():
    from app.services.audio_subtitle import generate_subtitle_file

    segments = [
        {'id': 1, 'start': 0.0, 'end': 2.5, 'text': 'Hello world'},
        {'id': 2, 'start': 2.5, 'end': 5.0, 'text': 'Test subtitle'},
    ]

    with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
        output_path = f.name

    try:
        generate_subtitle_file(segments, 'srt', output_path)
        content = Path(output_path).read_text()
        assert '1\n' in content
        assert 'Hello world' in content
        assert '00:00:00,000 --> 00:00:02,500' in content
        assert '2\n' in content
        assert 'Test subtitle' in content
    finally:
        os.unlink(output_path)


def test_generate_subtitle_file_vtt():
    from app.services.audio_subtitle import generate_subtitle_file

    segments = [
        {'id': 1, 'start': 0.0, 'end': 2.5, 'text': 'Hello world'},
    ]

    with tempfile.NamedTemporaryFile(mode='w', suffix='.vtt', delete=False) as f:
        output_path = f.name

    try:
        generate_subtitle_file(segments, 'vtt', output_path)
        content = Path(output_path).read_text()
        assert 'WEBVTT' in content
        assert 'Hello world' in content
        assert '00:00:00.000 --> 00:00:02.500' in content
    finally:
        os.unlink(output_path)


def test_start_subtitle_missing_file(app):
    with app.app_context():
        from app.services.audio_subtitle import start_audio_subtitle
        task_id, error = start_audio_subtitle(999)
        assert task_id is None
        assert error is not None


def test_start_subtitle_creates_task(app):
    with app.app_context():
        with tempfile.NamedTemporaryFile(mode='w', suffix='.mp3', delete=False) as f:
            temp_path = f.name

        try:
            audio_file = File(
                filename='test.mp3',
                file_path=temp_path,
                file_type='audio',
                file_size=1000
            )
            db.session.add(audio_file)
            db.session.commit()

            from app.services.audio_subtitle import start_audio_subtitle
            task_id, error = start_audio_subtitle(audio_file.id)

            assert task_id is not None
            assert error is None

            task = db.session.get(Task, task_id)
            assert task.task_type == 'audio_subtitle'
            assert task.status == 'pending'
            params = task.get_params()
            assert params['audio_file_id'] == audio_file.id
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


def test_split_text_to_sentences():
    from app.services.audio_subtitle import _split_text_to_sentences
    text = "你好世界。这是第二句！真的吗？是的。"
    result = _split_text_to_sentences(text)
    assert len(result) == 4
    assert result[0] == "你好世界。"
    assert result[1] == "这是第二句！"
    assert result[2] == "真的吗？"
    assert result[3] == "是的。"


def test_split_text_to_sentences_english():
    from app.services.audio_subtitle import _split_text_to_sentences
    text = "Hello world. This is sentence two! Really? Yes."
    result = _split_text_to_sentences(text)
    assert len(result) == 4


def test_distribute_timestamps():
    from app.services.audio_subtitle import _distribute_timestamps
    sentences = ["你好世界。", "这是第二句！", "真的吗？"]
    result = _distribute_timestamps(sentences, 0.0, 10.0)
    assert len(result) == 3
    assert result[0]['start'] == 0.0
    assert result[0]['end'] > 0
    assert result[-1]['end'] == 10.0
    assert result[0]['text'] == "你好世界。"


def test_parse_result_splits_long_text():
    from app.services.audio_subtitle import _parse_result

    class FakeResult:
        text = "你好世界。这是第二句！真的吗？"
        segments = [
            {'text': "你好世界。这是第二句！真的吗？", 'start': 0.0, 'end': 10.0}
        ]

    result = _parse_result(FakeResult())
    assert len(result) == 3
    assert result[0]['text'] == "你好世界。"
    assert result[0]['start'] == 0.0
    assert result[0]['end'] > 0
    assert result[-1]['end'] == 10.0


def test_parse_result_keeps_short_text_intact():
    from app.services.audio_subtitle import _parse_result

    class FakeResult:
        text = "短句"
        segments = [
            {'text': "短句", 'start': 0.0, 'end': 5.0}
        ]

    result = _parse_result(FakeResult())
    assert len(result) == 1
    assert result[0]['text'] == "短句"


def test_subtitle_api_missing_file_id(client):
    response = client.post('/api/audio/subtitle',
                          json={},
                          content_type='application/json')
    assert response.status_code == 400
    data = response.get_json()
    assert 'error' in data


def test_subtitle_api_success(client, app):
    with app.app_context():
        with tempfile.NamedTemporaryFile(mode='w', suffix='.mp3', delete=False) as f:
            temp_path = f.name

        try:
            audio_file = File(
                filename='test.mp3',
                file_path=temp_path,
                file_type='audio',
                file_size=1000
            )
            db.session.add(audio_file)
            db.session.commit()
            file_id = audio_file.id
        finally:
            pass

    response = client.post('/api/audio/subtitle',
                          json={'audio_file_id': file_id},
                          content_type='application/json')
    assert response.status_code == 201
    data = response.get_json()
    assert 'task_id' in data

    if os.path.exists(temp_path):
        os.unlink(temp_path)


def test_subtitle_status_api(client):
    response = client.get('/api/audio/subtitle/status')
    assert response.status_code == 200
    data = response.get_json()
    assert 'models' in data
    assert 'mlx_audio_available' in data


def test_subtitle_result_not_found(client):
    response = client.get('/api/audio/subtitle/999/result')
    assert response.status_code == 404


def test_subtitle_export_missing_task(client):
    response = client.post('/api/audio/subtitle/999/export',
                          json={'format': 'srt'},
                          content_type='application/json')
    assert response.status_code == 404
