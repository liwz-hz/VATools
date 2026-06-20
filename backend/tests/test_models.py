import pytest
from app import create_app, db
from app.models import Task, File, Config

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

def test_task_creation(app):
    with app.app_context():
        task = Task(
            task_type='audio_extract',
            status='pending',
            input_file='test.mp4'
        )
        task.set_params({'output_format': 'mp3'})
        db.session.add(task)
        db.session.commit()
        
        assert task.id is not None
        assert task.task_type == 'audio_extract'
        assert task.get_params() == {'output_format': 'mp3'}

def test_file_creation(app):
    with app.app_context():
        file = File(
            filename='test.mp4',
            file_path='/uploads/test.mp4',
            file_type='video',
            file_size=1024000
        )
        db.session.add(file)
        db.session.commit()
        
        assert file.id is not None
        assert file.filename == 'test.mp4'

def test_config_creation(app):
    with app.app_context():
        config = Config(key='test_key', value='test_value')
        db.session.add(config)
        db.session.commit()
        
        assert config.key == 'test_key'
        assert config.value == 'test_value'

def test_task_to_dict(app):
    with app.app_context():
        task = Task(
            task_type='audio_separation',
            status='completed',
            input_file='input.mp3',
            output_file='output/',
            progress=100
        )
        task.set_params({'model': 'spleeter', 'stems': 2})
        db.session.add(task)
        db.session.commit()
        
        task_dict = task.to_dict()
        assert task_dict['task_type'] == 'audio_separation'
        assert task_dict['status'] == 'completed'
        assert task_dict['params'] == {'model': 'spleeter', 'stems': 2}
        assert task_dict['progress'] == 100
        assert task_dict['created_at'] is not None

def test_file_to_dict(app):
    with app.app_context():
        file = File(
            filename='video.mp4',
            file_path='/uploads/video.mp4',
            file_type='video',
            file_size=2048000,
            duration=120.5
        )
        db.session.add(file)
        db.session.commit()
        
        file_dict = file.to_dict()
        assert file_dict['filename'] == 'video.mp4'
        assert file_dict['duration'] == 120.5
        assert file_dict['created_at'] is not None

def test_config_to_dict(app):
    with app.app_context():
        config = Config(key='upload_dir', value='/custom/uploads')
        db.session.add(config)
        db.session.commit()
        
        config_dict = config.to_dict()
        assert config_dict['key'] == 'upload_dir'
        assert config_dict['value'] == '/custom/uploads'
        assert config_dict['updated_at'] is not None

def test_config_api_get(client):
    response = client.get('/api/config')
    assert response.status_code == 200
    data = response.get_json()
    assert 'upload_dir' in data
    assert 'workspace_dir' in data
    assert 'max_file_size' in data
    assert 'default_audio_format' in data

def test_config_api_update(client):
    response = client.put('/api/config', json={'upload_dir': '/new/uploads'})
    assert response.status_code == 200
    
    response = client.get('/api/config')
    data = response.get_json()
    assert data['upload_dir'] == '/new/uploads'

def test_config_api_reset(client):
    client.put('/api/config', json={'upload_dir': '/custom/path'})
    
    response = client.post('/api/config/reset')
    assert response.status_code == 200
    data = response.get_json()
    assert 'upload_dir' in data
