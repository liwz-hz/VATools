import pytest
from app import create_app, db
from app.models import File, Task
from app.services.audio_editor import start_audio_clip

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

def test_start_audio_clip(app):
    with app.app_context():
        audio_file = File(
            filename='test.mp3',
            file_path='/tmp/test.mp3',
            file_type='audio',
            file_size=1000,
            duration=60.0
        )
        db.session.add(audio_file)
        db.session.commit()
        
        task_id, error = start_audio_clip(
            audio_file.id,
            'extract',
            10.0,
            20.0,
            'mp3'
        )
        
        assert task_id is not None
        assert error is None
        
        task = Task.query.get(task_id)
        assert task is not None
        assert task.task_type == 'audio_clip'
