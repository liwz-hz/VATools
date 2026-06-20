import pytest
import os
import tempfile
from app import create_app, db
from app.models import File, Task, Config


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


def test_full_audio_extraction_workflow(client, tmp_path):
    test_file = tmp_path / "test.mp4"
    test_file.write_bytes(b"fake video content")
    
    with open(test_file, 'rb') as f:
        upload_response = client.post(
            '/api/files/upload',
            data={'file': (f, 'test.mp4')},
            content_type='multipart/form-data'
        )
    
    assert upload_response.status_code == 201
    file_data = upload_response.get_json()
    file_id = file_data['id']
    
    extract_response = client.post(
        '/api/audio/extract',
        json={
            'video_file_id': file_id,
            'output_format': 'mp3',
            'bitrate': '192k'
        }
    )
    
    assert extract_response.status_code == 201
    task_data = extract_response.get_json()
    assert 'task_id' in task_data
    
    task_response = client.get(f"/api/tasks/{task_data['task_id']}")
    assert task_response.status_code == 200


def test_config_management(client):
    get_response = client.get('/api/config')
    assert get_response.status_code == 200
    
    update_response = client.put(
        '/api/config',
        json={'default_audio_format': 'wav'}
    )
    assert update_response.status_code == 200
    
    get_response = client.get('/api/config')
    config = get_response.get_json()
    assert config['default_audio_format'] == 'wav'
    
    reset_response = client.post('/api/config/reset')
    assert reset_response.status_code == 200


def test_file_management(client, tmp_path):
    test_file = tmp_path / "test.mp3"
    test_file.write_bytes(b"fake audio content")
    
    with open(test_file, 'rb') as f:
        upload_response = client.post(
            '/api/files/upload',
            data={'file': (f, 'test.mp3')},
            content_type='multipart/form-data'
        )
    
    assert upload_response.status_code == 201
    file_data = upload_response.get_json()
    file_id = file_data['id']
    
    get_response = client.get(f'/api/files/{file_id}')
    assert get_response.status_code == 200
    
    list_response = client.get('/api/files')
    assert list_response.status_code == 200
    assert len(list_response.get_json()) >= 1
    
    delete_response = client.delete(f'/api/files/{file_id}')
    assert delete_response.status_code == 200
