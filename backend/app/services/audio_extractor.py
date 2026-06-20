import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from flask import current_app
from app import db, socketio
from app.models import Task, File
from app.utils.ffmpeg_utils import extract_audio, get_audio_duration, validate_audio_format
from app.config import Config
from loguru import logger
from sqlalchemy.orm import scoped_session, sessionmaker

def process_audio_extraction(task_id: int, app):
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
            input_file = session.query(File).filter_by(id=params['video_file_id']).first()
            
            if not input_file or not os.path.exists(input_file.file_path):
                raise Exception(f"Input file not found: {task.input_file}")
            
            output_format = params.get('output_format', Config.DEFAULT_AUDIO_FORMAT)
            bitrate = params.get('bitrate', Config.DEFAULT_BITRATE)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_filename = f"{timestamp}_{Path(input_file.filename).stem}.{output_format}"
            output_path = os.path.join(Config.WORKSPACE_DIR, 'audio', output_filename)
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            socketio.emit('task_progress', {
                'task_id': task.id,
                'progress': 10,
                'status': 'processing'
            })
            
            success, error = extract_audio(
                input_file.file_path,
                output_path,
                output_format,
                bitrate
            )
            
            if not success:
                raise Exception(error)
            
            duration = get_audio_duration(output_path)
            
            output_file = File(
                filename=output_filename,
                file_path=output_path,
                file_type='audio',
                file_size=os.path.getsize(output_path),
                duration=duration
            )
            session.add(output_file)
            session.flush()
            
            task.output_file = output_path
            task.status = 'completed'
            task.progress = 100
            task.completed_at = datetime.now(timezone.utc)
            session.commit()
            
            socketio.emit('task_completed', {
                'task_id': task.id,
                'output_file': output_filename,
                'file_id': output_file.id
            })
            
            logger.info(f"Audio extraction task {task_id} completed")
            
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
                
                logger.error(f"Audio extraction task {task_id} failed: {str(e)}")
        finally:
            session.remove()

def start_audio_extraction(video_file_id: int, output_format: str = 'mp3', bitrate: str = '192k'):
    format_valid, error = validate_audio_format(output_format)
    if not format_valid:
        return None, error
    
    video_file = db.session.get(File, video_file_id)
    if not video_file:
        return None, "Video file not found"
    
    task = Task(
        task_type='audio_extract',
        status='pending',
        input_file=video_file.file_path
    )
    task.set_params({
        'video_file_id': video_file_id,
        'output_format': output_format,
        'bitrate': bitrate
    })
    
    db.session.add(task)
    db.session.commit()
    
    from flask import current_app
    app = current_app._get_current_object()
    
    thread = threading.Thread(target=process_audio_extraction, args=(task.id, app))
    thread.start()
    
    return task.id, None
