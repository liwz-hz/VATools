import pytest
import os
from app import create_app, db
from app.models import File

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

def test_upload_file(client, tmp_path):
    test_file = tmp_path / "test.mp4"
    test_file.write_bytes(b"fake video content")
    
    with open(test_file, 'rb') as f:
        response = client.post(
            '/api/files/upload',
            data={'file': (f, 'test.mp4')},
            content_type='multipart/form-data'
        )
    
    assert response.status_code == 201
    data = response.get_json()
    assert data['filename'].endswith('test.mp4')
    assert data['file_type'] == 'video'

def test_get_files(client):
    response = client.get('/api/files')
    assert response.status_code == 200
    assert isinstance(response.get_json(), list)

def test_delete_file(client, app):
    with app.app_context():
        file = File(
            filename='test.mp4',
            file_path='/tmp/test.mp4',
            file_type='video',
            file_size=1000
        )
        db.session.add(file)
        db.session.commit()
        file_id = file.id
    
    response = client.delete(f'/api/files/{file_id}')
    assert response.status_code == 200
