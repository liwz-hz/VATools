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
