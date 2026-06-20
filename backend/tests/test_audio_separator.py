import pytest
import os
import tempfile
from app import create_app, db
from app.models import File, Task
from app.services.audio_separator import start_audio_separation

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

def test_start_audio_separation_missing_file(app):
    with app.app_context():
        task_id, error = start_audio_separation(999, ['vocals', 'drums', 'bass', 'other'])
        
        assert task_id is None
        assert error == "Audio file not found"

def test_start_audio_separation_creates_task(app):
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
            
            task_id, error = start_audio_separation(
                audio_file.id,
                ['vocals', 'drums', 'bass', 'other']
            )
            
            assert task_id is not None
            assert error is None
            
            task = db.session.get(Task, task_id)
            assert task is not None
            assert task.task_type == 'audio_separation'
            assert task.status == 'pending'
            
            params = task.get_params()
            assert params['audio_file_id'] == audio_file.id
            assert params['stems'] == ['vocals', 'drums', 'bass', 'other']
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

def test_start_audio_separation_default_stems(app):
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
            
            task_id, error = start_audio_separation(audio_file.id)
            
            assert task_id is not None
            assert error is None
            
            task = db.session.get(Task, task_id)
            params = task.get_params()
            assert params['stems'] == ['vocals', 'drums', 'bass', 'other']
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

def test_audio_separate_api_missing_file_id(client):
    response = client.post('/api/audio/separate',
                          json={'stems': ['vocals']},
                          content_type='application/json')
    
    assert response.status_code == 400
    data = response.get_json()
    assert 'error' in data
    assert 'audio_file_id' in data['error']

def test_audio_separate_api_success(client, app):
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
    
    response = client.post('/api/audio/separate',
                          json={'audio_file_id': file_id, 'stems': ['vocals', 'drums']},
                          content_type='application/json')
    
    assert response.status_code == 201
    data = response.get_json()
    assert 'task_id' in data
    
    if os.path.exists(temp_path):
        os.unlink(temp_path)
