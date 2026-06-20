import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from flask import current_app
from app import db, socketio
from app.models import Task, File
from app.config import Config
from loguru import logger
from sqlalchemy.orm import scoped_session, sessionmaker

def check_spleeter_available():
    try:
        from spleeter.separator import Separator
        return True
    except ImportError:
        return False

def get_device():
    try:
        import torch
        if Config.ACCELERATION_TYPE == 'auto':
            if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                return 'mps'
            return 'cpu'
        return Config.ACCELERATION_TYPE
    except:
        return 'cpu'

def process_audio_separation(task_id: int, app):
    with app.app_context():
        session = scoped_session(sessionmaker(bind=db.engine))
        
        try:
            task = session.query(Task).filter_by(id=task_id).first()
            if not task:
                logger.error(f"Task {task_id} not found")
                return
            
            task.status = 'processing'
            session.commit()
            
            params = task.get_params()
            audio_file = session.query(File).filter_by(id=params['audio_file_id']).first()
            
            if not audio_file or not os.path.exists(audio_file.file_path):
                raise Exception(f"Audio file not found: {task.input_file}")
            
            stems = params.get('stems', ['vocals', 'drums', 'bass', 'other'])
            
            # Check if Spleeter is available
            if not check_spleeter_available():
                raise Exception(
                    "Spleeter is not installed. Audio separation requires Python 3.9-3.11. "
                    "To enable this feature, use Python 3.9-3.11 and install: pip install spleeter==2.4.0"
                )
            
            socketio.emit('task_progress', {
                'task_id': task.id,
                'progress': 10,
                'status': 'processing'
            })
            
            device = get_device()
            logger.info(f"Using device: {device}")
            
            try:
                from spleeter.separator import Separator
            except ImportError as e:
                raise Exception(
                    "Failed to import Spleeter. Audio separation requires Python 3.9-3.11. "
                    f"Error: {str(e)}"
                )
            
            if 'vocals' in stems and len(stems) == 1:
                model = 'spleeter:2stems'
            else:
                model = 'spleeter:4stems'
            
            separator = Separator(model, multiprocess=False)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_dir = os.path.join(Config.WORKSPACE_DIR, 'separated', timestamp)
            
            socketio.emit('task_progress', {
                'task_id': task.id,
                'progress': 30,
                'status': 'processing'
            })
            
            separator.separate_to_file(
                audio_file.file_path,
                output_dir,
                codec='wav',
                offset=0,
                duration=None
            )
            
            socketio.emit('task_progress', {
                'task_id': task.id,
                'progress': 80,
                'status': 'processing'
            })
            
            output_files = []
            base_name = Path(audio_file.filename).stem
            
            for stem in stems:
                stem_path = os.path.join(output_dir, base_name, f'{stem}.wav')
                if os.path.exists(stem_path):
                    output_filename = f"{timestamp}_{stem}.wav"
                    final_path = os.path.join(Config.WORKSPACE_DIR, 'separated', output_filename)
                    
                    os.makedirs(os.path.dirname(final_path), exist_ok=True)
                    os.rename(stem_path, final_path)
                    
                    file_size = os.path.getsize(final_path)
                    output_file = File(
                        filename=output_filename,
                        file_path=final_path,
                        file_type='audio',
                        file_size=file_size
                    )
                    session.add(output_file)
                    output_files.append(output_filename)
            
            import shutil
            shutil.rmtree(output_dir, ignore_errors=True)
            
            task.output_file = ','.join(output_files)
            task.status = 'completed'
            task.progress = 100
            task.completed_at = datetime.now(timezone.utc)
            session.commit()
            
            socketio.emit('task_completed', {
                'task_id': task.id,
                'output_files': output_files
            })
            
            logger.info(f"Audio separation task {task_id} completed")
            
        except Exception as e:
            task = session.query(Task).filter_by(id=task_id).first()
            if task:
                task.status = 'failed'
                task.error_message = str(e)
                session.commit()
                
                socketio.emit('task_failed', {
                    'task_id': task.id,
                    'error': str(e)
                })
                
                logger.error(f"Audio separation task {task_id} failed: {str(e)}")
        finally:
            session.remove()

def start_audio_separation(audio_file_id: int, stems=None):
    if stems is None:
        stems = ['vocals', 'drums', 'bass', 'other']
    
    audio_file = db.session.get(File, audio_file_id)
    if not audio_file:
        return None, "Audio file not found"
    
    task = Task(
        task_type='audio_separation',
        status='pending',
        input_file=audio_file.file_path
    )
    task.set_params({
        'audio_file_id': audio_file_id,
        'stems': stems
    })
    
    db.session.add(task)
    db.session.commit()
    
    from flask import current_app
    app = current_app._get_current_object()
    
    thread = threading.Thread(target=process_audio_separation, args=(task.id, app))
    thread.start()
    
    return task.id, None
