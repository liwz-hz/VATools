import pytest
import os
import tempfile
from app import create_app, db
from app.models import File, Task
from app.services.audio_extractor import start_audio_extraction
from app.utils.ffmpeg_utils import validate_audio_format, check_ffmpeg_installed

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

def test_validate_audio_format():
    assert validate_audio_format('mp3')[0] == True
    assert validate_audio_format('wav')[0] == True
    assert validate_audio_format('flac')[0] == True
    assert validate_audio_format('invalid')[0] == False
    assert validate_audio_format('ogg')[0] == False

def test_check_ffmpeg_installed():
    installed, _ = check_ffmpeg_installed()
    assert isinstance(installed, bool)

def test_start_audio_extraction_invalid_format(app):
    with app.app_context():
        video_file = File(
            filename='test.mp4',
            file_path='/tmp/test.mp4',
            file_type='video',
            file_size=1000
        )
        db.session.add(video_file)
        db.session.commit()
        
        task_id, error = start_audio_extraction(video_file.id, 'invalid_format', '192k')
        
        assert task_id is None
        assert error is not None
        assert 'Invalid audio format' in error

def test_start_audio_extraction_missing_file(app):
    with app.app_context():
        task_id, error = start_audio_extraction(999, 'mp3', '192k')
        
        assert task_id is None
        assert error == "Video file not found"

def test_start_audio_extraction_creates_task(app):
    with app.app_context():
        with tempfile.NamedTemporaryFile(mode='w', suffix='.mp4', delete=False) as f:
            temp_path = f.name
        
        try:
            video_file = File(
                filename='test.mp4',
                file_path=temp_path,
                file_type='video',
                file_size=1000
            )
            db.session.add(video_file)
            db.session.commit()
            
            task_id, error = start_audio_extraction(video_file.id, 'mp3', '192k')
            
            assert task_id is not None
            assert error is None
            
            task = db.session.get(Task, task_id)
            assert task is not None
            assert task.task_type == 'audio_extract'
            assert task.status == 'pending'
            
            params = task.get_params()
            assert params['video_file_id'] == video_file.id
            assert params['output_format'] == 'mp3'
            assert params['bitrate'] == '192k'
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

def test_audio_extract_api_missing_file_id(client):
    response = client.post('/api/audio/extract', 
                          json={'output_format': 'mp3'},
                          content_type='application/json')
    
    assert response.status_code == 400
    data = response.get_json()
    assert 'error' in data
    assert 'video_file_id' in data['error']

def test_audio_extract_api_invalid_format(client):
    response = client.post('/api/audio/extract',
                          json={'video_file_id': 1, 'output_format': 'ogg'},
                          content_type='application/json')
    
    assert response.status_code == 400
    data = response.get_json()
    assert 'error' in data
    assert 'Invalid audio format' in data['error']

def test_audio_extract_api_invalid_bitrate(client):
    response = client.post('/api/audio/extract',
                          json={'video_file_id': 1, 'output_format': 'mp3', 'bitrate': '500k'},
                          content_type='application/json')
    
    assert response.status_code == 400
    data = response.get_json()
    assert 'error' in data
    assert 'Invalid bitrate' in data['error']

def test_audio_extract_api_no_body(client):
    response = client.post('/api/audio/extract', content_type='application/json')
    
    assert response.status_code == 400
