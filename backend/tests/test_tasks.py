import pytest
from app import create_app, db
from app.models import Task

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

def test_get_tasks(client, app):
    with app.app_context():
        task = Task(
            task_type='audio_extract',
            status='pending',
            input_file='test.mp4'
        )
        db.session.add(task)
        db.session.commit()
    
    response = client.get('/api/tasks')
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1

def test_get_task(client, app):
    with app.app_context():
        task = Task(
            task_type='audio_extract',
            status='pending',
            input_file='test.mp4'
        )
        db.session.add(task)
        db.session.commit()
        task_id = task.id
    
    response = client.get(f'/api/tasks/{task_id}')
    assert response.status_code == 200
    data = response.get_json()
    assert data['task_type'] == 'audio_extract'

def test_cancel_task(client, app):
    with app.app_context():
        task = Task(
            task_type='audio_extract',
            status='pending',
            input_file='test.mp4'
        )
        db.session.add(task)
        db.session.commit()
        task_id = task.id
    
    response = client.delete(f'/api/tasks/{task_id}')
    assert response.status_code == 200
    
    with app.app_context():
        cancelled_task = Task.query.get(task_id)
        assert cancelled_task.status == 'cancelled'
